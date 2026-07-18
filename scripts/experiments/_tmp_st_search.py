import json, subprocess

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJhZG1pbiIsImlzX2FkbWluIjp0cnVlLCJleHAiOjE3ODQzNzc5NjAsImlhdCI6MTc4Mzc3MzE2MH0.qhTOkOKwye3LjGwuTxEPNyiTX-rY47qnbd6GU03m9BM"

# 常用ST股名片段
keywords = ["长方","金科","金鸿","中天","康美","中珠","昌鱼","天娱","步森","宏图","华讯","全筑","大集","天成","银河","普华","如意","金洲","海源","博天","中润","嘉应","国美","华夏","新海","美讯","亚太","金圆","泛海","庞大","海航","永泰","西水","实达","信通","南卫","瑞茂","中捷","华塑","豆神","华英","中房","金科"]

hits = []
seen = set()
for kw in keywords:
    try:
        out = subprocess.run(['curl','-s','-G','-H',f'Authorization: Bearer {TOKEN}',
                              '--data-urlencode',f'keyword={kw}','--data-urlencode','limit=10',
                              'http://127.0.0.1:8010/api/stock-search'],capture_output=True,text=True,timeout=6)
        d = json.loads(out.stdout)
        items = d.get('items',[]) if isinstance(d,dict) else []
        for s in items:
            if not isinstance(s,dict): continue
            code = s.get('code','') or s.get('stock_code','')
            name = s.get('name','') or s.get('stock_name','')
            if 'ST' in name or '*ST' in name:
                key = (code,name)
                if key not in seen:
                    seen.add(key)
                    hits.append({'code':code,'name':name})
    except Exception as e:
        pass

print(f"找到ST相关: {len(hits)}")
for h in hits[:50]:
    print(h)
