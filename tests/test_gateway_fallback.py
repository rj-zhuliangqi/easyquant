from __future__ import annotations

import pandas as pd

from app.akshare_client import AkshareGateway


class _FakeResponse:
    def __init__(self, text: str = "", payload: dict | None = None) -> None:
        self.text = text
        self._payload = payload or {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_market_index_spot_uses_tencent_primary_format(monkeypatch) -> None:
    gateway = AkshareGateway()
    monkeypatch.setattr(gateway, "_run", lambda fetcher, timeout_seconds=25: pd.DataFrame())

    quote_text = "\n".join(
        [
            'v_s_sh000001="1~涓婅瘉鎸囨暟~000001~4132.46~0.93~0.02~390629502~80974729~~688038.86~ZS~";',
            'v_s_sz399001="51~娣辫瘉鎴愭寚~399001~15408.72~-121.51~-0.78~460716161~100290040~~494514.37~ZS~";',
        ]
    )
    monkeypatch.setattr(gateway, "_request_get", lambda url, **kwargs: _FakeResponse(text=quote_text))

    frame = gateway.fetch_market_index_spot()

    assert list(frame["symbol"]) == ["sh000001", "sz399001"]
    assert frame.loc[0, "name"] == "涓婅瘉鎸囨暟"
    assert float(frame.loc[0, "price"]) == 4132.46
    assert float(frame.loc[0, "change_amount"]) == 0.93
    assert float(frame.loc[0, "change_percent"]) == 0.02


def test_market_index_history_falls_back_to_tencent_when_akshare_is_empty(monkeypatch) -> None:
    gateway = AkshareGateway()
    monkeypatch.setattr(gateway, "_run", lambda fetcher, timeout_seconds=25: pd.DataFrame())

    payload = {
        "data": {
            "sh000001": {
                "day": [
                    ["2026-05-09", "3201.00", "3205.00", "3208.00", "3198.00", "100000000"],
                    ["2026-05-12", "3204.00", "3209.00", "3210.00", "3201.00", "120000000"],
                    ["2026-05-13", "3209.00", "3212.00", "3214.00", "3207.00", "132000000"],
                ]
            }
        }
    }
    monkeypatch.setattr(gateway, "_request_get", lambda url, **kwargs: _FakeResponse(payload=payload))

    frame = gateway.fetch_market_index_history("sh000001", days=20)

    assert list(frame.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert frame.iloc[-1]["date"] == "2026-05-13"
    assert float(frame.iloc[-1]["close"]) == 3212.0
    assert float(frame.iloc[-1]["volume"]) == 132000000.0


def test_stock_daily_history_falls_back_to_eastmoney_when_akshare_is_empty(monkeypatch) -> None:
    gateway = AkshareGateway()
    monkeypatch.setattr(gateway, "_run", lambda fetcher, timeout_seconds=25: pd.DataFrame())

    payload = {
        "data": {
            "klines": [
                "2026-05-12,10.01,10.20,10.35,9.98,120000,560000000,3.50,1.90,0.19,8.80",
                "2026-05-13,10.20,10.55,10.66,10.18,160000,730000000,4.20,3.43,0.35,10.20",
            ]
        }
    }
    monkeypatch.setattr(gateway, "_request_get", lambda url, **kwargs: _FakeResponse(payload=payload))

    frame = gateway.fetch_stock_daily_history("002111", "20260501", "20260514")

    assert frame.iloc[-1].iloc[0] == "2026-05-13"
    assert float(frame.iloc[-1].iloc[6]) == 730000000.0
    assert float(frame.iloc[-1].iloc[10]) == 10.2
