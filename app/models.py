from datetime import datetime

from datetime import date

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint
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
