import json, subprocess

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJhZG1pbiIsImlzX2FkbWluIjp0cnVlLCJleHAiOjE3ODQzNzc5NjAsImlhdCI6MTc4Mzc3MzE2MH0.qhTOkOKwye3LjGwuTxEPNyiTX-rY47qnbd6GU03m9BM"
HDR = f"Authorization: Bearer {TOKEN}"

# 首页 + 系统摘要 + overview
for ep in ['/api/home/market-overview','/api/home/system-summary','/api/home/status','/api/overview?sector_type=industry']:
    out = subprocess.run(['curl','-s','-G','-H',HDR,'--max-time','8',f'http://127.0.0.1:8010{ep}'],capture_output=True,text=True,timeout=12)
    print(f"=== {ep} ===")
    print(out.stdout[:1200])
    print()
