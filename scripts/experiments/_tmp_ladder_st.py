import json, subprocess

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJhZG1pbiIsImlzX2FkbWluIjp0cnVlLCJleHAiOjE3ODQzNzc5NjAsImlhdCI6MTc4Mzc3MzE2MH0.qhTOkOKwye3LjGwuTxEPNyiTX-rY47qnbd6GU03m9BM"
HDR = f"Authorization: Bearer {TOKEN}"

out = subprocess.run(['curl','-s','-G','-H',HDR,'--max-time','10','http://127.0.0.1:8010/api/limit-up/ladder'],capture_output=True,text=True,timeout=15)
d = json.loads(out.stdout)
groups = d.get('groups', [])
st_in_ladder = []
for g in groups:
    for stk in g.get('stocks', []):
        n = stk.get('name', '') or ''
        if 'ST' in n or n.startswith('*'):
            st_in_ladder.append({k:stk.get(k) for k in ['code','name','industry','change_percent','turnover','net_inflow','board_count','seal_amount']})

print(f"涨停池ST股数: {len(st_in_ladder)}")
for s in st_in_ladder:
    print(s)
