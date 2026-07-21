"""逐个查询 ST 行情"""
import urllib.request
import re
import json
import time

CODES = [
    "000056", "000609", "000838", "002485", "002713",
    "300147", "300212", "300301", "300338", "300716",
    "300831", "600289", "600678", "600730", "600745", "603843",
]


def to_tencent(code: str) -> str:
    if code.startswith(("60", "68", "11", "13", "5")):
        return f"sh{code}"
    return f"sz{code}"


def fetch(code: str):
    sym = to_tencent(code)
    url = f"https://qt.gtimg.cn/q={sym}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = resp.read().decode("gbk", errors="ignore")
    except Exception as e:
        return {"code": code, "err": str(e)}
    m = re.search(r'v_\w+="([^"]+)"', data)
    if not m:
        return {"code": code, "raw": data[:120]}
    parts = m.group(1).split("~")
    if len(parts) < 50:
        return {"code": code, "raw": data[:120]}
    try:
        chg = (float(parts[3]) - float(parts[4])) / float(parts[4]) * 100 if parts[4] else 0
    except Exception:
        chg = 0
    return {
        "code": code,
        "name": parts[1],
        "price": parts[3],
        "prev_close": parts[4],
        "open": parts[5],
        "high": parts[33],
        "low": parts[34],
        "change_pct": round(chg, 2),
        "volume_hand": parts[6],
        "amount_yuan": parts[37],
        "turnover_pct": parts[38],
        "pe": parts[39],
        "amplitude": parts[43] if len(parts) > 43 else "",
        "circulating_market_cap": parts[44] if len(parts) > 44 else "",
        "total_market_cap": parts[45] if len(parts) > 45 else "",
    }


results = []
for c in CODES:
    r = fetch(c)
    results.append(r)
    print(f"{c} {r.get('name','?'):<10} 现价={r.get('price','-'):<8} 涨幅={r.get('change_pct','-'):+}% 量={r.get('volume_hand','-')} 换手={r.get('turnover_pct','-')}")
    time.sleep(0.4)

results.sort(key=lambda x: x.get("change_pct", -999), reverse=True)
with open("data/ai_center/inbox/.tmp_st_tencent.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\nSaved {len(results)} rows")