import json
with open('/Users/jwkj/easyquant/data/ai_center/inbox/1900_超短线复盘_2026-06-24_20260624_190024.json') as f:
    d = json.load(f)
required = ['trading_date','skill_name','job_name','job_type','run_type','source_input_ref','_meta','summary','result_payload','raw_output']
missing = [k for k in required if k not in d]
print('missing top-level keys:', missing)
for p in d['result_payload']['structured_picks']:
    fields = ['stock_code','stock_name','pick_level','reason_summary','reason_detail','sector_name','theme_tags','capital_profile','signal_context','risk_flags','entry_hint','confidence_score']
    m = [k for k in fields if k not in p]
    print(f"  {p['stock_code']} {p['stock_name']}: missing={m}, level={p['pick_level']}, tags={len(p['theme_tags'])}, risk={len(p['risk_flags'])}, cap_profile_keys={list(p['capital_profile'].keys())}")
print('raw_output length:', len(d['raw_output']))
print('hot_sectors:', len(d['summary']['hot_sectors']))
print('risk_signals:', len(d['summary']['risk_signals']))
