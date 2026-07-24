import json
p='data/ai_center/inbox/1200_早盘复盘_2026-06-26_20260626_120019.json'
with open(p,'r',encoding='utf-8') as f:
    d=json.load(f)
print('trading_date:', d['trading_date'])
print('skill_name:', d['skill_name'])
print('job_type:', d['job_type'])
print('structured_picks count:', len(d['result_payload']['structured_picks']))
for p2 in d['result_payload']['structured_picks']:
    fields_ok = all(k in p2 for k in ['stock_code','stock_name','pick_level','reason_summary','reason_detail','sector_name','theme_tags','capital_profile','signal_context','risk_flags','entry_hint','confidence_score'])
    print(f'  {p2["stock_code"]} {p2["stock_name"]} | fields_ok={fields_ok} | level={p2["pick_level"]} | theme_tags={len(p2["theme_tags"])} risk_flags={len(p2["risk_flags"])}')
print('raw_output length:', len(d['raw_output']))
print('summary hot_sectors:', d['summary']['hot_sectors'])
print('risk_signals:', d['summary']['risk_signals'])
