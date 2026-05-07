from datetime import datetime

import pandas as pd

from app.services.collector import FundFlowCollector


class FakeGateway:
    def fetch_industry_realtime(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "行业": "半导体",
                    "行业指数": 8123.11,
                    "行业-涨跌幅": "1.56%",
                    "流入资金": 120.5,
                    "流出资金": 88.3,
                    "净额": 32.2,
                    "公司家数": 145,
                    "领涨股": "北方华创",
                    "领涨股-涨跌幅": "4.12%",
                    "当前价": 320.55,
                }
            ]
        )

    def fetch_concept_realtime(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "概念": "AI芯片",
                    "概念指数": 3021.88,
                    "概念-涨跌幅": "-0.35%",
                    "流入资金": 25.8,
                    "流出资金": 31.2,
                    "净额": -5.4,
                    "公司家数": 18,
                    "领涨股": "寒武纪",
                    "领涨股-涨跌幅": "2.22%",
                    "当前价": 188.18,
                }
            ]
        )


def test_collect_snapshot_normalizes_and_persists_rows(db_session, sample_time: datetime) -> None:
    collector = FundFlowCollector(gateway=FakeGateway())

    result = collector.collect_snapshot(db_session, captured_at=sample_time)

    assert result["industry"] == 1
    assert result["concept"] == 1

    snapshots = collector.list_snapshots(db_session)
    assert len(snapshots) == 2

    industry_row = next(row for row in snapshots if row.sector_type == "industry")
    assert industry_row.captured_at == sample_time
    assert industry_row.sector_name == "半导体"
    assert industry_row.sector_index == 8123.11
    assert industry_row.change_percent == 1.56
    assert industry_row.inflow == 120.5
    assert industry_row.outflow == 88.3
    assert industry_row.net_amount == 32.2
    assert industry_row.leading_stock == "北方华创"
    assert industry_row.leading_stock_change == 4.12

    concept_row = next(row for row in snapshots if row.sector_type == "concept")
    assert concept_row.sector_name == "AI芯片"
    assert concept_row.change_percent == -0.35
    assert concept_row.net_amount == -5.4
