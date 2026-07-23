"""MultiFactorService 单测（P2-2）：Z-score 打分 + 反向因子 + TopN。"""

from datetime import date

import pandas as pd
import pytest

from app.models import StockDailyBasic, StockIndicatorDaily
from app.services.multifactor import DEFAULT_FACTORS, MultiFactorService


def test_winsorize_zscore_clips_extreme():
    """缩尾 0.5%/99.5% 后极端值不爆炸。"""
    s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 100.0])
    z = MultiFactorService._winsorize_zscore(s)
    assert z.max() < 5
    assert z.min() > -5


def test_compute_scores_topn(db_session):
    td = date(2026, 7, 22)
    for i in range(20):
        code = f"{600000 + i:06d}"
        db_session.add(StockDailyBasic(stock_code=code, trading_date=td,
            pe_ttm=10 + i, pb=1 + i * 0.1, turnover_rate=1 + i * 0.1,
            total_mv=1e10 + i * 1e9, volume_ratio=1 + i * 0.05))
        db_session.add(StockIndicatorDaily(stock_code=code, trading_date=td,
            data_hash="x", change_20d=5 + i * 0.5, rsi14=50 + i))
    db_session.commit()
    svc = MultiFactorService()
    result = svc.compute_scores(db_session, td, topn=5)
    assert len(result) == 5
    # 降序
    scores = [r["score"] for r in result]
    assert scores == sorted(scores, reverse=True)
    assert "stock_code" in result[0]
    assert "pe_ttm" in result[0]


def test_compute_scores_empty(db_session):
    svc = MultiFactorService()
    assert svc.compute_scores(db_session, date(2026, 7, 22)) == []


def test_compute_scores_reverse_pe(db_session):
    """pe_ttm 反向因子：小 pe 高分，应排第一。"""
    td = date(2026, 7, 22)
    for i in range(10):
        db_session.add(StockDailyBasic(stock_code=f"{i:06d}", trading_date=td,
            pe_ttm=10 + i * 10, pb=1.0, turnover_rate=2.0, total_mv=1e10, volume_ratio=1.0))
    db_session.commit()
    svc = MultiFactorService()
    result = svc.compute_scores(db_session, td, factors={"pe_ttm": False}, topn=3)
    assert len(result) == 3
    # pe 最小的 000000 应排第一
    assert result[0]["stock_code"] == "000000"


def test_default_factors_has_seven():
    """默认 7 因子覆盖估值/动量/量能/规模。"""
    assert len(DEFAULT_FACTORS) == 7
    assert "pe_ttm" in DEFAULT_FACTORS
    assert "change_20d" in DEFAULT_FACTORS
