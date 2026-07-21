import json, re
with open('/tmp/easyquant_market_data_2026-07-03.json') as f:
    data = json.load(f)
ind = data['individual_rankings']['individual']
sec = data['sector_rankings']['industry']

def parse_pct(s):
    if isinstance(s, (int, float)): return float(s)
    if isinstance(s, str):
        m = re.search(r'(-?\d+\.?\d*)', s)
        return float(m.group(1)) if m else 0.0
    return 0.0

def parse_amt(s):
    if not isinstance(s, str): return 0.0
    m = re.match(r'([-\d.]+)([万亿]?)', s)
    if not m: return 0.0
    v = float(m.group(1)); u = m.group(2)
    if u == '万': return v / 10000
    if u == '亿': return v
    if u == '万亿': return v * 10000
    return v

parsed = []
for r in ind:
    pct = parse_pct(r.get('涨跌幅','0'))
    turnover = parse_pct(r.get('换手率','0'))
    net = parse_amt(r.get('净额','0'))
    inflow = parse_amt(r.get('流入资金','0'))
    amt = parse_amt(r.get('成交额','0'))
    parsed.append({**r, '_pct': pct, '_turnover': turnover, '_net': net, '_inflow': inflow, '_amt': amt})

print('=== 竞价强势候选: 涨幅 3-8%, 换手>=3%, 净额为正, 排除ST ===')
cands = [r for r in parsed if 'ST' not in r.get('股票简称','') and 3 <= r['_pct'] < 8 and r['_turnover'] >= 3 and r['_net'] > 0]
cands.sort(key=lambda x: (x['_net'], x['_pct']), reverse=True)
for r in cands[:30]:
    code = str(r.get('股票代码',''))
    print(f"  {code:<8} {r.get('股票简称',''):<10} 涨:{r.get('涨跌幅',''):>8} 换:{r.get('换手率',''):>6} 净额:{r.get('净额','')} 流入:{r.get('流入资金','')}")

print()
print('=== 竞价抢筹: 涨幅 8-15%, 换手>=5%, 净额流入 ===')
qb = [r for r in parsed if 'ST' not in r.get('股票简称','') and 8 < r['_pct'] < 15 and r['_turnover'] >= 5 and r['_net'] > 0]
qb.sort(key=lambda x: x['_net'], reverse=True)
for r in qb[:20]:
    code = str(r.get('股票代码',''))
    print(f"  {code:<8} {r.get('股票简称',''):<10} 涨:{r.get('涨跌幅',''):>8} 换:{r.get('换手率',''):>6} 净额:{r.get('净额','')}")

print()
print('=== 弱转强 (前日跌,今涨): 涨幅 4-9%, 换手>=5%, 净额流入 ===')
weak_to_strong = [r for r in parsed if 'ST' not in r.get('股票简称','') and 4 < r['_pct'] < 9 and r['_turnover'] >= 5 and r['_net'] > 0]
weak_to_strong.sort(key=lambda x: x['_inflow'], reverse=True)
for r in weak_to_strong[:20]:
    code = str(r.get('股票代码',''))
    print(f"  {code:<8} {r.get('股票简称',''):<10} 涨:{r.get('涨跌幅',''):>8} 换:{r.get('换手率',''):>6} 净额:{r.get('净额','')} 流入:{r.get('流入资金','')}")

print()
print('=== 高位涨停: 涨幅>=19.5% 排除ST ===')
zts = [r for r in parsed if 'ST' not in r.get('股票简称','') and r['_pct'] >= 19.5]
zts.sort(key=lambda x: x['_amt'], reverse=True)
for r in zts[:25]:
    code = str(r.get('股票代码',''))
    print(f"  {code:<8} {r.get('股票简称',''):<10} 涨:{r.get('涨跌幅',''):>8} 换:{r.get('换手率',''):>6} 净额:{r.get('净额','')} 成交:{r.get('成交额','')}")

print()
print(f'涨幅>=19.5% 总数(非ST): {len(zts)}')
print(f'涨幅 9.5-19.5% 总数(非ST): {len([r for r in parsed if "ST" not in r.get("股票简称","") and 9.5 <= r["_pct"] < 19.5])}')
print(f'涨幅 0-9.5% 总数(非ST): {len([r for r in parsed if "ST" not in r.get("股票简称","") and 0 < r["_pct"] < 9.5])}')
print(f'跌停(-9.5%及以下)总数(非ST): {len([r for r in parsed if "ST" not in r.get("股票简称","") and r["_pct"] <= -9.5])}')
