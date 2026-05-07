from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Callable

import akshare as ak
import pandas as pd


class AkshareGateway:
    def fetch_industry_realtime(self) -> pd.DataFrame:
        return self._run(lambda: ak.stock_fund_flow_industry(symbol="即时"))

    def fetch_concept_realtime(self) -> pd.DataFrame:
        return self._run(lambda: ak.stock_fund_flow_concept(symbol="即时"))

    def fetch_individual_realtime(self) -> pd.DataFrame:
        return self._run(lambda: ak.stock_fund_flow_individual(symbol="即时"))

    def fetch_sector_stocks(self, sector_name: str) -> pd.DataFrame:
        return self._run(lambda: ak.stock_sector_fund_flow_summary(symbol=sector_name, indicator="今日"))

    def fetch_daily_history(self, sector_type: str, sector_name: str) -> pd.DataFrame:
        if sector_type == "industry":
            return self._run(lambda: ak.stock_sector_fund_flow_hist(symbol=sector_name))
        return self._run(lambda: ak.stock_concept_fund_flow_hist(symbol=sector_name))

    def _run(self, fetcher: Callable[[], pd.DataFrame], timeout_seconds: int = 25) -> pd.DataFrame:
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(fetcher)
                result = future.result(timeout=timeout_seconds)
                return result if isinstance(result, pd.DataFrame) else pd.DataFrame()
        except TimeoutError:
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()
