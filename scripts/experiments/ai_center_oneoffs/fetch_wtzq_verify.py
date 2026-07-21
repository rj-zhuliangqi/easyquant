import json
import urllib.request
import sys
import time

# Candidate stocks to verify
CANDIDATES = [
    "002575",  # 群兴玩具
    "301526",  # 国际复材
    "300304",  # 云意电气
    "688711",  # 宏微科技
    "000970",  # 中科三环
    "603011",  # 合锻智能
    "301488",  # 豪恩汽电
    "002851",  # 麦格米特
    "300657",  # 弘信电子
    "301511",  # 德福科技
    "000636",  # 风华高科
    "000063",  # 中兴通讯
]

# Market prefix mapping for eastmoney
def get_market_prefix(code):
    if code.startswith('6'):
        return '1'
    elif code.startswith('0') or code.startswith('3'):
        return '0'
    elif code.startswith('688') or code.startswith('689'):
        return '1'
    return '0'

# Fetch real-time quote from eastmoney
def fetch_realtime_quote(code):
    prefix = get_market_prefix(code)
    secid = f"{prefix}.{code}"
    url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f44,f45,f46,f47,f48,f50,f51,f52,f55,f57,f58,f60,f116,f117,f162,f167,f168,f169,f170,f171,f292"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return data.get('data', {})
    except Exception as e:
        print(f"Error fetching {code}: {e}", file=sys.stderr)
        return None

# Fetch minute-level data for the day
def fetch_minute_data(code):
    prefix = get_market_prefix(code)
    secid = f"{prefix}.{code}"
    url = f"https://push2his.eastmoney.com/api/qt/stock/trends2/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58&iscr=0&ndays=1"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return data.get('data', {})
    except Exception as e:
        print(f"Error fetching minute data for {code}: {e}", file=sys.stderr)
        return None

# Fetch capital flow data
def fetch_capital_flow(code):
    prefix = get_market_prefix(code)
    secid = f"{prefix}.{code}"
    url = f"https://push2.eastmoney.com/api/qt/stock/fflow/kline/get?secid={secid}&fields1=f1,f2,f3,f7&fields2=f51,f52,f53,f54,f55&klt=1&lmt=0"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return data.get('data', {})
    except Exception as e:
        print(f"Error fetching capital flow for {code}: {e}", file=sys.stderr)
        return None

results = {}

for code in CANDIDATES:
    print(f"\n=== Fetching {code} ===")
    time.sleep(0.3)

    # Real-time quote
    quote = fetch_realtime_quote(code)
    minute = fetch_minute_data(code)
    time.sleep(0.3)
    capflow = fetch_capital_flow(code)
    time.sleep(0.3)

    info = {
        'code': code,
        'quote': {},
        'trends': {},
        'capital_flow': {},
        'confirm_signals': {}
    }

    if quote:
        info['quote'] = {
            'name': quote.get('f58', ''),
            'price': quote.get('f43', 0) / 100 if quote.get('f43', 0) > 1000 else quote.get('f43', 0),
            'change_pct': quote.get('f170', 0) / 100 if quote.get('f170', 0) else 0,
            'high': quote.get('f44', 0) / 100 if quote.get('f44', 0) > 1000 else quote.get('f44', 0),
            'low': quote.get('f45', 0) / 100 if quote.get('f45', 0) > 1000 else quote.get('f45', 0),
            'open': quote.get('f46', 0) / 100 if quote.get('f46', 0) > 1000 else quote.get('f46', 0),
            'volume': quote.get('f47', 0),
            'amount': quote.get('f48', 0),
            'turnover': quote.get('f168', 0) / 100 if quote.get('f168', 0) else 0,
            'pe': quote.get('f167', 0) / 100 if quote.get('f167', 0) else 0,
            'market_cap': quote.get('f116', 0),
            'main_net_inflow': quote.get('f62', 0),
        }

    if minute:
        preClose = minute.get('preClose', 0)
        trends = minute.get('trends', [])
        info['trends'] = {
            'preClose': preClose,
            'count': len(trends),
            'first_5': trends[:5] if trends else [],
            'last_5': trends[-5:] if trends else [],
        }

        # Analyze trend patterns for confirmation
        if len(trends) >= 10:
            # Check if price sustained above VWAP
            prices = []
            volumes = []
            avg_prices = []
            for t in trends:
                parts = t.split(',')
                if len(parts) >= 6:
                    try:
                        p = float(parts[1])
                        v = int(parts[4])
                        ap = float(parts[5]) if len(parts) > 5 else p
                        prices.append(p)
                        volumes.append(v)
                        avg_prices.append(ap)
                    except:
                        pass

            if prices:
                current_price = prices[-1]
                vwap = avg_prices[-1] if avg_prices else sum(prices) / len(prices)
                open_price = prices[0]
                high_price = max(prices)
                low_price = min(prices)

                # Signal 1: Price above VWAP (sustained strength)
                above_vwap = current_price >= vwap

                # Signal 2: Volume pattern - check if volume is sustained (not just opening spike)
                if len(volumes) >= 10:
                    first_10_min_vol = sum(volumes[:10])
                    recent_10_min_vol = sum(volumes[-10:])
                    vol_sustained = recent_10_min_vol >= first_10_min_vol * 0.3
                else:
                    vol_sustained = True

                # Signal 3: Price trend - higher lows after 9:40
                if len(prices) > 20:
                    # Check prices from index 10 onward (after 9:40)
                    post_940 = prices[10:]
                    if len(post_940) >= 5:
                        lows_in_segments = []
                        seg_size = max(1, len(post_940) // 5)
                        for i in range(5):
                            seg = post_940[i*seg_size:(i+1)*seg_size]
                            if seg:
                                lows_in_segments.append(min(seg))
                        higher_lows = all(lows_in_segments[i] >= lows_in_segments[i-1] * 0.998 for i in range(1, len(lows_in_segments)))
                    else:
                        higher_lows = True
                else:
                    higher_lows = True

                # Signal 4: No sharp reversal (price not dropping >1% from high)
                drop_from_high = (high_price - current_price) / high_price * 100 if high_price > 0 else 0
                no_sharp_reversal = drop_from_high < 2.0

                info['confirm_signals'] = {
                    'above_vwap': above_vwap,
                    'vwap': round(vwap, 2),
                    'current_vs_vwap': round((current_price - vwap) / vwap * 100, 2),
                    'vol_sustained': vol_sustained,
                    'higher_lows': higher_lows,
                    'no_sharp_reversal': no_sharp_reversal,
                    'drop_from_high_pct': round(drop_from_high, 2),
                    'open_price': open_price,
                    'current_price': current_price,
                    'high_price': high_price,
                    'low_price': low_price,
                }

    if capflow:
        klines = capflow.get('klines', [])
        info['capital_flow'] = {
            'count': len(klines),
            'last_10': klines[-10:] if klines else [],
        }

        # Analyze capital flow pattern
        if klines:
            inflows = []
            for k in klines:
                parts = k.split(',')
                if len(parts) >= 4:
                    try:
                        # f51=time, f52=main_inflow, f53=main_outflow, f54=main_net
                        net = float(parts[3]) if len(parts) > 3 else 0
                        inflows.append(net)
                    except:
                        pass

            if inflows:
                total_net = sum(inflows)
                positive_count = sum(1 for x in inflows if x > 0)
                # Check if 9:40-10:05 capital flow is sustained
                recent_nets = inflows[-15:] if len(inflows) >= 15 else inflows
                recent_positive = sum(1 for x in recent_nets if x > 0)
                sustained_inflow = recent_positive >= len(recent_nets) * 0.5

                info['confirm_signals']['capital_sustained'] = sustained_inflow
                info['confirm_signals']['total_net_flow'] = round(total_net, 2)
                info['confirm_signals']['positive_ratio'] = round(positive_count / len(inflows) * 100, 1)

    results[code] = info
    print(f"  Name: {info['quote'].get('name', 'N/A')}")
    print(f"  Price: {info['quote'].get('price', 'N/A')}, Change: {info['quote'].get('change_pct', 'N/A')}%")
    print(f"  Signals: {json.dumps(info['confirm_signals'], ensure_ascii=False, indent=2)}")

# Save results
output_path = '/Users/jwkj/easyquant/data/ai_center/wtzq_verify_data.json'
with open(output_path, 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\nResults saved to {output_path}")
