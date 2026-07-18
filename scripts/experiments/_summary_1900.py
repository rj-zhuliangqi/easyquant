import json
with open('/tmp/easyquant_market_data_2026-06-24.json') as f:
    d = json.load(f)

sectors = d['sector_rankings']['industry']
print(f'Total sectors: {len(sectors)}')
print('=== Top 15 Sectors ===')
for s in sectors[:15]:
    print(f"  {s['序号']}. {s['行业']}: {s['行业-涨跌幅']}% 净额={s['净额']}亿 领涨={s['领涨股']}({s['领涨股-涨跌幅']}%)")

print()
print('=== Bottom 10 Sectors ===')
for s in sectors[-10:]:
    print(f"  {s['序号']}. {s['行业']}: {s['行业-涨跌幅']}% 净额={s['净额']}亿 领涨={s['领涨股']}({s['领涨股-涨跌幅']}%)")

print()
print('=== Limit Up Pool ===')
lp = d['limit_up_pool']['limit_up_pool']
print(f'Type: {type(lp)}, count: {len(lp) if hasattr(lp, "__len__") else "?"}')
if isinstance(lp, list) and lp:
    print('First item keys:', list(lp[0].keys()))
    for item in lp[:20]:
        print(f"  {item}")

print()
print('=== Individual rankings ===')
ind = d['individual_rankings']['individual']
print(f'count: {len(ind) if hasattr(ind, "__len__") else "?"}')
if isinstance(ind, list) and ind:
    print('First item keys:', list(ind[0].keys()) if isinstance(ind[0], dict) else ind[0])
    for item in ind[:10]:
        print(f"  {item}")
