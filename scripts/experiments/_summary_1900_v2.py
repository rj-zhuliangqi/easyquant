import json
with open('/tmp/easyquant_market_data_2026-06-24.json') as f:
    d = json.load(f)

ind = d['individual_rankings']['individual']

def parse_pct(s):
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).replace('%','').replace(',','')
    try:
        return float(s)
    except:
        return None

def parse_amt(s):
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s)
    if '亿' in s:
        try: return float(s.replace('亿','')) * 1e8
        except: return 0
    if '万' in s:
        try: return float(s.replace('万','')) * 1e4
        except: return 0
    try: return float(s)
    except: return 0

# Categorize
limit_up_normal = []  # ~10%
limit_up_20 = []  # 20% (创业板/科创板)
near_limit_up = []  # 7-9.9%
limit_down = []
broken_limit = []  # opened limit then fell

for s in ind:
    pct = parse_pct(s.get('涨跌幅'))
    if pct is None:
        continue
    code = str(s.get('股票代码','')).zfill(6)
    name = s.get('股票简称','')
    if pct >= 19.5:
        limit_up_20.append((code, name, pct, s.get('成交额'), s.get('净额')))
    elif 9.5 <= pct < 11:
        limit_up_normal.append((code, name, pct, s.get('成交额'), s.get('净额')))
    elif 7 <= pct < 9.5:
        near_limit_up.append((code, name, pct, s.get('成交额'), s.get('净额')))
    elif pct <= -9.5:
        limit_down.append((code, name, pct, s.get('成交额'), s.get('净额')))

print(f'20%涨停: {len(limit_up_20)}')
print(f'10%涨停: {len(limit_up_normal)}')
print(f'7-9.5%(冲高): {len(near_limit_up)}')
print(f'跌停: {len(limit_down)}')

print()
print('=== 20%涨停 ===')
for it in limit_up_20[:30]:
    print(f"  {it[0]} {it[1]}: {it[2]}% 额={it[3]} 净={it[4]}")

print()
print('=== 10%涨停 (前30) ===')
for it in limit_up_normal[:30]:
    print(f"  {it[0]} {it[1]}: {it[2]}% 额={it[3]} 净={it[4]}")

print()
print('=== 跌停 ===')
for it in limit_down[:30]:
    print(f"  {it[0]} {it[1]}: {it[2]}% 额={it[3]} 净={it[4]}")

# 整体涨跌家数
up_count = sum(1 for s in ind if parse_pct(s.get('涨跌幅')) and parse_pct(s.get('涨跌幅')) > 0)
flat_count = sum(1 for s in ind if parse_pct(s.get('涨跌幅')) == 0)
down_count = sum(1 for s in ind if parse_pct(s.get('涨跌幅')) is not None and parse_pct(s.get('涨跌幅')) < 0)
total = len(ind)
print(f"\n总数={total}, 涨={up_count}, 平={flat_count}, 跌={down_count}")

# 个股涨幅分布
print()
print('=== 跌幅前20 ===')
ranked_down = sorted([s for s in ind if parse_pct(s.get('涨跌幅')) is not None], key=lambda x: parse_pct(x.get('涨跌幅')))
for s in ranked_down[:20]:
    print(f"  {s['股票代码']} {s['股票简称']}: {s['涨跌幅']} 额={s.get('成交额')}")
