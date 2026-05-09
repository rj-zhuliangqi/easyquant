from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import IndividualStockSnapshot, SectorStockSnapshot


class RealtimeCacheService:
    def __init__(self, gateway: Any, now_provider: Any | None = None) -> None:
        self.gateway = gateway
        self.now_provider = now_provider or datetime.now

    def get_sector_stocks(
        self,
        session: Session,
        sector_type: str,
        sector_name: str,
        trading_date: date | None = None,
        force_refresh: bool = False,
        sort_by: str = "net_amount",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 10,
    ) -> dict:
        target_date = trading_date or self.now_provider().date()
        latest_time = None if force_refresh else self._latest_sector_stock_timestamp(session, sector_type, sector_name, target_date)
        source_status = "cache_hit"

        if latest_time is None:
            latest_time = self.refresh_sector_stocks(session, sector_type=sector_type, sector_name=sector_name, trading_date=target_date)
            source_status = "fetched" if latest_time is not None else "unavailable"

        rows = self._sector_stock_rows(session, sector_type, sector_name, target_date, latest_time) if latest_time else []
        actual_date = target_date

        if not rows:
            fallback = self._latest_sector_stock_any_date(session, sector_type, sector_name)
            if fallback is not None:
                actual_date, latest_time = fallback
                rows = self._sector_stock_rows(session, sector_type, sector_name, actual_date, latest_time)
                source_status = "stale_cache"

        total = len(rows)
        rows = self._sort_sector_stock_rows(rows, sort_by=sort_by, sort_order=sort_order)
        rows = self._paginate_rows(rows, page=page, page_size=page_size)

        payload = {
            "sector_type": sector_type,
            "sector_name": sector_name,
            "trading_date": actual_date.isoformat(),
            "updated_at": latest_time.isoformat() if latest_time else None,
            "source_status": source_status,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "page": page,
            "page_size": page_size,
            "total": total,
            "stocks": [self._sector_stock_to_dict(row) for row in rows],
        }
        if not rows:
            payload["message"] = "板块成分股资金流暂不可用，缓存缺失且本次实时抓取未拿到数据。"
        return payload

    def refresh_sector_stocks(
        self,
        session: Session,
        sector_type: str,
        sector_name: str,
        trading_date: date | None = None,
    ) -> datetime | None:
        captured_at = self.now_provider().replace(second=0, microsecond=0)
        target_date = trading_date or captured_at.date()
        frame = self.gateway.fetch_sector_stocks(sector_type, sector_name).fillna("")
        rows = []

        for record in frame.to_dict(orient="records"):
            stock_code = self._to_str(record.get("代码")) or ""
            stock_name = self._to_str(record.get("名称")) or ""
            if not stock_code and not stock_name:
                continue
            rows.append(
                SectorStockSnapshot(
                    sector_type=sector_type,
                    sector_name=sector_name,
                    trading_date=target_date,
                    captured_at=captured_at,
                    stock_code=stock_code,
                    stock_name=stock_name,
                    latest_price=self._to_float(record.get("最新价")),
                    change_percent=self._to_float(record.get("今日涨跌幅")),
                    main_net_amount=self._to_float(record.get("今日主力净流入-净额")),
                )
            )

        if not rows:
            return None

        session.execute(
            delete(SectorStockSnapshot).where(
                SectorStockSnapshot.sector_type == sector_type,
                SectorStockSnapshot.sector_name == sector_name,
                SectorStockSnapshot.trading_date == target_date,
                SectorStockSnapshot.captured_at == captured_at,
            )
        )
        session.add_all(rows)
        session.commit()
        return captured_at

    def get_individual_rankings(
        self,
        session: Session,
        limit: int,
        trading_date: date | None = None,
        force_refresh: bool = False,
        sort_by: str = "net_amount",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 15,
    ) -> dict:
        target_date = trading_date or self.now_provider().date()
        latest_time = None if force_refresh else self._latest_individual_timestamp(session, target_date)
        source_status = "cache_hit"

        if latest_time is None:
            latest_time = self.refresh_individual_rankings(session, trading_date=target_date)
            source_status = "fetched" if latest_time is not None else "unavailable"

        rows = self._individual_rows(session, target_date, latest_time) if latest_time else []
        rows = self._sort_individual_rows(rows, sort_by=sort_by, sort_order=sort_order)
        if limit > 0:
            rows = rows[:limit]
        total = len(rows)
        rows = self._paginate_rows(rows, page=page, page_size=page_size)
        return {
            "trading_date": target_date.isoformat(),
            "updated_at": latest_time.isoformat() if latest_time else None,
            "source_status": source_status,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "page": page,
            "page_size": page_size,
            "total": total,
            "stocks": [self._individual_stock_to_dict(row) for row in rows],
        }

    def refresh_individual_rankings(self, session: Session, trading_date: date | None = None) -> datetime | None:
        captured_at = self.now_provider().replace(second=0, microsecond=0)
        target_date = trading_date or captured_at.date()
        frame = self.gateway.fetch_individual_realtime().fillna("")
        rows = []

        for record in frame.to_dict(orient="records"):
            stock_code = self._to_str(record.get("股票代码")) or ""
            stock_name = self._to_str(record.get("股票简称")) or ""
            if not stock_code and not stock_name:
                continue
            rows.append(
                IndividualStockSnapshot(
                    trading_date=target_date,
                    captured_at=captured_at,
                    stock_code=stock_code,
                    stock_name=stock_name,
                    latest_price=self._to_float(record.get("最新价")),
                    change_percent=self._to_float(record.get("涨跌幅")),
                    net_amount=self._to_float(record.get("净额")),
                )
            )

        if not rows:
            return None

        session.execute(
            delete(IndividualStockSnapshot).where(
                IndividualStockSnapshot.trading_date == target_date,
                IndividualStockSnapshot.captured_at == captured_at,
            )
        )
        session.add_all(rows)
        session.commit()
        return captured_at

    def _latest_sector_stock_timestamp(
        self,
        session: Session,
        sector_type: str,
        sector_name: str,
        trading_date: date,
    ) -> datetime | None:
        return session.scalar(
            select(SectorStockSnapshot.captured_at)
            .where(
                SectorStockSnapshot.sector_type == sector_type,
                SectorStockSnapshot.sector_name == sector_name,
                SectorStockSnapshot.trading_date == trading_date,
            )
            .order_by(SectorStockSnapshot.captured_at.desc())
        )

    def _latest_sector_stock_any_date(
        self,
        session: Session,
        sector_type: str,
        sector_name: str,
    ) -> tuple[date, datetime] | None:
        row = session.execute(
            select(SectorStockSnapshot.trading_date, SectorStockSnapshot.captured_at)
            .where(
                SectorStockSnapshot.sector_type == sector_type,
                SectorStockSnapshot.sector_name == sector_name,
            )
            .order_by(SectorStockSnapshot.trading_date.desc(), SectorStockSnapshot.captured_at.desc())
            .limit(1)
        ).first()
        if row is None:
            return None
        return row[0], row[1]

    def _latest_individual_timestamp(self, session: Session, trading_date: date) -> datetime | None:
        return session.scalar(
            select(IndividualStockSnapshot.captured_at)
            .where(IndividualStockSnapshot.trading_date == trading_date)
            .order_by(IndividualStockSnapshot.captured_at.desc())
        )

    def _sector_stock_rows(
        self,
        session: Session,
        sector_type: str,
        sector_name: str,
        trading_date: date,
        captured_at: datetime,
    ) -> list[SectorStockSnapshot]:
        return list(
            session.scalars(
                select(SectorStockSnapshot)
                .where(
                    SectorStockSnapshot.sector_type == sector_type,
                    SectorStockSnapshot.sector_name == sector_name,
                    SectorStockSnapshot.trading_date == trading_date,
                    SectorStockSnapshot.captured_at == captured_at,
                )
                .order_by(SectorStockSnapshot.main_net_amount.desc(), SectorStockSnapshot.stock_code.asc())
            )
        )

    def _individual_rows(self, session: Session, trading_date: date, captured_at: datetime | None) -> list[IndividualStockSnapshot]:
        if captured_at is None:
            return []
        return list(
            session.scalars(
                select(IndividualStockSnapshot)
                .where(
                    IndividualStockSnapshot.trading_date == trading_date,
                    IndividualStockSnapshot.captured_at == captured_at,
                )
                .order_by(IndividualStockSnapshot.net_amount.desc(), IndividualStockSnapshot.stock_code.asc())
            )
        )

    @staticmethod
    def _sort_sector_stock_rows(
        rows: list[SectorStockSnapshot],
        sort_by: str,
        sort_order: str,
    ) -> list[SectorStockSnapshot]:
        key = (sort_by or "net_amount").lower()
        descending = (sort_order or "desc").lower() != "asc"
        if key == "change_percent":
            return RealtimeCacheService._sort_rows_with_nulls_last(
                rows,
                value_getter=lambda row: row.change_percent,
                descending=descending,
                tie_breaker=lambda row: row.stock_code,
            )
        return RealtimeCacheService._sort_rows_with_nulls_last(
            rows,
            value_getter=lambda row: row.main_net_amount,
            descending=descending,
            tie_breaker=lambda row: row.stock_code,
        )

    @staticmethod
    def _sort_individual_rows(
        rows: list[IndividualStockSnapshot],
        sort_by: str,
        sort_order: str,
    ) -> list[IndividualStockSnapshot]:
        key = (sort_by or "net_amount").lower()
        descending = (sort_order or "desc").lower() != "asc"
        if key == "change_percent":
            return RealtimeCacheService._sort_rows_with_nulls_last(
                rows,
                value_getter=lambda row: row.change_percent,
                descending=descending,
                tie_breaker=lambda row: row.stock_code,
            )
        return RealtimeCacheService._sort_rows_with_nulls_last(
            rows,
            value_getter=lambda row: row.net_amount,
            descending=descending,
            tie_breaker=lambda row: row.stock_code,
        )

    @staticmethod
    def _paginate_rows(rows: list[Any], page: int, page_size: int) -> list[Any]:
        safe_page = max(page, 1)
        safe_page_size = max(page_size, 1)
        start = (safe_page - 1) * safe_page_size
        end = start + safe_page_size
        return rows[start:end]

    @staticmethod
    def _sort_rows_with_nulls_last(
        rows: list[Any],
        value_getter: Any,
        descending: bool,
        tie_breaker: Any,
    ) -> list[Any]:
        with_values = [row for row in rows if value_getter(row) is not None]
        without_values = [row for row in rows if value_getter(row) is None]
        with_values.sort(key=lambda row: (value_getter(row), tie_breaker(row)), reverse=descending)
        without_values.sort(key=tie_breaker)
        return with_values + without_values

    @staticmethod
    def _sector_stock_to_dict(row: SectorStockSnapshot) -> dict:
        return {
            "代码": row.stock_code,
            "名称": row.stock_name,
            "最新价": row.latest_price,
            "今日涨跌幅": row.change_percent,
            "今日主力净流入-净额": row.main_net_amount,
        }

    @staticmethod
    def _individual_stock_to_dict(row: IndividualStockSnapshot) -> dict:
        return {
            "股票代码": row.stock_code,
            "股票简称": row.stock_name,
            "最新价": row.latest_price,
            "涨跌幅": row.change_percent,
            "净额": row.net_amount,
        }

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        if isinstance(value, str):
            normalized = value.replace("%", "").replace(",", "").strip()
            multiplier = 1.0
            if normalized.endswith("万"):
                multiplier = 10000.0
                normalized = normalized[:-1]
            elif normalized.endswith("亿"):
                multiplier = 100000000.0
                normalized = normalized[:-1]
            return float(normalized) * multiplier
        return float(value)

    @staticmethod
    def _to_str(value: Any) -> str | None:
        if value is None or value == "":
            return None
        return str(value)
