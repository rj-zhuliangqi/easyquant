import json

with open('/private/tmp/easyquant_market_data_2026-06-26.json','r',encoding='utf-8') as f:
    data = json.load(f)

sectors = data['sector_rankings']['industry']
print('=== 行业涨幅榜（前15） ===')
for s in sectors[:15]:
    chg = float(s['行业-涨跌幅']) if not isinstance(s['行业-涨跌幅'], str) else 0.0
    jing = float(s['净额'])
    print(f"  #{s['序号']} {s['行业']} {chg:+.2f}% 净额:{jing:+.2f}亿 领涨:{s['领涨股']}({s['领涨股-涨跌幅']:+.2f}%)")
print()
print('=== 行业跌幅榜（末10） ===')
for s in sectors[-10:]:
    chg = float(s['行业-涨跌幅']) if not isinstance(s['行业-涨跌幅'], str) else 0.0
    jing = float(s['净额'])
    print(f"  #{s['序号']} {s['行业']} {chg:+.2f}% 净额:{jing:+.2f}亿 领涨:{s['领涨股']}({s['领涨股-涨跌幅']:+.2f}%)")

print()
print('=== 个股涨幅前 25 ===')
items = data['individual_rankings']['individual']


def parse_pct(s):
    try:
        return float(str(s).replace('%', ''))
    except Exception:
        return 0.0


sorted_items = sorted(items, key=lambda x: parse_pct(x.get('涨跌幅', '0%')), reverse=True)
for s in sorted_items[:25]:
    print(f"  {s['股票简称']} ({s['股票代码']}) {s.get('涨跌幅','-')} 换手:{s.get('换手率','-')} 净额:{s.get('净额','-')}")

print()
print('=== 个股跌幅前 20 ===')
for s in sorted_items[-20:]:
    print(f"  {s['股票简称']} ({s['股票代码']}) {s.get('涨跌幅','-')} 换手:{s.get('换手率','-')} 净额:{s.get('净额','-')}")

print()
arr = [parse_pct(x.get('涨跌幅','0%')) for x in items]
pos = sum(1 for x in arr if x>0)
neg = sum(1 for x in arr if x<0)
lim_up = sum(1 for x in arr if x>=19.9)
lim_dn = sum(1 for x in arr if x<=-19.9)
print(f'全市场: 涨{pos} 跌{neg} (涨:{pos*100/len(arr):.1f}%) 涨幅≥20%:{lim_up} 跌幅≤-20%:{lim_dn}')

print()
print('=== 资金净流入前 20 ===')
def parse_yi(s):
    try:
        return float(str(s).replace('亿','').replace('+',''))
    except Exception:
        return 0.0

sj = sorted(items, key=lambda x: parse_yi(x.get('净额','0')), reverse=True)
for s in sj[:20]:
    print(f"  {s['股票简称']}({s['股票代码']}) 净额:{s.get('净额','-')} 涨幅:{s.get('涨跌幅','-')}")

print()
print('=== 资金净流出前 20 ===')
for s in sj[-20:]:
    print(f"  {s['股票简称']}({s['股票代码']}) 净额:{s.get('净额','-')} 涨幅:{s.get('涨跌幅','-')}")
