"""Additional context: try wider ST queries and recent news/processed data."""
import json
import urllib.parse
import urllib.request

API = "http://127.0.0.1:8010"


def login():
    req = urllib.request.Request(
        f"{API}/api/auth/login",
        data=json.dumps({"username": "admin", "password": "admin123"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=8).read())["access_token"]


def api_get(path, token, timeout=20):
    req = urllib.request.Request(f"{API}{path}", headers={"Authorization": f"Bearer {token}"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def main():
    token = login()
    out = {}
    # try alternate sector names + bigger limits
    queries = [
        ("st_big", "/api/sector-stocks?sector_name=ST&sector_type=concept&limit=200"),
        ("st_em_full", "/api/sector-stocks?sector_name=ST摘帽&sector_type=concept&limit=200"),
        ("st_em_pred", "/api/sector-stocks?sector_name=" + urllib.parse.quote("摘帽预期") + "&sector_type=concept&limit=200"),
        ("st_huifu", "/api/sector-stocks?sector_name=" + urllib.parse.quote("ST摘帽") + "&sector_type=concept&limit=200"),
        ("st_qudiao", "/api/sector-stocks?sector_name=" + urllib.parse.quote("摘星脱帽") + "&sector_type=concept&limit=200"),
        ("st_pop", "/api/sector-stocks?sector_name=" + urllib.parse.quote("ST板块") + "&sector_type=concept&limit=200"),
    ]
    for name, p in queries:
        try:
            r = api_get(p, token)
            out[name] = r
            print(name, "OK total=", r.get("total"), "len=", len(r.get("stocks", [])), "sector=", r.get("sector_name"))
        except Exception as e:
            print(name, "ERR", e)
    with open("/Users/jwkj/easyquant/scripts/_st_2030_more.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    # show first sample with all rows
    if "st_big" in out:
        stocks = out["st_big"].get("stocks", [])
        print(f"--- st_big has {len(stocks)} stocks ---")
        for s in stocks[:30]:
            print(s)


if __name__ == "__main__":
    main()
