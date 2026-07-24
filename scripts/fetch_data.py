#!/usr/bin/env python3
"""多数据源市场数据预取脚本

为选股 Skill 提供统一的结构化市场数据。
数据源优先级：本地API → 东方财富 → 腾讯财经 → 新浪财经 → AKShare

用法:
    python scripts/fetch_data.py --date 2026-06-07 --output /tmp/easyquant_market_data.json
    python scripts/fetch_data.py --date 2026-06-07 --types sectors,individual,limit-up
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
LOCAL_API_BASE = "http://127.0.0.1:8010"
REQUEST_TIMEOUT = 15  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_get_json(url: str, label: str) -> tuple[dict | None, bool]:
    """GET url, return (json_dict, success). Never raises."""
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        print(f"  [{_ts()}] ✓ {label}")
        return resp.json(), True
    except Exception as exc:
        print(f"  [{_ts()}] ✗ {label}: {exc}")
        return None, False


def _fetch_local_api(path: str, label: str) -> tuple[dict | None, bool]:
    """Fetch from local EasyQuant API."""
    return _safe_get_json(f"{LOCAL_API_BASE}{path}", f"local:{label}")


# ---------------------------------------------------------------------------
# Data Fetchers (per data type, with multi-source fallback)
# ---------------------------------------------------------------------------

def fetch_market_indices(trading_date: str) -> tuple[dict, list[str]]:
    """大盘指数：上证、深证、创业板"""
    sources: list[str] = []

    # Source 1: 本地 API
    data, ok = _fetch_local_api("/api/limit-up/summary", "market_indices")
    if ok and data:
        sources.append("local_api")
        return data, sources

    # Source 2: 腾讯财经
    tencent_url = (
        "https://qt.gtimg.cn/q="
        "sh000001,"  # 上证
        "sz399001,"  # 深证
        "sz399006"   # 创业板
    )
    data, ok = _safe_get_json(tencent_url, "tencent:market_indices")
    if ok and data:
        sources.append("tencent")
        return data, sources

    # Source 3: 新浪财经
    sina_url = "https://hq.sinajs.cn/list=s_sh000001,s_sz399001,s_sz399006"
    data, ok = _safe_get_json(sina_url, "sina:market_indices")
    if ok and data:
        sources.append("sina")
        return data, sources

    return {}, sources


def fetch_sector_rankings(trading_date: str) -> tuple[dict, list[str]]:
    """板块资金流排名（行业+概念）"""
    sources: list[str] = []

    # Source 1: 本地 API
    data, ok = _fetch_local_api("/api/overview", "sector_rankings")
    if ok and data:
        sources.append("local_api")
        return data, sources

    # Source 2: 东方财富行业资金流
    eastmoney_url = (
        "https://push2.eastmoney.com/api/qt/clist/get"
        "?pn=1&pz=50&po=1&np=1"
        "&fltt=2&invt=2&fid=f3"
        "&fs=m:90+t:2&fields=f2,f3,f4,f12,f14"
    )
    data, ok = _safe_get_json(eastmoney_url, "eastmoney:sector_industry")
    if ok and data:
        sources.append("eastmoney")
        return data, sources

    # Source 3: AKShare
    try:
        import akshare as ak
        df = ak.stock_fund_flow_industry(symbol="即时")
        data = {"industry": df.to_dict(orient="records")}
        sources.append("akshare")
        print(f"  [{_ts()}] ✓ akshare:sector_industry")
        return data, sources
    except Exception as exc:
        print(f"  [{_ts()}] ✗ akshare:sector_industry: {exc}")

    return {}, sources


def fetch_individual_rankings(trading_date: str) -> tuple[dict, list[str]]:
    """个股资金流排名"""
    sources: list[str] = []

    # Source 1: 本地 API
    data, ok = _fetch_local_api("/api/individual-rankings", "individual_rankings")
    if ok and data:
        sources.append("local_api")
        return data, sources

    # Source 2: 东方财富个股资金流
    eastmoney_url = (
        "https://push2.eastmoney.com/api/qt/clist/get"
        "?pn=1&pz=100&po=1&np=1"
        "&fltt=2&invt=2&fid=f62"
        "&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
        "&fields=f2,f3,f12,f14,f62,f184,f66,f69,f72,f75,f78,f81,f164,f174"
    )
    data, ok = _safe_get_json(eastmoney_url, "eastmoney:individual")
    if ok and data:
        sources.append("eastmoney")
        return data, sources

    # Source 3: AKShare
    try:
        import akshare as ak
        df = ak.stock_fund_flow_individual(symbol="即时")
        data = {"individual": df.to_dict(orient="records")}
        sources.append("akshare")
        print(f"  [{_ts()}] ✓ akshare:individual")
        return data, sources
    except Exception as exc:
        print(f"  [{_ts()}] ✗ akshare:individual: {exc}")

    return {}, sources


def fetch_limit_up_pool(trading_date: str) -> tuple[dict, list[str]]:
    """涨停池数据"""
    sources: list[str] = []

    # Source 1: 本地 API
    data, ok = _fetch_local_api("/api/limit-up/ladder", "limit_up_ladder")
    if ok and data:
        sources.append("local_api")
        # 也获取炸板池和温度
        broken, _ = _fetch_local_api("/api/limit-up/broken", "limit_up_broken")
        temp, _ = _fetch_local_api("/api/limit-up/temperature", "limit_up_temperature")
        if broken:
            data["broken_pool"] = broken
        if temp:
            data["temperature"] = temp
        return data, sources

    # Source 2: 东方财富
    eastmoney_url = (
        "https://push2.eastmoney.com/api/qt/clist/get"
        "?pn=1&pz=50&po=1&np=1"
        "&fltt=2&invt=2&fid=f3"
        "&fs=b:BK0815&fields=f2,f3,f12,f14,f15"
    )
    data, ok = _safe_get_json(eastmoney_url, "eastmoney:limit_up")
    if ok and data:
        sources.append("eastmoney")
        return data, sources

    # Source 3: AKShare
    try:
        import akshare as ak
        df = ak.stock_zt_pool_em(date=trading_date)
        data = {"limit_up_pool": df.to_dict(orient="records")}
        sources.append("akshare")
        print(f"  [{_ts()}] ✓ akshare:limit_up")
        return data, sources
    except Exception as exc:
        print(f"  [{_ts()}] ✗ akshare:limit_up: {exc}")

    return {}, sources


def fetch_monitor_signals(trading_date: str) -> tuple[dict, list[str]]:
    """板块信号（加速、持续性、背离等）"""
    sources: list[str] = []

    # 只有本地 API 有此数据（Dashboard 计算结果）
    data, ok = _fetch_local_api("/api/monitor-signals", "monitor_signals")
    if ok and data:
        sources.append("local_api")
        return data, sources

    return {}, sources


def fetch_opportunities(trading_date: str) -> tuple[dict, list[str]]:
    """机会池数据"""
    sources: list[str] = []

    # 只有本地 API 有此数据（MarketSignal 计算结果）
    data, ok = _fetch_local_api("/api/opportunities", "opportunities")
    if ok and data:
        sources.append("local_api")
        return data, sources

    return {}, sources


def fetch_sector_stocks(sector_name: str) -> tuple[dict, list[str]]:
    """某板块的个股列表"""
    sources: list[str] = []

    # Source 1: 本地 API
    import urllib.parse
    encoded = urllib.parse.quote(sector_name)
    data, ok = _fetch_local_api(
        f"/api/sector-stocks?sector_name={encoded}&sector_type=concept&limit=20",
        f"sector_stocks:{sector_name}",
    )
    if ok and data:
        sources.append("local_api")
        return data, sources

    # Source 2: AKShare
    try:
        import akshare as ak
        df = ak.stock_board_concept_cons_em(symbol=sector_name)
        data = {"stocks": df.to_dict(orient="records")}
        sources.append("akshare")
        print(f"  [{_ts()}] ✓ akshare:sector_stocks:{sector_name}")
        return data, sources
    except Exception as exc:
        print(f"  [{_ts()}] ✗ akshare:sector_stocks:{sector_name}: {exc}")

    return {}, sources


# ---------------------------------------------------------------------------
# Main: Assemble full data package
# ---------------------------------------------------------------------------

# All available data types and their fetchers
ALL_DATA_TYPES = {
    "market_indices": fetch_market_indices,
    "sector_rankings": fetch_sector_rankings,
    "individual_rankings": fetch_individual_rankings,
    "limit_up_pool": fetch_limit_up_pool,
    "monitor_signals": fetch_monitor_signals,
    "opportunities": fetch_opportunities,
}


def assemble_data(trading_date: str, data_types: list[str] | None = None) -> dict[str, Any]:
    """Assemble the full market data package."""
    types_to_fetch = data_types or list(ALL_DATA_TYPES.keys())
    all_sources_used: list[str] = []
    result: dict[str, Any] = {}

    for dtype in types_to_fetch:
        fetcher = ALL_DATA_TYPES.get(dtype)
        if fetcher is None:
            print(f"  [{_ts()}] ⚠ Unknown data type: {dtype}, skipping")
            continue

        print(f"\n[{_ts()}] Fetching {dtype}...")
        data, sources = fetcher(trading_date)
        result[dtype] = data
        all_sources_used.extend(sources)

    # Build metadata
    result["meta"] = {
        "date": trading_date,
        "fetched_at": datetime.now().isoformat(),
        "sources_used": sorted(set(all_sources_used)),
        "data_types_fetched": list(result.keys()),
    }

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="预取市场数据供选股 Skill 使用")
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="交易日期 (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="输出文件路径 (默认 /tmp/easyquant_market_data_{date}.json)",
    )
    parser.add_argument(
        "--types", "-t",
        default=None,
        help="要获取的数据类型，逗号分隔 (默认全部)。可选: "
             + ", ".join(ALL_DATA_TYPES.keys()),
    )

    args = parser.parse_args()
    trading_date = args.date
    output_path = args.output or f"/tmp/easyquant_market_data_{trading_date}.json"

    data_types = None
    if args.types:
        data_types = [t.strip() for t in args.types.split(",")]

    print(f"[{_ts()}] EasyQuant Market Data Fetcher")
    print(f"[{_ts()}] Trading date: {trading_date}")
    print(f"[{_ts()}] Output: {output_path}")
    if data_types:
        print(f"[{_ts()}] Types: {data_types}")

    start = time.time()
    result = assemble_data(trading_date, data_types)
    elapsed = time.time() - start

    # Write output
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    # Summary
    sources = result.get("meta", {}).get("sources_used", [])
    types_ok = sum(1 for k, v in result.items() if k != "meta" and v)
    types_total = len(result) - 1  # exclude meta

    print(f"\n[{_ts()}] ===== Summary =====")
    print(f"  Data types: {types_ok}/{types_total} fetched successfully")
    print(f"  Sources used: {', '.join(sources) if sources else 'NONE (all failed!)'}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  Output: {output_path}")
    print(f"  Size: {output_file.stat().st_size / 1024:.1f} KB")

    if types_ok == 0:
        print(f"\n  ⚠ WARNING: No data fetched! Check if the local API is running on {LOCAL_API_BASE}")
        sys.exit(1)


if __name__ == "__main__":
    main()
