"""TuShare 数据源适配器（2000 积分档）。

与 ``AkshareGateway`` 同方法名 + 同返回列契约，service 零改动即可换注入。
TuShare 核心优势：按 ``trade_date`` 一次拉全市场（daily/daily_basic/moneyflow/
adj_factor/stk_limit/top_list），日线回补从逐只 90 分钟降到 ~10 秒；服务端 API
不受 Clash/push2 风控影响。

2000 档实测边界（2026-07-23 token 实测）：
- 可用：daily/daily_basic/adj_factor/stock_basic/stk_limit/moneyflow/top_list/top_inst/
  income/balancesheet/cashflow/fina_indicator/block_trade/share_float/stk_holdernumber/index_daily
- 不可用：limit_list_d（打板专题涨停池）、盘中实时快照（TuShare 是 EOD）
  -> 这两类保留 AkshareGateway（CompositeGateway 降级）

单位换算（适配层统一，最易出错点）：
  vol 手 -> 股 ×100 | daily.amount 千元 -> 元 ×1000 |
  total_mv/circ_mv 万元 -> 元 ×10000 | moneyflow 万元 -> 元 ×10000

复权：``daily`` 返回不复权 raw 价。``fetch_daily_by_date`` 默认返回 raw
（最新交易日前复权 = 原始价，直接存 stock_daily_bars 即 qfq 口径）；拉历史日时
传 ``qfq_baseline_adj``（全市场最新 adj_factor 字典），qfq = raw × adj / baseline。
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable

import pandas as pd
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

logger = logging.getLogger(__name__)


class _RateLimiter:
    """按 key（接口名）限速：同一 key 最小间隔 min_interval 秒。线程安全。

    与 AkshareGateway 的限流器同构但独立实例——TuShare（200 次/分钟）与
    AKShare（~3 QPS 爬虫）节奏不同，独立节流避免互相阻塞。
    """

    def __init__(self, min_interval: float = 0.3) -> None:
        self._min_interval = min_interval
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, key: str) -> None:
        with self._lock:
            now = time.time()
            last = self._last.get(key, 0.0)
            elapsed = now - last
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last[key] = time.time()


_rate_limiter = _RateLimiter(min_interval=0.3)


def _backoff_sleep(attempt: int, base: float = 1.0) -> None:
    """指数退避：attempt=0 -> base*1s, 1 -> base*2s, 2 -> base*4s。"""
    time.sleep(base * (2 ** attempt))


# 单位换算常量
_VOL_UNIT = 100.0  # TuShare vol 手 -> 股
_AMOUNT_UNIT = 1000.0  # TuShare daily.amount 千元 -> 元
_MV_UNIT = 10000.0  # TuShare total_mv/circ_mv 万元 -> 元
_MONEYFLOW_UNIT = 10000.0  # TuShare moneyflow 万元 -> 元


def _to_ts_code(code: str) -> str:
    """6 位代码 -> TuShare ts_code（带交易所后缀）。000725 -> 000725.SZ，600519 -> 600519.SH。"""
    code = str(code).strip().zfill(6)
    if code.startswith(("4", "8", "920")):
        return f"{code}.BJ"
    if code.startswith("6"):
        return f"{code}.SH"
    return f"{code}.SZ"


def _from_ts_code(ts_code: str) -> str:
    """TuShare ts_code -> 6 位代码。000725.SZ -> 000725。"""
    return str(ts_code).split(".")[0].zfill(6)


def _to_trade_date_str(d: Any) -> str:
    """date/datetime/str -> YYYYMMDD。"""
    if d is None:
        return ""
    if isinstance(d, str):
        return d.replace("-", "")[:8]
    return d.strftime("%Y%m%d")


def _index_symbol_to_ts(symbol: str) -> str:
    """sh000001 -> 000001.SH，sz399001 -> 399001.SZ。"""
    s = str(symbol).lower()
    if s.startswith("sh"):
        return f"{symbol[2:]}.SH"
    if s.startswith("sz"):
        return f"{symbol[2:]}.SZ"
    return _to_ts_code(symbol)


class TushareGateway:
    """TuShare 2000 档数据源适配器。

    ``pro`` 可注入（单测传 fake pro，避免真调 API）。
    """

    def __init__(self, token: str | None = None, pro: Any | None = None) -> None:
        self._token = token or ""
        if pro is not None:
            self._pro = pro
            self._ts: Any = None
        else:
            from app.config import TUSHARE_TOKEN

            self._token = token or TUSHARE_TOKEN
            if not self._token:
                raise ValueError("TuShare token 未配置：请设置 EQ_TUSHARE_TOKEN 环境变量")
            import tushare as ts

            ts.set_token(self._token)
            self._pro = ts.pro_api(self._token)
            self._ts = ts
        self._source_snapshots: dict[str, dict[str, object]] = {}
        self._stock_basic_cache: pd.DataFrame | None = None
        self._stock_basic_cache_at: datetime | None = None

    # ---------------- 限流 / snapshot（与 AkshareGateway 一致） ----------------

    def _call(
        self,
        fn: Callable[[], pd.DataFrame],
        rate_key: str = "tushare",
        timeout: int = 60,
        retries: int = 2,
    ) -> pd.DataFrame:
        """TuShare SDK 调用壳：限流 + 超时 + 指数退避重试。

        TuShare 2000 档 200 次/分钟，``_rate_limiter`` 全局单例按 rate_key 节流。
        ``shutdown(wait=False)`` 避免 SDK 内部无 timeout 调用挂死调度线程（同 AkshareGateway._run）。
        """
        for attempt in range(retries + 1):
            _rate_limiter.wait(rate_key)
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(fn)
            try:
                result = future.result(timeout=timeout)
                return result if isinstance(result, pd.DataFrame) else pd.DataFrame()
            except FuturesTimeoutError:
                future.cancel()
                logger.warning("tushare %s timeout (attempt %d/%d)", rate_key, attempt + 1, retries + 1)
            except Exception:  # noqa: BLE001
                logger.exception("tushare %s failed (attempt %d/%d)", rate_key, attempt + 1, retries + 1)
            finally:
                executor.shutdown(wait=False)
            if attempt < retries:
                _backoff_sleep(attempt)
        logger.warning("tushare %s %d 次重试全失败", rate_key, retries + 1)
        return pd.DataFrame()

    def _set_source_snapshot(
        self,
        key: str,
        *,
        source_label: str = "tushare",
        fallback_used: bool = False,
        updated_at: str | None = None,
        degraded_fields: list[str] | None = None,
        meta: dict[str, object] | None = None,
    ) -> None:
        snapshot: dict[str, object] = {
            "source_label": source_label,
            "updated_at": updated_at,
            "fallback_used": fallback_used,
            "degraded_fields": degraded_fields or [],
        }
        if meta:
            snapshot["meta"] = {k: v for k, v in meta.items() if v is not None}
        self._source_snapshots[key] = snapshot

    def get_source_snapshot(self, key: str) -> dict[str, object]:
        return self._source_snapshots.get(key, {})

    # ---------------- 批量方法（按 trade_date，TuShare 独有优势） ----------------

    def fetch_stock_basic(self) -> pd.DataFrame:
        """全市场在市股票列表（list_status=L）。缓存 12 小时。

        返回列：ts_code, code(6位), symbol, name, area, industry, cnspell, market, list_date
        """
        now = datetime.now()
        if (
            self._stock_basic_cache is not None
            and self._stock_basic_cache_at is not None
            and now - self._stock_basic_cache_at < timedelta(hours=12)
        ):
            return self._stock_basic_cache.copy()
        df = self._call(
            lambda: self._pro.stock_basic(exchange="", list_status="L"),
            rate_key="tushare-stock_basic",
        )
        if df.empty:
            self._set_source_snapshot("stock_basic", degraded_fields=["stock_basic"])
            return df
        df = df.copy()
        df["code"] = df["ts_code"].apply(_from_ts_code)
        self._stock_basic_cache = df
        self._stock_basic_cache_at = now
        self._set_source_snapshot("stock_basic", updated_at=now.isoformat(), meta={"count": len(df)})
        return df.copy()

    def fetch_daily_by_date(
        self,
        trade_date: Any,
        *,
        qfq_baseline_adj: dict[str, float] | None = None,
    ) -> pd.DataFrame:
        """全市场某交易日日线（一次调用 ~5500 行）。

        返回列（已换算单位）：ts_code, code, trade_date(YYYYMMDD),
        open, close, high, low, volume(股), amount(元), change_pct,
        adj_factor, up_limit, down_limit

        复权：默认 raw 不复权（最新交易日前复权 = 原始价，直接存即 qfq 口径）。
        拉历史日时传 ``qfq_baseline_adj``（全市场最新 adj_factor 字典），
        qfq = raw × adj_factor / baseline。
        """
        td = _to_trade_date_str(trade_date)
        daily = self._call(lambda: self._pro.daily(trade_date=td), rate_key="tushare-daily")
        if daily.empty:
            self._set_source_snapshot("daily_by_date", degraded_fields=["daily"])
            return pd.DataFrame()
        adj = self._call(lambda: self._pro.adj_factor(trade_date=td), rate_key="tushare-adj_factor")
        lim = self._call(lambda: self._pro.stk_limit(trade_date=td), rate_key="tushare-stk_limit")

        daily = daily.copy()
        daily["code"] = daily["ts_code"].apply(_from_ts_code)
        daily["trade_date"] = td
        daily["volume"] = pd.to_numeric(daily.get("vol"), errors="coerce") * _VOL_UNIT
        daily["amount"] = pd.to_numeric(daily.get("amount"), errors="coerce") * _AMOUNT_UNIT
        daily["change_pct"] = pd.to_numeric(daily.get("pct_chg"), errors="coerce")
        daily = daily[["ts_code", "code", "trade_date", "open", "close", "high", "low", "volume", "amount", "change_pct"]].copy()

        if not adj.empty:
            adj_map = dict(zip(adj["ts_code"], pd.to_numeric(adj["adj_factor"], errors="coerce")))
            daily["adj_factor"] = daily["ts_code"].map(adj_map)
        else:
            daily["adj_factor"] = None
        if not lim.empty:
            lim_map = lim.set_index("ts_code")
            daily["up_limit"] = daily["ts_code"].map(lim_map["up_limit"].to_dict())
            daily["down_limit"] = daily["ts_code"].map(lim_map["down_limit"].to_dict())
        else:
            daily["up_limit"] = None
            daily["down_limit"] = None

        if qfq_baseline_adj:
            baseline = daily["ts_code"].map(qfq_baseline_adj)
            ratio = pd.to_numeric(daily["adj_factor"], errors="coerce") / baseline
            for col in ("open", "close", "high", "low"):
                daily[col] = pd.to_numeric(daily[col], errors="coerce") * ratio
            self._set_source_snapshot(
                "daily_by_date", updated_at=datetime.now().isoformat(),
                meta={"count": len(daily), "qfq": True},
            )
        else:
            self._set_source_snapshot(
                "daily_by_date", updated_at=datetime.now().isoformat(),
                meta={"count": len(daily), "qfq": "raw(=latest qfq)"},
            )
        return daily

    def fetch_daily_basic_by_date(self, trade_date: Any) -> pd.DataFrame:
        """全市场某交易日每日指标（PE/PB/市值/换手率/量比/股息率）。

        返回列（市值已换算为元）：ts_code, code, trade_date, close, turnover_rate,
        turnover_rate_f, volume_ratio, pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm,
        total_share, float_share, free_share, total_mv(元), circ_mv(元)
        """
        td = _to_trade_date_str(trade_date)
        df = self._call(lambda: self._pro.daily_basic(trade_date=td), rate_key="tushare-daily_basic")
        if df.empty:
            self._set_source_snapshot("daily_basic_by_date", degraded_fields=["daily_basic"])
            return df
        df = df.copy()
        df["code"] = df["ts_code"].apply(_from_ts_code)
        df["trade_date"] = td
        for col in ("total_mv", "circ_mv"):
            df[col] = pd.to_numeric(df.get(col), errors="coerce") * _MV_UNIT
        self._set_source_snapshot(
            "daily_basic_by_date", updated_at=datetime.now().isoformat(), meta={"count": len(df)}
        )
        return df

    def fetch_fund_flow_by_date(self, trade_date: Any) -> pd.DataFrame:
        """全市场某交易日资金流（一次 ~5200 行）。

        返回列（已换算为元）：ts_code, code, trade_date,
        main_net_amount(主力净额=net_mf_amount), main_net_ratio(留 None, backfill join daily.amount 自算),
        super_large_net(超大单净额), large_net(大单净额)
        """
        td = _to_trade_date_str(trade_date)
        df = self._call(lambda: self._pro.moneyflow(trade_date=td), rate_key="tushare-moneyflow")
        if df.empty:
            self._set_source_snapshot("fund_flow_by_date", degraded_fields=["moneyflow"])
            return df
        df = df.copy()
        df["code"] = df["ts_code"].apply(_from_ts_code)
        df["trade_date"] = td
        df["main_net_amount"] = pd.to_numeric(df.get("net_mf_amount"), errors="coerce") * _MONEYFLOW_UNIT
        buy_elg = pd.to_numeric(df.get("buy_elg_amount"), errors="coerce")
        sell_elg = pd.to_numeric(df.get("sell_elg_amount"), errors="coerce")
        df["super_large_net"] = (buy_elg - sell_elg) * _MONEYFLOW_UNIT
        buy_lg = pd.to_numeric(df.get("buy_lg_amount"), errors="coerce")
        sell_lg = pd.to_numeric(df.get("sell_lg_amount"), errors="coerce")
        df["large_net"] = (buy_lg - sell_lg) * _MONEYFLOW_UNIT
        df["main_net_ratio"] = None  # backfill_by_date join daily.amount 后自算 main_net/amount*100
        out = df[["ts_code", "code", "trade_date", "main_net_amount", "main_net_ratio", "super_large_net", "large_net"]].copy()
        self._set_source_snapshot(
            "fund_flow_by_date", updated_at=datetime.now().isoformat(), meta={"count": len(out)}
        )
        return out

    def fetch_lhb_by_date(self, trade_date: Any) -> pd.DataFrame:
        """全市场某交易日龙虎榜 + 机构席位（top_list + top_inst）。

        机构席位从 top_inst 重建：side='0' 买方 / '1' 卖方，exalter 含"机构"计为机构席位。
        比 AkshareGateway 解读列正则解析更准（直接按席位统计）。

        返回列：ts_code, code, trade_date, name, close, pct_change, turnover_rate,
        amount, l_buy, l_sell, l_amount, net_amount, net_rate, reason,
        inst_buy_count, inst_sell_count, inst_net_count(净席位=买-卖)
        """
        td = _to_trade_date_str(trade_date)
        tl = self._call(lambda: self._pro.top_list(trade_date=td), rate_key="tushare-top_list")
        if tl.empty:
            self._set_source_snapshot("lhb_by_date", degraded_fields=["lhb"])
            return pd.DataFrame()
        tl = tl.copy()
        tl["code"] = tl["ts_code"].apply(_from_ts_code)
        tl["trade_date"] = td

        ti = self._call(lambda: self._pro.top_inst(trade_date=td), rate_key="tushare-top_inst")
        inst_buy: dict[str, int] = {}
        inst_sell: dict[str, int] = {}
        if not ti.empty:
            ti = ti.copy()
            ti["is_inst"] = ti["exalter"].astype(str).str.contains("机构", na=False)
            buy = ti[(ti["side"] == "0") & ti["is_inst"]].groupby("ts_code").size()
            sell = ti[(ti["side"] == "1") & ti["is_inst"]].groupby("ts_code").size()
            inst_buy = buy.to_dict()
            inst_sell = sell.to_dict()
        tl["inst_buy_count"] = tl["ts_code"].map(inst_buy).fillna(0).astype(int)
        tl["inst_sell_count"] = tl["ts_code"].map(inst_sell).fillna(0).astype(int)
        tl["inst_net_count"] = tl["inst_buy_count"] - tl["inst_sell_count"]

        out_cols = [
            "ts_code", "code", "trade_date", "name", "close", "pct_change", "turnover_rate",
            "amount", "l_buy", "l_sell", "l_amount", "net_amount", "net_rate", "reason",
            "inst_buy_count", "inst_sell_count", "inst_net_count",
        ]
        out = tl[out_cols].copy()
        self._set_source_snapshot(
            "lhb_by_date", updated_at=datetime.now().isoformat(), meta={"count": len(out)}
        )
        return out

    def fetch_stk_limit_by_date(self, trade_date: Any) -> pd.DataFrame:
        """全市场某交易日涨跌停价（涨停精确判定用）。"""
        td = _to_trade_date_str(trade_date)
        df = self._call(lambda: self._pro.stk_limit(trade_date=td), rate_key="tushare-stk_limit")
        if df.empty:
            return df
        df = df.copy()
        df["code"] = df["ts_code"].apply(_from_ts_code)
        df["trade_date"] = td
        return df[["ts_code", "code", "trade_date", "up_limit", "down_limit"]]

    # ---------------- 兼容方法（与 AkshareGateway 同签名，供逐只 fallback） ----------------

    def fetch_stock_daily_history(
        self, symbol: str, start: str, end: str, adjust: str = ""
    ) -> pd.DataFrame:
        """逐只日线（兼容 AkshareGateway 签名，返回中文列）。

        TuShare 用 pro_bar（支持 adj）。adjust="" 不复权 / "qfq" 前复权 / "hfq" 后复权。
        返回列与 AkshareGateway 一致：日期/开盘/收盘/最高/最低/成交量/成交额/振幅/涨跌幅/涨跌额/换手率
        （振幅/换手率 TuShare daily 无，置 None；由 backfill_by_date 的 daily_basic 补换手率）。
        """
        if self._ts is None:
            raise NotImplementedError("pro_bar 需要 tushare SDK，pro 注入模式下不可用")
        ts_code = _to_ts_code(symbol)
        adj = adjust if adjust in ("qfq", "hfq") else None
        df = self._call(
            lambda: self._ts.pro_bar(
                ts_code=ts_code,
                start_date=_to_trade_date_str(start),
                end_date=_to_trade_date_str(end),
                adj=adj,
                freq="D",
            ),
            rate_key="tushare-pro_bar",
        )
        if df.empty:
            return df
        df = df.sort_values("trade_date").copy()
        df["涨跌幅"] = pd.to_numeric(df.get("pct_chg"), errors="coerce")
        df["涨跌额"] = pd.to_numeric(df.get("change"), errors="coerce")
        df["成交量"] = pd.to_numeric(df.get("vol"), errors="coerce") * _VOL_UNIT
        df["成交额"] = pd.to_numeric(df.get("amount"), errors="coerce") * _AMOUNT_UNIT
        df["振幅"] = None
        df["换手率"] = None
        df["日期"] = df["trade_date"]
        df["开盘"] = pd.to_numeric(df.get("open"), errors="coerce")
        df["收盘"] = pd.to_numeric(df.get("close"), errors="coerce")
        df["最高"] = pd.to_numeric(df.get("high"), errors="coerce")
        df["最低"] = pd.to_numeric(df.get("low"), errors="coerce")
        self._set_source_snapshot(
            f"stock_daily_history:{symbol}",
            updated_at=datetime.now().isoformat(),
            meta={"adjust": adjust or "none"},
        )
        return df[["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "振幅", "涨跌幅", "涨跌额", "换手率"]]

    def fetch_market_index_history(self, symbol: str, days: int = 20) -> pd.DataFrame:
        """指数日线（英文列，与 AkshareGateway 一致）。symbol 如 sh000001 -> 000001.SH。"""
        ts_code = _index_symbol_to_ts(symbol)
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")
        df = self._call(
            lambda: self._pro.index_daily(ts_code=ts_code, start_date=start, end_date=end),
            rate_key="tushare-index_daily",
        )
        if df.empty:
            return df
        df = df.sort_values("trade_date").tail(days).copy()
        df["date"] = df["trade_date"]
        df["volume"] = pd.to_numeric(df.get("vol"), errors="coerce")
        df["open"] = pd.to_numeric(df.get("open"), errors="coerce")
        df["high"] = pd.to_numeric(df.get("high"), errors="coerce")
        df["low"] = pd.to_numeric(df.get("low"), errors="coerce")
        df["close"] = pd.to_numeric(df.get("close"), errors="coerce")
        self._set_source_snapshot(
            f"market_index_history:{symbol}",
            updated_at=datetime.now().isoformat(),
            meta={"days": len(df)},
        )
        return df[["date", "open", "high", "low", "close", "volume"]]

    # ---------------- TuShare 2000 档不可用（CompositeGateway 走 AkshareGateway） ----------------

    def fetch_individual_realtime(self) -> pd.DataFrame:
        """盘中实时快照：TuShare 2000 档无（EOD only）。"""
        raise NotImplementedError("TuShare 无盘中实时快照，请用 AkshareGateway")

    def fetch_limit_up_pool(self, date_str: str) -> pd.DataFrame:
        """涨停池四子池：limit_list_d 需 5000 分/打板专题，2000 档无权限。"""
        raise NotImplementedError("TuShare 2000 档无 limit_list_d，请用 AkshareGateway")

    def fetch_previous_limit_up_pool(self, date_str: str) -> pd.DataFrame:
        raise NotImplementedError("TuShare 2000 档无涨停池，请用 AkshareGateway")

    def fetch_broken_limit_up_pool(self, date_str: str) -> pd.DataFrame:
        raise NotImplementedError("TuShare 2000 档无涨停池，请用 AkshareGateway")

    def fetch_strong_limit_up_pool(self, date_str: str) -> pd.DataFrame:
        raise NotImplementedError("TuShare 2000 档无涨停池，请用 AkshareGateway")
