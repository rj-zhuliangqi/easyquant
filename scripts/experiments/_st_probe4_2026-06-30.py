"""补充 ST 板块整体 + 涨停信息"""
import urllib.request
import re
import json
import time

# 1) ST 板块整体走势 — 通过新浪/腾讯指数
print("=== ST 板块指数 (新浪) ===")
urls = [
    ("http://hq.sinajs.cn/list=sz399987", "新浪-hq"),  # 中证 ST 指数
]
for url, label in urls:
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.sina.com.cn",
        })
        resp = urllib.request.urlopen(req, timeout=10)
        data = resp.read().decode("gbk", errors="ignore")
        print(label, ":", data[:400])
    except Exception as e:
        print(label, "err:", e)
    time.sleep(0.5)

# 2) 通过腾讯查行业板块涨跌幅
print("\n=== 行业板块涨跌幅 (腾讯, 取 ST 板块) ===")
# 行业代码
industry_codes = [
    "BK0438",  # ST 板块
    "BK0475",  # 风险警示
    "BK0511",  # ST板块
]
for code in industry_codes:
    url = f"https://qt.gtimg.cn/q=s_pk{scode}" if False else f"https://qt.gtimg.cn/q=s_pk{code}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = resp.read().decode("gbk", errors="ignore")
        print(code, ":", data[:300])
    except Exception as e:
        print(code, "err:", e)
    time.sleep(0.5)

# 3) 通用盘面 — 上证、创业、深证成指、沪深300
print("\n=== 主要指数 (腾讯) ===")
idx = ["sh000001", "sz399001", "sz399006", "sh000300", "sh000016", "sz399905"]
url = "https://qt.gtimg.cn/q=" + ",".join(idx)
try:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk", errors="ignore")
    print(data)
except Exception as e:
    print("idx err:", e)

# 4) 全市场涨停 / 跌停家数 (akshare 失效, 通过腾讯查不行; 直接读本地 ai_runs)
print("\n=== 本地 ai_runs 历史涨停统计 ===")
import sqlite3
conn = sqlite3.connect("file:data/sector_fund_monitor.db?mode=ro", uri=True)
cur = conn.cursor()
try:
    rows = cur.execute("""
        SELECT trading_day, summary FROM ai_runs
        WHERE trading_day >= '2026-06-20'
          AND (job_name LIKE '%早盘%' OR job_name LIKE '%复盘%')
        ORDER BY trading_day DESC LIMIT 10
    """).fetchall()
    for r in rows:
        print(r[0], "->", (r[1] or "")[:150])
except Exception as e:
    print("err:", e)

# 5) 涨停板 (新浪)
print("\n=== 涨停 (新浪实时) ===")
try:
    url = "http://vip.stock.finance.sina.com.cn/quotes_service/view/cn_bill_download.php?symbol=zt&num=5&page=1&sort=ticktime&asc=0&volume=0&amount=0&type=0&day=2026-06-30"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk", errors="ignore")
    print(data[:500])
except Exception as e:
    print("zt err:", e)

# 6) 东方财富热股接口 (主题)
print("\n=== 主题热度 ===")
try:
    url = "https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=20&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:90+t:3&fields=f2,f3,f4,f8,f12,f14"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"})
    resp = urllib.request.urlopen(req, timeout=10)
    print(resp.read().decode("utf-8", errors="ignore")[:500])
except Exception as e:
    print("hot err:", e)