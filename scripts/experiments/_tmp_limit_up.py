import json, subprocess

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJhZG1pbiIsImlzX2FkbWluIjp0cnVlLCJleHAiOjE3ODQzNzc5NjAsImlhdCI6MTc4Mzc3MzE2MH0.qhTOkOKwye3LjGwuTxEPNyiTX-rY47qnbd6GU03m9BM"
HDR = f"Authorization: Bearer {TOKEN}"

# limit-up 涨停池 + 跌停 + 列表 + summary
print("=== /api/limit-up/dates ===")
out = subprocess.run(['curl','-s','-G','-H',HDR,'--max-time','8','http://127.0.0.1:8010/api/limit-up/dates'], capture_output=True,text=True,timeout=10)
print(out.stdout[:600])

print("\n=== /api/limit-up/summary ===")
out = subprocess.run(['curl','-s','-G','-H',HDR,'--max-time','8','http://127.0.0.1:8010/api/limit-up/summary'],capture_output=True,text=True,timeout=10)
print(out.stdout[:1500])

print("\n=== /api/limit-up/search 搜索 ST ===")
out = subprocess.run(['curl','-s','-G','-H',HDR,'--data-urlencode','keyword=ST','--max-time','8','http://127.0.0.1:8010/api/limit-up/search'],capture_output=True,text=True,timeout=10)
print(out.stdout[:1500])

print("\n=== /api/limit-up/ladder ===")
out = subprocess.run(['curl','-s','-G','-H',HDR,'--max-time','8','http://127.0.0.1:8010/api/limit-up/ladder'],capture_output=True,text=True,timeout=10)
print(out.stdout[:1500])

print("\n=== /api/limit-up/temperature ===")
out = subprocess.run(['curl','-s','-G','-H',HDR,'--max-time','8','http://127.0.0.1:8010/api/limit-up/temperature'],capture_output=True,text=True,timeout=10)
print(out.stdout[:1500])
