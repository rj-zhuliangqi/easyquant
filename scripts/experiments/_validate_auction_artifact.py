import json
from pathlib import Path
from collections import Counter

p = Path('/Users/jwkj/easyquant/data/ai_center/inbox/0926_集合竞价分析_2026-07-11_20260711_092623.json')
with open(p) as f:
    data = json.load(f)

required_top = ['trading_date', 'skill_name', 'job_name', 'job_type', 'run_type', 'source_input_ref', '_meta', 'summary', 'result_payload', 'raw_output']
missing_top = [k for k in required_top if k not in data]
print('Missing top keys:', missing_top)

required_pick = ['stock_code', 'stock_name', 'pick_level', 'reason_summary', 'reason_detail', 'sector_name', 'theme_tags', 'capital_profile', 'signal_context', 'risk_flags', 'entry_hint', 'confidence_score']
allowed_levels = {'watch', 'candidate', 'confirm', 'strong_recommend'}

picks = data['result_payload']['structured_picks']
print('Total picks:', len(picks))
all_ok = True
for i, p in enumerate(picks):
    miss = [k for k in required_pick if k not in p]
    if miss:
        print(f'Pick {i} missing:', miss)
        all_ok = False
        continue
    if not isinstance(p['theme_tags'], list) or len(p['theme_tags']) == 0:
        print(f'Pick {i} theme_tags empty')
        all_ok = False
    if not isinstance(p['risk_flags'], list) or len(p['risk_flags']) == 0:
        print(f'Pick {i} risk_flags empty')
        all_ok = False
    if not isinstance(p['capital_profile'], dict) or len(p['capital_profile']) == 0:
        print(f'Pick {i} capital_profile empty')
        all_ok = False
    if p['pick_level'] not in allowed_levels:
        print(f'Pick {i} invalid level:', p['pick_level'])
        all_ok = False
    if not (0.1 <= p['confidence_score'] <= 0.99):
        print(f'Pick {i} confidence out of range:', p['confidence_score'])
        all_ok = False

print('All picks valid:', all_ok)

print()
print('Skill:', data['skill_name'])
print('Job:', data['job_name'])
print('Trading date:', data['trading_date'])
print('Schema version:', data['_meta']['schema_version'])
print('Summary phase:', data['summary']['market_phase'])
print('Hot sectors:', data['summary']['hot_sectors'])
print()
print('raw_output length:', len(data['raw_output']), 'chars')
print('raw_output starts:', data['raw_output'][:80])
print()
print('Counts by level:')
levels = Counter([pp['pick_level'] for pp in picks])
for k, v in levels.items():
    print(' ', k + ':', v)

# Verify HTML in raw_output contains required tags
raw = data['raw_output']
checks = {
    'h2': raw.count('<h2>'),
    'h3': raw.count('<h3>'),
    'table': raw.count('<table>'),
    'up': raw.count('class="up"'),
    'down': raw.count('class="down"'),
    'limit-up': raw.count('class="limit-up"'),
    'sector': raw.count('class="sector"'),
    'stock': raw.count('class="stock"'),
    'highlight': raw.count('class="highlight"'),
    'inflow': raw.count('class="inflow"'),
    'outflow': raw.count('class="outflow"'),
    'alert-good': raw.count('class="alert-good"'),
    'alert-bad': raw.count('class="alert-bad"'),
    'tag': raw.count('class="tag"'),
    'risk-box': raw.count('class="risk-box"'),
    'hr': raw.count('<hr>'),
}
print()
print('HTML element counts:')
for k, v in checks.items():
    print(' ', k + ':', v)