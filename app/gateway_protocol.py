"""数据源网关统一协议（Protocol）。

``AkshareGateway`` 与 ``TushareGateway`` 鸭子类型实现同一组方法（service 用
``gateway: Any`` 注入，靠方法名 + 返回列契约隐式约定）。本 Protocol 把契约显式化，
便于新增 ``TushareGateway`` 时对照、并为 ``CompositeGateway`` 双源互备提供类型基准。

P0 只文档化核心方法签名；未覆盖的方法（板块/概念/龙虎榜明细等）仍按现有隐式契约。
后续 P1 可补全为完整 Protocol 并让两个 Gateway 显式继承。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class MarketDataGateway(Protocol):
    """数据源网关协议。返回列契约见各方法文档与 ``AkshareGateway`` 实现。"""

    # ---- TuShare 批量方法（按 trade_date 一次拉全市场；TuShare 独有优势）----
    def fetch_daily_by_date(self, trade_date: Any, *, qfq_baseline_adj: dict[str, float] | None = None) -> pd.DataFrame:
        """全市场某交易日日线（已换算单位：volume 股 / amount 元）。"""
        ...

    def fetch_daily_basic_by_date(self, trade_date: Any) -> pd.DataFrame:
        """全市场每日指标（PE/PB/市值/换手率/量比；市值元）。"""
        ...

    def fetch_fund_flow_by_date(self, trade_date: Any) -> pd.DataFrame:
        """全市场资金流（main_net_amount 等已换算为元）。"""
        ...

    def fetch_lhb_by_date(self, trade_date: Any) -> pd.DataFrame:
        """全市场龙虎榜 + 机构席位（top_list + top_inst 重建）。"""
        ...

    def fetch_stk_limit_by_date(self, trade_date: Any) -> pd.DataFrame:
        """全市场涨跌停价（涨停精确判定）。"""
        ...

    def fetch_stock_basic(self) -> pd.DataFrame:
        """全市场在市股票列表（含 name/industry/list_date）。"""
        ...

    # ---- 逐只/通用方法（AkshareGateway 与 TushareGateway 共有签名）----
    def fetch_stock_daily_history(self, symbol: str, start: str, end: str, adjust: str = "") -> pd.DataFrame:
        """逐只日线（中文列：日期/开盘/收盘/最高/最低/成交量/成交额/振幅/涨跌幅/涨跌额/换手率）。"""
        ...

    def fetch_individual_realtime(self) -> pd.DataFrame:
        """全市场实时快照（盘中；TuShare 无，由 CompositeGateway 走 AKShare）。"""
        ...

    def fetch_market_index_history(self, symbol: str, days: int = 20) -> pd.DataFrame:
        """指数日线（英文列：date/open/high/low/close/volume）。"""
        ...

    def get_source_snapshot(self, key: str) -> dict[str, object]:
        """数据来源/降级标记（前端展示用）。"""
        ...
