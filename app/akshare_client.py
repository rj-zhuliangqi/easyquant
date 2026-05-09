from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from io import StringIO
from typing import Callable

import akshare as ak
import pandas as pd
import requests


class AkshareGateway:
    def __init__(self) -> None:
        self._concept_board_index: pd.DataFrame | None = None
        self._concept_board_index_ths: pd.DataFrame | None = None
        self._industry_board_index: pd.DataFrame | None = None
        self._last_individual_realtime: pd.DataFrame = pd.DataFrame()
        self._last_individual_fetch_at: datetime | None = None

    def fetch_sector_catalog(self, sector_type: str) -> list[str]:
        if sector_type == "industry":
            return self._extract_names(self._get_industry_board_index(), "板块名称")

        names = self._extract_names(self._get_concept_board_index(), "板块名称")
        names += self._extract_names(self._get_concept_board_index_ths(), "name")
        return sorted(set(names))

    def fetch_industry_realtime(self) -> pd.DataFrame:
        return self._run(lambda: ak.stock_fund_flow_industry(symbol="即时"))

    def fetch_concept_realtime(self) -> pd.DataFrame:
        return self._run(lambda: ak.stock_fund_flow_concept(symbol="即时"))

    def fetch_individual_realtime(self) -> pd.DataFrame:
        now = datetime.now()
        if (
            self._last_individual_fetch_at is not None
            and now - self._last_individual_fetch_at < timedelta(seconds=30)
            and not self._last_individual_realtime.empty
        ):
            return self._last_individual_realtime.copy()

        for _ in range(2):
            frame = self._standardize_columns(self._run(lambda: ak.stock_fund_flow_individual(symbol="即时")))
            if not frame.empty:
                self._last_individual_realtime = frame
                self._last_individual_fetch_at = now
                return frame.copy()

        if not self._last_individual_realtime.empty:
            return self._last_individual_realtime.copy()
        return pd.DataFrame()

    def fetch_sector_stocks(self, sector_type: str, sector_name: str) -> pd.DataFrame:
        if sector_type == "industry":
            industry_symbol = self._resolve_industry_symbol(sector_name)
            summary = self._standardize_columns(
                self._run(lambda: ak.stock_sector_fund_flow_summary(symbol=industry_symbol, indicator="今日"))
            )
            if summary.empty and industry_symbol != sector_name:
                summary = self._standardize_columns(
                    self._run(lambda: ak.stock_sector_fund_flow_summary(symbol=sector_name, indicator="今日"))
                )
            if not summary.empty:
                return self._select_stock_flow_columns(
                    summary,
                    code_key="代码",
                    name_key="名称",
                    price_key="最新价",
                    change_key="今天涨跌幅",
                    net_key="今日主力净流入-净额",
                )
            members = self._standardize_columns(self._run(lambda: ak.stock_board_industry_cons_em(symbol=industry_symbol)))
            if members.empty and industry_symbol != sector_name:
                members = self._standardize_columns(self._run(lambda: ak.stock_board_industry_cons_em(symbol=sector_name)))
            return self._merge_members_with_realtime_flow(members)

        concept_symbol = self._resolve_concept_symbol(sector_name)
        members = self._standardize_columns(self._run(lambda: ak.stock_board_concept_cons_em(symbol=concept_symbol)))
        if members.empty:
            members = self._fetch_concept_members_ths(sector_name)
        return self._merge_members_with_realtime_flow(members)

    def fetch_daily_history(self, sector_type: str, sector_name: str) -> pd.DataFrame:
        if sector_type == "industry":
            return self._run(lambda: ak.stock_sector_fund_flow_hist(symbol=sector_name))
        return self._run(lambda: ak.stock_concept_fund_flow_hist(symbol=sector_name))

    def _merge_members_with_realtime_flow(self, members: pd.DataFrame) -> pd.DataFrame:
        columns = ["代码", "名称", "最新价", "今天涨跌幅", "今日主力净流入-净额"]
        if members.empty:
            return pd.DataFrame(columns=columns)

        members = members.copy()
        members["代码"] = members.get("代码", "").map(self._normalize_code)
        realtime = self.fetch_individual_realtime()
        if realtime.empty:
            members["今天涨跌幅"] = members.get("涨跌幅", "")
            members["今日主力净流入-净额"] = ""
            return members.reindex(columns=columns, fill_value="")

        flow = realtime.copy()
        flow["代码"] = flow.get("股票代码", "").map(self._normalize_code)
        flow = flow.rename(
            columns={
                "股票简称": "资金流名称",
                "涨跌幅": "资金流涨跌幅",
                "净额": "资金流净额",
                "最新价": "资金流最新价",
            }
        )
        merged = members.merge(
            flow[["代码", "资金流名称", "资金流最新价", "资金流涨跌幅", "资金流净额"]],
            on="代码",
            how="left",
        )
        result = pd.DataFrame(
            {
                "代码": merged.get("代码", ""),
                "名称": merged.get("名称", ""),
                "最新价": merged.get("资金流最新价", merged.get("最新价", "")),
                "今天涨跌幅": merged.get("资金流涨跌幅", merged.get("涨跌幅", "")),
                "今日主力净流入-净额": merged.get("资金流净额", ""),
            }
        )
        return result.reindex(columns=columns, fill_value="")

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
            return pd.DataFrame(columns=["代码", "名称", "最新价", "今天涨跌幅", "今日主力净流入-净额"])

        selected = pd.DataFrame(
            {
                "代码": frame.get(code_key, ""),
                "名称": frame.get(name_key, ""),
                "最新价": frame.get(price_key, ""),
                "今天涨跌幅": frame.get(change_key, ""),
                "今日主力净流入-净额": frame.get(net_key, ""),
            }
        )
        return selected.reindex(columns=["代码", "名称", "最新价", "今天涨跌幅", "今日主力净流入-净额"], fill_value="")

    @staticmethod
    def _standardize_columns(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame
        renamed = {
            column: "".join(str(column).split())
            for column in frame.columns
        }
        return frame.rename(columns=renamed)

    def _resolve_concept_symbol(self, sector_name: str) -> str:
        index = self._get_concept_board_index()
        if index.empty:
            return sector_name

        target = self._normalize_sector_name(sector_name)
        for row in index.to_dict(orient="records"):
            board_name = str(row.get("板块名称", ""))
            board_code = str(row.get("板块代码", ""))
            normalized_name = self._normalize_sector_name(board_name)
            if board_name == sector_name or normalized_name == target:
                return board_code or board_name

        for row in index.to_dict(orient="records"):
            board_name = str(row.get("板块名称", ""))
            board_code = str(row.get("板块代码", ""))
            normalized_name = self._normalize_sector_name(board_name)
            if target and (target in normalized_name or normalized_name in target):
                return board_code or board_name

        best_match_code = ""
        best_score = 0.0
        for row in index.to_dict(orient="records"):
            board_name = str(row.get("板块名称", ""))
            board_code = str(row.get("板块代码", ""))
            normalized_name = self._normalize_sector_name(board_name)
            score = SequenceMatcher(None, target, normalized_name).ratio()
            if score > best_score:
                best_score = score
                best_match_code = board_code or board_name
        if best_match_code and best_score >= 0.5:
            return best_match_code

        return sector_name

    def _resolve_industry_symbol(self, sector_name: str) -> str:
        index = self._get_industry_board_index()
        if index.empty:
            return sector_name

        target = self._normalize_sector_name(sector_name)
        for row in index.to_dict(orient="records"):
            board_name = str(row.get("板块名称", ""))
            normalized_name = self._normalize_sector_name(board_name)
            if board_name == sector_name or normalized_name == target:
                return board_name

        for row in index.to_dict(orient="records"):
            board_name = str(row.get("板块名称", ""))
            normalized_name = self._normalize_sector_name(board_name)
            if target and (target in normalized_name or normalized_name in target):
                return board_name

        best_match_name = ""
        best_score = 0.0
        for row in index.to_dict(orient="records"):
            board_name = str(row.get("板块名称", ""))
            normalized_name = self._normalize_sector_name(board_name)
            score = SequenceMatcher(None, target, normalized_name).ratio()
            if score > best_score:
                best_score = score
                best_match_name = board_name
        if best_match_name and best_score >= 0.5:
            return best_match_name

        return sector_name

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
        for suffix in ("概念", "板块", "行业", "运输"):
            if text.endswith(suffix):
                text = text[: -len(suffix)]
        return text

    @staticmethod
    def _extract_names(frame: pd.DataFrame, column: str) -> list[str]:
        if frame.empty or column not in frame.columns:
            return []
        return [
            item
            for item in frame[column].astype(str).map(lambda value: "".join(value.split())).tolist()
            if item
        ]

    def _resolve_concept_code_ths(self, sector_name: str) -> str | None:
        index = self._get_concept_board_index_ths()
        if index.empty or "name" not in index.columns or "code" not in index.columns:
            return None

        target = self._normalize_sector_name(sector_name)
        records = index.to_dict(orient="records")

        for row in records:
            name = str(row.get("name", ""))
            code = str(row.get("code", ""))
            normalized_name = self._normalize_sector_name(name)
            if name == sector_name or normalized_name == target:
                return code or None

        for row in records:
            name = str(row.get("name", ""))
            code = str(row.get("code", ""))
            normalized_name = self._normalize_sector_name(name)
            if target and (target in normalized_name or normalized_name in target):
                return code or None

        best_code = ""
        best_score = 0.0
        for row in records:
            name = str(row.get("name", ""))
            code = str(row.get("code", ""))
            normalized_name = self._normalize_sector_name(name)
            score = SequenceMatcher(None, target, normalized_name).ratio()
            if score > best_score:
                best_score = score
                best_code = code
        if best_code and best_score >= 0.5:
            return best_code
        return None

    def _fetch_concept_members_ths(self, sector_name: str) -> pd.DataFrame:
        code = self._resolve_concept_code_ths(sector_name)
        if not code:
            return pd.DataFrame(columns=["代码", "名称", "最新价", "涨跌幅"])

        url = f"http://q.10jqka.com.cn/gn/detail/code/{code}/"
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
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

    def _run(self, fetcher: Callable[[], pd.DataFrame], timeout_seconds: int = 25) -> pd.DataFrame:
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(fetcher)
                result = future.result(timeout=timeout_seconds)
                return result if isinstance(result, pd.DataFrame) else pd.DataFrame()
        except TimeoutError:
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()
