import json
with open('/mnt/d/easyquant/data/ai_center/inbox/1450_尾盘选股_2026-06-09_20260609_145025.json') as f:
    d = json.load(f)
required = ['trading_date','skill_name','job_name','job_type','run_type','source_input_ref','_meta','summary','result_payload','raw_output']
for r in required:
    assert r in d, 'Missing: ' + r
picks = d['result_payload']['structured_picks']
pick_fields = ['stock_code','stock_name','pick_level','reason_summary','reason_detail','sector_name','theme_tags','capital_profile','signal_context','risk_flags','entry_hint','confidence_score']
for i, p in enumerate(picks):
    for f in pick_fields:
        assert f in p, 'Pick %d missing: %s' % (i, f)
    assert isinstance(p['theme_tags'], list) and len(p['theme_tags']) > 0
    assert isinstance(p['risk_flags'], list) and len(p['risk_flags']) > 0
    assert isinstance(p['capital_profile'], dict) and len(p['capital_profile']) > 0
    assert 0.1 <= p['confidence_score'] <= 0.99
    assert p['pick_level'] in ['watch','candidate','confirm','strong_recommend']
print('Validation passed!')
for p in picks:
    print('  %-18s %s %s conf=%.2f' % (p['pick_level'], p['stock_code'], p['stock_name'], p['confidence_score']))
