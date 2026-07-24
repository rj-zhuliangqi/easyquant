import json
with open('/tmp/easyquant_market_data_2026-06-24.json') as f:
    d = json.load(f)
ind = d['individual_rankings']['individual']
print('Total:', len(ind))
print('Sample:', ind[0])
print('Type of 涨跌幅:', type(ind[0].get('涨跌幅')))
# Try parsing as float
def get_pct(r):
    v = r.get('涨跌幅')
    if isinstance(v, (int,float)): return v
    try: return float(str(v).replace('%','').strip())
    except: return None

vals = [get_pct(r) for r in ind]
vals = [v for v in vals if v is not None]
up = sum(1 for v in vals if v>0)
dn = sum(1 for v in vals if v<0)
zd = sum(1 for v in vals if v==0)
zt = sum(1 for v in vals if 9.5<=v<11)
dt = sum(1 for v in vals if -11<v<=-9.5)
zt20 = sum(1 for v in vals if v>=19.5)
dt20 = sum(1 for v in vals if v<=-19.5)
print(f'parsed total={len(vals)} 涨={up} 平={zd} 跌={dn}')
print(f'10cm涨停={zt} 10cm跌停={dt} 20cm涨停={zt20} 20cm跌停={dt20}')
