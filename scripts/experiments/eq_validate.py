import json
with open('/Users/jwkj/easyquant/data/ai_center/inbox/0926_集合竞价分析_2026-07-18_20260718_092622.json') as f:
    d=json.load(f)
print('OK trading_date:',d['trading_date'])
print('skill_name:',d['skill_name'])
print('picks count:',len(d['result_payload']['structured_picks']))
for p in d['result_payload']['structured_picks']:
    print(f"  {p['pick_level']:<18} {p['stock_code']} {p['stock_name']:<10} theme={p['theme_tags']}")
print('raw_output len:',len(d['raw_output']))
required=['stock_code','stock_name','pick_level','reason_summary','reason_detail','sector_name','theme_tags','capital_profile','signal_context','risk_flags','entry_hint','confidence_score']
for i,p in enumerate(d['result_payload']['structured_picks']):
    miss=[k for k in required if k not in p]
    print(f'pick#{i} missing:',miss if miss else 'NONE')
    assert isinstance(p['theme_tags'],list) and len(p['theme_tags'])>0
    assert isinstance(p['risk_flags'],list) and len(p['risk_flags'])>0
    assert isinstance(p['capital_profile'],dict) and len(p['capital_profile'])>0
    assert 0.1<=p['confidence_score']<=0.99
print('VALIDATION OK')