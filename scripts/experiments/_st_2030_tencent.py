"""Enrich the 10 ST candidates with tencent qt quote data."""
import json
import re
import urllib.request

CODES = [
    ("sz300301", "ST长方"),
    ("sz300716", "*ST泉为"),
    ("sz002713", "*ST东易"),
    ("sh600289", "ST信通"),
    ("sz000838", "*ST发展"),
    ("sz002822", "ST中装"),
    ("sz300831", "ST派瑞"),
    ("sh603021", "*ST华鹏"),
    ("sh605336", "*ST帅电"),
    ("sh603595", "ST东尼"),
]

opener = urllib.request.build_opener()
opener.addheaders = [
    ("User-Agent", "Mozilla/5.0"),
    ("Referer", "https://finance.qq.com"),
]

url = "http://qt.gtimg.cn/q=" + ",".join(c[0] for c in CODES)
raw = opener.open(url, timeout=10).read().decode("gbk", errors="ignore")

result = []
for line in raw.splitlines():
    m = re.match(r'v_([a-z]{2}\d+)="([^"]*)"', line)
    if not m:
        continue
    tc, payload = m.group(1), m.group(2)
    parts = payload.split("~")
    if len(parts) < 50:
        continue

    def fnum(idx):
        try:
            return float(parts[idx]) if parts[idx] else 0.0
        except ValueError:
            return 0.0

    name = parts[1]
    code = parts[2]
    cur = fnum(3)
    prev = fnum(4)
    open_p = fnum(5)
    high = fnum(33)
    low = fnum(34)
    chg = fnum(31)
    chg_pct = fnum(32)
    amount_wan = fnum(37)
    turnover = fnum(38)
    pe = fnum(39)
    mktcap_yi = fnum(44)
    float_mc_yi = fnum(45)
    pb = fnum(46)
    limit_up = fnum(47)
    limit_down = fnum(48)
    vol_lots = fnum(36)  # 量比
    row = dict(
        tencent_code=tc, code=code, name=name,
        cur=cur, prev=prev, open=open_p, high=high, low=low,
        chg=chg, chg_pct=chg_pct,
        amount_wan=amount_wan, amount_yi=amount_wan / 1e4,
        turnover_pct=turnover, vol_ratio=vol_lots,
        pe=pe, pb=pb,
        mktcap_yi=mktcap_yi, float_mc_yi=float_mc_yi,
        limit_up=limit_up, limit_down=limit_down,
        is_limit_up=abs(cur - limit_up) < 0.01 and chg_pct > 0,
        is_limit_down=abs(cur - limit_down) < 0.01 and chg_pct < 0,
        on_high=abs(cur - high) < 0.005,
    )
    result.append(row)

# preserve order
order = {c[0]: i for i, c in enumerate(CODES)}
result.sort(key=lambda r: order.get(r["tencent_code"], 999))

print(f"{'代码':<8} {'名称':<10} {'最新':>6} {'涨幅':>7} {'成交额':>8} {'换手':>6} {'流通':>8} {'涨停':>6} {'封板':>5}")
for r in result:
    flag = "涨停" if r["is_limit_up"] else ("一字" if r["is_limit_up"] and r["open"] == r["high"] else "")
    print(
        f"{r['code']:<8} {r['name']:<10} {r['cur']:>6.2f} {r['chg_pct']:>6.2f}% "
        f"{r['amount_yi']:>7.2f}亿 {r['turnover_pct']:>5.2f}% {r['float_mc_yi']:>6.2f}亿 "
        f"{r['limit_up']:>5.2f} {flag:>5}"
    )

with open("/Users/jwkj/easyquant/scripts/_st_2030_tencent.json", "w") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("SAVED")
