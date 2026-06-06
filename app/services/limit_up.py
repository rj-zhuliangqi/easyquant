from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Callable

import pandas as pd


class LimitUpService:
    def __init__(self, gateway: Any, now_provider: Callable[[], datetime] | None = None) -> None:
        self.gateway = gateway
        self.now_provider = now_provider or datetime.now

    def get_available_dates(self, count: int = 10) -> dict:
        current = self.now_provider().date()
        dates: list[str] = []
        cursor = current
        while len(dates) < count:
            if cursor.weekday() < 5:
                dates.append(cursor.isoformat())
            cursor -= timedelta(days=1)
        return {"dates": dates}

    def get_summary(self, trading_date: date, market_scope: str = "all") -> dict:
        current = self._load_limit_up_pool(trading_date, market_scope)
        broken = self._load_broken_pool(trading_date, market_scope)
        previous = self._load_previous_pool(trading_date, market_scope)

        current_codes = set(current["code"].tolist())
        promotion_count = sum(1 for code in previous["code"].tolist() if code in current_codes)
        previous_count = len(previous)

        highest_board = int(current["board_count"].max()) if not current.empty else 0
        first_board_count = int((current["board_count"] == 1).sum()) if not current.empty else 0
        high_board_count = int((current["board_count"] >= 2).sum()) if not current.empty else 0
        broken_count = len(broken)

        return {
            "trading_date": trading_date.isoformat(),
            "market_scope": market_scope,
            "highest_board": highest_board,
            "limit_up_count": len(current),
            "first_board_count": first_board_count,
            "high_board_count": high_board_count,
            "broken_count": broken_count,
            "promotion_count": promotion_count,
            "promotion_rate": round(promotion_count / previous_count, 4) if previous_count else 0.0,
            "break_rate": round(broken_count / previous_count, 4) if previous_count else 0.0,
            "yesterday_limit_count": previous_count,
            "strong_count": len(self._load_strong_pool(trading_date, market_scope)),
        }

    def get_ladder(self, trading_date: date, market_scope: str = "all", sort_by: str = "board_count") -> dict:
        current = self._sort_rows(self._load_limit_up_pool(trading_date, market_scope), sort_by=sort_by, descending=True)
        groups: list[dict[str, Any]] = []

        for board_count, frame in current.groupby("board_count", sort=True):
            ordered = frame.sort_values(["board_count", "first_limit_up_time", "net_inflow"], ascending=[False, True, False], kind="stable")
            leader = self._serialize_stock_row(ordered.iloc[0])
            groups.append(
                {
                    "board_count": int(board_count),
                    "label": f"{int(board_count)}连板" if int(board_count) > 1 else "首板",
                    "stock_count": len(frame),
                    "leader": leader,
                    "total_turnover": float(frame["turnover"].fillna(0).sum()),
                    "avg_turnover_rate": round(float(frame["turnover_rate"].fillna(0).mean()), 4) if len(frame) else 0.0,
                    "avg_net_inflow": round(float(frame["net_inflow"].fillna(0).mean()), 4) if len(frame) else 0.0,
                    "stocks": [self._serialize_stock_row(row) for _, row in ordered.iterrows()],
                }
            )

        groups.sort(key=lambda item: item["board_count"], reverse=True)
        return {"trading_date": trading_date.isoformat(), "market_scope": market_scope, "groups": groups, "total": len(current)}

    def get_broken_pool(self, trading_date: date, market_scope: str = "all", sort_by: str = "turnover") -> dict:
        broken = self._sort_rows(self._load_broken_pool(trading_date, market_scope), sort_by=sort_by, descending=True)
        return {
            "trading_date": trading_date.isoformat(),
            "market_scope": market_scope,
            "total": len(broken),
            "items": [self._serialize_stock_row(row, source_view="broken") for _, row in broken.iterrows()],
        }

    def get_stock_detail(self, trading_date: date, stock_code: str) -> dict:
        current = self._load_limit_up_pool(trading_date, "all")
        broken = self._load_broken_pool(trading_date, "all")
        strong = self._load_strong_pool(trading_date, "all")

        row = current[current["code"] == stock_code]
        source_view = "ladder"
        if row.empty:
            row = broken[broken["code"] == stock_code]
            source_view = "broken"
        if row.empty:
            raise KeyError(stock_code)

        stock = row.iloc[0]
        strong_row = strong[strong["code"] == stock_code]
        market = self._infer_market(stock_code)
        start_date = (trading_date - timedelta(days=10)).strftime("%Y%m%d")
        end_date = (trading_date + timedelta(days=1)).strftime("%Y%m%d")

        daily_history = self._normalize_daily_history(self.gateway.fetch_stock_daily_history(stock_code, start_date, end_date)).tail(5)
        fund_flow_history = self._normalize_stock_fund_flow(self.gateway.fetch_stock_fund_flow_history(stock_code, market)).tail(5)

        peer_group = current[current["board_count"] == stock["board_count"]] if source_view == "ladder" else broken
        peer_rankings = self._build_peer_rankings(peer_group, stock_code)

        return {
            "trading_date": trading_date.isoformat(),
            "source_view": source_view,
            "stock": self._serialize_stock_row(stock, source_view=source_view),
            "judgement": {
                "seal_status": "连板封住" if source_view == "ladder" else "炸板未封住",
                "rebound_limit_up": bool(stock.get("broken_board_count", 0) and source_view == "ladder"),
                "broken_board_count": int(stock.get("broken_board_count", 0) or 0),
                "seal_amount": self._to_float(stock.get("seal_amount")),
                "volume_ratio": self._to_float(strong_row.iloc[0]["volume_ratio"]) if not strong_row.empty else None,
                "amplitude": self._to_float(stock.get("amplitude")) or (self._to_float(daily_history.iloc[-1]["amplitude"]) if not daily_history.empty else None),
            },
            "turnover_history": daily_history[["date", "turnover_rate"]].to_dict(orient="records"),
            "net_inflow_history": fund_flow_history[["date", "net_inflow"]].to_dict(orient="records"),
            "turnover_amount_history": daily_history[["date", "turnover"]].to_dict(orient="records"),
            "change_percent_history": daily_history[["date", "change_percent"]].to_dict(orient="records"),
            "peer_rankings": peer_rankings,
        }

    def search(self, trading_date: date, keyword: str, market_scope: str = "all") -> dict:
        target = keyword.strip().lower()
        current = self._load_limit_up_pool(trading_date, market_scope)
        broken = self._load_broken_pool(trading_date, market_scope)

        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for frame, source_view in ((current, "ladder"), (broken, "broken")):
            matched = frame[
                frame["code"].astype(str).str.lower().str.contains(target, na=False)
                | frame["name"].astype(str).str.lower().str.contains(target, na=False)
            ]
            for _, row in matched.iterrows():
                code = str(row["code"])
                if code in seen:
                    continue
                seen.add(code)
                items.append(self._serialize_stock_row(row, source_view=source_view))

        return {"trading_date": trading_date.isoformat(), "keyword": keyword, "items": items}

    def _load_limit_up_pool(self, trading_date: date, market_scope: str) -> pd.DataFrame:
        frame = self._normalize_limit_up_frame(self.gateway.fetch_limit_up_pool(trading_date.strftime("%Y%m%d")), source_view="ladder")
        return self._filter_market_scope(frame, market_scope)

    def _load_previous_pool(self, trading_date: date, market_scope: str) -> pd.DataFrame:
        frame = self._normalize_previous_pool(self.gateway.fetch_previous_limit_up_pool(trading_date.strftime("%Y%m%d")))
        return self._filter_market_scope(frame, market_scope)

    def _load_broken_pool(self, trading_date: date, market_scope: str) -> pd.DataFrame:
        frame = self._normalize_broken_pool(self.gateway.fetch_broken_limit_up_pool(trading_date.strftime("%Y%m%d")))
        return self._filter_market_scope(frame, market_scope)

    def _load_strong_pool(self, trading_date: date, market_scope: str) -> pd.DataFrame:
        frame = self._normalize_strong_pool(self.gateway.fetch_strong_limit_up_pool(trading_date.strftime("%Y%m%d")))
        return self._filter_market_scope(frame, market_scope)

    @staticmethod
    def _normalize_limit_up_frame(frame: pd.DataFrame, source_view: str) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["code", "name", "board_count", "latest_price", "change_percent", "turnover", "turnover_rate", "net_inflow", "industry", "seal_amount", "first_limit_up_time", "last_limit_up_time", "broken_board_count", "amplitude", "float_market_value", "total_market_value", "source_view"])
        def series(name: str, default: Any = "") -> pd.Series:
            if name in frame.columns:
                return frame[name]
            return pd.Series([default] * len(frame), index=frame.index)

        normalized = pd.DataFrame(
            {
                "code": series("代码").astype(str),
                "name": series("名称").astype(str),
                "board_count": pd.to_numeric(series("连板数", 1), errors="coerce").fillna(1).astype(int),
                "latest_price": pd.to_numeric(series("最新价"), errors="coerce"),
                "change_percent": pd.to_numeric(series("涨跌幅"), errors="coerce"),
                "turnover": pd.to_numeric(series("成交额"), errors="coerce"),
                "turnover_rate": pd.to_numeric(series("换手率"), errors="coerce"),
                "net_inflow": pd.to_numeric(series("封板资金"), errors="coerce"),
                "industry": series("所属行业").astype(str),
                "seal_amount": pd.to_numeric(series("封板资金"), errors="coerce"),
                "first_limit_up_time": series("首次封板时间").astype(str),
                "last_limit_up_time": series("最后封板时间").astype(str),
                "broken_board_count": pd.to_numeric(series("炸板次数", 0), errors="coerce").fillna(0).astype(int),
                "amplitude": pd.to_numeric(series("振幅"), errors="coerce"),
                "float_market_value": pd.to_numeric(series("流通市值"), errors="coerce"),
                "total_market_value": pd.to_numeric(series("总市值"), errors="coerce"),
                "source_view": source_view,
            }
        )
        return normalized

    def _normalize_previous_pool(self, frame: pd.DataFrame) -> pd.DataFrame:
        normalized = self._normalize_limit_up_frame(frame, source_view="previous")
        if not frame.empty:
            normalized["board_count"] = pd.to_numeric(frame.get("昨日连板数", 1), errors="coerce").fillna(1).astype(int)
        return normalized

    def _normalize_broken_pool(self, frame: pd.DataFrame) -> pd.DataFrame:
        return self._normalize_limit_up_frame(frame, source_view="broken")

    def _normalize_strong_pool(self, frame: pd.DataFrame) -> pd.DataFrame:
        normalized = self._normalize_limit_up_frame(frame, source_view="strong")
        if not frame.empty:
            normalized["volume_ratio"] = pd.to_numeric(frame.get("量比"), errors="coerce")
        else:
            normalized["volume_ratio"] = pd.Series(dtype="float64")
        return normalized

    @staticmethod
    def _normalize_daily_history(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["date", "turnover", "amplitude", "change_percent", "turnover_rate"])
        normalized = pd.DataFrame(
            {
                "date": frame.get("日期"),
                "turnover": pd.to_numeric(frame.get("成交额"), errors="coerce"),
                "amplitude": pd.to_numeric(frame.get("振幅"), errors="coerce"),
                "change_percent": pd.to_numeric(frame.get("涨跌幅"), errors="coerce"),
                "turnover_rate": pd.to_numeric(frame.get("换手率"), errors="coerce"),
            }
        )
        normalized["date"] = normalized["date"].map(lambda value: value.isoformat() if hasattr(value, "isoformat") else str(value))
        return normalized

    @staticmethod
    def _normalize_stock_fund_flow(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["date", "net_inflow"])
        normalized = pd.DataFrame(
            {
                "date": frame.get("日期"),
                "net_inflow": pd.to_numeric(frame.get("主力净流入-净额"), errors="coerce"),
            }
        )
        normalized["date"] = normalized["date"].map(lambda value: value.isoformat() if hasattr(value, "isoformat") else str(value))
        return normalized

    @staticmethod
    def _serialize_stock_row(row: pd.Series, source_view: str | None = None) -> dict:
        return {
            "code": str(row.get("code", "")),
            "name": str(row.get("name", "")),
            "board_count": int(row.get("board_count", 0) or 0),
            "latest_price": LimitUpService._to_float(row.get("latest_price")),
            "change_percent": LimitUpService._to_float(row.get("change_percent")),
            "turnover": LimitUpService._to_float(row.get("turnover")),
            "turnover_rate": LimitUpService._to_float(row.get("turnover_rate")),
            "net_inflow": LimitUpService._to_float(row.get("net_inflow")),
            "industry": str(row.get("industry", "")),
            "seal_amount": LimitUpService._to_float(row.get("seal_amount")),
            "first_limit_up_time": str(row.get("first_limit_up_time", "")),
            "last_limit_up_time": str(row.get("last_limit_up_time", "")),
            "broken_board_count": int(row.get("broken_board_count", 0) or 0),
            "amplitude": LimitUpService._to_float(row.get("amplitude")),
            "float_market_value": LimitUpService._to_float(row.get("float_market_value")),
            "total_market_value": LimitUpService._to_float(row.get("total_market_value")),
            "source_view": source_view or str(row.get("source_view", "")),
        }

    @staticmethod
    def _sort_rows(frame: pd.DataFrame, sort_by: str, descending: bool) -> pd.DataFrame:
        if frame.empty or sort_by not in frame.columns:
            return frame
        return frame.sort_values(sort_by, ascending=not descending, kind="stable", na_position="last")

    @staticmethod
    def _filter_market_scope(frame: pd.DataFrame, market_scope: str) -> pd.DataFrame:
        if frame.empty or market_scope == "all":
            return frame
        predicates = {
            "mainboard": lambda code: not (code.startswith("300") or code.startswith("688")),
            "gem": lambda code: code.startswith("300"),
            "star": lambda code: code.startswith("688"),
        }
        predicate = predicates.get(market_scope)
        if predicate is None:
            return frame
        return frame[frame["code"].astype(str).map(predicate)].reset_index(drop=True)

    @staticmethod
    def _infer_market(stock_code: str) -> str:
        return "sh" if str(stock_code).startswith(("600", "601", "603", "605", "688")) else "sz"

    @staticmethod
    def _to_float(value: Any) -> float | None:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _build_peer_rankings(self, frame: pd.DataFrame, stock_code: str) -> dict:
        if frame.empty:
            return {"turnover_rank": None, "turnover_rate_rank": None, "net_inflow_rank": None, "seal_time_rank": None}

        rankings = {}
        for key, column, ascending in (
            ("turnover_rank", "turnover", False),
            ("turnover_rate_rank", "turnover_rate", False),
            ("net_inflow_rank", "net_inflow", False),
            ("seal_time_rank", "first_limit_up_time", True),
        ):
            ordered = frame.sort_values(column, ascending=ascending, na_position="last", kind="stable").reset_index(drop=True)
            match = ordered.index[ordered["code"] == stock_code].tolist()
            rankings[key] = match[0] + 1 if match else None
        return rankings
