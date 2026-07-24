"""Fetch concept board and top movers from Sina."""
import urllib.request, json, urllib.parse

def fetch(url):
    req = urllib.request.Request(url, headers={'Referer':'https://finance.sina.com.cn/'})
    return urllib.request.urlopen(req, timeout=15).read().decode('gbk', errors='ignore')

# Concept boards
try:
    txt = fetch('https://vip.stock.finance.sina.com.cn/q/api/jsonp.php/var%20conceptData=/Market_Center.getHQNodes')
    print("=== getHQNodes ===")
    print(txt[:500])
except Exception as e:
    print("E1", e)

# Try industry ranking via newer sina endpoint
for node in ['hangye_ZL01','sw2_ml','sw2_ZL01']:
    try:
        url = f'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=80&sort=changepercent&asc=0&node={node}&_s_r_a=init'
        txt = fetch(url)
        print(f"=== {node} ===")
        print(txt[:800])
    except Exception as e:
        print("E", node, e)

# Top gainers by individual stock
url = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=40&sort=changepercent&asc=0&node=hs_a&symbol=&_s_r_a=page'
txt = fetch(url)
print("=== hs_a top40 by chg ===")
import re
# parse JSON
try:
    data = json.loads(txt)
    for r in data[:25]:
        print(f"{r.get('symbol','')} {r.get('name','')} 涨跌幅={r.get('changepercent','')}% 现价={r.get('trade','')} 成交额={float(r.get('amount',0))/1e8:.2f}亿 换手={r.get('turnoverratio','')}%")
except Exception as e:
    print("PARSE_ERR", e, txt[:500])
