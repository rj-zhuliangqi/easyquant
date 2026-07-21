from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime, timedelta
from app.time_utils import now_cn
from difflib import SequenceMatcher
from io import StringIO
from typing import Callable

import akshare as ak
import pandas as pd
import requests


logger = logging.getLogger(__name__)


SECTOR_STOCK_COLUMNS = ["代码", "名称", "最新价", "今日涨跌幅", "今日主力净流入-净额"]
INDIVIDUAL_COLUMNS = ["股票代码", "股票简称", "最新价", "涨跌幅", "净额"]


INDIVIDUAL_EXTENDED_COLUMNS = [
    "股票代码",
    "股票简称",
    "最新价",
    "涨跌幅",
    "净额",
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
        self._set_source_snapshot(
            f"stock_daily_history:{symbol}",
            source_label="eastmoney" if not frame.empty else "akshare",
            fallback_used=not frame.empty,
            updated_at=now_cn().isoformat(),
            meta={"adjust": adjust or "fqt=1"},
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
        """扩展 clist fields：`f12,f14,f2,f3,f62,f8,f9,f23,f20,f21` 一并取回。

        字段含义：f12=代码 / f14=名称 / f2=最新价 / f3=涨跌幅 / f62=主力净额 /
        f8=换手率 / f9=市盈率(动) / f23=市净率 / f20=总市值 / f21=流通市值。
        字段缺失或解析失败时**不影响**基础列；只是扩展列变 None。
        """
        items = self._fetch_eastmoney_clist(
            fields="f12,f14,f2,f3,f62,f8,f9,f23,f20,f21",
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
    ):
        merged_headers = {"User-Agent": "Mozilla/5.0"}
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
        except Exception:
            logger.warning("akshare _request_get 失败: url=%s", url, exc_info=True)
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

    def _run(self, fetcher: Callable[[], pd.DataFrame], timeout_seconds: int = 25) -> pd.DataFrame:
        """在独立 executor 中执行 fetcher，超时后不等待卡死线程。

        关键点：``shutdown(wait=False)`` -- 旧实现用 ``with ThreadPoolExecutor`` 会在
        退出时 ``shutdown(wait=True)``，阻塞到底层 requests 真正跑完；akshare 内部
        requests 多数无 timeout，一旦挂起 25s 超时实际变无限等待，会耗死 scheduler 线程。
        """
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(fetcher)
        try:
            result = future.result(timeout=timeout_seconds)
            return result if isinstance(result, pd.DataFrame) else pd.DataFrame()
        except TimeoutError:
            future.cancel()
            logger.warning("akshare fetcher timeout after %ss", timeout_seconds)
            return pd.DataFrame()
        except Exception:
            logger.exception("akshare fetcher failed")
            return pd.DataFrame()
        finally:
            executor.shutdown(wait=False)

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
