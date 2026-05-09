from datetime import datetime, timedelta

import pandas as pd

from app.akshare_client import AkshareGateway


def test_resolve_concept_symbol_supports_fuzzy_board_name_match() -> None:
    gateway = AkshareGateway()
    gateway._concept_board_index = pd.DataFrame(
        [
            {"板块名称": "国资云概念", "板块代码": "BK1008"},
            {"板块名称": "机器人执行器", "板块代码": "BK1145"},
        ]
    )

    assert gateway._resolve_concept_symbol("国资云") == "BK1008"


def test_resolve_industry_symbol_supports_alias_name_match() -> None:
    gateway = AkshareGateway()
    gateway._industry_board_index = pd.DataFrame(
        [
            {"板块名称": "铁路公路", "板块代码": "BK0421"},
            {"板块名称": "航空机场", "板块代码": "BK1484"},
        ]
    )

    assert gateway._resolve_industry_symbol("公路铁路运输") == "铁路公路"


def test_fetch_individual_realtime_uses_last_cache_when_fetch_failed() -> None:
    class StubGateway(AkshareGateway):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def _run(self, fetcher, timeout_seconds: int = 25):  # type: ignore[override]
            self.calls += 1
            return pd.DataFrame()

    gateway = StubGateway()
    gateway._last_individual_realtime = pd.DataFrame(
        [
            {"股票代码": "000001", "股票简称": "示例股", "净额": "1.00亿"},
        ]
    )
    gateway._last_individual_fetch_at = datetime.now() - timedelta(minutes=1)

    result = gateway.fetch_individual_realtime()

    assert gateway.calls == 2
    assert len(result) == 1
    assert str(result.iloc[0]["股票代码"]) == "000001"


def test_fetch_sector_catalog_merges_em_and_ths_concepts() -> None:
    gateway = AkshareGateway()
    gateway._concept_board_index = pd.DataFrame(
        [
            {"板块名称": "国资云概念", "板块代码": "BK1008"},
            {"板块名称": "商业航天", "板块代码": "BK0963"},
        ]
    )
    gateway._concept_board_index_ths = pd.DataFrame(
        [
            {"name": "商业航天", "code": "309130"},
            {"name": "中船系", "code": "301713"},
        ]
    )

    catalog = gateway.fetch_sector_catalog("concept")

    assert "商业航天" in catalog
    assert "中船系" in catalog
    assert "国资云概念" in catalog


def test_fetch_sector_stocks_uses_ths_fallback_for_missing_concept_members() -> None:
    class StubGateway(AkshareGateway):
        def _run(self, fetcher, timeout_seconds: int = 25):  # type: ignore[override]
            return pd.DataFrame()

        def _fetch_concept_members_ths(self, sector_name: str) -> pd.DataFrame:  # type: ignore[override]
            return pd.DataFrame(
                [
                    {"代码": "000001", "名称": "平安银行", "最新价": 12.3, "涨跌幅": "1.20%"},
                    {"代码": "000002", "名称": "万科A", "最新价": 9.1, "涨跌幅": "0.80%"},
                ]
            )

        def fetch_individual_realtime(self) -> pd.DataFrame:  # type: ignore[override]
            return pd.DataFrame(
                [
                    {"股票代码": "000001", "股票简称": "平安银行", "最新价": 12.5, "涨跌幅": "1.35%", "净额": "1.00亿"},
                ]
            )

    gateway = StubGateway()
    gateway._concept_board_index = pd.DataFrame(
        [
            {"板块名称": "商业航天", "板块代码": "BK0963"},
        ]
    )

    result = gateway.fetch_sector_stocks("concept", "成飞概念")

    assert len(result) == 2
    assert set(result.columns.tolist()) == {"代码", "名称", "最新价", "今天涨跌幅", "今日主力净流入-净额"}