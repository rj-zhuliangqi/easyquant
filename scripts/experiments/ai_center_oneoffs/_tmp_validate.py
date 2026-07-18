import json
p = '/Users/jwkj/easyquant/data/ai_center/inbox/2130_每日持仓复盘_2026-06-24_20260624_213024.json'
d = json.load(open(p))
assert d['trading_date']=='2026-06-24'
picks = d['result_payload']['structured_picks']
for pp in picks:
    required = ['stock_code','stock_name','pick_level','reason_summary','reason_detail','sector_name','theme_tags','capital_profile','signal_context','risk_flags','entry_hint','confidence_score']
    missing = [k for k in required if k not in pp]
    assert not missing, f"{pp['stock_code']} missing {missing}"
    assert isinstance(pp['theme_tags'], list) and pp['theme_tags']
    assert isinstance(pp['risk_flags'], list) and pp['risk_flags']
    assert isinstance(pp['capital_profile'], dict) and pp['capital_profile']
    assert pp['pick_level'] in ('watch','candidate','confirm','strong_recommend')
print('Validation OK -', len(picks), 'picks')
print('Levels:', {pl: sum(1 for x in picks if x['pick_level']==pl) for pl in ['strong_recommend','confirm','candidate','watch']})
print('skill_name:', d['skill_name'])
print('job_name:', d['job_name'])
print('job_type:', d['job_type'])
print('raw_output length:', len(d['raw_output']))
print('summary keys:', list(d['summary'].keys()))
