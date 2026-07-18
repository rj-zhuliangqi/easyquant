import json, re

with open('/tmp/easyquant_market_data_2026-07-11.json', 'r') as f:
    data = json.load(f)

def to_pct(s):
    if s is None: return None
    m = re.search(r'-?\d+\.?\d*', str(s))
    return float(m.group()) if m else None

def to_num(s):
    if s is None: return None
    if isinstance(s, (int, float)): return float(s)
    text = str(s).strip()
    if '亿' in text:
        text = text.replace('亿', '')
    elif '万' in text:
        text = text.replace('万', '')
    m = re.search(r'-?\d+\.?\d*', text)
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
        'in_amt': to_num(r.get('流入资金')),
        'out_amt': to_num(r.get('流出资金')),
    })

print('=== Distribution ===')
print('Total parsed:', len(stocks))
print('>= 9.9%:', len([s for s in stocks if s['change_pct'] >= 9.9]))
print('7-9.9%:', len([s for s in stocks if 7 <= s['change_pct'] < 9.9]))
print('5-7%:', len([s for s in stocks if 5 <= s['change_pct'] < 7]))
print('3-5%:', len([s for s in stocks if 3 <= s['change_pct'] < 5]))
print('2-3%:', len([s for s in stocks if 2 <= s['change_pct'] < 3]))
print()

print('=== Limit-up zone (>=9.9%) by amount ===')
top_zone = [s for s in stocks if s['change_pct'] >= 9.9]
top_zone = sorted(top_zone, key=lambda x: x['amount'] or 0, reverse=True)
for s in top_zone[:20]:
    print(s['code'], s['name'], ('+' if s['change_pct']>=0 else '') + str(s['change_pct']) + '%', '价' + str(s['price']), '成交' + str(s['amount']) + '亿', '换手' + str(s['turnover_pct']) + '%', '净额' + str(s['net_inflow']) + '亿')

print()
print('=== 7-9.9% by amount ===')
mid_zone = [s for s in stocks if 7 <= s['change_pct'] < 9.9]
mid_zone = sorted(mid_zone, key=lambda x: x['amount'] or 0, reverse=True)
for s in mid_zone[:20]:
    print(s['code'], s['name'], ('+' if s['change_pct']>=0 else '') + str(s['change_pct']) + '%', '价' + str(s['price']), '成交' + str(s['amount']) + '亿', '换手' + str(s['turnover_pct']) + '%', '净额' + str(s['net_inflow']) + '亿')

print()
print('=== 5-7% turnover>=8%, amount>=3亿 ===')
mid2 = [s for s in stocks if 5 <= s['change_pct'] < 7 and (s['turnover_pct'] or 0) >= 8 and (s['amount'] or 0) >= 3]
mid2 = sorted(mid2, key=lambda x: x['amount'] or 0, reverse=True)
for s in mid2[:20]:
    print(s['code'], s['name'], ('+' if s['change_pct']>=0 else '') + str(s['change_pct']) + '%', '成交' + str(s['amount']) + '亿', '换手' + str(s['turnover_pct']) + '%')

print()
print('=== 3-5% turnover>=10%, amount>=5亿 ===')
mid3 = [s for s in stocks if 3 <= s['change_pct'] < 5 and (s['turnover_pct'] or 0) >= 10 and (s['amount'] or 0) >= 5]
mid3 = sorted(mid3, key=lambda x: x['amount'] or 0, reverse=True)
for s in mid3[:20]:
    print(s['code'], s['name'], ('+' if s['change_pct']>=0 else '') + str(s['change_pct']) + '%', '成交' + str(s['amount']) + '亿', '换手' + str(s['turnover_pct']) + '%')

print()
print('=== Sector leaders (top sector ranking) ===')
sec = data['sector_rankings']['industry']
sec_sorted = sorted(sec, key=lambda x: x.get('行业-涨跌幅', 0), reverse=True)
for s in sec_sorted[:12]:
    print(s.get('行业'), s.get('行业-涨跌幅'), '领涨' + str(s.get('领涨股')) + ' ' + str(s.get('领涨股-涨跌幅')) + '%')