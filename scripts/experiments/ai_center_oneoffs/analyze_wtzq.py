import json

with open('/tmp/easyquant_market_data_2026-06-09.json') as f:
    d = json.load(f)

ind = d['individual_rankings']['individual']

candidates = []
for s in ind:
    try:
        pct_str = str(s.get('涨跌幅', '0%')).replace('%', '')
        pct = float(pct_str)
        turnover_str = str(s.get('换手率', '0%')).replace('%', '')
        turnover = float(turnover_str)
        net_raw = str(s.get('净额', '0'))
        if '亿' in net_raw:
            net_val = float(net_raw.replace('亿', ''))
        elif '万' in net_raw:
            net_val = float(net_raw.replace('万', '')) / 10000
        else:
            net_val = float(net_raw)
        code = str(s.get('股票代码', '')).zfill(6)
        name = s.get('股票简称', '')
        price = s.get('最新价', 0)
        amount = s.get('成交额', '0')
        in_flow = s.get('流入资金', '0')
        out_flow = s.get('流出资金', '0')
        candidates.append({
            'code': code, 'name': name, 'pct': pct,
            'turnover': turnover, 'net_flow': net_val,
            'price': price, 'amount': amount,
            'in_flow': in_flow, 'out_flow': out_flow
        })
    except Exception as e:
        continue

candidates.sort(key=lambda x: x['pct'], reverse=True)

print("=== TOP 40 GAINERS ===")
for c in candidates[:40]:
    print(f"{c['code']} {c['name']} {c['pct']:.2f}% t:{c['turnover']:.1f}% n:{c['net_flow']:.3f}yi vol:{c['amount']}")

print("\n=== WEAK-TO-STRONG (2-8% gain, positive flow, turnover>=3%) ===")
wtos = [c for c in candidates if 2 <= c['pct'] <= 8 and c['net_flow'] > 0 and c['turnover'] >= 3]
for c in wtos[:40]:
    print(f"{c['code']} {c['name']} {c['pct']:.2f}% t:{c['turnover']:.1f}% n:{c['net_flow']:.3f}yi vol:{c['amount']}")

print(f"\nTotal stocks: {len(candidates)}")
print(f"Weak-to-strong candidates: {len(wtos)}")

# Sector data
sectors = d['sector_rankings']['industry']
print("\n=== TOP 15 SECTORS ===")
for s in sectors[:15]:
    print(f"{s['行业']} {s['行业-涨跌幅']:.2f}% net:{s['净额']}yi leader:{s['领涨股']}({s['领涨股-涨跌幅']:.2f}%)")
