import json
import urllib.request
import sys
import time

CANDIDATES = {
    "002575": "群兴玩具",
    "301526": "国际复材",
    "300304": "云意电气",
    "688711": "宏微科技",
    "000970": "中科三环",
    "603011": "合锻智能",
    "301488": "豪恩汽电",
    "002851": "麦格米特",
    "300657": "弘信电子",
    "301511": "德福科技",
    "000636": "风华高科",
    "000063": "中兴通讯",
}

def get_tencent_code(code):
    if code.startswith('6'):
        return f"sh{code}"
    else:
        return f"sz{code}"

def fetch_tencent_quotes(codes):
    tencent_codes = [get_tencent_code(c) for c in codes]
    codes_str = ','.join(tencent_codes)
    url = f"https://qt.gtimg.cn/q={codes_str}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            text = resp.read().decode('gbk')
            return text
    except Exception as e:
        print(f"Error fetching tencent: {e}", file=sys.stderr)
        return ""

def parse_tencent_quote(raw_text):
    results = {}
    blocks = raw_text.strip().split(';')
    for block in blocks:
        block = block.strip()
        if not block or '~' not in block:
            continue
        try:
            eq_idx = block.index('=')
            key = block[:eq_idx].split('~')[-1] if '~' in block[:eq_idx] else ''
            vals = block[eq_idx+1:].strip('"').split('~')
            if len(vals) >= 50:
                code = vals[2]
                name = vals[1]
                price = float(vals[3])
                yclose = float(vals[4])
                open_p = float(vals[5])
                vol = int(vals[6])
                high = float(vals[33]) if vals[33] else price
                low = float(vals[34]) if vals[34] else price
                amount = float(vals[37]) if vals[37] else 0
                turnover = float(vals[38]) if vals[38] else 0
                change_pct = round((price - yclose) / yclose * 100, 2) if yclose > 0 else 0

                # Parse time-series data if available (v51 field)
                results[code] = {
                    'name': name,
                    'price': price,
                    'open': open_p,
                    'high': high,
                    'low': low,
                    'yclose': yclose,
                    'volume': vol,
                    'amount': amount,
                    'turnover': turnover,
                    'change_pct': change_pct,
                }
        except Exception as e:
            continue
    return results

def fetch_em_quote(code):
    prefix = '1' if code.startswith('6') else '0'
    secid = f"{prefix}.{code}"
    url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f44,f45,f46,f47,f48,f57,f58,f60,f116,f117,f168,f170,f171"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'Referer': 'https://quote.eastmoney.com/',
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return data.get('data', {})
    except Exception as e:
        return None

def fetch_em_trends(code):
    prefix = '1' if code.startswith('6') else '0'
    secid = f"{prefix}.{code}"
    url = f"https://push2his.eastmoney.com/api/qt/stock/trends2/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58&iscr=0&ndays=1"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'Referer': 'https://quote.eastmoney.com/',
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return data.get('data', {})
    except Exception as e:
        return None

# Step 1: Tencent batch quotes
print("=== Fetching Tencent batch quotes ===")
raw = fetch_tencent_quotes(list(CANDIDATES.keys()))
tencent_data = parse_tencent_quote(raw)

for code in tencent_data:
    d = tencent_data[code]
    print(f"{code} {d['name']} price:{d['price']} change:{d['change_pct']}% open:{d['open']} high:{d['high']} low:{d['low']} vol:{d['volume']} turnover:{d['turnover']}")

# Step 2: Try Eastmoney trends for each stock
print("\n=== Fetching Eastmoney trends (with Referer) ===")
em_results = {}
for code in CANDIDATES:
    trends = fetch_em_trends(code)
    if trends:
        preClose = trends.get('preClose', 0)
        trend_list = trends.get('trends', [])
        name = CANDIDATES[code]
        print(f"{code} {name}: preClose={preClose}, trend_points={len(trend_list)}")
        if trend_list:
            print(f"  First: {trend_list[0]}")
            print(f"  Last:  {trend_list[-1]}")
        em_results[code] = {
            'preClose': preClose,
            'trends': trend_list,
        }
    else:
        print(f"{code}: No trend data")
    time.sleep(0.5)

# Save all data
output = {
    'tencent': tencent_data,
    'eastmoney_trends': {},
}

for code in em_results:
    t = em_results[code]
    output['eastmoney_trends'][code] = {
        'preClose': t['preClose'],
        'trend_count': len(t['trends']),
        'first_5': t['trends'][:5],
        'last_5': t['trends'][-5:],
        'all_trends': t['trends'],
    }

with open('/Users/jwkj/easyquant/data/ai_center/wtzq_verify_data.json', 'w') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print("\nData saved.")
