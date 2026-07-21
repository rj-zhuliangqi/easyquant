import json, subprocess

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJhZG1pbiIsImlzX2FkbWluIjp0cnVlLCJleHAiOjE3ODQzNzc5NjAsImlhdCI6MTc4Mzc3MzE2MH0.qhTOkOKwye3LjGwuTxEPNyiTX-rY47qnbd6GU03m9BM"
HDR = f"Authorization: Bearer {TOKEN}"

def fetch_all(sector_name, max_count=260):
    all_items = []
    for offset in range(0, max_count, 50):
        qname = sector_name  # already urlencoded
        url = f'http://127.0.0.1:8010/api/sector-stocks?sector_name={qname}&sector_type=concept&limit=50&offset={offset}'
        try:
            out = subprocess.run(['curl','-s','-G','-H',HDR,'--max-time','20',url],capture_output=True,text=True,timeout=25)
            d = json.loads(out.stdout)
            items = d.get('items', d.get('stocks', []))
            all_items.extend(items)
            total = d.get('total', None)
            print(f"  offset={offset} got={len(items)} total={total}")
            if total and offset + len(items) >= total: break
        except Exception as e:
            print(f"  offset={offset} ERR: {e}")
    # 去重
    seen = set()
    uniq = []
    for it in all_items:
        if not isinstance(it, dict): continue
        k = (it.get('代码'), it.get('名称'))
        if k not in seen:
            seen.add(k); uniq.append(it)
    return uniq

# ST板块
st_items = fetch_all("ST%E6%9D%BF%E5%9D%97")
zt_items = fetch_all("%E6%91%98%E5%B8%BD")

print(f"\n去重后 ST={len(st_items)} 摘帽={len(zt_items)}")
if st_items:
    print("ST样例:", st_items[0])
    # 涨幅排序
    def pct(x):
        try: return float(x.get('今日涨跌幅', 0))
        except: return 0
    st_sorted = sorted(st_items, key=pct, reverse=True)
    print("\n=== ST板块 涨幅 Top 15 ===")
    for s in st_sorted[:15]:
        print(f"  {s.get('代码')} {s.get('名称')}  {pct(s):+.2f}% 价:{s.get('最新价')} 流入:{s.get('今日主力净流入-净额')}")

    print("\n=== ST板块 跌幅 Top 10 ===")
    for s in st_sorted[-10:]:
        print(f"  {s.get('代码')} {s.get('名称')}  {pct(s):+.2f}% 价:{s.get('最新价')}")

print()
if zt_items:
    def pct2(x):
        try: return float(x.get('今日涨跌幅', 0))
        except: return 0
    zt_sorted = sorted(zt_items, key=pct2, reverse=True)
    print("=== 摘帽板块 涨幅 Top 15 ===")
    for s in zt_sorted[:15]:
        print(f"  {s.get('代码')} {s.get('名称')}  {pct2(s):+.2f}% 价:{s.get('最新价')} 流入:{s.get('今日主力净流入-净额')}")

with open('/Users/jwkj/easyquant/.tmp_st_panel.json', 'w') as f:
    json.dump({'st':st_items,'zt':zt_items}, f, ensure_ascii=False, default=str)
print("\n已保存 .tmp_st_panel.json")
