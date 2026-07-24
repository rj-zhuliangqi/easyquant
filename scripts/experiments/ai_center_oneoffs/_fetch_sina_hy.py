"""Fetch sector data via Sina industry endpoint."""
import urllib.request, json

req = urllib.request.Request(
    'https://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php',
    headers={'Referer': 'https://finance.sina.com.cn/'}
)
data = urllib.request.urlopen(req, timeout=15).read().decode('gbk', errors='ignore')

# parse: var S_Finance_bankuai_sinaindustry = {"key":"key,name,count,price?,change,pct_change,vol,amt,leader_code,leader_pct,leader_price,leader_chg,leader_name", ...}
import re
m = re.search(r'=\s*({.*})\s*$', data.strip())
raw = json.loads(m.group(1))

rows = []
for k, v in raw.items():
    parts = v.split(',')
    # parts[0]=key, parts[1]=name, parts[2]=count, parts[3]=avgprice, parts[4]=change, parts[5]=pct, parts[6]=vol, parts[7]=amt, parts[8]=leader_code, parts[9]=leader_pct, parts[10]=leader_price, parts[11]=leader_chg, parts[12]=leader_name
    try:
        rows.append({
            'name': parts[1],
            'count': int(parts[2]),
            'pct': float(parts[5]),
            'amt': float(parts[7])/1e8,
            'leader_name': parts[12],
            'leader_pct': float(parts[9]),
        })
    except: pass

rows.sort(key=lambda x: x['pct'], reverse=True)
print("=== TOP 15 INDUSTRY (Sina) ===")
for r in rows[:15]:
    print(f"{r['name']:8s} 涨跌幅={r['pct']:+.2f}% 成交={r['amt']:.1f}亿 领涨={r['leader_name']}({r['leader_pct']:+.2f}%) 个数={r['count']}")
print()
print("=== BOTTOM 10 INDUSTRY (Sina) ===")
for r in rows[-10:]:
    print(f"{r['name']:8s} 涨跌幅={r['pct']:+.2f}% 成交={r['amt']:.1f}亿 领涨={r['leader_name']}({r['leader_pct']:+.2f}%) 个数={r['count']}")

# Total volume across all industries
total_amt = sum(r['amt'] for r in rows)
print(f"\n两市行业合计成交={total_amt:.1f}亿")

# Save
with open('/tmp/sina_industry_0623.json','w',encoding='utf-8') as f:
    json.dump(rows, f, ensure_ascii=False, indent=2)
