import json, os
path = '/Users/jwkj/easyquant/data/ai_center/inbox/2130_每日持仓复盘_2026-06-26_20260626_213023.json'
with open(path, 'r', encoding='utf-8') as f:
    d = json.load(f)
print('=== 最终校验 ===')
print('FILE OK, size:', os.path.getsize(path), 'bytes')
print('trading_date:', d['trading_date'])
print('picks:', len(d['result_payload']['structured_picks']))
for p in d['result_payload']['structured_picks']:
    print(f"  {p['stock_code']} {p['stock_name']} ({p['pick_level']}, conf={p['confidence_score']})")
print('raw_output chars:', len(d['raw_output']))
all_classes = ['up','down','limit-up','limit-down','sector','stock','highlight','inflow','outflow','tag']
for c in all_classes:
    needle = '<span class="' + c + '">'
    print(f'  span.{c}: {d["raw_output"].count(needle)}')
for cls in ['alert-good', 'alert-bad', 'risk-box']:
    needle = '<div class="' + cls + '">'
    print(f'  div.{cls}: {d["raw_output"].count(needle)}')
print('  <table>:', d['raw_output'].count('<table>'))
print('  <hr>:', d['raw_output'].count('<hr>'))
print('  <h2>:', d['raw_output'].count('<h2>'))
print('  <h3>:', d['raw_output'].count('<h3>'))
