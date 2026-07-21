import json
with open('/tmp/easyquant_market_data_2026-07-18.json','r') as f:
    d=json.load(f)
ind = d['sector_rankings']['industry']
ind_sorted = sorted(ind, key=lambda x: x.get('行业-涨跌幅',0), reverse=True)
print('=== INDUSTRY TOP30 ===')
for r in ind_sorted[:30]:
    print(f"{r.get('行业-涨跌幅',0):>6.2f}%  {r['行业']:<14} 领涨:{r.get('领涨股','')}({r.get('领涨股-涨跌幅',0):>5.2f}%)  净额:{r.get('净额',0):>7.2f}亿")
print('=== INDUSTRY BOTTOM15 ===')
for r in ind_sorted[-15:]:
    print(f"{r.get('行业-涨跌幅',0):>6.2f}%  {r['行业']:<14} 领涨:{r.get('领涨股','')}({r.get('领涨股-涨跌幅',0):>5.2f}%)  净额:{r.get('净额',0):>7.2f}亿")
print('=== INDIVIDUAL TOP25 ===')
indiv = d['individual_rankings']['individual']
for r in indiv[:25]:
    print(f"{r['股票代码']} {r['股票简称']:<10} {r['涨跌幅']:>7} 净额:{r.get('净额','')} 成交:{r.get('成交额','')} 换手:{r.get('换手率','')}")