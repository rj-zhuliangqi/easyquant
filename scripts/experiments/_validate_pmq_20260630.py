#!/usr/bin/env python3
"""Final validation of the JSON output."""
import json
import sys

path = '/Users/jwkj/easyquant/data/ai_center/inbox/0820_盘前消息面挖掘_2026-06-30_20260630_082023.json'
try:
    with open(path) as f:
        d = json.load(f)
except Exception as e:
    print(f"FAIL: cannot parse: {e}")
    sys.exit(1)

print(f"OK: parsed {path}")
print(f"  top-level keys: {list(d.keys())}")
print(f"  summary keys: {list(d['summary'].keys())}")
print(f"  result_payload keys: {list(d['result_payload'].keys())}")
print(f"  headline_items: {len(d['result_payload']['headline_items'])}")
print(f"  structured_picks: {len(d['result_payload']['structured_picks'])}")
for p in d['result_payload']['structured_picks']:
    fields_ok = all(k in p for k in ['stock_code', 'stock_name', 'pick_level', 'reason_summary', 'reason_detail', 'sector_name', 'theme_tags', 'capital_profile', 'signal_context', 'risk_flags', 'entry_hint', 'confidence_score'])
    print(f"  - {p['stock_code']} {p['stock_name']} ({p['pick_level']}) fields={fields_ok} tags={len(p['theme_tags'])} risks={len(p['risk_flags'])} cap_keys={list(p['capital_profile'].keys())}")
ro = d['raw_output']
print(f"  raw_output length: {len(ro)} chars")
checks = {
    'h2': '<h2>' in ro,
    'table': '<table>' in ro,
    'risk-box': 'class="risk-box"' in ro,
    'alert-good': 'class="alert-good"' in ro,
    'alert-bad': 'class="alert-bad"' in ro,
    'stock span': 'class="stock"' in ro,
    'sector span': 'class="sector"' in ro,
    'highlight': 'class="highlight"' in ro,
    'inflow': 'class="inflow"' in ro,
    'outflow': 'class="outflow"' in ro,
    'tag': 'class="tag"' in ro,
    'up': 'class="up"' in ro,
    'down': 'class="down"' in ro,
    'limit-up': 'class="limit-up"' in ro,
    'hr': '<hr>' in ro,
    'no html/body/head outer': '<html' not in ro and '<body' not in ro and '<head' not in ro,
}
for k, v in checks.items():
    print(f"  {k}: {v}")