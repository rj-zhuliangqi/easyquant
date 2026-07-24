"""多因子打分模型（P2-2 简化版）。

报告 6.3.2 七步流程的务实起步版：选因子 -> 预处理（缩尾 + Z-score）-> 等权合成 -> TopN。
等权为最诚实基线（报告原话）；IC/ICIR 加权 + 行业市值中性化 + 样本外验证留后续迭代。

因子（从 stock_daily_basic + stock_indicators_daily 实时读，不持久化）：
  估值：pe_ttm（反向）、pb（反向）-- 越小越好
  动量：change_20d（正向）、rsi14（正向）
  量能：turnover_rate（正向）、volume_ratio（正向）
  规模：total_mv（反向，小市值效应）
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import StockDailyBasic, StockIndicatorDaily

logger = logging.getLogger(__name__)

# 默认因子清单 + 方向（True=正向，False=反向取负）
DEFAULT_FACTORS: dict[str, bool] = {
    "pe_ttm": False,      # 估值，越小越好
    "pb": False,          # 估值，越小越好
    "change_20d": True,   # 动量，越大越好
    "rsi14": True,        # 动量
    "turnover_rate": True,
    "volume_ratio": True,
    "total_mv": False,    # 规模，小市值效应
}

# 反向因子集合（值越小得分越高 -> 取负）
_REVERSE = {f for f, pos in DEFAULT_FACTORS.items() if not pos}

# daily_basic 列 vs indicators 列
_BASIC_COLS = {"pe_ttm", "pb", "turnover_rate", "total_mv", "volume_ratio", "pe", "ps", "circ_mv", "dv_ratio"}
_IND_COLS = {"change_20d", "rsi14", "macd_hist", "ma_bullish", "change_5d", "change_10d", "bias20"}


class MultiFactorService:
    """多因子等权打分（Z-score 标准化 + 缩尾去极值 + TopN）。"""

    def compute_scores(
        self,
        session: Session,
        trading_date: Any = None,
        factors: dict[str, bool] | None = None,
        topn: int = 20,
        exclude_st: bool = True,
    ) -> list[dict[str, Any]]:
        """算多因子等权打分 TopN。

        返回 [{stock_code, score, <factor>...}, ...] 按 score 降序。
        """
        factors = factors or DEFAULT_FACTORS
        td = trading_date or self._latest_basic_date(session)
        if td is None:
            return []

        df = self._load_factor_data(session, td, list(factors.keys()))
        if df.empty:
            return []

        # 排除 ST（stock_daily_basic 无 name，从 stock_basic 查？简化：name 不在此表，跳过 ST 过滤或后续补）
        # 反向因子取负
        for f in factors:
            if f in _REVERSE and f in df.columns:
                df[f] = -pd.to_numeric(df[f], errors="coerce")

        # 缩尾 + Z-score
        z_cols = []
        for f in factors:
            if f not in df.columns:
                continue
            z = self._winsorize_zscore(pd.to_numeric(df[f], errors="coerce"))
            df[f"{f}_z"] = z
            z_cols.append(f"{f}_z")

        if not z_cols:
            return []

        df["score"] = df[z_cols].sum(axis=1, skipna=True)
        df = df.dropna(subset=["score"])
        df = df.nlargest(topn, "score")

        rows: list[dict[str, Any]] = []
        for _, r in df.iterrows():
            row = {
                "stock_code": str(r["stock_code"]),
                "score": round(float(r["score"]), 3),
            }
            for f in factors:
                if f in df.columns:
                    v = r[f]
                    row[f] = round(float(v), 3) if pd.notna(v) else None
            rows.append(row)
        return rows

    def _latest_basic_date(self, session: Session) -> Any:
        return session.scalar(select(func.max(StockDailyBasic.trading_date)))

    def _load_factor_data(self, session: Session, td: Any, factor_names: list[str]) -> pd.DataFrame:
        basic_factors = [f for f in factor_names if f in _BASIC_COLS]
        ind_factors = [f for f in factor_names if f in _IND_COLS]

        dfs: list[pd.DataFrame] = []
        if basic_factors:
            cols = [StockDailyBasic.stock_code] + [getattr(StockDailyBasic, f) for f in basic_factors]
            rows = list(session.execute(select(*cols).where(StockDailyBasic.trading_date == td)))
            bdf = pd.DataFrame(rows, columns=["stock_code"] + basic_factors)
            bdf["stock_code"] = bdf["stock_code"].astype(str).str.zfill(6)
            dfs.append(bdf)
        if ind_factors:
            cols = [StockIndicatorDaily.stock_code] + [getattr(StockIndicatorDaily, f) for f in ind_factors]
            rows = list(session.execute(select(*cols).where(StockIndicatorDaily.trading_date == td)))
            idf = pd.DataFrame(rows, columns=["stock_code"] + ind_factors)
            idf["stock_code"] = idf["stock_code"].astype(str).str.zfill(6)
            dfs.append(idf)

        if not dfs:
            return pd.DataFrame()
        df = dfs[0]
        for d in dfs[1:]:
            df = df.merge(d, on="stock_code", how="left")
        return df

    @staticmethod
    def _winsorize_zscore(s: pd.Series) -> pd.Series:
        """缩尾 0.5%/99.5% + Z-score 标准化。"""
        s = s.dropna()
        if len(s) < 5:
            return pd.Series(np.nan, index=s.index)
        lo, hi = s.quantile(0.005), s.quantile(0.995)
        s = s.clip(lo, hi)
        mean, std = s.mean(), s.std()
        if not std or pd.isna(std) or std == 0:
            return pd.Series(0.0, index=s.index)
        return (s - mean) / std
