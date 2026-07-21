import json
with open('/tmp/easyquant_market_data_2026-06-24.json') as f:
    d = json.load(f)

ind = d['individual_rankings']['individual']

def parse_pct(s):
    try:
        return float(str(s).replace('%','').replace(',',''))
    except:
        return None

# 找出"高换手+涨停+主力净流出"=出货嫌疑
out_flow_limit_up = []
for s in ind:
    pct = parse_pct(s.get('涨跌幅'))
    if pct is None or pct < 9.5:
        continue
    net = s.get('净额','')
    if '-' in str(net):
        out_flow_limit_up.append((s['股票代码'], s['股票简称'], pct, s.get('成交额'), net))

print('=== 涨停但主力净流出 (出货嫌疑) ===')
for it in sorted(out_flow_limit_up, key=lambda x: x[2], reverse=True)[:20]:
    print(f"  {it[0]} {it[1]}: {it[2]}% 额={it[3]} 净={it[4]}")

# 房地产板块所有股
print()
print('=== 万通发展所属房地产板块情况(板块整体-3.14%) ===')
real_estate_limit = [s for s in ind if s.get('股票简称') in ['万通发展']]
for s in real_estate_limit:
    print(f"  {s}")

# 能源金属板块涨停潮
print()
print('=== 能源金属/锂电池涨停潮 ===')
li_names = ['永杉锂业', '雅化集团', '泰和新材', '中复神鹰', '兴发集团']
for s in ind:
    if s.get('股票简称') in li_names:
        print(f"  {s['股票代码']} {s['股票简称']}: {s['涨跌幅']} 净={s.get('净额')} 额={s.get('成交额')}")

# AI算力相关
print()
print('=== AI算力/数据中心涨停 ===')
ai_names = ['宏景科技','协创数据','领益智造','一博科技','聚辰股份','光力科技','杰创智能','中恒电气','汇成股份']
for s in ind:
    if s.get('股票简称') in ai_names:
        print(f"  {s['股票代码']} {s['股票简称']}: {s['涨跌幅']} 净={s.get('净额')} 额={s.get('成交额')} 换={s.get('换手率')}")
