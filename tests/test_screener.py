"""ScreenerService 单测：指标计算（连涨/量比/MA/平台突破/涨停判定/RSI/MACD）、
DSL 多操作符组合、板块过滤、资金流降级 warnings、6 套内置预设可执行、性能冒烟。"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import pytest

from app.models import (
    IndividualStockSnapshot,
    ScreenerPreset,
    ScreenerPresetHit,
    StockDailyBar,
    StockFundFlowDaily,
)
from app.services.daily_bars import DailyBarsService
from app.services.screener import (
    BUILTIN_PRESETS,
    INDICATOR_REGISTRY,
    ScreenerService,
    apply_dsl,
    compute_features,
)


# ---------------- 合成数据辅助 -----------------


def _make_bars(
    code: str,
    n_days: int = 30,
    start: date = date(2026, 4, 1),
    *,
    trend: float = 0.05,
    vol_base: float = 1_000_000.0,
    seed: int = 0,
) -> pd.DataFrame:
    dates = pd.date_range(start, periods=n_days, freq="B")
    rng = np.random.default_rng(seed)
    base = 10.0 + np.cumsum(np.full(n_days, trend)) + rng.normal(0, 0.1, n_days)
    rows = []
    for i, d in enumerate(dates):
        prev = base[i - 1] if i > 0 else base[0]
        rows.append({
            "stock_code": code,
            "trading_date": d,
            "open": float(base[i] - 0.05),
            "close": float(base[i]),
            "high": float(base[i] + 0.1),
            "low": float(base[i] - 0.1),
            "volume": float(vol_base + i * 10_000),
            "amount": float((vol_base + i * 10_000) * 10),
            "change_pct": float(0.0 if i == 0 else (base[i] - prev) / prev * 100),
            "turnover_rate": float(1.5 + i * 0.05),
        })
    return pd.DataFrame(rows)


def _seed_bars(session, df: pd.DataFrame) -> None:
    for _, row in df.iterrows():
        session.add(StockDailyBar(
            stock_code=row["stock_code"],
            trading_date=row["trading_date"].date() if hasattr(row["trading_date"], "date") else row["trading_date"],
            open=float(row["open"]), close=float(row["close"]),
            high=float(row["high"]), low=float(row["low"]),
            volume=float(row["volume"]), amount=float(row["amount"]),
            change_pct=float(row["change_pct"]), turnover_rate=float(row["turnover_rate"]),
        ))
    session.commit()


def _seed_flow(session, code: str, dates: list[date], amounts: list[float]) -> None:
    for d, amt in zip(dates, amounts):
        session.add(StockFundFlowDaily(
            stock_code=code, trading_date=d,
            main_net_amount=amt, main_net_ratio=5.0,
            super_large_net=amt * 0.5, large_net=amt * 0.5,
        ))
    session.commit()


# ---------------- 指标计算 -----------------


def test_consecutive_up_days() -> None:
    """连涨 3 天 -> consecutive_up_days=3。"""
    df = _make_bars("000001", n_days=10, trend=0.0, seed=1)
    # 强制最后 3 天上涨，前面持平
    closes = df["close"].tolist()
    base = closes[-4]
    closes[-3] = base + 0.5
    closes[-2] = closes[-3] + 0.5
    closes[-1] = closes[-2] + 0.5
    df["close"] = closes
    df["high"] = df["close"] + 0.1
    df["low"] = df["close"] - 0.1

    out = compute_features(df, pd.DataFrame(), df["trading_date"].iloc[-1].date())
    assert int(out.iloc[0]["consecutive_up_days"]) == 3


def test_volume_ratio_excludes_today() -> None:
    """量比 = 当日量 / 前 5 日均量（不含当日）。"""
    df = _make_bars("000001", n_days=10, seed=2)
    # 当日前 5 日（索引 -6..-2）量固定 100 万，当日量 200 万
    vols = df["volume"].tolist()
    for i in range(len(vols) - 6, len(vols) - 1):
        vols[i] = 1_000_000.0
    vols[-1] = 2_000_000.0
    df["volume"] = vols
    out = compute_features(df, pd.DataFrame(), df["trading_date"].iloc[-1].date())
    ratio = float(out.iloc[0]["volume_ratio"])
    assert abs(ratio - 2.0) < 1e-6


def test_ma_relations_and_bullish() -> None:
    """严格上升趋势 -> ma_bullish=1。"""
    df = _make_bars("000001", n_days=70, trend=0.3, seed=3)
    out = compute_features(df, pd.DataFrame(), df["trading_date"].iloc[-1].date())
    assert int(out.iloc[0]["ma_bullish"]) == 1
    # close_vs_ma20 应为正
    assert float(out.iloc[0]["close_vs_ma20"]) > 0


def test_platform_breakout() -> None:
    """当日收盘 > 前 20 日最高价 -> platform_breakout=1。"""
    df = _make_bars("000001", n_days=25, trend=0.0, seed=4)
    # 第 21 日（索引 20）创新高
    df.loc[df.index[-1], "close"] = df["high"].iloc[:-1].max() + 1.0
    df.loc[df.index[-1], "high"] = df["close"].iloc[-1] + 0.1
    out = compute_features(df, pd.DataFrame(), df["trading_date"].iloc[-1].date())
    assert int(out.iloc[0]["platform_breakout"]) == 1


def test_limit_up_threshold_main_vs_cyb() -> None:
    """主板 9.8% 阈值 vs 创业板 19.8% 阈值。"""
    # 主板 9.9% -> 涨停
    df_main = _make_bars("600000", n_days=5, seed=5)
    df_main.loc[df_main.index[-1], "change_pct"] = 9.9
    out_main = compute_features(df_main, pd.DataFrame(), df_main["trading_date"].iloc[-1].date())
    assert int(out_main.iloc[0]["limit_up_today"]) == 1

    # 创业板 9.9% -> 非涨停（需 19.8%）
    df_cyb = _make_bars("300001", n_days=5, seed=6)
    df_cyb.loc[df_cyb.index[-1], "change_pct"] = 9.9
    out_cyb = compute_features(df_cyb, pd.DataFrame(), df_cyb["trading_date"].iloc[-1].date())
    assert int(out_cyb.iloc[0]["limit_up_today"]) == 0

    # 创业板 20.0% -> 涨停
    df_cyb2 = _make_bars("300002", n_days=5, seed=7)
    df_cyb2.loc[df_cyb2.index[-1], "change_pct"] = 20.0
    out_cyb2 = compute_features(df_cyb2, pd.DataFrame(), df_cyb2["trading_date"].iloc[-1].date())
    assert int(out_cyb2.iloc[0]["limit_up_today"]) == 1


def test_rsi14_in_known_range() -> None:
    """强上涨序列 RSI 应接近 100；强下跌接近 0。"""
    df_up = _make_bars("000001", n_days=20, trend=0.5, seed=8)
    out_up = compute_features(df_up, pd.DataFrame(), df_up["trading_date"].iloc[-1].date())
    assert float(out_up.iloc[0]["rsi14"]) > 70

    df_dn = _make_bars("000002", n_days=20, trend=-0.5, seed=9)
    out_dn = compute_features(df_dn, pd.DataFrame(), df_dn["trading_date"].iloc[-1].date())
    assert float(out_dn.iloc[0]["rsi14"]) < 30


def test_macd_values_finite() -> None:
    """MACD 三列应为有限数值。"""
    df = _make_bars("000001", n_days=40, trend=0.1, seed=10)
    out = compute_features(df, pd.DataFrame(), df["trading_date"].iloc[-1].date())
    for col in ("macd_dif", "macd_dea", "macd_hist"):
        val = float(out.iloc[0][col])
        assert not np.isnan(val), f"{col} is NaN"


# ---------------- DSL -----------------


def _sample_frame() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "stock_code": "000001", "close": 10.0, "change_pct": 4.0,
            "consecutive_up_days": 5, "volume_ratio": 3.0, "platform_breakout": 1,
            "main_net_inflow": 1e6, "main_net_inflow_5d": 2e6,
            "close_vs_ma20": 1.0, "close_vs_ma10": 1.0,
            "limit_up_today": 0, "rsi14": 60.0, "change_3d": -1.0,
            "change_5d": 5.0, "change_20d": 12.0, "change_10d": 8.0,
            "macd_dif": 0.1, "main_net_inflow_5d_pct_mv": 0.8,
            "main_net_inflow_days": 4, "turnover_rate": 5.0, "ma_bullish": 1,
        },
        {
            "stock_code": "000002", "close": 5.0, "change_pct": -2.0,
            "consecutive_up_days": 1, "volume_ratio": 0.5, "platform_breakout": 0,
            "main_net_inflow": -1e6, "main_net_inflow_5d": -5e5,
            "close_vs_ma20": -2.0, "close_vs_ma10": -2.0,
            "limit_up_today": 0, "rsi14": 25.0, "change_3d": -5.0,
            "change_5d": -8.0, "change_20d": -20.0, "change_10d": -10.0,
            "macd_dif": -0.1, "main_net_inflow_5d_pct_mv": -0.5,
            "main_net_inflow_days": 0, "turnover_rate": 25.0, "ma_bullish": 0,
        },
    ])


def test_dsl_between_op() -> None:
    df = _sample_frame()
    out = apply_dsl(df, [{"indicator": "volume_ratio", "op": "between", "value": [2.0, 5.0]}])
    assert out["stock_code"].tolist() == ["000001"]


def test_dsl_multiple_conditions_and() -> None:
    df = _sample_frame()
    out = apply_dsl(df, [
        {"indicator": "consecutive_up_days", "op": ">=", "value": 4},
        {"indicator": "change_pct", "op": "<", "value": 5.0},
        {"indicator": "platform_breakout", "op": "==", "value": 1},
    ])
    assert out["stock_code"].tolist() == ["000001"]


def test_dsl_missing_column_treated_as_not_match() -> None:
    """缺失列（资金流未回填）对该股票记为不满足。"""
    df = _sample_frame().drop(columns=["main_net_inflow"])
    out = apply_dsl(df, [{"indicator": "main_net_inflow", "op": ">", "value": 0}])
    assert out.empty


def test_dsl_board_filter_via_service(db_session) -> None:
    """ScreenerService._resolve_codes 按 boards 过滤。"""
    captured_at = datetime(2026, 5, 14, 15, 0, 0)
    rows = [
        {"trading_date": date(2026, 5, 14), "code": "000001", "name": "主板", "price": 10.0, "change_pct": 1.0, "net_amount": 200_000_000.0},
        {"trading_date": date(2026, 5, 14), "code": "300001", "name": "创业板", "price": 10.0, "change_pct": 1.0, "net_amount": 200_000_000.0},
        {"trading_date": date(2026, 5, 14), "code": "688001", "name": "科创板", "price": 10.0, "change_pct": 1.0, "net_amount": 200_000_000.0},
    ]
    for row in rows:
        db_session.add(IndividualStockSnapshot(
            trading_date=row["trading_date"], captured_at=captured_at,
            stock_code=row["code"], stock_name=row["name"],
            latest_price=row["price"], change_percent=row["change_pct"], net_amount=row["net_amount"],
        ))
    db_session.commit()

    daily_bars = DailyBarsService(gateway=None, now_provider=lambda: datetime(2026, 5, 14, 16, 0, 0))
    screener = ScreenerService(daily_bars_service=daily_bars)
    codes = screener._resolve_codes(db_session, {"boards": ["cyb"]})
    assert codes == ["300001"]


# ---------------- 资金流降级 warnings -----------------


def test_run_warns_when_fund_flow_empty(db_session) -> None:
    """全库资金流为空时，资金类条件触发 warnings。"""
    df = _make_bars("000001", n_days=30, trend=0.1, seed=11)
    _seed_bars(db_session, df)
    # universe 快照
    db_session.add(IndividualStockSnapshot(
        trading_date=df["trading_date"].iloc[-1].date(),
        captured_at=datetime(2026, 5, 14, 15, 0, 0),
        stock_code="000001", stock_name="测试",
        latest_price=10.0, change_percent=1.0, net_amount=200_000_000.0,
    ))
    db_session.commit()

    daily_bars = DailyBarsService(gateway=None, now_provider=lambda: datetime(2026, 5, 14, 16, 0, 0))
    screener = ScreenerService(daily_bars_service=daily_bars)
    result = screener.run(db_session, {
        "conditions": [
            {"indicator": "main_net_inflow", "op": ">", "value": 0},
        ],
        "universe": {"boards": ["main", "cyb", "kcb"]},
        "limit": 50,
    })
    assert any("资金流" in w for w in result["warnings"])


# ---------------- 6 套内置预设可执行 -----------------


def test_all_builtin_presets_runnable(db_session) -> None:
    """预设 conditions 全部能被 apply_dsl 处理（不抛错）。IR 策略用 evaluate_ir，跳过。"""
    df = _sample_frame()
    for preset in BUILTIN_PRESETS:
        if preset.get("ir"):
            continue  # IR 策略走 evaluate_ir，不测 apply_dsl
        out = apply_dsl(df, preset["conditions"])
        assert isinstance(out, pd.DataFrame)  # 不抛错即通过


def test_seed_builtin_presets_idempotent(db_session) -> None:
    screener = ScreenerService()
    added1 = screener.seed_builtin_presets(db_session)
    added2 = screener.seed_builtin_presets(db_session)
    assert added1 == len(BUILTIN_PRESETS)
    assert added2 == 0
    rows = db_session.query(ScreenerPreset).all()
    assert len(rows) == len(BUILTIN_PRESETS)
    assert all(r.is_builtin for r in rows)


def test_delete_builtin_preset_forbidden(db_session) -> None:
    screener = ScreenerService()
    screener.seed_builtin_presets(db_session)
    first = db_session.query(ScreenerPreset).first()
    with pytest.raises(PermissionError):
        screener.delete_preset(db_session, first.id)


def test_save_and_delete_custom_preset(db_session) -> None:
    screener = ScreenerService()
    row = screener.save_preset(
        db_session,
        name="我的策略",
        description="测试",
        conditions=[{"indicator": "rsi14", "op": "<", "value": 30}],
        universe={"boards": ["main"]},
        order_by="rsi14",
        order="asc",
    )
    assert row["name"] == "我的策略"
    rows = screener.list_presets(db_session)
    assert any(r["name"] == "我的策略" for r in rows)
    ok = screener.delete_preset(db_session, row["id"])
    assert ok is True


def test_save_preset_cannot_override_builtin(db_session) -> None:
    screener = ScreenerService()
    screener.seed_builtin_presets(db_session)
    with pytest.raises(PermissionError):
        screener.save_preset(
            db_session,
            name="放量突破",
            description="覆盖",
            conditions=[],
        )


# ---------------- 命中历史 ----------------


def test_snapshot_preset_hits_records_all_presets(db_session) -> None:
    """无 bars 数据时各预设命中 0，但每个预设都应写一行快照。"""
    screener = ScreenerService()
    screener.seed_builtin_presets(db_session)
    res = screener.snapshot_preset_hits(db_session, date(2026, 7, 22))
    assert res["snapshots"] == len(BUILTIN_PRESETS)
    rows = db_session.query(ScreenerPresetHit).all()
    assert len(rows) == len(BUILTIN_PRESETS)
    assert all(r.hit_count == 0 for r in rows)
    assert all(r.trading_date == date(2026, 7, 22) for r in rows)


def test_snapshot_preset_hits_idempotent_upsert(db_session) -> None:
    """同日重跑覆盖不新增行。"""
    screener = ScreenerService()
    screener.seed_builtin_presets(db_session)
    screener.snapshot_preset_hits(db_session, date(2026, 7, 22))
    screener.snapshot_preset_hits(db_session, date(2026, 7, 22))
    rows = db_session.query(ScreenerPresetHit).filter_by(trading_date=date(2026, 7, 22)).all()
    assert len(rows) == len(BUILTIN_PRESETS)


def test_get_hit_history_returns_recent(db_session) -> None:
    screener = ScreenerService()
    screener.seed_builtin_presets(db_session)
    preset = db_session.query(ScreenerPreset).first()
    # 手写 3 天快照
    ScreenerService._upsert_hit(db_session, preset.id, date(2026, 7, 20), 3, ["000001", "000002"], datetime.now())
    ScreenerService._upsert_hit(db_session, preset.id, date(2026, 7, 21), 5, ["000003"], datetime.now())
    ScreenerService._upsert_hit(db_session, preset.id, date(2026, 7, 22), 0, [], datetime.now())
    hist = screener.get_hit_history(db_session, preset.id, days=5)
    assert len(hist) == 3
    assert [h["trading_date"] for h in hist] == ["2026-07-20", "2026-07-21", "2026-07-22"]
    assert hist[1]["hit_count"] == 5
    assert hist[0]["hit_codes"] == ["000001", "000002"]


# ---------------- 策略目录 / 个股详情 (Phase 3) ----------------


def test_strategies_catalog_merges_hits(db_session) -> None:
    from app.models import ScreenerPresetHit

    screener = ScreenerService()
    screener.seed_builtin_presets(db_session)
    preset = db_session.query(ScreenerPreset).first()
    db_session.add(ScreenerPresetHit(preset_id=preset.id, trading_date=date(2026, 7, 22),
                                     hit_count=7, hit_codes='["000001"]'))
    db_session.commit()

    catalog = screener.strategies_catalog(db_session)
    assert len(catalog) == len(BUILTIN_PRESETS)
    entry = next(c for c in catalog if c["id"] == preset.id)
    assert entry["name"] == preset.name
    assert entry["category"] == preset.category
    assert entry["match_mode"] == preset.match_mode
    assert 7 in entry["hit_5d"]
    assert entry["total_5d"] == 7
    assert entry["last_hit_date"] == "2026-07-22"
    # 没命中数据的预设 hit_5d 为空、avg_5d=0
    other = next(c for c in catalog if c["id"] != preset.id)
    assert other["hit_5d"] == []
    assert other["avg_5d"] == 0.0


def test_stock_detail_aggregates_sources(db_session) -> None:
    from app.models import StockDailyBasic, StockIndicatorDaily, StockLhbDetail, StockRealtimeEod

    code = "000001"
    _seed_bars(db_session, _make_bars(code, n_days=10, start=date(2026, 7, 1), seed=2))
    db_session.add(StockRealtimeEod(
        stock_code=code, stock_name="平安", trading_date=date(2026, 7, 10),
        close=11.0, change_pct=1.2, turnover_rate=2.0, pe_dynamic=8.0,
        pb=0.9, total_mv=2e11, float_mv=1.5e11,
    ))
    # 估值/换手率权威源：stock_daily_basic（stock_detail 改从本表读 pe/pb/mv/turnover）
    db_session.add(StockDailyBasic(
        stock_code=code, trading_date=date(2026, 7, 10),
        pe_ttm=8.0, pb=0.9, total_mv=2e11, circ_mv=1.5e11, turnover_rate=2.0,
    ))
    db_session.add(StockIndicatorDaily(
        stock_code=code, trading_date=date(2026, 7, 10),
        compute_version="bars.v2.indicators.v1", data_hash="x", bar_count=10,
        rsi14=55.0, ma20=10.5, volume_ratio=1.8, main_net_inflow=1e7,
    ))
    _seed_flow(db_session, code, [date(2026, 7, 9), date(2026, 7, 10)], [1e7, -5e6])
    db_session.add(StockLhbDetail(
        trading_date=date(2026, 7, 10), stock_code=code, stock_name="平安",
        reason="涨幅偏离7%", interpretation="3家机构买入", net_buy=1e8, inst_net_count=3,
    ))
    db_session.commit()

    screener = ScreenerService()
    detail = screener.stock_detail(db_session, code)
    assert detail is not None
    assert detail["code"] == code
    assert detail["name"] == "平安"
    assert len(detail["kline"]) == 10
    assert detail["kline"][0]["date"] == "2026-07-01"
    assert detail["basics"]["latest_price"] == 11.0
    assert detail["basics"]["pe_dynamic"] == 8.0
    assert len(detail["fund_flow"]) == 2
    assert len(detail["lhb"]) == 1
    assert detail["lhb"][0]["inst_net_count"] == 3
    assert detail["indicators"]["rsi14"] == 55.0
    assert detail["indicators"]["data_date"] == "2026-07-10"


def test_stock_detail_missing_code_returns_none(db_session) -> None:
    screener = ScreenerService()
    assert screener.stock_detail(db_session, "999999") is None


# ---------------- 性能冒烟 -----------------


def test_performance_2000_stocks_x_120_days() -> None:
    """2000 只 × 120 交易日合成数据，特征计算 < 8s（P1 加 KDJ/BOLL/OBV/ATR/CCI/BIAS 12 指标，原 3s 阈值放宽）。"""
    frames = []
    for i in range(2000):
        code = f"{600000 + i:06d}"
        frames.append(_make_bars(code, n_days=120, seed=i % 100))
    bars = pd.concat(frames, ignore_index=True)
    start = time.time()
    out = compute_features(bars, pd.DataFrame(), bars["trading_date"].iloc[-1].date())
    elapsed = time.time() - start
    assert len(out) == 2000
    assert elapsed < 8.0, f"特征计算耗时 {elapsed:.2f}s 超过 8s 阈值"


# ---------------- 指标注册表 -----------------


def test_indicator_registry_has_all_groups() -> None:
    groups = {meta["group"] for meta in INDICATOR_REGISTRY.values()}
    expected = {"基础", "趋势", "动量", "量能", "形态", "资金流"}
    assert expected.issubset(groups)
    # 关键指标存在
    for name in [
        "ma5", "ma20", "ma60", "close_vs_ma20", "ma_bullish",
        "consecutive_up_days", "rsi14", "macd_dif", "volume_ratio",
        "limit_up_today", "platform_breakout",
        "main_net_inflow", "main_net_inflow_5d", "main_net_inflow_5d_pct_mv",
    ]:
        assert name in INDICATOR_REGISTRY


# ---------------- run() 完整路径 -----------------


def test_run_returns_results_with_data_date(db_session) -> None:
    df = _make_bars("000001", n_days=30, trend=0.2, seed=20)
    _seed_bars(db_session, df)
    db_session.add(IndividualStockSnapshot(
        trading_date=df["trading_date"].iloc[-1].date(),
        captured_at=datetime(2026, 5, 14, 15, 0, 0),
        stock_code="000001", stock_name="测试",
        latest_price=10.0, change_percent=1.0, net_amount=200_000_000.0,
    ))
    db_session.commit()

    daily_bars = DailyBarsService(gateway=None, now_provider=lambda: datetime(2026, 5, 14, 16, 0, 0))
    screener = ScreenerService(daily_bars_service=daily_bars)
    result = screener.run(db_session, {
        "conditions": [{"indicator": "close_vs_ma20", "op": ">=", "value": -100}],
        "universe": {"boards": ["main"]},
        "order_by": "close_vs_ma20",
        "order": "desc",
        "limit": 10,
    })
    assert result["data_date"] is not None
    assert result["total"] >= 1
    assert all("code" in r for r in result["results"])


def test_run_uses_precomputed_indicators_without_attr_error(db_session) -> None:
    """stock_indicators_daily 有数据时，_load_precomputed_indicators 遍历 Row 不应
    抛 AttributeError（回归：select(Entity) 漏 .scalars()，r.stock_code 取值炸）。

    旧实现 ``session.execute(select(StockIndicatorDaily)...)`` 返回 Row，循环里
    ``r.stock_code`` 抛 ``AttributeError: stock_code`` -> /api/screener/run 500。
    表空时在 ``if not rows: return`` 提前返回掩盖了 bug；表有数据（TuShare 回补后）即炸。
    """
    from app.models import StockIndicatorDaily

    code = "000001"
    df = _make_bars(code, n_days=30, trend=0.2, seed=21)
    _seed_bars(db_session, df)
    latest = df["trading_date"].iloc[-1].date()
    # 预计算行：volume_ratio=9.5 作为哨兵，live compute 不会产出此值（合成数据 ~1.0）
    db_session.add(StockIndicatorDaily(
        stock_code=code, trading_date=latest,
        compute_version="bars.v2.indicators.v1", data_hash="regress", bar_count=30,
        volume_ratio=9.5, rsi14=13.5, close_vs_ma20=2.0,
    ))
    db_session.add(IndividualStockSnapshot(
        trading_date=latest, captured_at=datetime(2026, 5, 14, 15, 0, 0),
        stock_code=code, stock_name="测试",
        latest_price=10.0, change_percent=1.0, net_amount=200_000_000.0,
    ))
    db_session.commit()

    daily_bars = DailyBarsService(gateway=None, now_provider=lambda: datetime(2026, 5, 14, 16, 0, 0))
    screener = ScreenerService(daily_bars_service=daily_bars)
    result = screener.run(db_session, {
        "conditions": [{"indicator": "change_pct", "op": ">=", "value": -100}],
        "universe": {"boards": ["main"]},
        "order_by": "change_pct",
        "order": "desc",
        "limit": 10,
    })
    assert result["total"] >= 1
    # 哨兵值穿透到结果 -> 预计算覆盖路径完整执行（循环体跑了 + map 覆盖生效）
    assert result["results"][0]["volume_ratio"] == 9.5


def test_realtime_lookup_callable_does_not_raise(db_session) -> None:
    """修 _realtime_lookup 用 callable() 后，传 callable 不再 TypeError。"""
    df = _make_bars("000001", n_days=30, trend=0.0, seed=42)
    _seed_bars(db_session, df)
    db_session.add(IndividualStockSnapshot(
        trading_date=df["trading_date"].iloc[-1].date(),
        captured_at=datetime(2026, 5, 14, 15, 0, 0),
        stock_code="000001", stock_name="测试",
        latest_price=10.0, change_percent=1.0, net_amount=200_000_000.0,
    ))
    db_session.commit()

    daily_bars = DailyBarsService(gateway=None, now_provider=lambda: datetime(2026, 5, 14, 16, 0, 0))
    screener = ScreenerService(daily_bars_service=daily_bars)

    def my_lookup(codes):
        return pd.DataFrame({"stock_code": codes, "pe_dynamic": [12.5] * len(codes)})

    # 传 callable 不抛异常（旧 isinstance(x, Callable) 会 TypeError）
    result = screener.run(db_session, {
        "conditions": [{"indicator": "change_pct", "op": ">=", "value": -100}],
        "universe": {"boards": ["main"]},
        "order_by": "change_pct",
        "order": "desc",
        "limit": 10,
        "_realtime_lookup": my_lookup,
    })
    assert result["total"] >= 1


# ---------------- daily_basic 基础组（PE/PB/市值/换手率） ----------------


def test_load_daily_basic_fallback_to_recent(db_session) -> None:
    """当日 daily_basic 未发布时，_load_daily_basic 回退到 <= td 的最近一日。"""
    from app.models import StockDailyBasic
    from app.services.screener import _load_daily_basic

    code = "000001"
    # 只种 0722，不种 0723
    db_session.add(StockDailyBasic(
        stock_code=code, trading_date=date(2026, 7, 22),
        pe_ttm=4.95, pb=0.46, total_mv=2.13e11, circ_mv=2.13e11, turnover_rate=0.53,
    ))
    db_session.commit()
    df = _load_daily_basic(db_session, [code], date(2026, 7, 23))
    assert not df.empty
    row = df.iloc[0]
    assert row["pe_dynamic"] == 4.95  # pe_ttm -> pe_dynamic
    assert row["float_mv"] == 2.13e11  # circ_mv -> float_mv
    assert row["turnover_rate"] == 0.53


def test_run_surfaces_pe_mv_close_from_daily_basic(db_session) -> None:
    """screener.run 结果含 close(=latest_price)/pe/总市值，turnover 缺失时由 daily_basic 补。"""
    from app.models import StockDailyBasic, StockRealtimeEod

    code = "000001"
    df_bars = _make_bars(code, n_days=30, trend=0.2, seed=33)
    _seed_bars(db_session, df_bars)
    latest = df_bars["trading_date"].iloc[-1].date()
    db_session.add(StockRealtimeEod(
        stock_code=code, stock_name="平安银行", trading_date=latest,
        close=11.09, change_pct=1.29, turnover_rate=None,  # realtime_eod 换手率缺失
    ))
    db_session.add(StockDailyBasic(
        stock_code=code, trading_date=latest,
        pe_ttm=4.95, pb=0.46, total_mv=2.13e11, circ_mv=2.13e11, turnover_rate=0.53,
    ))
    db_session.add(IndividualStockSnapshot(
        trading_date=latest, captured_at=datetime(2026, 5, 14, 15, 0, 0),
        stock_code=code, stock_name="平安银行",
        latest_price=11.0, change_percent=1.0, net_amount=200_000_000.0,
    ))
    db_session.commit()

    daily_bars = DailyBarsService(gateway=None, now_provider=lambda: datetime(2026, 5, 14, 16, 0, 0))
    screener = ScreenerService(daily_bars_service=daily_bars)
    result = screener.run(db_session, {
        "conditions": [{"indicator": "change_pct", "op": ">=", "value": -100}],
        "universe": {"boards": ["main"]},
        "limit": 10,
    })
    assert result["total"] >= 1
    r = result["results"][0]
    assert r["close"] == 11.09  # 现价 = latest_price（realtime_eod.close）
    assert r["pe_dynamic"] == 4.95  # 来自 daily_basic
    assert r["total_mv"] == 2.13e11
    assert r["turnover_rate"] == 2.95  # bars 有今日值，优先于 daily_basic（仅补缺）


def test_run_fills_turnover_from_daily_basic_when_bars_missing(db_session) -> None:
    """bars.turnover_rate 缺失时，daily_basic.turnover_rate 补位。"""
    from app.models import StockDailyBar, StockDailyBasic, StockRealtimeEod

    code = "000002"
    df_bars = _make_bars(code, n_days=30, trend=0.2, seed=34)
    _seed_bars(db_session, df_bars)
    latest = df_bars["trading_date"].iloc[-1].date()
    # 把最新 bar 的换手率置空（模拟 daily 接口无换手率、_backfill_turnover 未跑）
    db_session.query(StockDailyBar).filter_by(stock_code=code, trading_date=latest).update({"turnover_rate": None})
    db_session.add(StockRealtimeEod(
        stock_code=code, stock_name="万科A", trading_date=latest,
        close=10.0, change_pct=1.0, turnover_rate=None,
    ))
    db_session.add(StockDailyBasic(
        stock_code=code, trading_date=latest,
        pe_ttm=8.0, pb=0.9, total_mv=1.2e11, circ_mv=1.2e11, turnover_rate=3.14,
    ))
    db_session.add(IndividualStockSnapshot(
        trading_date=latest, captured_at=datetime(2026, 5, 14, 15, 0, 0),
        stock_code=code, stock_name="万科A",
        latest_price=10.0, change_percent=1.0, net_amount=200_000_000.0,
    ))
    db_session.commit()

    daily_bars = DailyBarsService(gateway=None, now_provider=lambda: datetime(2026, 5, 14, 16, 0, 0))
    screener = ScreenerService(daily_bars_service=daily_bars)
    result = screener.run(db_session, {
        "conditions": [{"indicator": "change_pct", "op": ">=", "value": -100}],
        "universe": {"boards": ["main"]},
        "limit": 10,
    })
    r = result["results"][0]
    assert r["turnover_rate"] == 3.14  # bars 缺失 -> daily_basic 补


def test_stock_detail_basics_from_daily_basic(db_session) -> None:
    """stock_detail 的 pe/pb/mv 取 stock_daily_basic（realtime_eod 这几列 NULL）。"""
    from app.models import StockDailyBasic, StockRealtimeEod

    code = "600519"
    _seed_bars(db_session, _make_bars(code, n_days=10, start=date(2026, 7, 1), seed=5))
    db_session.add(StockRealtimeEod(
        stock_code=code, stock_name="贵州茅台", trading_date=date(2026, 7, 10),
        close=1298.44, change_pct=-0.31,  # realtime_eod 不再提供 pe/pb/mv
    ))
    db_session.add(StockDailyBasic(
        stock_code=code, trading_date=date(2026, 7, 10),
        pe_ttm=19.72, pb=6.02, total_mv=1.63e12, circ_mv=1.63e12, turnover_rate=0.52,
    ))
    db_session.commit()

    screener = ScreenerService()
    detail = screener.stock_detail(db_session, code)
    b = detail["basics"]
    assert b["latest_price"] == 1298.44  # 取 realtime_eod 今日
    assert b["pe_dynamic"] == 19.72  # 取 daily_basic
    assert b["pb"] == 6.02
    assert b["total_mv"] == 1.63e12
    assert b["float_mv"] == 1.63e12
    assert b["turnover_rate"] == 0.52


def test_refresh_daily_basic_upserts(db_session) -> None:
    """refresh_daily_basic 拉 daily_basic 入库 stock_daily_basic + 回填 bars.turnover_rate。"""
    from app.models import StockDailyBar, StockDailyBasic

    code = "000001"
    td = date(2026, 7, 23)
    # 预置一条当日 bar（turnover_rate 待回填）
    db_session.add(StockDailyBar(
        stock_code=code, trading_date=td, open=11.0, close=11.09, high=11.2, low=10.9,
        volume=1e7, amount=1e8, change_pct=1.29, turnover_rate=None,
    ))
    db_session.commit()

    # mock tushare gateway：返回单只 daily_basic
    basic_df = pd.DataFrame([{
        "code": code, "close": 11.09, "turnover_rate": 0.53, "turnover_rate_f": 0.53,
        "volume_ratio": 0.63, "pe": 5.0, "pe_ttm": 4.95, "pb": 0.46,
        "ps": 1.2, "ps_ttm": 1.1, "dv_ratio": 2.0, "dv_ttm": 2.1,
        "total_mv": 2.13e11, "circ_mv": 2.13e11,
        "total_share": 1.9e10, "float_share": 1.9e10, "free_share": 1.9e10,
    }])

    class _Gw:
        def fetch_daily_basic_by_date(self, trade_date):
            return basic_df

    daily_bars = DailyBarsService(gateway=None, tushare_gateway=_Gw())
    n = daily_bars.refresh_daily_basic(db_session, td)
    assert n == 1
    row = db_session.query(StockDailyBasic).filter_by(stock_code=code, trading_date=td).one()
    assert row.pe_ttm == 4.95
    assert row.total_mv == 2.13e11
    # bars.turnover_rate 被回填
    bar = db_session.query(StockDailyBar).filter_by(stock_code=code, trading_date=td).one()
    assert bar.turnover_rate == 0.53


def test_main_net_inflow_3d_computed(db_session) -> None:
    """compute_features 算出 3日主力净流入 = 近3日 main_net_amount 之和。"""
    code = "000001"
    df_bars = _make_bars(code, n_days=20, trend=0.1, seed=7)
    _seed_bars(db_session, df_bars)
    latest = df_bars["trading_date"].iloc[-1].date()
    # 近3日资金流：100, 200, 300 -> 3d 合计 600
    _seed_flow(db_session, code, [latest - timedelta(days=i) for i in range(2, -1, -1)], [100.0, 200.0, 300.0])
    db_session.commit()

    from app.services.screener import compute_features
    from sqlalchemy import select
    from app.models import StockFundFlowDaily
    flows = list(db_session.execute(
        select(StockFundFlowDaily).where(StockFundFlowDaily.stock_code == code)
    ).scalars())
    flow_df = pd.DataFrame([{
        "stock_code": f.stock_code, "trading_date": f.trading_date,
        "main_net_amount": f.main_net_amount, "main_net_ratio": f.main_net_ratio,
        "super_large_net": f.super_large_net,
    } for f in flows])
    frame = compute_features(df_bars, flow_df, latest)
    row = frame[frame["stock_code"] == code].iloc[0]
    assert row["main_net_inflow_3d"] == 600.0
    assert row["main_net_inflow"] == 300.0  # 当日
