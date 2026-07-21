import json
d=json.load(open('/tmp/easyquant_market_data_2026-06-24.json'))
ir = d['individual_rankings']['individual']

def parse_amt(s):
    if s is None: return 0.0
    if isinstance(s, (int, float)): return float(s)
    s = str(s).replace(',', '').strip()
    if s == '' or s == '-': return 0.0
    mul = 1.0
    if s.endswith('亿'):
        s = s[:-1]
    elif s.endswith('万'):
        mul = 1e-4
        s = s[:-1]
    elif s.endswith('%'):
        s = s[:-1]
    try:
        return float(s)*mul
    except:
        return 0.0

rows = []
for r in ir:
    code = str(r.get('股票代码','')).zfill(6)
    name = r.get('股票简称','')
    chg = parse_amt(r.get('涨跌幅'))
    tr = parse_amt(r.get('换手率'))
    inflow = parse_amt(r.get('流入资金'))
    outflow = parse_amt(r.get('流出资金'))
    net = parse_amt(r.get('净额'))
    vol = parse_amt(r.get('成交额'))
    price = r.get('最新价') or 0
    rows.append({'code':code,'name':name,'chg':chg,'tr':tr,'inflow':inflow,'outflow':outflow,'net':net,'vol':vol,'price':price})

def is_st(name):
    n = (name or '').upper()
    return 'ST' in n

big = [r for r in rows if r['vol']>=30.0 and 1.0<=r['chg']<=8.0 and r['net']>=1.0 and not is_st(r['name'])]
big.sort(key=lambda x: x['net'], reverse=True)
print('candidates count:', len(big))
print()
hdr = '{:<8}{:<12}{:>8}{:>8}{:>10}{:>10}{:>10}'.format('code','name','chg%','tr%','net','vol','price')
print(hdr)
for r in big[:40]:
    line = '{:<8}{:<12}{:>8.2f}{:>8.2f}{:>10.2f}{:>10.2f}{:>10.2f}'.format(
        r['code'], r['name'], r['chg'], r['tr'], r['net'], r['vol'], r['price'])
    print(line)

print()
print('=== top net inflow overall (any chg) ===')
allrows = sorted([r for r in rows if not is_st(r['name'])], key=lambda x: x['net'], reverse=True)
for r in allrows[:30]:
    line = '{:<8}{:<12}{:>8.2f}{:>8.2f}{:>10.2f}{:>10.2f}{:>10.2f}'.format(
        r['code'], r['name'], r['chg'], r['tr'], r['net'], r['vol'], r['price'])
    print(line)
