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
    parsed.append({**r, '_pct': parse_pct(r.get('涨跌幅','0')),
                          '_turnover': parse_pct(r.get('换手率','0')),
                          '_net': parse_amt(r.get('净额','0')),
                          '_inflow': parse_amt(r.get('流入资金','0')),
                          '_amt': parse_amt(r.get('成交额','0'))})

def is_eligible(r):
    name = r.get('股票简称','')
    if 'ST' in name: return False
    if r['_pct'] >= 100: return False
    if r['_amt'] < 0.1: return False
    return True

elig = [r for r in parsed if is_eligible(r)]
print(f'合格股票池: {len(elig)}')

zt = [r for r in elig if r['_pct'] >= 19.5]
dt = [r for r in elig if r['_pct'] <= -9.5]
zst = [r for r in elig if 9.5 <= r['_pct'] < 19.5]
up = [r for r in elig if r['_pct'] > 0]
dn = [r for r in elig if r['_pct'] < 0]
print(f'涨停: {len(zt)} | 准涨停: {len(zst)} | 跌停: {len(dt)} | 涨: {len(up)} | 跌: {len(dn)}')

# 板块
print('=== 行业涨幅 Top 12 ===')
top_sec = sorted(sec, key=lambda x: x['行业-涨跌幅'], reverse=True)[:12]
for s in top_sec:
    print(f"  {s['行业']:<8} {s['行业-涨跌幅']:>5.2f}% 领涨:{s['领涨股']}({s['领涨股-涨跌幅']:.2f}%)")
print('=== 行业跌幅 Top 8 ===')
for s in sorted(sec, key=lambda x: x['行业-涨跌幅'])[:8]:
    print(f"  {s['行业']:<8} {s['行业-涨跌幅']:>5.2f}% 领涨:{s['领涨股']}({s['领涨股-涨跌幅']:.2f}%)")

# 板块聚合统计: 个股属于哪个板块 - 用领涨股名匹配
sec_by_lead = {s['领涨股']: s['行业'] for s in sec if s.get('领涨股')}

# 强势板块下的同板块其它高涨幅股
print()
print('=== 强势板块中个股 (板块涨幅>=0.4% 且 个股涨幅>=3%) ===')
strong_sec = {s['行业'] for s in top_sec if s['行业-涨跌幅'] >= 0.4}
sec_pct_map = {s['行业']: s['行业-涨跌幅'] for s in sec}
# 简单把个股按领涨股名归类
grouped = {}
for r in elig:
    name = r.get('股票简称','')
    if name in sec_by_lead:
        sec_name = sec_by_lead[name]
        grouped.setdefault(sec_name, []).append(r)

# 板块内高涨幅分布
for sname in sorted(strong_sec, key=lambda x: -sec_pct_map.get(x, 0))[:10]:
    members = grouped.get(sname, [])
    high = [m for m in members if m['_pct'] >= 3]
    if high:
        print(f"  {sname}({sec_pct_map[sname]:.2f}%) 强股: {len(high)}只")
        for r in sorted(high, key=lambda x: -x['_pct'])[:3]:
            print(f"    {r['股票代码']} {r['股票简称']} 涨{r['_pct']:.2f}% 换{r['_turnover']:.2f}% 净额{r['_net']:.3f}亿")

# 净流入
print()
print('=== 个股净流入 Top 12 ===')
for r in sorted([r for r in elig if r['_net']>0], key=lambda x: x['_net'], reverse=True)[:12]:
    print(f"  {r['股票代码']} {r['股票简称']:<10} 涨{r['_pct']:>6.2f}% 换{r['_turnover']:>5.2f}% 净额{r['_net']:.3f}亿")
print('=== 个股净流出 Top 12 ===')
for r in sorted([r for r in elig if r['_net']<0], key=lambda x: x['_net'])[:12]:
    print(f"  {r['股票代码']} {r['股票简称']:<10} 涨{r['_pct']:>6.2f}% 换{r['_turnover']:>5.2f}% 净额{r['_net']:.3f}亿")
