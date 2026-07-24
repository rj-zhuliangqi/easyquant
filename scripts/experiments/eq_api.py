import requests, json
t = requests.post('http://127.0.0.1:8010/api/auth/login', json={'username':'admin','password':'admin123'}, timeout=5).json()['access_token']
H = {'Authorization': f'Bearer {t}'}
for ep in ['/api/overview','/api/individual-rankings','/api/monitor-signals','/api/limit-up/ladder','/api/market-pulse']:
    try:
        r = requests.get(f'http://127.0.0.1:8010{ep}', headers=H, timeout=15)
        print(ep, r.status_code, len(r.text))
        if r.status_code == 200:
            with open(f'/Users/jwkj/easyquant/.tmp_{ep.replace("/","_")}.json','w') as f:
                f.write(r.text)
    except Exception as e:
        print(ep, 'ERR', repr(e))