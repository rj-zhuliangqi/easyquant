import json

with open('data/ai_center/inbox/1900_超短线复盘_2026-06-18_20260618_190024.json', 'r') as f:
    data = json.load(f)

print('Top-level keys:', list(data.keys()))
print('trading_date:', data['trading_date'])
print('skill_name:', data['skill_name'])
print('job_type:', data['job_type'])
print()

picks = data['result_payload']['structured_picks']
print(f'Structured picks: {len(picks)} stocks')
required = ['stock_code','stock_name','pick_level','reason_summary','reason_detail','sector_name','theme_tags','capital_profile','signal_context','risk_flags','entry_hint','confidence_score']
for p in picks:
    missing = [k for k in required if k not in p]
    name = p.get('stock_name','?')
    if missing:
        print(f'  {name}: MISSING {missing}')
    else:
        print(f'  OK: {name}({p["stock_code"]}) level={p["pick_level"]} score={p["confidence_score"]}')
        if not p['theme_tags']:
            print(f'    WARN: theme_tags empty')
        if not p['risk_flags']:
            print(f'    WARN: risk_flags empty')

raw = data['raw_output']
print(f'\nraw_output length: {len(raw)} chars')
checks = ['<h2>','<table>','<hr>','class="up"','class="down"','class="limit-up"','class="sector"','class="stock"','class="highlight"','class="inflow"','class="outflow"','class="alert-good"','class="alert-bad"','class="risk-box"','class="tag"']
for c in checks:
    if c in raw:
        print(f'  OK: {c}')
    else:
        print(f'  MISSING: {c}')

print('\n=== SUMMARY ===')
print(json.dumps(data['summary'], ensure_ascii=False, indent=2)[:600])
