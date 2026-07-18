import json, subprocess
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJhZG1pbiIsImlzX2FkbWluIjp0cnVlLCJleHAiOjE3ODQzNzc5NjAsImlhdCI6MTc4Mzc3MzE2MH0.qhTOkOKwye3LjGwuTxEPNyiTX-rY47qnbd6GU03m9BM"
HDR = f"Authorization: Bearer {TOKEN}"

# 拉涨停池看结构
for kw in ["摘帽","ST板块","ST","*ST","高德","柘中","天娱","步森"]:
    out = subprocess.run(['curl','-s','-G','-H',HDR,'--data-urlencode',f'keyword={kw}','--max-time','10','http://127.0.0.1:8010/api/limit-up/search'],capture_output=True,text=True,timeout=12)
    try:
        d = json.loads(out.stdout)
        items = d.get('items',[]) if isinstance(d,dict) else []
        print(f"--- {kw} -> {len(items)} results ---")
        for it in items[:3]:
            print("   ", it if not isinstance(it,dict) else {k:it.get(k) for k in ['code','name','industry','change_percent']})
    except: print('err',kw)
