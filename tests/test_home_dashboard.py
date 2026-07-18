"""Home 行动优先级字段完整性测试（P4-4 补强）。

build_action_priority 必须返回 source / updated_at / link 三个字段，
前端 HomeView.vue 模板绑了它们；缺一不可。
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.time_utils import now_cn


class _StubSectorDashboard:
    def get_latest_rankings(self, *a, **kw):
        return {"leaders": []}


class _StubMarketTemperature:
    band = "正常"

    def get_temperature(self, target_date, market_scope="all"):
        return {"temperature_band": self.band, "summary_text": "测试摘要"}


class _StubLimitUp:
    """MarketSignalService 构造所需的 limit_up stub，build_action_priority 不会触发它。"""


class _StubRealtimeCache:
    """MarketSignalService 构造所需的 realtime_cache stub。"""


def _make_sig(band: str = "正常") -> "MarketSignalService":
    from app.services.market_signal import MarketSignalService

    temp = _StubMarketTemperature()
    temp.band = band
    return MarketSignalService(
        dashboard=_StubSectorDashboard(),
        limit_up=_StubLimitUp(),
        market_temperature=temp,
        realtime_cache=_StubRealtimeCache(),
        now_provider=now_cn,
    )


def test_action_priority_contains_source_updated_at_link() -> None:
    sig = _make_sig("正常")
    payload = sig.build_action_priority(session=None, trading_date=date(2026, 7, 19))

    # 三个前端模板字段必须齐
    assert payload.get("source"), f"action_priority.source 缺失：{payload!r}"
    assert payload.get("updated_at"), f"action_priority.updated_at 缺失：{payload!r}"
    assert payload.get("link"), f"action_priority.link 缺失：{payload!r}"
    # updated_at 形如 ISO 字符串
    iso = payload["updated_at"]
    parsed = datetime.fromisoformat(iso)
    assert parsed.tzinfo is not None, "updated_at 应带 tz 信息（now_cn() = Asia/Shanghai）"
    assert payload["link"].startswith("/"), f"link 应为站内路由：{payload['link']!r}"


def test_action_priority_band_changes_source_and_link() -> None:
    # 高温分支
    sig_hi = _make_sig("过热")
    p_hi = sig_hi.build_action_priority(session=None, trading_date=date(2026, 7, 19))
    assert p_hi["source"] == "市场温度"
    assert p_hi["link"] == "/limit-up-ladder"

    # 正常分支
    sig_lo = _make_sig("正常")
    p_lo = sig_lo.build_action_priority(session=None, trading_date=date(2026, 7, 19))
    assert p_lo["source"] == "板块强弱"
    assert p_lo["link"] == "/sector-monitor"
