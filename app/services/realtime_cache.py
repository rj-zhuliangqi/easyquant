from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.models import IndividualStockSnapshot, SectorStockSnapshot, WatchedSector


class RealtimeCacheService:
    def __init__(self, gateway: Any, now_provider: Any | None = None) -> None:
        self.gateway = gateway
        self.now_provider = now_provider or datetime.now
        self.individual_ttl_seconds = 90
        self.sector_stock_ttl_seconds = 90

    def get_sector_stocks(
        self,
        session: Session,
        sector_type: str,
        sector_name: str,
        trading_date: date | None = None,
        force_refresh: bool = False,
        background_refresh: bool = False,
        prefer_cache: bool = True,
        sort_by: str = "net_amount",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 10,
    ) -> dict:
        current_time = self.now_provider().replace(second=0, microsecond=0)
        requested_date = trading_date or current_time.date()
        target_date = requested_date
        resolved_sector_type = sector_type
        canonical_name = self.gateway.resolve_sector_name(sector_type, sector_name) or sector_name
        latest_time = None if force_refresh else self._latest_sector_stock_timestamp(session, sector_type, canonical_name, target_date)
        source_status = "cache_hit"
        fallback_reason = None
        attempted_current_refresh = False

        # P5-1d: 原 background_refresh 分支只设 "refreshing" 状态但不实际发起刷新（死参数），
        # 删除后落到下面的实际刷新逻辑；参数保留以兼容 API 但不再有副作用
        if latest_time is None and not force_refresh and target_date == current_time.date():
            latest_time = self.refresh_sector_stocks(
                session,
                sector_type=sector_type,
                sector_name=canonical_name,
                trading_date=target_date,
            )
            source_status = "fetched" if latest_time is not None else "unavailable"
            attempted_current_refresh = True

            if latest_time is None and sector_type == "industry":
                alternate_sector_type = "concept"
                alternate_name = self.gateway.resolve_sector_name(alternate_sector_type, sector_name) or sector_name
                alternate_time = self.refresh_sector_stocks(
                    session,
                    sector_type=alternate_sector_type,
                    sector_name=alternate_name,
                    trading_date=target_date,
                )
                if alternate_time is not None:
                    resolved_sector_type = alternate_sector_type
                    canonical_name = alternate_name
                    latest_time = alternate_time
                    source_status = "fetched"
                    fallback_reason = "alternate_sector_type"

        if latest_time is None and not force_refresh:
            fallback_date = self._latest_sector_stock_trading_date(session, sector_type, canonical_name, requested_date)
            if fallback_date is not None and fallback_date != requested_date:
                target_date = fallback_date
                latest_time = self._latest_sector_stock_timestamp(session, resolved_sector_type, canonical_name, target_date)
                source_status = "stale_cache"
                fallback_reason = "latest_cached_trading_date"

        is_stale = self._is_stale(latest_time, current_time, target_date, self.sector_stock_ttl_seconds)
        should_refresh = force_refresh or (latest_time is None and not attempted_current_refresh) or (is_stale and not prefer_cache)
        if should_refresh and target_date == current_time.date():
            latest_time = self.refresh_sector_stocks(
                session,
                sector_type=sector_type,
                sector_name=canonical_name,
                trading_date=target_date,
            )
            source_status = "fetched" if latest_time is not None else "unavailable"
        elif is_stale and latest_time is not None:
            source_status = "stale_cache"

        if latest_time is None and not force_refresh:
            latest_time = self._latest_sector_stock_timestamp(session, sector_type, canonical_name, target_date)
            if latest_time is not None:
                source_status = "stale_cache"

        rows = self._sector_stock_rows(session, resolved_sector_type, canonical_name, target_date, latest_time) if latest_time else []
        individual_fallback = self._individual_fallback_by_code(session, target_date) if rows else {}
        change_percent_meta = self._sector_stock_change_percent_meta(rows, individual_fallback)
        total = len(rows)
        rows = self._sort_sector_stock_rows(rows, sort_by=sort_by, sort_order=sort_order, individual_fallback=individual_fallback)
        rows = self._paginate_rows(rows, page=page, page_size=page_size)
        live_quotes = self._live_quotes_by_code([row.stock_code for row in rows]) if rows else {}

        payload = {
            "sector_type": resolved_sector_type,
            "requested_sector_type": sector_type,
            "resolved_sector_type": resolved_sector_type,
            "sector_name": canonical_name,
            "requested_sector_name": sector_name,
            "trading_date": target_date.isoformat(),
            "requested_trading_date": requested_date.isoformat(),
            "resolved_trading_date": target_date.isoformat(),
            "fallback_reason": fallback_reason,
            "updated_at": latest_time.isoformat() if latest_time else None,
            "source_status": source_status if rows or source_status == "refreshing" else "unavailable",
            "sort_by": sort_by,
            "sort_order": sort_order,
            "page": page,
            "page_size": page_size,
            "total": total,
            "change_percent_meta": change_percent_meta,
            "refresh_recommended": source_status in {"stale_cache", "refreshing"} and target_date == current_time.date(),
            "stocks": [self._sector_stock_to_dict(row, individual_fallback.get(row.stock_code), live_quotes.get(row.stock_code)) for row in rows],
        }
        if not rows:
            payload["message"] = "该板块成分股资金流当前不可用，可能尚未完成预采样，或该交易日没有存档。"
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
        rows: list[SectorStockSnapshot] = []
        seen_codes: set[str] = set()

        for record in frame.to_dict(orient="records"):
            stock_code = self._to_str(record.get("代码")) or ""
            stock_name = self._to_str(record.get("名称")) or ""
            if not stock_code and not stock_name:
                continue
            unique_key = stock_code or stock_name
            if unique_key in seen_codes:
                continue
            seen_codes.add(unique_key)
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
        prefer_cache: bool = True,
        sort_by: str = "net_amount",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 15,
    ) -> dict:
        current_time = self.now_provider().replace(second=0, microsecond=0)
        requested_date = trading_date or current_time.date()
        target_date = requested_date
        cached_latest_time = self._latest_individual_timestamp(session, target_date)
        latest_time = None if force_refresh else cached_latest_time
        source_status = "cache_hit"
        fallback_reason = None

        if latest_time is None and not force_refresh:
            fallback_date = self._latest_individual_trading_date(session, requested_date)
            if fallback_date is not None and fallback_date != requested_date:
                target_date = fallback_date
                cached_latest_time = self._latest_individual_timestamp(session, target_date)
                latest_time = cached_latest_time
                source_status = "stale_cache"
                fallback_reason = "latest_cached_trading_date"

        is_stale = self._is_stale(latest_time, current_time, target_date, self.individual_ttl_seconds)
        should_refresh = force_refresh or latest_time is None or (is_stale and not prefer_cache)
        if should_refresh and target_date == current_time.date():
            refreshed_time = self.refresh_individual_rankings(session, trading_date=target_date)
            if refreshed_time is not None:
                latest_time = refreshed_time
                source_status = "fetched"
            else:
                fallback_date = self._latest_individual_trading_date(session, requested_date)
                fallback_time = self._latest_individual_timestamp(session, fallback_date) if fallback_date is not None else None
                if fallback_time is not None:
                    target_date = fallback_date
                    latest_time = fallback_time
                    source_status = "stale_cache"
                    fallback_reason = (
                        "cached_snapshot_after_refresh_failure"
                        if fallback_date == requested_date
                        else "latest_cached_trading_date"
                    )
                else:
                    latest_time = None
                    source_status = "unavailable"
        elif is_stale and latest_time is not None:
            source_status = "stale_cache"

        if latest_time is None and not force_refresh:
            latest_time = self._latest_individual_timestamp(session, target_date)
            if latest_time is not None:
                source_status = "stale_cache"

        rows = self._individual_rows(session, target_date, latest_time) if latest_time else []
        rows = self._sort_individual_rows(rows, sort_by=sort_by, sort_order=sort_order)
        total = len(rows)
        if limit > 0:
            rows = rows[:limit]
            total = len(rows)
        rows = self._paginate_rows(rows, page=page, page_size=page_size)
        live_quotes = self._live_quotes_by_code([row.stock_code for row in rows]) if rows else {}
        payload = {
            "trading_date": target_date.isoformat(),
            "requested_trading_date": requested_date.isoformat(),
            "resolved_trading_date": target_date.isoformat(),
            "fallback_reason": fallback_reason,
            "updated_at": latest_time.isoformat() if latest_time else None,
            "source_status": source_status if rows else "unavailable",
            "sort_by": sort_by,
            "sort_order": sort_order,
            "page": page,
            "page_size": page_size,
            "total": total,
            "refresh_recommended": source_status == "stale_cache" and target_date == current_time.date(),
            "stocks": [self._individual_stock_to_dict(row, live_quotes.get(row.stock_code)) for row in rows],
        }
        if not rows:
            payload["message"] = "当前个股资金榜暂无可用缓存。"
        return payload

    def search_individual_stocks(
        self,
        session: Session,
        keyword: str,
        trading_date: date | None = None,
        limit: int = 20,
    ) -> dict:
        current_time = self.now_provider().replace(second=0, microsecond=0)
        requested_date = trading_date or current_time.date()
        target_date = requested_date
        latest_time = self._latest_individual_timestamp(session, target_date)
        source_status = "cache_hit"
        fallback_reason = None

        if latest_time is None:
            fallback_date = self._latest_individual_trading_date(session, requested_date)
            if fallback_date is not None:
                target_date = fallback_date
                latest_time = self._latest_individual_timestamp(session, target_date)
                if fallback_date != requested_date:
                    source_status = "stale_cache"
                    fallback_reason = "latest_cached_trading_date"

        query = (keyword or "").strip()
        rows: list[IndividualStockSnapshot] = []
        if latest_time is not None and query:
            like = f"%{query}%"
            rows = list(
                session.scalars(
                    select(IndividualStockSnapshot)
                    .where(
                        IndividualStockSnapshot.trading_date == target_date,
                        IndividualStockSnapshot.captured_at == latest_time,
                        or_(IndividualStockSnapshot.stock_code.like(like), IndividualStockSnapshot.stock_name.like(like)),
                    )
                    .order_by(IndividualStockSnapshot.net_amount.desc(), IndividualStockSnapshot.stock_code.asc())
                    .limit(max(limit, 1))
                )
            )

        return {
            "keyword": query,
            "requested_trading_date": requested_date.isoformat(),
            "resolved_trading_date": target_date.isoformat() if latest_time else None,
            "fallback_reason": fallback_reason,
            "updated_at": latest_time.isoformat() if latest_time else None,
            "source_status": source_status if rows else "unavailable",
            "items": [self._individual_stock_to_dict(row) for row in rows],
        }

    def refresh_individual_rankings(self, session: Session, trading_date: date | None = None) -> datetime | None:
        captured_at = self.now_provider().replace(second=0, microsecond=0)
        target_date = trading_date or captured_at.date()
        frame = self.gateway.fetch_individual_realtime().fillna("")
        rows: list[IndividualStockSnapshot] = []
        seen_codes: set[str] = set()

        for record in frame.to_dict(orient="records"):
            stock_code = self._to_str(record.get("股票代码")) or ""
            stock_name = self._to_str(record.get("股票简称")) or ""
            if not stock_code and not stock_name:
                continue
            if stock_code and stock_code in seen_codes:
                continue
            if stock_code:
                seen_codes.add(stock_code)
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

    def list_watched_sectors(self, session: Session, sector_type: str | None = None) -> list[dict]:
        stmt = select(WatchedSector).where(WatchedSector.enabled.is_(True)).order_by(WatchedSector.sector_type.asc(), WatchedSector.sector_name.asc())
        if sector_type:
            stmt = stmt.where(WatchedSector.sector_type == sector_type)
        rows = list(session.scalars(stmt))
        return [{"sector_type": row.sector_type, "sector_name": row.sector_name, "enabled": row.enabled} for row in rows]

    def sync_watched_sectors(self, session: Session, items: list[dict[str, Any]]) -> list[dict]:
        normalized_items = []
        seen = set()
        for item in items:
            sector_type = "concept" if item.get("sector_type") == "concept" else "industry"
            requested_name = self._to_str(item.get("sector_name")) or ""
            canonical_name = self.gateway.resolve_sector_name(sector_type, requested_name) or requested_name
            key = (sector_type, canonical_name)
            if not canonical_name or key in seen:
                continue
            seen.add(key)
            normalized_items.append({"sector_type": sector_type, "sector_name": canonical_name, "enabled": True})

        # P5-1f: merge upsert，不再全表 delete+insert
        incoming_keys = {(item["sector_type"], item["sector_name"]) for item in normalized_items}
        existing = {(row.sector_type, row.sector_name): row for row in session.scalars(select(WatchedSector))}
        for item in normalized_items:
            row = existing.get((item["sector_type"], item["sector_name"]))
            if row is not None:
                row.enabled = item["enabled"]
            else:
                session.add(WatchedSector(**item))
        for key, row in existing.items():
            if key not in incoming_keys:
                session.delete(row)
        session.commit()
        return normalized_items

    def refresh_watched_sector_stocks(self, session: Session, trading_date: date | None = None) -> dict[str, int]:
        count = 0
        for item in self.list_watched_sectors(session):
            refreshed_at = self.refresh_sector_stocks(
                session,
                sector_type=item["sector_type"],
                sector_name=item["sector_name"],
                trading_date=trading_date,
            )
            if refreshed_at is not None:
                count += 1
        return {"prefetched": count}

    def prefetch_sector_batch(self, session: Session, items: list[dict[str, Any]], trading_date: date | None = None) -> int:
        deduped: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in items:
            sector_type = "concept" if item.get("sector_type") == "concept" else "industry"
            requested_name = self._to_str(item.get("sector_name")) or ""
            canonical_name = self.gateway.resolve_sector_name(sector_type, requested_name) or requested_name
            key = (sector_type, canonical_name)
            if not canonical_name or key in seen:
                continue
            seen.add(key)
            deduped.append(key)

        refreshed = 0
        for sector_type, sector_name in deduped:
            captured_at = self.refresh_sector_stocks(
                session,
                sector_type=sector_type,
                sector_name=sector_name,
                trading_date=trading_date,
            )
            if captured_at is not None:
                refreshed += 1
        return refreshed

    def rotate_sector_batch(
        self,
        session: Session,
        sector_type: str,
        sector_names: list[str],
        trading_date: date | None,
        batch_size: int,
        offset_seed: int | None = None,
    ) -> list[str]:
        canonical_names = [
            self.gateway.resolve_sector_name(sector_type, sector_name) or sector_name
            for sector_name in sector_names
            if sector_name
        ]
        normalized = []
        seen = set()
        for name in canonical_names:
            if name in seen:
                continue
            seen.add(name)
            normalized.append(name)
        if not normalized or batch_size <= 0:
            return []

        seed = offset_seed if offset_seed is not None else self.now_provider().minute
        start = (seed * batch_size) % len(normalized)
        rotated = normalized[start:] + normalized[:start]
        selected = rotated[: min(batch_size, len(rotated))]
        self.prefetch_sector_batch(
            session,
            [{"sector_type": sector_type, "sector_name": sector_name} for sector_name in selected],
            trading_date=trading_date,
        )
        return selected

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

    def _latest_sector_stock_trading_date(
        self,
        session: Session,
        sector_type: str,
        sector_name: str,
        requested_date: date,
    ) -> date | None:
        fallback = session.scalar(
            select(SectorStockSnapshot.trading_date)
            .where(
                SectorStockSnapshot.sector_type == sector_type,
                SectorStockSnapshot.sector_name == sector_name,
                SectorStockSnapshot.trading_date <= requested_date,
            )
            .distinct()
            .order_by(SectorStockSnapshot.trading_date.desc())
            .limit(1)
        )
        if fallback is not None:
            return fallback
        return session.scalar(
            select(SectorStockSnapshot.trading_date)
            .where(
                SectorStockSnapshot.sector_type == sector_type,
                SectorStockSnapshot.sector_name == sector_name,
            )
            .distinct()
            .order_by(SectorStockSnapshot.trading_date.desc())
            .limit(1)
        )

    def _latest_individual_timestamp(self, session: Session, trading_date: date) -> datetime | None:
        return session.scalar(
            select(IndividualStockSnapshot.captured_at)
            .where(IndividualStockSnapshot.trading_date == trading_date)
            .order_by(IndividualStockSnapshot.captured_at.desc())
        )

    def _latest_individual_trading_date(self, session: Session, requested_date: date) -> date | None:
        fallback = session.scalar(
            select(IndividualStockSnapshot.trading_date)
            .where(IndividualStockSnapshot.trading_date <= requested_date)
            .distinct()
            .order_by(IndividualStockSnapshot.trading_date.desc())
            .limit(1)
        )
        if fallback is not None:
            return fallback
        return session.scalar(
            select(IndividualStockSnapshot.trading_date)
            .distinct()
            .order_by(IndividualStockSnapshot.trading_date.desc())
            .limit(1)
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

    def _individual_fallback_by_code(self, session: Session, trading_date: date) -> dict[str, IndividualStockSnapshot]:
        latest_time = self._latest_individual_timestamp(session, trading_date)
        if latest_time is None:
            return {}
        return {row.stock_code: row for row in self._individual_rows(session, trading_date, latest_time)}

    def _live_quotes_by_code(self, stock_codes: list[str]) -> dict[str, dict[str, Any]]:
        fetcher = getattr(self.gateway, "fetch_stock_quote_batch", None)
        if not callable(fetcher):
            return {}
        try:
            return fetcher(stock_codes) or {}
        except Exception:
            return {}

    @staticmethod
    def _sort_sector_stock_rows(
        rows: list[SectorStockSnapshot],
        sort_by: str,
        sort_order: str,
        individual_fallback: dict[str, IndividualStockSnapshot] | None = None,
    ) -> list[SectorStockSnapshot]:
        key = (sort_by or "net_amount").lower()
        descending = (sort_order or "desc").lower() != "asc"
        if key == "change_percent":
            return RealtimeCacheService._sort_rows_with_nulls_last(
                rows,
                value_getter=lambda row: RealtimeCacheService._sector_stock_change_percent(row, individual_fallback),
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
    def _is_stale(latest_time: datetime | None, current_time: datetime, target_date: date, ttl_seconds: int) -> bool:
        if latest_time is None:
            return True
        if target_date != current_time.date():
            return False
        return (current_time - latest_time).total_seconds() > ttl_seconds

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
    def _sector_stock_change_percent(
        row: SectorStockSnapshot,
        individual_fallback: dict[str, IndividualStockSnapshot] | None = None,
    ) -> float | None:
        if row.change_percent is not None:
            return row.change_percent
        return individual_fallback.get(row.stock_code).change_percent if individual_fallback and row.stock_code in individual_fallback else None

    @staticmethod
    def _sector_stock_change_percent_meta(
        rows: list[SectorStockSnapshot],
        individual_fallback: dict[str, IndividualStockSnapshot] | None = None,
    ) -> dict:
        original_missing = sum(1 for row in rows if row.change_percent is None)
        filled = sum(
            1
            for row in rows
            if row.change_percent is None
            and individual_fallback
            and row.stock_code in individual_fallback
            and individual_fallback[row.stock_code].change_percent is not None
        )
        return {
            "total": len(rows),
            "original_missing_count": original_missing,
            "filled_from_individual_cache": filled,
            "missing_count": max(original_missing - filled, 0),
        }

    @staticmethod
    def _sector_stock_to_dict(
        row: SectorStockSnapshot,
        fallback: IndividualStockSnapshot | None = None,
        live_quote: dict[str, Any] | None = None,
    ) -> dict:
        latest_price = row.latest_price if row.latest_price is not None else fallback.latest_price if fallback is not None else None
        change_percent = row.change_percent if row.change_percent is not None else fallback.change_percent if fallback is not None else None
        if live_quote:
            latest_price = live_quote.get("price", latest_price)
            change_percent = live_quote.get("change_percent", change_percent)
        return {
            "代码": row.stock_code,
            "名称": row.stock_name,
            "最新价": latest_price,
            "今日涨跌幅": change_percent,
            "今日主力净流入-净额": row.main_net_amount,
        }

    @staticmethod
    def _individual_stock_to_dict(row: IndividualStockSnapshot, live_quote: dict[str, Any] | None = None) -> dict:
        latest_price = row.latest_price
        change_percent = row.change_percent
        if live_quote:
            latest_price = live_quote.get("price", latest_price)
            change_percent = live_quote.get("change_percent", change_percent)
        return {
            "股票代码": row.stock_code,
            "股票简称": row.stock_name,
            "最新价": latest_price,
            "涨跌幅": change_percent,
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
