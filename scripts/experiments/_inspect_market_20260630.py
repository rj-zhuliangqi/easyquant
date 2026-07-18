"""Inspect prefetch data for the 20:00 super-short stock pick job."""
import json
import re

P = '/tmp/easyquant_market_data_2026-06-30.json'
with open(P) as f:
    d = json.load(f)

ind = d['individual_rankings']['individual']
sec = d['sector_rankings']['industry']

def pct(s):
    try:
        return float(str(s).rstrip('%'))
    except Exception:
        return 0.0

print('=== Top 30 by 涨跌幅 ===')
for x in ind[:30]:
    print(f"  {x.get('股票简称')}({x.get('股票代码')}): {x.get('涨跌幅')} 换手={x.get('换手率')} 净额={x.get('净额')} 成交={x.get('成交额')}")

print()
print('=== 涨幅分布 ===')
print('20cm 涨停(>=19.9%):', sum(1 for x in ind if pct(x.get('涨跌幅')) >= 19.9))
print('10cm 涨停(9.97~10.05):', sum(1 for x in ind if 9.97 <= pct(x.get(x.get('涨跌幅', '0%'), '0%')) <= 10.05))
print('涨幅>=15%:', sum(1 for x in ind if pct(x.get('涨跌幅')) >= 15))
print('涨幅>=10%:', sum(1 for x in ind if pct(x.get('涨跌幅')) >= 10))
print('涨幅>=5%:', sum(1 for x in ind if pct(x.get('涨跌幅')) >= 5))
print('涨幅>=0%:', sum(1 for x in ind if pct(x.get('涨跌幅')) >= 0))
print('跌幅<=-5%:', sum(1 for x in ind if pct(x.get('涨跌幅')) <= -5))
print('跌幅<=-10%:', sum(1 for x in ind if pct(x.get('涨跌幅')) <= -10))
print('总股票数:', len(ind))

print()
print('=== 行业板块 Top 30 ===')
for s in sec[:30]:
    print(f"  #{s.get('序号')} {s.get('行业')}: {s.get('行业-涨跌幅')}% 领涨={s.get('领涨股')}({s.get('领涨股-涨跌幅')}%) 净额={s.get('净额')}亿")

print()
print('=== 行业板块 跌幅榜 Bottom 10 ===')
for s in sec[-10:]:
    print(f"  #{s.get('序号')} {s.get('行业')}: {s.get('行业-涨跌幅')}% 领涨={s.get('领涨股')}({s.get('领涨股-涨跌幅')}%) 净额={s.get('净额')}亿")

print()
print('=== 板块涨幅 > 5% 列表 ===')
for s in sec:
    if s.get('行业-涨跌幅', 0) >= 5.0:
        print(f"  {s.get('行业')}: +{s.get('行业-涨跌幅')}% 领涨={s.get('领涨股')}({s.get('领涨股-涨跌幅')}%) 净额={s.get('净额')}亿")

print()
print('=== 板块跌幅 < 0 列表 ===')
for s in sec:
    if s.get('行业-涨跌幅', 0) < 0:
        print(f"  {s.get('行业')}: {s.get('行业-涨跌幅')}% 净额={s.get('净额')}亿")