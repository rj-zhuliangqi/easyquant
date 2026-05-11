from datetime import date
from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FundFlowSnapshot(Base):
    __tablename__ = "fund_flow_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sector_type: Mapped[str] = mapped_column(String(20), index=True)
    sector_name: Mapped[str] = mapped_column(String(120), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    sector_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    inflow: Mapped[float | None] = mapped_column(Float, nullable=True)
    outflow: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    company_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    leading_stock: Mapped[str | None] = mapped_column(String(120), nullable=True)
    leading_stock_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    leading_stock_price: Mapped[float | None] = mapped_column(Float, nullable=True)


class FundFlowDailyHistory(Base):
    __tablename__ = "fund_flow_daily_history"
    __table_args__ = (UniqueConstraint("sector_type", "sector_name", "trading_date", name="uq_sector_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sector_type: Mapped[str] = mapped_column(String(20), index=True)
    sector_name: Mapped[str] = mapped_column(String(120), index=True)
    trading_date: Mapped[date] = mapped_column(Date, index=True)
    main_net_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    main_net_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)


class SectorStockSnapshot(Base):
    __tablename__ = "sector_stock_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "sector_type",
            "sector_name",
            "trading_date",
            "captured_at",
            "stock_code",
            name="uq_sector_stock_snapshot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sector_type: Mapped[str] = mapped_column(String(20), index=True)
    sector_name: Mapped[str] = mapped_column(String(120), index=True)
    trading_date: Mapped[date] = mapped_column(Date, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    stock_code: Mapped[str] = mapped_column(String(20), index=True)
    stock_name: Mapped[str] = mapped_column(String(120))
    latest_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    main_net_amount: Mapped[float | None] = mapped_column(Float, nullable=True)


class IndividualStockSnapshot(Base):
    __tablename__ = "individual_stock_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "trading_date",
            "captured_at",
            "stock_code",
            name="uq_individual_stock_snapshot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trading_date: Mapped[date] = mapped_column(Date, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    stock_code: Mapped[str] = mapped_column(String(20), index=True)
    stock_name: Mapped[str] = mapped_column(String(120))
    latest_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_amount: Mapped[float | None] = mapped_column(Float, nullable=True)


class WatchedSector(Base):
    __tablename__ = "watched_sectors"
    __table_args__ = (UniqueConstraint("sector_type", "sector_name", name="uq_watched_sector"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sector_type: Mapped[str] = mapped_column(String(20), index=True)
    sector_name: Mapped[str] = mapped_column(String(120), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
