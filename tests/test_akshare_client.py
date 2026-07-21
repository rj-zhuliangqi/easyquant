from datetime import datetime, timedelta

import pandas as pd

from app.akshare_client import AkshareGateway, INDIVIDUAL_COLUMNS, INDIVIDUAL_EXTENDED_COLUMNS
from app.time_utils import now_cn


def test_fetch_individual_realtime_uses_last_cache_when_fetch_failed() -> None:
    class StubGateway(AkshareGateway):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def _run(self, fetcher, timeout_seconds: int = 25):  # type: ignore[override]
            self.calls += 1
            return pd.DataFrame()

    gateway = StubGateway()
    gateway._fetch_individual_realtime_eastmoney = lambda: pd.DataFrame()  # type: ignore[method-assign]
    gateway._last_individual_realtime = pd.DataFrame(
        [
            {
                INDIVIDUAL_COLUMNS[0]: "000001",
                INDIVIDUAL_COLUMNS[1]: "Sample",
                INDIVIDUAL_COLUMNS[4]: "100000000.0",
            },
        ]
    )
    gateway._last_individual_fetch_at = now_cn() - timedelta(minutes=1)

    result = gateway.fetch_individual_realtime()

    assert gateway.calls == 2
    assert len(result) == 1
    assert str(result.iloc[0][INDIVIDUAL_COLUMNS[0]]) == "000001"
    assert gateway.get_source_snapshot("individual_realtime")["source_label"] == "cache"


def test_fetch_individual_realtime_uses_eastmoney_as_primary_source(monkeypatch) -> None:
    gateway = AkshareGateway()
    payload = {
        "data": {
            "diff": [
                {"f12": "600900", "f14": "CGN Power", "f2": 27.3, "f3": 1.52, "f62": 1241000000.0},
                {"f12": "300058", "f14": "BlueFocus", "f2": 18.52, "f3": 3.46, "f62": 920000000.0},
            ]
        }
    }
    monkeypatch.setattr(gateway, "_request_get", lambda url, **kwargs: type("R", (), {"json": lambda self: payload})())

    frame = gateway.fetch_individual_realtime()
    source = gateway.get_source_snapshot("individual_realtime")

    assert len(frame) == 2
    assert str(frame.iloc[0][INDIVIDUAL_COLUMNS[0]]) == "600900"
    assert float(frame.iloc[0][INDIVIDUAL_COLUMNS[4]]) == 1241000000.0
    assert source["source_label"] == "eastmoney"
    assert source["fallback_used"] is False


def test_fetch_individual_realtime_paginates_eastmoney_results(monkeypatch) -> None:
    gateway = AkshareGateway()

    class Response:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_request(url, **kwargs):
        params = kwargs.get("params") or {}
        pn = int(params.get("pn", 1))
        pz = int(params.get("pz", 100))
        total = 230
        start = (pn - 1) * pz
        end = min(start + pz, total)
        diff = [
            {
                "f12": f"{600000 + index}",
                "f14": f"Stock{index}",
                "f2": 10.0 + index,
                "f3": 1.0,
                "f62": 1000000.0 + index,
            }
            for index in range(start, end)
        ]
        return Response({"data": {"total": total, "diff": diff}})

    monkeypatch.setattr(gateway, "_request_get", fake_request)

    frame = gateway.fetch_individual_realtime()

    assert len(frame) == 230
    assert str(frame.iloc[-1][INDIVIDUAL_COLUMNS[0]]) == str(600000 + 229)


def test_fetch_market_breadth_uses_eastmoney_as_primary_source(monkeypatch) -> None:
    gateway = AkshareGateway()
    
    class Response:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_request(url, **kwargs):
        params = kwargs.get("params") or {}
        pn = int(params.get("pn", 1))
        pz = int(params.get("pz", 100))
        total = 2400
        start = (pn - 1) * pz
        end = min(start + pz, total)
        diff = []
        for index in range(start, end):
            mod = index % 4
            if mod == 0:
                change = 1.2
            elif mod == 1:
                change = 19.98
            elif mod == 2:
                change = -9.99
            else:
                change = 0.0
            diff.append({"f12": f"{600000 + index}", "f14": f"Stock{index}", "f2": 10.0, "f3": change, "f6": 1000000.0})
        return Response({"data": {"total": total, "diff": diff}})

    monkeypatch.setattr(gateway, "_request_get", fake_request)

    frame = gateway.fetch_market_breadth()
    source = gateway.get_source_snapshot("market_breadth")
    records = frame.to_dict(orient="records")

    assert [item["value"] for item in records[:5]] == [1200.0, 600.0, 600.0, 600.0, 600.0]
    assert source["source_label"] == "eastmoney"
    assert source["fallback_used"] is False


def test_fetch_market_breadth_falls_back_to_cached_snapshot_when_partial(monkeypatch) -> None:
    gateway = AkshareGateway()
    gateway._last_market_breadth = pd.DataFrame(
        [
            {"item": "up_count", "value": 2000.0},
            {"item": "down_count", "value": 1800.0},
            {"item": "flat_count", "value": 300.0},
            {"item": "limit_up_count", "value": 80.0},
            {"item": "limit_down_count", "value": 12.0},
            {"item": "market_activity", "value": "48.78%"},
            {"item": "updated_at", "value": "2026-05-19 14:00:00"},
        ]
    )
    gateway._last_market_breadth_fetch_at = now_cn()

    class Response:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_request(url, **kwargs):
        params = kwargs.get("params") or {}
        pn = int(params.get("pn", 1))
        if pn == 1:
            diff = [
                {"f12": f"{600000 + index}", "f14": f"Stock{index}", "f2": 10.0, "f3": 1.0, "f6": 1000000.0}
                for index in range(100)
            ]
        else:
            diff = []
        return Response({"data": {"total": 5529, "diff": diff}})

    monkeypatch.setattr(gateway, "_request_get", fake_request)
    monkeypatch.setattr(gateway, "_run", lambda fetcher, timeout_seconds=25: pd.DataFrame())

    frame = gateway.fetch_market_breadth()
    source = gateway.get_source_snapshot("market_breadth")

    assert frame.to_dict(orient="records")[0]["value"] == 2000.0
    assert source["source_label"] == "cache"
    assert source["fallback_used"] is True


def test_fetch_market_breadth_falls_back_to_akshare_spot_snapshot(monkeypatch) -> None:
    gateway = AkshareGateway()

    class Response:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_request(url, **kwargs):
        params = kwargs.get("params") or {}
        pn = int(params.get("pn", 1))
        diff = [{"f12": "600000", "f14": "OnlyOne", "f2": 10.0, "f3": 1.0, "f6": 1000000.0}] if pn == 1 else []
        return Response({"data": {"total": 5529, "diff": diff}})

    spot_rows = []
    for index in range(120):
        mod = index % 4
        if mod == 0:
            change = 1.2
        elif mod == 1:
            change = 19.98
        elif mod == 2:
            change = -9.99
        else:
            change = 0.0
        spot_rows.append(
            {"code": f"{600000 + index}", "name": f"Spot{index}", "change_percent": change, "turnover": 1000000.0 + index}
        )
    spot_frame = pd.DataFrame(spot_rows)

    monkeypatch.setattr(gateway, "_request_get", fake_request)
    monkeypatch.setattr(gateway, "_run", lambda fetcher, timeout_seconds=25: spot_frame.copy())

    frame = gateway.fetch_market_breadth()
    source = gateway.get_source_snapshot("market_breadth")
    records = frame.to_dict(orient="records")

    assert [item["value"] for item in records[:5]] == [60.0, 30.0, 30.0, 30.0, 30.0]
    assert source["source_label"] == "akshare"
    assert source["fallback_used"] is True


def test_fetch_stock_daily_history_forwards_adjust_qfq(monkeypatch) -> None:
    """向 akshare 透传 adjust="qfq"，并在 source snapshot 记录以供回归。"""
    gateway = AkshareGateway()

    def fake_run(fetcher, timeout_seconds: int = 25):
        # 直接执行 fetcher，借此触发 ak.stock_zh_a_hist stub；不真正联网。
        return pd.DataFrame([{"日期": "2026-05-01", "收盘": 10.0, "开盘": 9.0}])

    monkeypatch.setattr(gateway, "_run", fake_run)
    monkeypatch.setattr(gateway, "_fetch_stock_daily_history_eastmoney", lambda **_: pd.DataFrame())

    frame = gateway.fetch_stock_daily_history("600000", "20260401", "20260515", adjust="qfq")
    assert not frame.empty
    snap = gateway.get_source_snapshot("stock_daily_history:600000")
    assert snap["meta"]["adjust"] == "qfq"


def test_fetch_stock_daily_history_default_adjust_empty_for_backward_compat(monkeypatch) -> None:
    """P5-1d: limit_up 等老调用方不传 adjust，应保持 "" 旧口径。"""
    gateway = AkshareGateway()
    called = {"yes": False}

    def fake_run(fetcher, timeout_seconds: int = 25):
        called["yes"] = True
        return pd.DataFrame([{"日期": "2026-05-01", "收盘": 10.0, "开盘": 9.0}])

    monkeypatch.setattr(gateway, "_run", fake_run)
    monkeypatch.setattr(gateway, "_fetch_stock_daily_history_eastmoney", lambda **_: pd.DataFrame())

    gateway.fetch_stock_daily_history("002111", "20260501", "20260514")
    assert called["yes"] is True
    snap = gateway.get_source_snapshot("stock_daily_history:002111")
    assert snap["meta"]["adjust"] == ""


def test_fetch_individual_realtime_extends_columns_with_turnover_pe_pbmv(monkeypatch) -> None:
    """q3: clist 扩展字段后,新增列加入结果（不影响原 INDIVIDUAL_COLUMNS 兼容）。"""
    gateway = AkshareGateway()
    payload = {
        "data": {
            "diff": [
                {
                    "f12": "600900", "f14": "CGN Power",
                    "f2": 27.3, "f3": 1.52, "f62": 1241000000.0,
                    "f8": 1.23, "f9": 12.5, "f23": 1.4, "f20": 1.23e11, "f21": 1.0e11,
                },
            ]
        }
    }
    monkeypatch.setattr(
        gateway,
        "_request_get",
        lambda url, **kwargs: type("R", (), {"json": lambda self: payload})(),
    )

    frame = gateway.fetch_individual_realtime()

    # 扩展列存在
    assert "换手率" in frame.columns
    assert "市盈率动" in frame.columns
    assert "市净率" in frame.columns
    assert "总市值" in frame.columns
    assert "流通市值" in frame.columns
    assert list(frame.columns) == INDIVIDUAL_EXTENDED_COLUMNS
    assert float(frame.iloc[0]["换手率"]) == 1.23
    assert float(frame.iloc[0]["市盈率动"]) == 12.5
    # 老基础列值仍正确（兼容）
    assert str(frame.iloc[0][INDIVIDUAL_COLUMNS[0]]) == "600900"


def test_fetch_individual_realtime_extended_columns_missing_handled(monkeypatch) -> None:
    """字段缺失时仅扩展列为 None，基础列不受影响。"""
    gateway = AkshareGateway()
    payload = {
        "data": {
            "diff": [
                {"f12": "600900", "f14": "CGN", "f2": 27.3, "f3": 1.52, "f62": 1241000000.0},
            ]
        }
    }
    monkeypatch.setattr(
        gateway,
        "_request_get",
        lambda url, **kwargs: type("R", (), {"json": lambda self: payload})(),
    )

    frame = gateway.fetch_individual_realtime()
    assert len(frame) == 1
    assert frame.iloc[0]["换手率"] is None
    assert frame.iloc[0]["市盈率动"] is None
    assert float(frame.iloc[0][INDIVIDUAL_COLUMNS[2]]) == 27.3
