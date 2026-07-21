"""Comprehensive ST data fetch via local backend."""
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


def api_get(path, token):
    if "?" in path:
        base, qs = path.split("?", 1)
        params = urllib.parse.parse_qs(qs)
        path = base + "?" + urllib.parse.urlencode(params, doseq=True)
    full = f"{API}{path}"
    req = urllib.request.Request(full, headers={"Authorization": f"Bearer {token}"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def main():
    token = login()
    out = {}
    # Get bigger ST sector list, sorted by change desc / asc
    paths = {
        "st_top_gain": "/api/sector-stocks?sector_name=ST&sector_type=concept&limit=50&sort_by=change_percent&sort_order=desc",
        "st_top_loss": "/api/sector-stocks?sector_name=ST&sector_type=concept&limit=50&sort_by=change_percent&sort_order=asc",
        "st_top_amt": "/api/sector-stocks?sector_name=ST&sector_type=concept&limit=50&sort_by=net_inflow&sort_order=desc",
        "st_top_outflow": "/api/sector-stocks?sector_name=ST&sector_type=concept&limit=50&sort_by=net_inflow&sort_order=asc",
        "st_default": "/api/sector-stocks?sector_name=ST板块&sector_type=concept&limit=50",
        "st_em_zhaimao": "/api/sector-stocks?sector_name=ST摘帽&sector_type=concept&limit=30",
        "st_reorg": "/api/sector-stocks?sector_name=重组&sector_type=concept&limit=30",
    }
    for name, p in paths.items():
        try:
            r = api_get(p, token)
            out[name] = r
            n = len(r.get("stocks", []))
            print(name, "OK total=", r.get("total"), "stocks=", n)
        except Exception as e:
            print(name, "ERR", e)
            out[name] = {"error": str(e)}

    # Try other endpoints
    for ep in ["/api/sectors", "/api/sectors/concept", "/api/sectors/concept?limit=20",
               "/api/sector-pulse", "/api/market/snapshot", "/api/market/overview",
               "/api/calendar/today"]:
        try:
            r = api_get(ep, token)
            out[ep] = r
            print(ep, "OK keys=", list(r.keys())[:8] if isinstance(r, dict) else type(r).__name__)
        except Exception as e:
            print(ep, "ERR", str(e)[:80])

    with open("/Users/jwkj/easyquant/scripts/_st_2030_full.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
