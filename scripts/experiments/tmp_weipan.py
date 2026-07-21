import json, re, sys

def parse_amount(val):
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(',', '')
    if '亿' in s:
        return float(s.replace('亿', ''))
    elif '万' in s:
        return float(s.replace('万', '')) / 10000
    try:
        v = float(s)
        if abs(v) > 1000:
            return v / 10000
        return v
    except:
        return 0.0

def parse_pct(val):
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace('%', '')
    try:
        return float(s)
    except:
        return 0.0

with open('/tmp/easyquant_market_data_2026-06-09.json') as f:
    data = json.load(f)

sectors = data['sector_rankings']['industry']
sector_map = {}
for i, s in enumerate(sectors):
    name = s['行业']
    sector_map[name] = {
        'net_inflow': float(s.get('净额', 0)),
        'chg': float(s.get('行业-涨跌幅', 0)),
        'rank': i + 1,
        'leader': s.get('领涨股', ''),
        'leader_chg': float(s.get('领涨股-涨跌幅', 0)),
        'company_count': int(s.get('公司家数', 0))
    }

top10_sectors = sorted(sector_map.keys(), key=lambda x: sector_map[x]['net_inflow'], reverse=True)[:10]
print("=== TOP 10 SECTORS BY NET INFLOW ===")
for s in top10_sectors:
    info = sector_map[s]
    print("  %s: net=%.2f chg=%.2f%% rank=%d" % (s, info['net_inflow'], info['chg'], info['rank']))

individual = data['individual_rankings']['individual']
print("\nTotal stocks: %d" % len(individual))

candidates = []
for s in individual:
    code = str(s.get('股票代码', '')).zfill(6)
    name = str(s.get('股票简称', ''))
    net = parse_amount(s.get('净额', 0))
    chg = parse_pct(s.get('涨跌幅', 0))
    price = float(s.get('最新价', 0)) if s.get('最新价') else 0
    turnover = parse_pct(s.get('换手率', 0))
    amount = parse_amount(s.get('成交额', 0))

    if 'ST' in name or 'st' in name:
        continue
    if price <= 0:
        continue
    if net < 1.0:
        continue
    if chg < 2.0 or chg > 8.0:
        continue
    if chg >= 9.9:
        continue
    if turnover < 1.0:
        continue
    if amount < 2.0:
        continue

    candidates.append({
        'code': code, 'name': name, 'net': net, 'chg': chg,
        'price': price, 'turnover': turnover, 'amount': amount
    })

print("After filter: %d stocks" % len(candidates))
candidates.sort(key=lambda x: x['net'], reverse=True)

for c in candidates[:30]:
    print("  %s %s chg=%+.2f%% net=%+.2f turnover=%.2f%% amount=%.2f" % (
        c['code'], c['name'], c['chg'], c['net'], c['turnover'], c['amount']))
