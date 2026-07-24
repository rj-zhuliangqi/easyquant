#!/usr/bin/env python3
"""Extract key data from prefetch file."""
import json

with open("/tmp/easyquant_market_data_2026-06-30.json") as f:
    d = json.load(f)

# Top sectors (industry)
industry = d["sector_rankings"]["industry"]
print(f"=== TOP 15 SECTORS (industry) ===")
top = sorted(industry, key=lambda x: x.get("行业-涨跌幅", 0), reverse=True)[:15]
for i, s in enumerate(top, 1):
    print(f"{i}. {s['行业']}: {s['行业-涨跌幅']:+.2f}% 净额={s['净额']:+.2f}亿 领涨={s['领涨股']}({s['领涨股-涨跌幅']:+.2f}%) 家数={s['公司家数']}")

print(f"\n=== BOTTOM 10 SECTORS (industry) ===")
bot = sorted(industry, key=lambda x: x.get("行业-涨跌幅", 0))[:10]
for i, s in enumerate(bot, 1):
    print(f"{i}. {s['行业']}: {s['行业-涨跌幅']:+.2f}% 净额={s['净额']:+.2f}亿 领涨={s['领涨股']}({s['领涨股-涨跌幅']:+.2f}%) 家数={s['公司家数']}")

# Individual rankings
print(f"\n=== INDIVIDUAL RANKINGS ===")
ind = d["individual_rankings"]["individual"]
print("Top-level keys:", list(ind.keys())[:20] if isinstance(ind, dict) else f"len={len(ind)}")
if isinstance(ind, dict):
    for k, v in ind.items():
        if isinstance(v, list):
            print(f"  {k}: list len={len(v)}")
            if v:
                print(f"    first: {v[0]}")

# Limit-up pool
print(f"\n=== LIMIT-UP POOL ===")
lu = d["limit_up_pool"]["limit_up_pool"]
if isinstance(lu, dict):
    for k, v in lu.items():
        if isinstance(v, list):
            print(f"  {k}: list len={len(v)}")
            if v:
                print(f"    first: {v[0]}")
elif isinstance(lu, list):
    print(f"len={len(lu)}")
    if lu:
        print(f"first: {lu[0]}")