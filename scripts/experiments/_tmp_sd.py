import json, subprocess
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJhZG1pbiIsImlzX2FkbWluIjp0cnVlLCJleHAiOjE3ODQzNzc5NjAsImlhdCI6MTc4Mzc3MzE2MH0.qhTOkOKwye3LjGwuTxEPNyiTX-rY47qnbd6GU03m9BM"
HDR = f"Authorization: Bearer {TOKEN}"

# 直接调 sector-stocks 用 sector_name 不同编码方式 -- 服务端可能会做DB lookup
# 先看 /api/sectors 字段, 但已知需要 sector_type, 试 industry 类型查"综合"等不靠谱
# 试 /api/sector-detail 直接给板块名
for url in [
    'http://127.0.0.1:8010/api/sector-detail?sector_name=ST%E6%9D%BF%E5%9D%97&sector_type=concept',
    'http://127.0.0.1:8010/api/sector-detail?sector_name=%E6%91%98%E5%B8%BD&sector_type=concept',
    'http://127.0.0.1:8010/api/sector-stocks?sector_name=ST%E6%9D%BF%E5%9D%97&sector_type=concept&limit=40&offset=0',
]:
    try:
        out = subprocess.run(['curl','-s','-G','-H',HDR,'--max-time','30',url],capture_output=True,text=True,timeout=35)
        print(f"--- {url[-60:]} ---")
        print(f"   code:{out.returncode} size:{len(out.stdout)}")
        print(out.stdout[:500])
    except subprocess.TimeoutExpired:
        print(f"--- {url} --- TIMEOUT")
