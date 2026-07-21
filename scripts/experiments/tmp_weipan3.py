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

# Market indices from Tencent API
# sh000001: 4010.03 +1.28%
# sz399001: 15268.71 +3.02%
# sz399006: 3961.75 +3.93%

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
top10_set = set(top10_sectors)

# Known sector mappings for key stocks
stock_sector_map = {
    '000725': '光学光电子', '600522': '通信设备', '600487': '通信设备',
    '300476': '元件', '600498': '通信设备', '300346': '电子化学品',
    '300502': '通信设备', '300285': '电子化学品', '601138': '消费电子',
    '000063': '通信设备', '600584': '半导体', '002837': '通信设备',
    '002428': '小金属', '002916': '元件', '002384': '消费电子',
    '300394': '通信设备', '688012': '半导体', '600111': '小金属',
    '000100': '光学光电子', '688498': '半导体', '603986': '半导体',
    '002371': '半导体', '000988': '通信设备', '300433': '消费电子',
    '600549': '小金属', '000831': '小金属', '300395': '半导体',
    '002475': '消费电子', '600105': '通信设备', '688313': '半导体',
    '002969': '包装印刷', '002466': '能源金属', '002463': '元件',
    '000021': '消费电子', '002049': '半导体', '300408': '元件',
    '300666': '半导体', '300390': '能源金属', '688126': '半导体',
    '300570': '通信设备', '600176': '非金属材料', '300475': '半导体',
    '300548': '通信设备', '600183': '元件', '002851': '自动化设备',
    '603160': '通信设备', '600919': '银行', '000977': 'IT服务',
    '002372': '半导体', '688396': '半导体', '300861': '消费电子',
    '688008': '半导体', '301205': '通信设备', '300806': '电子化学品',
    '002467': '消费电子', '600390': '化学制品', '601012': '光伏设备',
    '300059': '互联网电商', '600396': '电力', '002046': '军工电子',
    '300014': '消费电子', '002415': '消费电子',
}

individual = data['individual_rankings']['individual']

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

    sector = stock_sector_map.get(code, '')

    candidates.append({
        'code': code, 'name': name, 'net': net, 'chg': chg,
        'price': price, 'turnover': turnover, 'amount': amount,
        'sector': sector
    })

# Deduplicate by code (some stocks appear twice)
seen = set()
unique_candidates = []
for c in candidates:
    if c['code'] not in seen:
        seen.add(c['code'])
        unique_candidates.append(c)
candidates = unique_candidates

# Score and classify
for c in candidates:
    score = 0
    sector = c['sector']
    sector_info = sector_map.get(sector, {})

    # Capital strength (max 30 points)
    if c['net'] >= 10:
        score += 30
    elif c['net'] >= 5:
        score += 25
    elif c['net'] >= 3:
        score += 20
    elif c['net'] >= 2:
        score += 15
    else:
        score += 10

    # Sector resonance (max 25 points)
    if sector in top10_sectors:
        sector_rank = top10_sectors.index(sector) + 1
        if sector_rank <= 3:
            score += 25
        elif sector_rank <= 5:
            score += 20
        else:
            score += 15
        # Sector net inflow positive
        if sector_info.get('net_inflow', 0) > 10:
            score += 5
        elif sector_info.get('net_inflow', 0) > 0:
            score += 3
    elif sector and sector_info.get('net_inflow', 0) > 0:
        score += 8

    # Price action quality (max 20 points)
    if 3.0 <= c['chg'] <= 6.0:
        score += 20
    elif 2.0 <= c['chg'] < 3.0:
        score += 12
    elif 6.0 < c['chg'] <= 8.0:
        score += 15

    # Turnover rate (max 10 points)
    if 3.0 <= c['turnover'] <= 10.0:
        score += 10
    elif 1.0 <= c['turnover'] < 3.0:
        score += 5
    elif c['turnover'] > 10.0:
        score += 7

    # Volume (max 10 points)
    if c['amount'] >= 50:
        score += 10
    elif c['amount'] >= 20:
        score += 7
    elif c['amount'] >= 5:
        score += 5
    else:
        score += 3

    c['score'] = score

    # Classify pick level
    if sector in top10_set and score >= 70:
        c['level'] = 'strong_recommend'
    elif sector in top10_set and score >= 55:
        c['level'] = 'confirm'
    elif score >= 45:
        c['level'] = 'candidate'
    else:
        c['level'] = 'watch'

candidates.sort(key=lambda x: x['score'], reverse=True)

# Apply quota limits
picks = {'strong_recommend': [], 'confirm': [], 'candidate': [], 'watch': []}
for c in candidates:
    level = c['level']
    quotas = {'strong_recommend': 2, 'confirm': 3, 'candidate': 3, 'watch': 5}
    if len(picks[level]) < quotas[level] and sum(len(v) for v in picks.values()) < 10:
        picks[level].append(c)

# Print results
print("=== FINAL PICKS ===")
total = 0
for level in ['strong_recommend', 'confirm', 'candidate', 'watch']:
    for c in picks[level]:
        total += 1
        sector_info = sector_map.get(c['sector'], {})
        net_inflow = sector_info.get('net_inflow', 0)
        print("[%s] %s %s chg=%+.2f%% net=%.2f亿 sector=%s(净额%.2f亿) score=%d turnover=%.1f%% amount=%.1f亿" % (
            level.upper(), c['code'], c['name'], c['chg'], c['net'],
            c['sector'], net_inflow, c['score'], c['turnover'], c['amount']))

print("\nTotal picks: %d / Total scanned: %d" % (total, len(individual)))

# Output as JSON for further processing
output = {
    'picks': picks,
    'market': {
        'sh000001': {'close': 4010.03, 'chg': 1.28},
        'sz399001': {'close': 15268.71, 'chg': 3.02},
        'sz399006': {'close': 3961.75, 'chg': 3.93}
    },
    'top10_sectors': top10_sectors,
    'sector_map': {k: v for k, v in sector_map.items() if k in top10_sectors},
    'total_scanned': len(individual),
    'total_candidates': len(candidates)
}
print("\n=== JSON OUTPUT ===")
print(json.dumps(output, ensure_ascii=False))
