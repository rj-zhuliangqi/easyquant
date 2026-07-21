from __future__ import annotations

import logging
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime, timedelta
from app.time_utils import now_cn
from difflib import SequenceMatcher
from io import StringIO
from typing import Callable
from urllib.parse import urlparse

import akshare as ak
import pandas as pd
import requests


logger = logging.getLogger(__name__)


# ==================== 反封禁三件套 (2026-07-21) ====================
# (1) UA 池轮换 - 避免固定 "Mozilla/5.0" 被识别为爬虫
# (2) 按域名限速 - 每域名最小间隔，防瞬时并发触发限流
# (3) 指数退避重试 - 失败后 1s->2s->4s 重试，而非只重试 1 次

UA_POOL = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
]


def _random_ua() -> str:
    return random.choice(UA_POOL)


def _domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


class _RateLimiter:
    """按 key（通常是域名）限速：同一 key 最小间隔 min_interval 秒。线程安全。"""

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


# 全局单例：每域名最小间隔 0.3s（~3 QPS），东财/新浪/腾讯都不会触发限流
_rate_limiter = _RateLimiter(min_interval=0.3)


def _backoff_sleep(attempt: int, base: float = 1.0) -> None:
    """指数退避：attempt=0 -> base*1s, 1 -> base*2s, 2 -> base*4s。"""
    time.sleep(base * (2 ** attempt))


SECTOR_STOCK_COLUMNS = ["代码", "名称", "最新价", "今日涨跌幅", "今日主力净流入-净额"]
INDIVIDUAL_COLUMNS = ["股票代码", "股票简称", "最新价", "涨跌幅", "净额"]


INDIVIDUAL_EXTENDED_COLUMNS = [
    "股票代码",
    "股票简称",
    "最新价",
    "涨跌幅",
    "净额",
    "成交额",  # eastmoney clist field f6（主力净额外的实际成交额，避免 universe 永远 fallback 到 net_amount）
    "换手率",
    "市盈率动",
    "市净率",
    "总市值",
    "流通市值",
]
INDIVIDUAL_COLUMN_ALIASES = {
    "turnover_rate": "换手率",
    "pe_dynamic": "市盈率动",
    "pb": "市净率",
    "total_mv": "总市值",
    "float_mv": "流通市值",
    "amount": "成交额",  # daily_bars._safe_fetch_realtime_amounts 用 amount 语义查 this col
}


class AkshareGateway:
    def __init__(self) -> None:
        self._concept_board_index: pd.DataFrame | None = None
        self._concept_board_index_ths: pd.DataFrame | None = None
        self._industry_board_index: pd.DataFrame | None = None
        self._last_individual_realtime: pd.DataFrame = pd.DataFrame()
        self._last_individual_fetch_at: datetime | None = None
        self._last_market_breadth: pd.DataFrame = pd.DataFrame()
        self._last_market_breadth_fetch_at: datetime | None = None
        self._source_snapshots: dict[str, dict[str, object]] = {}

    def fetch_sector_catalog(self, sector_type: str) -> list[str]:
        if sector_type == "industry":
            return self._extract_names(self._get_industry_board_index(), "板块名称")

        names = self._extract_names(self._get_concept_board_index(), "板块名称")
        names += self._extract_names(self._get_concept_board_index_ths(), "name")
        return sorted(set(names))

    def resolve_sector_name(self, sector_type: str, sector_name: str) -> str | None:
        if not sector_name:
            return None
        if sector_type == "industry":
            return self._resolve_industry_name(sector_name)
        return self._resolve_concept_name(sector_name)

    def fetch_industry_realtime(self) -> pd.DataFrame:
        return self._run(lambda: ak.stock_fund_flow_industry(symbol="即时"))

    def fetch_concept_realtime(self) -> pd.DataFrame:
        return self._run(lambda: ak.stock_fund_flow_concept(symbol="即时"))

    def fetch_individual_realtime(self) -> pd.DataFrame:
        now = now_cn()
        if (
            self._last_individual_fetch_at is not None
            and now - self._last_individual_fetch_at < timedelta(seconds=30)
            and not self._last_individual_realtime.empty
        ):
            return self._last_individual_realtime.copy()

        frame = self._fetch_individual_realtime_eastmoney()
        if not frame.empty:
            self._last_individual_realtime = frame
            self._last_individual_fetch_at = now
            self._set_source_snapshot(
                "individual_realtime",
                source_label="eastmoney",
                fallback_used=False,
                updated_at=now.isoformat(),
            )
            # 扩展开关：抛扩展列，外层使用时只取前 5 列（INDIVIDUAL_COLUMNS），无副作用。
            return frame.reindex(columns=INDIVIDUAL_EXTENDED_COLUMNS)

        # Fallback 链: 同花顺 (旧) -> 新浪 spot (新, 含成交额, 兼容 daily_bars 期望列)。
        # 新浪 spot 优先: 当东财整体拒连(本机 IP 限流)且同花顺也挂时仍能返回 5528 只。
        sina_frame = self._fetch_individual_realtime_sina()
        if not sina_frame.empty:
            self._last_individual_realtime = sina_frame
            self._last_individual_fetch_at = now
            self._set_source_snapshot(
                "individual_realtime",
                source_label="sina",
                fallback_used=True,
                updated_at=now.isoformat(),
            )
            return sina_frame

        for _ in range(2):
            frame = self._standardize_columns(self._run(lambda: ak.stock_fund_flow_individual(symbol="即时")))
            if not frame.empty:
                self._last_individual_realtime = frame
                self._last_individual_fetch_at = now
                self._set_source_snapshot(
                    "individual_realtime",
                    source_label="akshare",
                    fallback_used=True,
                    updated_at=now.isoformat(),
                )
                return frame.copy()

        if not self._last_individual_realtime.empty:
            self._set_source_snapshot(
                "individual_realtime",
                source_label="cache",
                fallback_used=True,
                updated_at=self._last_individual_fetch_at.isoformat() if self._last_individual_fetch_at else now.isoformat(),
                degraded_fields=["individual_realtime"],
            )
            return self._last_individual_realtime.copy()
        self._set_source_snapshot(
            "individual_realtime",
            source_label="eastmoney",
            fallback_used=False,
            updated_at=now.isoformat(),
            degraded_fields=["individual_realtime"],
        )
        return pd.DataFrame(columns=INDIVIDUAL_COLUMNS)

    def fetch_sector_stocks(self, sector_type: str, sector_name: str) -> pd.DataFrame:
        if sector_type == "industry":
            industry_name = self._resolve_industry_name(sector_name) or sector_name
            summary = self._standardize_columns(
                self._run(lambda: ak.stock_sector_fund_flow_summary(symbol=industry_name, indicator="今日"))
            )
            if not summary.empty:
                return self._select_stock_flow_columns(
                    summary,
                    code_key="代码",
                    name_key="名称",
                    price_key="最新价",
                    change_key="今日涨跌幅",
                    net_key="今日主力净流入-净额",
                )
            members = self._standardize_columns(self._run(lambda: ak.stock_board_industry_cons_em(symbol=industry_name)))
            return self._merge_members_with_realtime_flow(members)

        concept_name = self._resolve_concept_name(sector_name) or sector_name
        concept_symbol = self._resolve_concept_symbol(concept_name) or concept_name
        members = self._standardize_columns(self._run(lambda: ak.stock_board_concept_cons_em(symbol=concept_symbol)))
        if members.empty:
            members = self._fetch_concept_members_ths(concept_name)
        return self._merge_members_with_realtime_flow(members)

    def fetch_daily_history(self, sector_type: str, sector_name: str) -> pd.DataFrame:
        canonical_name = self.resolve_sector_name(sector_type, sector_name) or sector_name
        if sector_type == "industry":
            return self._standardize_columns(self._run(lambda: ak.stock_sector_fund_flow_hist(symbol=canonical_name)))
        return self._standardize_columns(self._run(lambda: ak.stock_concept_fund_flow_hist(symbol=canonical_name)))

    def fetch_limit_up_pool(self, date: str) -> pd.DataFrame:
        return self._standardize_columns(self._run(lambda: ak.stock_zt_pool_em(date=date)))

    def fetch_previous_limit_up_pool(self, date: str) -> pd.DataFrame:
        return self._standardize_columns(self._run(lambda: ak.stock_zt_pool_previous_em(date=date)))

    def fetch_broken_limit_up_pool(self, date: str) -> pd.DataFrame:
        return self._standardize_columns(self._run(lambda: ak.stock_zt_pool_zbgc_em(date=date)))

    def fetch_strong_limit_up_pool(self, date: str) -> pd.DataFrame:
        return self._standardize_columns(self._run(lambda: ak.stock_zt_pool_strong_em(date=date)))

    def fetch_limit_up_from_realtime(self) -> pd.DataFrame:
        """降级涨停池：东财涨停 API 挂时，用实时行情 + 涨幅阈值判定涨停股。

        复用 fetch_individual_realtime() 的东财->新浪->akshare fallback 链，
        所以即使东财整体封 IP，只要新浪能出数据，仍能给出当日涨停列表。

        缺失字段（vs 东财涨停池）：连板数/封单金额/封板时间/炸板次数/振幅/市值。
        连板数默认 1（无法判定），其他列留空。
        """
        rt = self.fetch_individual_realtime()
        if rt is None or rt.empty:
            return pd.DataFrame()
        if "涨跌幅" not in rt.columns or "股票代码" not in rt.columns:
            return pd.DataFrame()

        def _is_lu(code_val: object, pct_val: object) -> bool:
            if pct_val is None:
                return False
            try:
                pct = float(pct_val)
            except (TypeError, ValueError):
                return False
            if pd.isna(pct):
                return False
            code_str = str(code_val or "")
            # 科创/创业 20% 涨停，主板 10%；-0.2 容差（9.6/19.6 起算）
            threshold = 19.6 if code_str.startswith(("300", "301", "688", "689")) else 9.6
            return pct >= threshold

        mask = rt.apply(lambda r: _is_lu(r.get("股票代码"), r.get("涨跌幅")), axis=1)
        lu = rt[mask].copy()
        if lu.empty:
            return pd.DataFrame()
        # 映射成 _normalize_limit_up_frame 期望的中文列名
        return pd.DataFrame({
            "代码": lu["股票代码"].astype(str),
            "名称": lu.get("股票简称", "").astype(str),
            "连板数": 1,  # 降级：无法判定连板，默认 1 板
            "最新价": pd.to_numeric(lu.get("最新价"), errors="coerce"),
            "涨跌幅": pd.to_numeric(lu["涨跌幅"], errors="coerce"),
            "成交额": pd.to_numeric(lu.get("成交额"), errors="coerce"),
            "换手率": pd.to_numeric(lu.get("换手率"), errors="coerce"),
        })

    def fetch_stock_daily_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "",
    ) -> pd.DataFrame:
        """拉取个股日线。

        ``adjust`` 透传给 ``ak.stock_zh_a_hist`` 复权口径（"" 不复权 | "qfq" 前复权
        | "hfq" 后复权）；默认 "" 保持向后兼容，仅选股器等需要严格一致口径的场景
        显式传入 ``"qfq"``。
        """
        frame = self._standardize_columns(
            self._run(
                lambda: ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust=adjust,
                )
            )
        )
        if not frame.empty:
            self._set_source_snapshot(
                f"stock_daily_history:{symbol}",
                source_label="akshare",
                fallback_used=False,
                updated_at=now_cn().isoformat(),
                meta={"adjust": adjust or ""},
            )
            return frame
        frame = self._fetch_stock_daily_history_eastmoney(symbol=symbol, start_date=start_date, end_date=end_date)
        em_worked = not frame.empty
        if not em_worked:
            # 第三源: 腾讯 web.ifzq.gtimg.cn/appstock/app/fqkline/get (本机直连可用, 实测 0.6s 出 15 日)。
            # 东财 push2his 因 IP 限流拒连时唯一可信源; 注: 腾讯无复权控制, 强制 fqt=1。
            frame = self._fetch_stock_daily_history_tencent(symbol=symbol, start_date=start_date, end_date=end_date)
        self._set_source_snapshot(
            f"stock_daily_history:{symbol}",
            source_label=("akshare" if em_worked else ("eastmoney" if frame.empty else "tencent")),
            fallback_used=not em_worked and not frame.empty,
            updated_at=now_cn().isoformat(),
            meta={"adjust": adjust or ("fqt=1" if em_worked else "tencent-qfq")},
            degraded_fields=[] if not frame.empty else ["daily_history"],
        )
        return frame

    def fetch_stock_fund_flow_history(self, stock: str, market: str) -> pd.DataFrame:
        """个股资金流历史，双源 fallback。

        主源：``ak.stock_individual_fund_flow``（东财数据走 akshare 代理）；
        备源：东方财富 ``push2his.eastmoney.com/api/qt/stock/fflow/daykline/get``。
        任一源成功即返回；写入 ``_source_snapshots`` 供前端展示数据来源。
        """
        try:
            frame = self._standardize_columns(
                self._run(lambda: ak.stock_individual_fund_flow(stock=stock, market=market))
            )
            if not frame.empty:
                self._set_source_snapshot(
                    f"stock_fund_flow_history:{stock}",
                    source_label="akshare",
                    fallback_used=False,
                    updated_at=now_cn().isoformat(),
                )
                return frame
        except Exception:
            logger.warning("akshare fund_flow failed for %s, trying eastmoney", stock)

        frame = self._fetch_stock_fund_flow_history_eastmoney(stock, market)
        self._set_source_snapshot(
            f"stock_fund_flow_history:{stock}",
            source_label="eastmoney" if not frame.empty else "none",
            fallback_used=not frame.empty,
            updated_at=now_cn().isoformat(),
            degraded_fields=[] if not frame.empty else ["fund_flow_history"],
        )
        return frame

    def fetch_market_index_spot(self) -> pd.DataFrame:
        frame = self._fetch_market_index_spot_tencent_primary()
        if not frame.empty:
            self._set_source_snapshot(
                "market_index_spot",
                source_label="tencent",
                fallback_used=False,
                updated_at=now_cn().isoformat(),
            )
            return frame
        frame = self._standardize_columns(self._run(ak.stock_zh_index_spot_sina))
        self._set_source_snapshot(
            "market_index_spot",
            source_label="akshare" if not frame.empty else "tencent",
            fallback_used=not frame.empty,
            updated_at=now_cn().isoformat(),
            degraded_fields=[] if not frame.empty else ["spot"],
        )
        return frame

    def fetch_market_index_history(self, symbol: str, days: int = 20) -> pd.DataFrame:
        frame = self._fetch_market_index_history_tencent(symbol=symbol, days=days)
        if not frame.empty:
            self._set_source_snapshot(
                f"market_index_history:{symbol}",
                source_label="tencent",
                fallback_used=False,
                updated_at=now_cn().isoformat(),
            )
            return frame
        frame = self._standardize_columns(self._run(lambda: ak.stock_zh_index_daily(symbol=symbol)))
        if days > 0:
            frame = frame.tail(days)
        self._set_source_snapshot(
            f"market_index_history:{symbol}",
            source_label="akshare" if not frame.empty else "tencent",
            fallback_used=not frame.empty,
            updated_at=now_cn().isoformat(),
            degraded_fields=[] if not frame.empty else ["history"],
        )
        return frame

    def fetch_market_breadth(self) -> pd.DataFrame:
        frame = self._fetch_market_breadth_eastmoney()
        if self._market_breadth_looks_valid(frame):
            self._last_market_breadth = frame.copy()
            self._last_market_breadth_fetch_at = now_cn()
            self._set_source_snapshot(
                "market_breadth",
                source_label="eastmoney",
                fallback_used=False,
                updated_at=now_cn().isoformat(),
            )
            return frame

        spot_frame = self._standardize_columns(self._run(ak.stock_zh_a_spot, timeout_seconds=90))
        frame = self._build_market_breadth_from_spot(spot_frame)
        if self._market_breadth_looks_valid(frame, minimum_total=100):
            self._last_market_breadth = frame.copy()
            self._last_market_breadth_fetch_at = now_cn()
            self._set_source_snapshot(
                "market_breadth",
                source_label="akshare",
                fallback_used=True,
                updated_at=now_cn().isoformat(),
            )
            return frame

        if not self._last_market_breadth.empty:
            self._set_source_snapshot(
                "market_breadth",
                source_label="cache",
                fallback_used=True,
                updated_at=self._last_market_breadth_fetch_at.isoformat() if self._last_market_breadth_fetch_at else now_cn().isoformat(),
                degraded_fields=["market_breadth"],
            )
            return self._last_market_breadth.copy()

        frame = self._standardize_columns(self._run(ak.stock_market_activity_legu))
        self._set_source_snapshot(
            "market_breadth",
            source_label="akshare" if not frame.empty else "eastmoney",
            fallback_used=not frame.empty,
            updated_at=now_cn().isoformat(),
            degraded_fields=[] if not frame.empty else ["up_count", "down_count", "flat_count", "limit_up_count", "limit_down_count"],
        )
        return frame

    def fetch_stock_quote_batch(self, symbols: list[str]) -> dict[str, dict[str, float | str | None]]:
        normalized = [self._normalize_stock_symbol(symbol) for symbol in symbols if self._normalize_stock_symbol(symbol)]
        if not normalized:
            return {}
        url = f"https://qt.gtimg.cn/q={','.join(normalized)}"
        response = self._request_get(url)
        if response is None:
            return {}

        quotes: dict[str, dict[str, float | str | None]] = {}
        for line in response.text.splitlines():
            if "=" not in line or "~" not in line:
                continue
            symbol_part, payload = line.split("=", 1)
            full_symbol = symbol_part.replace("v_", "").strip()
            values = payload.strip().strip(";").strip('"').split("~")
            if len(values) < 6:
                continue
            stock_code = full_symbol[-6:]
            quotes[stock_code] = {
                "code": stock_code,
                "name": values[1] if len(values) > 1 else None,
                "price": self._to_float(values[3] if len(values) > 3 else None),
                "change_amount": self._to_float(values[31] if len(values) > 31 else values[4] if len(values) > 4 else None),
                "change_percent": self._to_float(values[32] if len(values) > 32 else values[5] if len(values) > 5 else None),
            }
        return quotes

    def get_source_snapshot(self, key: str) -> dict[str, object]:
        snapshot = self._source_snapshots.get(key, {})
        result: dict[str, object] = {
            "source_label": snapshot.get("source_label", "akshare"),
            "updated_at": snapshot.get("updated_at"),
            "fallback_used": bool(snapshot.get("fallback_used", False)),
            "degraded_fields": list(snapshot.get("degraded_fields", [])),
        }
        meta = snapshot.get("meta")
        if meta:
            result["meta"] = meta
        return result

    def _fetch_market_index_spot_tencent(self) -> pd.DataFrame:
        symbols = ["sh000001", "sz399001", "sz399006"]
        url = f"https://qt.gtimg.cn/q={','.join(f's_{symbol}' for symbol in symbols)}"
        response = self._request_get(url)
        if response is None:
            return pd.DataFrame()

        records: list[dict[str, object]] = []
        for line in response.text.splitlines():
            if "=" not in line or "~" not in line:
                continue
            symbol_part, payload = line.split("=", 1)
            symbol = symbol_part.replace("v_s_", "").strip()
            values = payload.strip().strip(";").strip('"').split("~")
            if len(values) < 6:
                continue
            turnover = self._to_float(values[7] if len(values) > 7 else None)
            records.append(
                {
                    "代码": symbol,
                    "名称": values[1],
                    "最新价": self._to_float(values[2]),
                    "涨跌额": self._to_float(values[3]),
                    "涨跌幅": self._to_float(values[4]),
                    "成交额": turnover * 100000000 if turnover is not None else None,
                }
            )
        return pd.DataFrame(records)

    def _fetch_market_index_spot_tencent_primary(self) -> pd.DataFrame:
        symbols = ["sh000001", "sz399001", "sz399006"]
        url = f"https://qt.gtimg.cn/q={','.join(f's_{symbol}' for symbol in symbols)}"
        response = self._request_get(url)
        if response is None:
            return pd.DataFrame()

        records: list[dict[str, object]] = []
        for line in response.text.splitlines():
            if "=" not in line or "~" not in line:
                continue
            symbol_part, payload = line.split("=", 1)
            symbol = symbol_part.replace("v_s_", "").strip()
            values = payload.strip().strip(";").strip('"').split("~")
            if len(values) < 6:
                continue
            turnover = self._to_float(values[7] if len(values) > 7 else values[5] if len(values) > 5 else None)
            records.append(
                {
                    "symbol": symbol,
                    "name": values[1],
                    "price": self._to_float(values[3] if len(values) > 3 else values[2]),
                    "change_amount": self._to_float(values[4] if len(values) > 4 else None),
                    "change_percent": self._to_float(values[5] if len(values) > 5 else None),
                    "turnover": turnover * (10000 if len(values) > 7 else 100000000) if turnover is not None else None,
                }
            )
        return pd.DataFrame(records)

    def _fetch_market_index_history_tencent(self, symbol: str, days: int = 20) -> pd.DataFrame:
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,{days},qfq"
        response = self._request_get(url)
        if response is None:
            return pd.DataFrame()
        try:
            payload = response.json()
        except Exception:
            return pd.DataFrame()

        items = payload.get("data", {}).get(symbol, {}).get("day", [])
        if not items:
            return pd.DataFrame()

        frame = pd.DataFrame(
            [
                {
                    "date": item[0],
                    "open": self._to_float(item[1]),
                    "close": self._to_float(item[2]),
                    "high": self._to_float(item[3]),
                    "low": self._to_float(item[4]),
                    "volume": self._to_float(item[5]),
                }
                for item in items
                if len(item) >= 6
            ]
        )
        return frame[["date", "open", "high", "low", "close", "volume"]]

    def _fetch_stock_daily_history_eastmoney(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        secid = self._eastmoney_secid(symbol)
        url = (
            "https://push2his.eastmoney.com/api/qt/stock/kline/get"
            f"?secid={secid}&fields1=f1,f2,f3,f4,f5,f6"
            "&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
            f"&klt=101&fqt=1&beg={start_date}&end={end_date}"
        )
        response = self._request_get(url, headers={"Referer": "https://quote.eastmoney.com/"})
        if response is None:
            return pd.DataFrame()
        try:
            payload = response.json()
        except Exception:
            return pd.DataFrame()

        klines = payload.get("data", {}).get("klines", [])
        if not klines:
            return pd.DataFrame()

        records: list[dict[str, object]] = []
        for item in klines:
            values = str(item).split(",")
            if len(values) < 11:
                continue
            records.append(
                {
                    "日期": values[0],
                    "开盘": self._to_float(values[1]),
                    "收盘": self._to_float(values[2]),
                    "最高": self._to_float(values[3]),
                    "最低": self._to_float(values[4]),
                    "成交量": self._to_float(values[5]),
                    "成交额": self._to_float(values[6]),
                    "振幅": self._to_float(values[7]),
                    "涨跌幅": self._to_float(values[8]),
                    "涨跌额": self._to_float(values[9]),
                    "换手率": self._to_float(values[10]),
                }
            )
        return pd.DataFrame(records)

    @staticmethod
    def _normalize_stock_symbol(symbol: str | None) -> str | None:
        code = str(symbol or "").strip()
        if len(code) != 6 or not code.isdigit():
            return None
        return f"sh{code}" if code.startswith("6") else f"sz{code}"

    def _fetch_stock_daily_history_tencent(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """腾讯 web.ifzq 直连版日线 fallback。

        endpoint: ``https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz000001,day,,,150,qfq``
        本机直连实测 0.6s 出数。东财 push2his 拒连时唯一可用日线源。
        返回字段: date/open/close/high/low/volume -- em 无 amount/change_pct/turnover_rate 列,
        后续 _daily_history_to_rows 用 _pick_col 兜底; 缺列字段会变 None, 仅供 universe 过滤不影响筛选.
        """
        market_symbol = self._normalize_stock_symbol(symbol)
        if not market_symbol:
            return pd.DataFrame()
        # 计算天数近似 (end - start 是 YYYYMMDD)
        try:
            from datetime import datetime
            s = datetime.strptime(start_date, "%Y%m%d")
            e = datetime.strptime(end_date, "%Y%m%d")
            days = max(1, (e - s).days)
        except Exception:
            days = 150
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={market_symbol},day,,,{days},qfq"
        response = self._request_get(url)
        if response is None:
            return pd.DataFrame()
        try:
            payload = response.json()
        except Exception:
            return pd.DataFrame()
        items = payload.get("data", {}).get(market_symbol, {}).get("qfqday", []) or payload.get("data", {}).get(market_symbol, {}).get("day", [])
        if not items:
            # 试 qfq 不存在时用未复权
            url2 = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={market_symbol},day,,,{days}"
            response2 = self._request_get(url2)
            if response2 is None:
                return pd.DataFrame()
            try:
                payload2 = response2.json()
                items = payload2.get("data", {}).get(market_symbol, {}).get("day", [])
            except Exception:
                return pd.DataFrame()
        if not items:
            return pd.DataFrame()
        records: list[dict[str, object]] = []
        for item in items:
            if not isinstance(item, list) or len(item) < 6:
                continue
            records.append(
                {
                    "日期": item[0],
                    "开盘": self._to_float(item[1]),
                    "收盘": self._to_float(item[2]),
                    "最高": self._to_float(item[3]),
                    "最低": self._to_float(item[4]),
                    "成交量": self._to_float(item[5]),
                    "成交额": None,
                    "涨跌幅": None,
                    "涨跌额": None,
                    "换手率": None,
                }
            )
        return pd.DataFrame(records)

    def _fetch_stock_fund_flow_history_eastmoney(self, stock: str, market: str) -> pd.DataFrame:
        """东方财富个股资金流历史接口。

        endpoint: ``https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get``
        返回 klines 每项 8 列 CSV：日期,主力净额,超大单净额,大单净额,中单净额,
        小单净额,主力净占比,大单净占比。本方法返回与 akshare 同名中文列的 DataFrame，
        以便 ``_fund_flow_history_to_rows`` 复用。
        """
        secid = self._eastmoney_secid(stock)
        url = (
            "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
            f"?secid={secid}&fields1=f1,f2,f3,f4,f5,f6"
            "&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
            "&lmt=1000&klt=1"
        )
        response = self._request_get(url, headers={"Referer": "https://quote.eastmoney.com/"})
        if response is None:
            return pd.DataFrame()
        try:
            payload = response.json()
        except Exception:
            return pd.DataFrame()

        klines = payload.get("data", {}).get("klines", []) or []
        if not klines:
            return pd.DataFrame()

        records: list[dict[str, object]] = []
        for item in klines:
            values = str(item).split(",")
            if len(values) < 8:
                continue
            records.append(
                {
                    "日期": values[0],
                    "主力净额": self._to_float(values[1]),
                    "超大单净额": self._to_float(values[2]),
                    "大单净额": self._to_float(values[3]),
                    "中单净额": self._to_float(values[4]),
                    "小单净额": self._to_float(values[5]),
                    "主力净占比": self._to_float(values[6]),
                    "大单净占比": self._to_float(values[7]),
                }
            )
        return pd.DataFrame(records)

    def _set_source_snapshot(
        self,
        key: str,
        *,
        source_label: str,
        fallback_used: bool,
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

    def _fetch_individual_realtime_eastmoney(self) -> pd.DataFrame:
        """扩展 clist fields：`f12,f14,f2,f3,f62,f6,f8,f9,f23,f20,f21` 一并取回。

        字段含义：f12=代码 / f14=名称 / f2=最新价 / f3=涨跌幅 / f62=主力净额 /
        f6=成交额 / f8=换手率 / f9=市盈率(动) / f23=市净率 / f20=总市值 / f21=流通市值。
        字段缺失或解析失败时**不影响**基础列；只是扩展列变 None。
        关键：f6=成交额 是 daily_bars universe 过滤的真实依据（之前 clist 没取，universe 永远 fallback 到 net_amount 主力净额，语义错位）。
        """
        items = self._fetch_eastmoney_clist(
            fields="f12,f14,f2,f3,f62,f6,f8,f9,f23,f20,f21",
            fid="f62",
            po=1,
            pz=10000,
        )
        if not items:
            return pd.DataFrame(columns=INDIVIDUAL_COLUMNS)
        rows = [
            {
                INDIVIDUAL_COLUMNS[0]: str(item.get("f12") or ""),
                INDIVIDUAL_COLUMNS[1]: str(item.get("f14") or ""),
                INDIVIDUAL_COLUMNS[2]: self._to_float(item.get("f2")),
                INDIVIDUAL_COLUMNS[3]: self._to_float(item.get("f3")),
                INDIVIDUAL_COLUMNS[4]: self._to_float(item.get("f62")),
                "成交额": self._to_float(item.get("f6")),
                "换手率": self._to_float(item.get("f8")),
                "市盈率动": self._to_float(item.get("f9")),
                "市净率": self._to_float(item.get("f23")),
                "总市值": self._to_float(item.get("f20")),
                "流通市值": self._to_float(item.get("f21")),
            }
            for item in items
            if item.get("f12")
        ]
        return pd.DataFrame(rows, columns=INDIVIDUAL_EXTENDED_COLUMNS)

    def _fetch_individual_realtime_sina(self) -> pd.DataFrame:
        """新浪 stock_zh_a_spot 直连版 fallback（绕过 akshare）。

        与东财路径返回列对齐：股票代码/股票简称/最新价/涨跌幅/净额/成交额/换手率 等。
        新浪 stock_zh_a_spot 含"成交额"列，5500+ 行 ~10s, 实测本机直连可用。
        当东财 push2 因 IP 限流拒连时, 这条路径是 universe 过滤的唯一可信源。
        新浪没有"主力净额"字段 -> 净额取成交额 * 涨跌幅 * 0.01 估算(下游不会用, universe 只看 amount)。
        """
        try:
            frame = self._run(ak.stock_zh_a_spot, timeout_seconds=90)
        except Exception:
            return pd.DataFrame()
        if frame is None or frame.empty:
            return pd.DataFrame()
        # 新浪列: 代码/名称/最新价/涨跌额/涨跌幅/买入/卖出/昨收/今开/最高/最低/成交量/成交额/时间戳
        records: list[dict[str, object]] = []
        for _, row in frame.iterrows():
            code = str(row.get("代码") or "").strip()
            # 新浪代码形如 "bj920000" -> 取末 6 位数字
            digits = "".join(ch for ch in code if ch.isdigit())
            if len(digits) < 6:
                continue
            code6 = digits[-6:].zfill(6)
            amount = self._to_float(row.get("成交额"))
            change_pct = self._to_float(row.get("涨跌幅"))
            # 净额无源 -> 用成交额 * 涨跌幅 / 100 (近似主力流向, 仅用于 cache 列对齐不参与筛选)
            net_amount = (amount * change_pct / 100.0) if (amount is not None and change_pct is not None) else None
            records.append(
                {
                    INDIVIDUAL_COLUMNS[0]: code6,
                    INDIVIDUAL_COLUMNS[1]: str(row.get("名称") or "").strip(),
                    INDIVIDUAL_COLUMNS[2]: self._to_float(row.get("最新价")),
                    INDIVIDUAL_COLUMNS[3]: change_pct,
                    INDIVIDUAL_COLUMNS[4]: net_amount,
                    "成交额": amount,
                    "换手率": self._to_float(row.get("成交量")),  # 新浪没换手率, 用成交量占位保列存在
                    "市盈率动": None,
                    "市净率": None,
                    "总市值": None,
                    "流通市值": None,
                }
            )
        if not records:
            return pd.DataFrame()
        return pd.DataFrame(records, columns=INDIVIDUAL_EXTENDED_COLUMNS)

    def _fetch_market_breadth_eastmoney(self) -> pd.DataFrame:
        items = self._fetch_eastmoney_clist(
            fields="f12,f14,f2,f3,f6",
            fid="f3",
            po=1,
            pz=10000,
        )
        if not items:
            return pd.DataFrame(columns=["item", "value"])

        up_count = 0
        down_count = 0
        flat_count = 0
        limit_up_count = 0
        limit_down_count = 0
        market_turnover = 0.0

        for item in items:
            code = str(item.get("f12") or "")
            name = str(item.get("f14") or "")
            change = self._to_float(item.get("f3"))
            market_turnover += self._to_float(item.get("f6")) or 0.0
            if change is None:
                continue
            if change > 0:
                up_count += 1
            elif change < 0:
                down_count += 1
            else:
                flat_count += 1
            if self._is_limit_move(code, name, change, direction="up"):
                limit_up_count += 1
            if self._is_limit_move(code, name, change, direction="down"):
                limit_down_count += 1

        total = up_count + down_count + flat_count
        market_activity = f"{(up_count / total) * 100:.2f}%" if total else None
        timestamp = now_cn().replace(second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        return pd.DataFrame(
            [
                {"item": "up_count", "value": float(up_count)},
                {"item": "down_count", "value": float(down_count)},
                {"item": "flat_count", "value": float(flat_count)},
                {"item": "limit_up_count", "value": float(limit_up_count)},
                {"item": "limit_down_count", "value": float(limit_down_count)},
                {"item": "market_activity", "value": market_activity},
                {"item": "market_turnover", "value": market_turnover},
                {"item": "updated_at", "value": timestamp},
            ]
        )

    def _build_market_breadth_from_spot(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["item", "value"])

        up_count = 0
        down_count = 0
        flat_count = 0
        limit_up_count = 0
        limit_down_count = 0
        market_turnover = 0.0

        for record in frame.to_dict(orient="records"):
            code = str(record.get("代码") or record.get("code") or "")
            name = str(record.get("名称") or record.get("name") or "")
            change = self._to_float(record.get("涨跌幅") or record.get("change_percent"))
            market_turnover += self._to_float(record.get("成交额") or record.get("turnover")) or 0.0
            if change is None:
                continue
            if change > 0:
                up_count += 1
            elif change < 0:
                down_count += 1
            else:
                flat_count += 1
            if self._is_limit_move(code, name, change, direction="up"):
                limit_up_count += 1
            if self._is_limit_move(code, name, change, direction="down"):
                limit_down_count += 1

        total = up_count + down_count + flat_count
        market_activity = f"{(up_count / total) * 100:.2f}%" if total else None
        timestamp = now_cn().replace(second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        return pd.DataFrame(
            [
                {"item": "up_count", "value": float(up_count)},
                {"item": "down_count", "value": float(down_count)},
                {"item": "flat_count", "value": float(flat_count)},
                {"item": "limit_up_count", "value": float(limit_up_count)},
                {"item": "limit_down_count", "value": float(limit_down_count)},
                {"item": "market_activity", "value": market_activity},
                {"item": "market_turnover", "value": market_turnover},
                {"item": "updated_at", "value": timestamp},
            ]
        )

    def _build_market_breadth_from_individual(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["item", "value"])

        up_count = 0
        down_count = 0
        flat_count = 0
        limit_up_count = 0
        limit_down_count = 0

        code_key = INDIVIDUAL_COLUMNS[0]
        name_key = INDIVIDUAL_COLUMNS[1]
        change_key = INDIVIDUAL_COLUMNS[3]

        for record in frame.to_dict(orient="records"):
            code = str(record.get(code_key) or "")
            name = str(record.get(name_key) or "")
            change = self._to_float(record.get(change_key))
            if change is None:
                continue
            if change > 0:
                up_count += 1
            elif change < 0:
                down_count += 1
            else:
                flat_count += 1
            if self._is_limit_move(code, name, change, direction="up"):
                limit_up_count += 1
            if self._is_limit_move(code, name, change, direction="down"):
                limit_down_count += 1

        total = up_count + down_count + flat_count
        market_activity = f"{(up_count / total) * 100:.2f}%" if total else None
        timestamp = now_cn().replace(second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
        return pd.DataFrame(
            [
                {"item": "up_count", "value": float(up_count)},
                {"item": "down_count", "value": float(down_count)},
                {"item": "flat_count", "value": float(flat_count)},
                {"item": "limit_up_count", "value": float(limit_up_count)},
                {"item": "limit_down_count", "value": float(limit_down_count)},
                {"item": "market_activity", "value": market_activity},
                {"item": "updated_at", "value": timestamp},
            ]
        )

    def _fetch_eastmoney_clist(
        self,
        *,
        fields: str,
        fid: str,
        po: int,
        pz: int,
        pn: int = 1,
    ) -> list[dict]:
        page_size = max(1, min(int(pz), 200))
        requested_total = max(int(pz), 1)
        current_page = max(int(pn), 1)
        collected: list[dict] = []
        total_available: int | None = None

        with requests.Session() as session:
            session.trust_env = False
            while len(collected) < requested_total:
                response = self._request_get(
                    "https://push2.eastmoney.com/api/qt/clist/get",
                    params={
                        "pn": current_page,
                        "pz": page_size,
                        "po": po,
                        "np": 1,
                        "fltt": 2,
                        "invt": 2,
                        "fid": fid,
                        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
                        "fields": fields,
                    },
                    headers={"Referer": "https://quote.eastmoney.com/"},
                    session=session,
                )
                if response is None:
                    break
                try:
                    payload = response.json()
                except Exception:
                    break

                data = payload.get("data") or {}
                diff = list(data.get("diff") or [])
                if total_available is None:
                    total_available = int(data.get("total") or 0) or len(diff)

                if not diff:
                    break

                remaining = requested_total - len(collected)
                collected.extend(diff[:remaining])

                if len(diff) < page_size:
                    break
                if total_available and len(collected) >= total_available:
                    break
                current_page += 1

        return collected[:requested_total]

    def _request_get(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
        session: requests.Session | None = None,
        timeout: tuple[float, float] = (5, 20),
        retries: int = 2,
    ):
        """带 UA 轮换 + 按域名限速 + 指数退避重试的 HTTP GET。"""
        domain = _domain_of(url)
        for attempt in range(retries + 1):
            _rate_limiter.wait(domain)
            # 每次重试换一个 UA（反指纹）
            merged_headers = {"User-Agent": _random_ua()}
            if headers:
                merged_headers.update(headers)
            try:
                if session is not None:
                    response = session.get(url, params=params, headers=merged_headers, timeout=timeout)
                    response.raise_for_status()
                    return response
                with requests.Session() as local_session:
                    local_session.trust_env = False
                    response = local_session.get(url, params=params, headers=merged_headers, timeout=timeout)
                    response.raise_for_status()
                    return response
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "akshare _request_get 失败 (attempt %d/%d): url=%s err=%s",
                    attempt + 1, retries + 1, url, exc,
                )
                if attempt < retries:
                    _backoff_sleep(attempt)
        logger.warning("akshare _request_get %d 次重试全失败: url=%s", retries + 1, url)
        return None

    @staticmethod
    def _market_breadth_looks_valid(frame: pd.DataFrame, minimum_total: int = 2000) -> bool:
        if frame.empty:
            return False
        records = frame.to_dict(orient="records")
        values = {str(item.get("item", "")): item.get("value") for item in records}
        up_count = AkshareGateway._to_float(values.get("up_count")) or 0.0
        down_count = AkshareGateway._to_float(values.get("down_count")) or 0.0
        flat_count = AkshareGateway._to_float(values.get("flat_count")) or 0.0
        total = up_count + down_count + flat_count
        return total >= minimum_total and (up_count > 0 or down_count > 0)

    @staticmethod
    def _is_limit_move(code: str, name: str, change_percent: float | None, *, direction: str) -> bool:
        if change_percent is None:
            return False
        threshold = 9.5
        upper_name = name.upper()
        if "ST" in upper_name:
            threshold = 4.8
        elif code.startswith(("300", "301", "688")):
            threshold = 19.5
        elif code.startswith(("4", "8")):
            threshold = 29.5
        return change_percent >= threshold if direction == "up" else change_percent <= -threshold

    def _merge_members_with_realtime_flow(self, members: pd.DataFrame) -> pd.DataFrame:
        if members.empty:
            return pd.DataFrame(columns=SECTOR_STOCK_COLUMNS)

        members = members.copy()
        if "现价" in members.columns and "最新价" not in members.columns:
            members = members.rename(columns={"现价": "最新价"})
        if "涨跌幅(%)" in members.columns and "涨跌幅" not in members.columns:
            members = members.rename(columns={"涨跌幅(%)": "涨跌幅"})
        members["代码"] = members.get("代码", "").map(self._normalize_code)

        realtime = self.fetch_individual_realtime()
        if realtime.empty:
            members["今日涨跌幅"] = members.get("涨跌幅", "")
            members["今日主力净流入-净额"] = ""
            return members.reindex(columns=SECTOR_STOCK_COLUMNS, fill_value="")

        flow = realtime.copy()
        flow["代码"] = flow.get("股票代码", "").map(self._normalize_code)
        flow = flow.rename(
            columns={
                "股票简称": "实时名称",
                "涨跌幅": "实时涨跌幅",
                "净额": "实时净额",
                "最新价": "实时最新价",
            }
        )
        merged = members.merge(
            flow[["代码", "实时名称", "实时最新价", "实时涨跌幅", "实时净额"]],
            on="代码",
            how="left",
        )
        result = pd.DataFrame(
            {
                "代码": merged.get("代码", ""),
                "名称": merged.get("名称", ""),
                "最新价": merged.get("实时最新价", merged.get("最新价", "")),
                "今日涨跌幅": merged.get("实时涨跌幅", merged.get("涨跌幅", "")),
                "今日主力净流入-净额": merged.get("实时净额", ""),
            }
        )
        return result.reindex(columns=SECTOR_STOCK_COLUMNS, fill_value="")

    @staticmethod
    def _select_stock_flow_columns(
        frame: pd.DataFrame,
        code_key: str,
        name_key: str,
        price_key: str,
        change_key: str,
        net_key: str,
    ) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=SECTOR_STOCK_COLUMNS)

        selected = pd.DataFrame(
            {
                "代码": frame.get(code_key, ""),
                "名称": frame.get(name_key, ""),
                "最新价": frame.get(price_key, ""),
                "今日涨跌幅": frame.get(change_key, ""),
                "今日主力净流入-净额": frame.get(net_key, ""),
            }
        )
        return selected.reindex(columns=SECTOR_STOCK_COLUMNS, fill_value="")

    @staticmethod
    def _standardize_columns(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame
        renamed = {column: "".join(str(column).split()) for column in frame.columns}
        return frame.rename(columns=renamed)

    def _resolve_concept_symbol(self, sector_name: str) -> str | None:
        index = self._get_concept_board_index()
        if index.empty:
            return None

        match = self._match_board_record(index.to_dict(orient="records"), sector_name, name_key="板块名称", code_key="板块代码")
        if match:
            return str(match.get("板块代码") or match.get("板块名称") or "")
        return None

    def _resolve_concept_name(self, sector_name: str) -> str | None:
        index = self._get_concept_board_index()
        if index.empty:
            return None

        match = self._match_board_record(index.to_dict(orient="records"), sector_name, name_key="板块名称", code_key="板块代码")
        if match:
            return str(match.get("板块名称") or "")

        ths_index = self._get_concept_board_index_ths()
        if ths_index.empty:
            return None
        ths_match = self._match_board_record(ths_index.to_dict(orient="records"), sector_name, name_key="name", code_key="code")
        if ths_match:
            return str(ths_match.get("name") or "")
        return None

    def _resolve_industry_name(self, sector_name: str) -> str | None:
        index = self._get_industry_board_index()
        if index.empty:
            return None

        match = self._match_board_record(index.to_dict(orient="records"), sector_name, name_key="板块名称", code_key="板块代码")
        if match:
            return str(match.get("板块名称") or "")
        return None

    def _match_board_record(
        self,
        records: list[dict],
        sector_name: str,
        *,
        name_key: str,
        code_key: str,
    ) -> dict | None:
        target = self._normalize_sector_name(sector_name)
        if not target:
            return None

        exact_aliases = {target, target.replace("概念", ""), target.replace("行业", ""), target.replace("板块", "")}
        for row in records:
            board_name = str(row.get(name_key, ""))
            normalized_name = self._normalize_sector_name(board_name)
            if board_name == sector_name or normalized_name in exact_aliases:
                return row

        for row in records:
            board_name = str(row.get(name_key, ""))
            normalized_name = self._normalize_sector_name(board_name)
            if target in normalized_name or normalized_name in target:
                return row

        best_match: dict | None = None
        best_score = 0.0
        for row in records:
            board_name = str(row.get(name_key, ""))
            normalized_name = self._normalize_sector_name(board_name)
            score = SequenceMatcher(None, target, normalized_name).ratio()
            if score > best_score:
                best_score = score
                best_match = row
        return best_match if best_score >= 0.5 else None

    def _get_concept_board_index(self) -> pd.DataFrame:
        if self._concept_board_index is None:
            self._concept_board_index = self._standardize_columns(self._run(ak.stock_board_concept_name_em))
        return self._concept_board_index

    def _get_concept_board_index_ths(self) -> pd.DataFrame:
        if self._concept_board_index_ths is None:
            self._concept_board_index_ths = self._standardize_columns(self._run(ak.stock_board_concept_name_ths))
        return self._concept_board_index_ths

    def _get_industry_board_index(self) -> pd.DataFrame:
        if self._industry_board_index is None:
            self._industry_board_index = self._standardize_columns(self._run(ak.stock_board_industry_name_em))
        return self._industry_board_index

    @staticmethod
    def _normalize_sector_name(value: object) -> str:
        text = "".join(str(value or "").split())
        text = text.replace("概念板块", "概念").replace("行业板块", "行业")
        for suffix in ("概念", "板块", "行业", "运输"):
            if text.endswith(suffix):
                text = text[: -len(suffix)]
        return text

    @staticmethod
    def _extract_names(frame: pd.DataFrame, column: str) -> list[str]:
        if frame.empty or column not in frame.columns:
            return []
        return [item for item in frame[column].astype(str).map(lambda value: "".join(value.split())).tolist() if item]

    def _resolve_concept_code_ths(self, sector_name: str) -> str | None:
        index = self._get_concept_board_index_ths()
        if index.empty or "name" not in index.columns or "code" not in index.columns:
            return None

        match = self._match_board_record(index.to_dict(orient="records"), sector_name, name_key="name", code_key="code")
        if match:
            return str(match.get("code") or "")
        return None

    def _fetch_concept_members_ths(self, sector_name: str) -> pd.DataFrame:
        code = self._resolve_concept_code_ths(sector_name)
        if not code:
            return pd.DataFrame(columns=["代码", "名称", "最新价", "涨跌幅"])

        url = f"http://q.10jqka.com.cn/gn/detail/code/{code}/"
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=(5, 20))
            response.raise_for_status()
            tables = pd.read_html(StringIO(response.text))
        except Exception:
            return pd.DataFrame(columns=["代码", "名称", "最新价", "涨跌幅"])

        members = pd.DataFrame()
        for table in tables:
            cleaned = self._standardize_columns(table)
            if "代码" in cleaned.columns and "名称" in cleaned.columns:
                members = cleaned
                break

        if members.empty:
            return pd.DataFrame(columns=["代码", "名称", "最新价", "涨跌幅"])
        if "现价" in members.columns and "最新价" not in members.columns:
            members = members.rename(columns={"现价": "最新价"})
        if "涨跌幅(%)" in members.columns and "涨跌幅" not in members.columns:
            members = members.rename(columns={"涨跌幅(%)": "涨跌幅"})
        members["代码"] = members.get("代码", "").map(self._normalize_code)
        return members.reindex(columns=["代码", "名称", "最新价", "涨跌幅"], fill_value="")

    @staticmethod
    def _normalize_code(value: object) -> str:
        if value is None or value == "":
            return ""
        text = "".join(str(value).split())
        return text.zfill(6) if text.isdigit() else text

    @staticmethod
    def _eastmoney_secid(symbol: str) -> str:
        code = "".join(ch for ch in str(symbol or "") if ch.isdigit())[-6:]
        return f"1.{code}" if code.startswith(("5", "6", "9")) or code.startswith("688") else f"0.{code}"

    def _run(
        self,
        fetcher: Callable[[], pd.DataFrame],
        timeout_seconds: int = 25,
        retries: int = 2,
        rate_key: str = "akshare-default",
    ) -> pd.DataFrame:
        """在独立 executor 中执行 fetcher，超时后不等待卡死线程。

        反封禁 (2026-07-21)：
        - 调用前 ``_rate_limiter.wait(rate_key)`` 限速
        - 失败/超时后指数退避重试 ``retries`` 次（默认 2 次 = 共 3 次尝试）

        关键点：``shutdown(wait=False)`` -- 旧实现用 ``with ThreadPoolExecutor`` 会在
        退出时 ``shutdown(wait=True)``，阻塞到底层 requests 真正跑完；akshare 内部
        requests 多数无 timeout，一旦挂起 25s 超时实际变无限等待，会耗死 scheduler 线程。
        """
        for attempt in range(retries + 1):
            _rate_limiter.wait(rate_key)
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(fetcher)
            try:
                result = future.result(timeout=timeout_seconds)
                return result if isinstance(result, pd.DataFrame) else pd.DataFrame()
            except TimeoutError:
                future.cancel()
                logger.warning(
                    "akshare fetcher timeout after %ss (attempt %d/%d)",
                    timeout_seconds, attempt + 1, retries + 1,
                )
            except Exception:
                logger.exception(
                    "akshare fetcher failed (attempt %d/%d)",
                    attempt + 1, retries + 1,
                )
            finally:
                executor.shutdown(wait=False)
            if attempt < retries:
                _backoff_sleep(attempt)
        logger.warning("akshare fetcher %d 次重试全失败", retries + 1)
        return pd.DataFrame()

    @staticmethod
    def _to_float(value: object) -> float | None:
        if value in (None, "", "--"):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).replace(",", "").replace("%", "").strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
