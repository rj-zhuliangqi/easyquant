import json, re
with open('/tmp/easyquant_market_data_2026-07-11.json', 'r') as f:
    data = json.load(f)

def to_pct(s):
    if s is None: return None
    m = re.search(r'-?\d+\.?\d*', str(s))
    return float(m.group()) if m else None

def to_num(s):
    if s is None: return None
    m = re.search(r'-?\d+\.?\d*', str(s))
    return float(m.group()) if m else None

indv = data['individual_rankings']['individual']

stocks = []
for r in indv:
    chg = to_pct(r.get('涨跌幅'))
    if chg is None: continue
    if chg > 100: continue
    stocks.append({
        'code': r.get('股票代码'),
        'name': r.get('股票简称'),
        'price': to_num(r.get('最新价')),
        'change_pct': chg,
        'turnover_pct': to_pct(r.get('换手率')),
        'net_inflow': to_num(r.get('净额')),
        'amount': to_num(r.get('成交额')),
        'in': to_num(r.get('流入资金')),
        'out': to_num(r.get('流出资金')),
    })

print('=== Counts ===')
print('Total parsed:', len(stocks))
print('>= 9.9%:', len([s for s in stocks if s['change_pct'] >= 9.9]))
print('>= 7%:', len([s for s in stocks if s['change_pct'] >= 7]))
print('>= 5%:', len([s for s in stocks if s['change_pct'] >= 5]))
print('>= 3%:', len([s for s in stocks if s['change_pct'] >= 3]))
print('>= 2%:', len([s for s in stocks if s['change_pct'] >= 2]))
print()
print('=== Top 30 by change_pct ===')
sorted_s = sorted(stocks, key=lambda x: x['change_pct'], reverse=True)
for s in sorted_s[:30]:
    chg_str = ('+' if s['change_pct']>=0 else '') + str(s['change_pct'])
    print(s['code'], s['name'], chg_str + '%', '价格' + str(s['price']), '换手' + str(s['turnover_pct']) + '%', '成交' + str(s['amount']) + '亿', '净额' + str(s['net_inflow']))

print()
print('=== ST candidates ===')
for s in sorted_s[:50]:
    if 'ST' in str(s['name']) or '退' in str(s['name']):
        print(s)

print()
print('=== Auction-strong candidates (3% to 7%, high turnover, big amount) ===')
mid = [s for s in stocks if 3 <= s['change_pct'] < 7 and s['amount'] and s['amount'] > 2]
mid_sorted = sorted(mid, key=lambda x: (x['amount'] or 0), reverse=True)
for s in mid_sorted[:25]:
    chg_str = ('+' if s['change_pct']>=0 else '') + str(s['change_pct'])
    print(s['code'], s['name'], chg_str + '%', '成交' + str(s['amount']) + '亿', '换手' + str(s['turnover_pct']) + '%')