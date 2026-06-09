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
top10_set = set(top10_sectors)

# Get limit up pool
limit_up = data.get('limit_up_pool', {})
print("Limit up pool keys:", list(limit_up.keys()) if isinstance(limit_up, dict) else type(limit_up))
if isinstance(limit_up, dict) and 'data' in limit_up:
    lu_data = limit_up['data']
    if isinstance(lu_data, list):
        print("Limit up stocks count:", len(lu_data))
        for s in lu_data[:5]:
            print("  Sample:", s)

# Get monitor signals
signals = data.get('monitor_signals', {})
print("\nMonitor signals:", signals if signals else "EMPTY")

# Get opportunities
opps = data.get('opportunities', {})
print("Opportunities:", opps if opps else "EMPTY")

# Market indices
indices = data.get('market_indices', {})
print("Market indices:", indices if indices else "EMPTY")

# Meta info
meta = data.get('meta', {})
print("Meta:", json.dumps(meta, ensure_ascii=False))

# Now let's try to get sector info for individual stocks
# The individual data doesn't have sector info, we need to enrich it
individual = data['individual_rankings']['individual']

# Build a mapping of stock -> sector by cross-referencing with sector leaders
# Since we don't have direct sector mapping, we'll use the sector data to infer

# Let's check what the local API can give us
print("\n=== INDIVIDUAL STOCK SAMPLE ===")
if individual:
    print("Keys:", list(individual[0].keys()))
    for s in individual[:3]:
        print(json.dumps(s, ensure_ascii=False))
