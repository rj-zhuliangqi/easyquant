import json

p = "/Users/jwkj/easyquant/data/ai_center/inbox/2130_每日持仓复盘_2026-07-18_20260718_213025.json"
d = json.load(open(p))
print("top keys:", list(d.keys()))
print("trading_date:", d["trading_date"], "| job_type:", d["job_type"], "| skill_name:", d["skill_name"])
print("summary keys:", list(d["summary"].keys()))
print("picks:", len(d["result_payload"]["structured_picks"]))
required = [
    "stock_code", "stock_name", "pick_level", "reason_summary", "reason_detail",
    "sector_name", "theme_tags", "capital_profile", "signal_context",
    "risk_flags", "entry_hint", "confidence_score",
]
for pk in d["result_payload"]["structured_picks"]:
    missing = [k for k in required if k not in pk]
    print(" ", pk["stock_code"], pk["stock_name"], pk["pick_level"],
          "fields=", len(pk), "missing=", missing,
          "tags=", len(pk["theme_tags"]), "risks=", len(pk["risk_flags"]),
          "cap=", len(pk["capital_profile"]))
print("raw_output length:", len(d["raw_output"]), "chars")
print("h2:", d["raw_output"].count("<h2>"), "table:", d["raw_output"].count("<table>"),
      "hr:", d["raw_output"].count("<hr>"), "risk-box:", d["raw_output"].count("risk-box"),
      "alert-good:", d["raw_output"].count("alert-good"), "alert-bad:", d["raw_output"].count("alert-bad"))
print("first 60 chars:", repr(d["raw_output"][:60]))
