import json, sys
p='/Users/jwkj/easyquant/data/ai_center/inbox/0926_集合竞价分析_2026-06-24_20260624_092623.json'
d=json.load(open(p))
assert d['trading_date']=='2026-06-24'
assert d['skill_name']=='09:26 集合竞价分析'
assert d['job_name']=='09:26 集合竞价分析'
assert d['job_type']=='stock_pick'
for pk in d['result_payload']['structured_picks']:
    required=['stock_code','stock_name','pick_level','reason_summary','reason_detail','sector_name','theme_tags','capital_profile','signal_context','risk_flags','entry_hint','confidence_score']
    for k in required:
        assert k in pk, f'missing {k}'
    assert pk['pick_level'] in ('watch','candidate','confirm','strong_recommend')
    assert isinstance(pk['theme_tags'],list) and len(pk['theme_tags'])>0
    assert isinstance(pk['risk_flags'],list) and len(pk['risk_flags'])>0
    assert isinstance(pk['capital_profile'],dict) and len(pk['capital_profile'])>0
print('OK picks=', len(d['result_payload']['structured_picks']))
print('raw_output_len:', len(d['raw_output']))
print('hot_sectors:', d['summary']['hot_sectors'])
