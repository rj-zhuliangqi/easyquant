"""Fetch ST market data via local backend API."""
import json
import urllib.request

API = "http://127.0.0.1:8010"

def login():
    req = urllib.request.Request(
        f"{API}/api/auth/login",
        data=json.dumps({"username": "admin", "password": "admin123"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=8).read())["access_token"]


def api_get(path, token):
    req = urllib.request.Request(f"{API}{path}", headers={"Authorization": f"Bearer {token}"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read())


def main():
    token = login()
    print("TOKEN_OK", len(token))
    out = {}
    for name, path in [
        ("overview", "/api/overview"),
        ("st_concept", "/api/sector-stocks?sector_name=ST板块&sector_type=concept&limit=50"),
        ("st_concept2", "/api/sector-stocks?sector_name=ST&sector_type=concept&limit=50"),
        ("sectors_top", "/api/sectors/top?limit=20"),
        ("trade_date", "/api/trade-date"),
    ]:
        try:
            out[name] = api_get(path, token)
            print(name, "OK", str(out[name])[:200])
        except Exception as e:
            out[name] = {"error": str(e)}
            print(name, "ERR", e)
    with open("/Users/jwkj/easyquant/scripts/_st_2030_local.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("SAVED")


if __name__ == "__main__":
    main()
