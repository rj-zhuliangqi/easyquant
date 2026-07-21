"""通过腾讯 + 本地数据库获取 ST 列表与行情"""
import sqlite3
import urllib.request
import json
import re

DB = "data/sector_fund_monitor.db"

# 1) 本地 db 取所有代码/名称，过滤 ST/*ST
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
cur = conn.cursor()
try:
    rows = cur.execute("SELECT code, name FROM stock_basic ORDER BY code").fetchall()
except Exception as e:
    print("stock_basic miss:", e)
    rows = []
print("stock_basic rows:", len(rows))

st_stocks = [(c, n) for c, n in rows if ("ST" in (n or "") or "退" in (n or ""))]
print(f"ST like in stock_basic: {len(st_stocks)}")
for c, n in st_stocks[:40]:
    print(c, n)

# 2) 兜底：ai_picks 表里搜历史 ST 标的
try:
    pks = cur.execute(
        "SELECT DISTINCT stock_code, stock_name FROM ai_picks WHERE stock_name LIKE '%ST%' OR stock_name LIKE '%退%' ORDER BY stock_code"
    ).fetchall()
    print(f"\nai_picks ST: {len(pks)}")
    for c, n in pks[:60]:
        print(c, n)
except Exception as e:
    print("ai_picks err:", e)

# 3) 腾讯行情批量拉
codes = [c for c, _ in st_stocks[:50]]
# 腾讯代码转换：6 位数字 → sh600000 / sz000000
def to_tencent(code: str) -> str:
    if code.startswith(("60", "68", "11", "13", "5")):
        return f"sh{code}"
    if code.startswith(("00", "30", "12", "20")):
        return f"sz{code}"
    if code.startswith(("8", "4")):
        return f"bj{code}"
    return f"sh{code}"

q = "=".join([to_tencent(c) for c in codes])
url = f"https://qt.gtimg.cn/q={q}"
print("\n=== 腾讯行情 ===")
try:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=15)
    data = resp.read().decode("gbk", errors="ignore")
    lines = data.strip().split("\n")
    out = []
    for line in lines:
        m = re.match(r'v_(\w+)="([^"]+)"', line)
        if not m:
            continue
        sym, payload = m.groups()
        parts = payload.split("~")
        if len(parts) < 50:
            continue
        code = sym[2:]
        name = parts[1]
        price = parts[3]
        prev_close = parts[4]
        open_p = parts[5]
        volume = parts[6]  # 手
        try:
            chg = (float(price) - float(prev_close)) / float(prev_close) * 100 if prev_close and float(prev_close) else 0
        except Exception:
            chg = 0
        out.append({
            "code": code,
            "name": name,
            "price": price,
            "prev_close": prev_close,
            "open": open_p,
            "change_pct": round(chg, 2),
            "high": parts[33] if len(parts) > 33 else "",
            "low": parts[34] if len(parts) > 34 else "",
            "volume_hand": volume,
            "amount_yuan": parts[37] if len(parts) > 37 else "",
            "turnover_pct": parts[38] if len(parts) > 38 else "",
            "pe": parts[39] if len(parts) > 39 else "",
        })
    # 排序按涨幅倒序
    out.sort(key=lambda x: x["change_pct"], reverse=True)
    for r in out:
        print(f"{r['code']} {r['name']:<10} 现价={r['price']:<8} 涨幅={r['change_pct']:+.2f}% 量={r['volume_hand']} 换手={r['turnover_pct']}")
    with open("data/ai_center/inbox/.tmp_st_tencent.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\nSaved {len(out)} rows to .tmp_st_tencent.json")
except Exception as e:
    print("tencent err:", e)

conn.close()