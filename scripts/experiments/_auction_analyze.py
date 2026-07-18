import json
import re
from datetime import datetime

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
    outflow = parse_amt(r.get('流出资金','0'))
    amt = parse_amt(r.get('成交额','0'))
    parsed.append({**r, '_pct': pct, '_turnover': turnover, '_net': net, '_inflow': inflow, '_outflow': outflow, '_amt': amt})

# 排除 ST 与新上市 (>= 100% 为新上市，不参与竞价)
def is_eligible(r):
    name = r.get('股票简称','')
    if 'ST' in name: return False
    if r['_pct'] >= 100: return False  # 新上市
    if r['_amt'] < 0.1: return False   # 成交额太小
    return True

elig = [r for r in parsed if is_eligible(r)]

# 板块索引: 名称 -> 涨跌幅
sec_map = {r['行业']: r for r in sec}

# 1) 板块联动 + 竞价抢筹 (strong_recommend)
#    找板块涨幅前 12 中领涨股 (>=3% 涨幅 + 板块涨幅 >=0.4%)
top_sec = sorted([s for s in sec if s['行业-涨跌幅'] >= 0.3], key=lambda x: x['行业-涨跌幅'], reverse=True)[:12]
top_sec_names = {s['行业'] for s in top_sec}
strong_picks = []
for r in elig:
    name = r.get('股票简称','')
    pct = r['_pct']
    # 找个股所属板块(按领涨股名)
    sec_match = None
    for s in top_sec:
        if s['领涨股'] == name:
            sec_match = s; break
    if sec_match is None: continue
    # 板块涨幅 0.4%+, 个股 4%-15%, 换手 5%+, 净额为正
    if sec_match['行业-涨跌幅'] >= 0.4 and 4 <= pct < 15 and r['_turnover'] >= 5 and r['_net'] > 0:
        strong_picks.append({**r, '_sec': sec_match['行业'], '_sec_pct': sec_match['行业-涨跌幅']})
strong_picks.sort(key=lambda x: (x['_sec_pct'], x['_net']), reverse=True)

# 2) 竞价强势 (confirm)
#    涨幅 3-8%, 换手 3%+, 净额流入, 不属于上述 strong
strong_codes = {r['股票代码'] for r in strong_picks}
confirm = [r for r in elig if r['股票代码'] not in strong_codes and 3 <= r['_pct'] < 8 and r['_turnover'] >= 3 and r['_net'] > 0]
confirm.sort(key=lambda x: (x['_net'], x['_pct']), reverse=True)

# 3) 弱转强 (candidate)
#    涨幅 4-9%, 换手 6%+, 净额流入(可小), 但换手偏低
candidate = [r for r in elig if r['股票代码'] not in strong_codes and 4 < r['_pct'] < 9 and 3 <= r['_turnover'] < 6 and r['_net'] > 0]
candidate.sort(key=lambda x: x['_pct'], reverse=True)

# 4) watch
#    涨幅 2-5%, 换手 2%+, 净额流入
watch = [r for r in elig if r['股票代码'] not in strong_codes and 2 <= r['_pct'] < 5 and r['_turnover'] >= 2 and r['_net'] > 0]
watch.sort(key=lambda x: x['_pct'], reverse=True)

print('strong_recommend (板块联动+竞价抢筹):', len(strong_picks))
for r in strong_picks[:5]:
    print(f"  {r['股票代码']} {r['股票简称']} 涨{r['_pct']:.2f}% 换{r['_turnover']:.2f}% 净额{r['_net']:.3f}亿 板块:{r['_sec']}({r['_sec_pct']:.2f}%)")

print('\nconfirm (竞价强势):', len(confirm))
for r in confirm[:8]:
    print(f"  {r['股票代码']} {r['股票简称']} 涨{r['_pct']:.2f}% 换{r['_turnover']:.2f}% 净额{r['_net']:.3f}亿")

print('\ncandidate (弱转强/换手中等):', len(candidate))
for r in candidate[:8]:
    print(f"  {r['股票代码']} {r['股票简称']} 涨{r['_pct']:.2f}% 换{r['_turnover']:.2f}% 净额{r['_net']:.3f}亿")

print('\nwatch (小幅高开+板块共振):', len(watch))
for r in watch[:8]:
    print(f"  {r['股票代码']} {r['股票简称']} 涨{r['_pct']:.2f}% 换{r['_turnover']:.2f}% 净额{r['_net']:.3f}亿")

print()
print('=== 涨跌停统计 ===')
zt = [r for r in elig if r['_pct'] >= 19.5]
dt = [r for r in elig if r['_pct'] <= -9.5]
zst = [r for r in elig if 9.5 <= r['_pct'] < 19.5]
print(f'涨停: {len(zt)} 家, 准涨停: {len(zst)} 家, 跌停: {len(dt)} 家')
print(f'上涨家数: {len([r for r in elig if r["_pct"]>0])}, 下跌: {len([r for r in elig if r["_pct"]<0])}')

print()
print('=== 板块涨幅 Top 10 ===')
for s in top_sec[:10]:
    print(f"  {s['行业']:<8} {s['行业-涨跌幅']:>6.2f}%  领涨:{s['领涨股']}({s['领涨股-涨跌幅']:>5.2f}%)")

print()
print('=== 板块跌幅 Top 8 ===')
for s in sorted(sec, key=lambda x: x['行业-涨跌幅'])[:8]:
    print(f"  {s['行业']:<10} {s['行业-涨跌幅']:>6.2f}%  领涨:{s['领涨股']}({s['领涨股-涨跌幅']:>5.2f}%)")

# 净流入 Top 板块(用行业下股票净额近似)
print()
print('=== 个股净流入 Top 10 ===')
top_in = sorted([r for r in elig if r['_net']>0], key=lambda x: x['_net'], reverse=True)[:10]
for r in top_in:
    print(f"  {r['股票代码']} {r['股票简称']:<10} 涨{r['_pct']:>6.2f}% 净额{r['_net']:.3f}亿")

# 净流出
print()
print('=== 个股净流出 Top 10 ===')
top_out = sorted([r for r in elig if r['_net']<0], key=lambda x: x['_net'])[:10]
for r in top_out:
    print(f"  {r['股票代码']} {r['股票简称']:<10} 涨{r['_pct']:>6.2f}% 净额{r['_net']:.3f}亿")
