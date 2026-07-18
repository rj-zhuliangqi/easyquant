import json
import sys

p = '/Users/jwkj/easyquant/data/ai_center/inbox/0940_弱转强-候选筛选_2026-07-02_20260702_094007.json'
try:
    with open(p) as f:
        d = json.load(f)
    print('JSON valid!')
    print(f"keys: {list(d.keys())}")
    print(f"trading_date: {d['trading_date']}")
    print(f"skill_name: {d['skill_name']}")
    print(f"job_name: {d['job_name']}")
    print(f"job_type: {d['job_type']}")
    print(f"run_type: {d['run_type']}")
    print(f"source_input_ref: {d['source_input_ref']}")
    print(f"_meta: {d['_meta']}")
    print(f"summary keys: {list(d['summary'].keys())}")
    print(f"hot_sectors count: {len(d['summary']['hot_sectors'])}")
    print(f"risk_signals count: {len(d['summary']['risk_signals'])}")
    print(f"structured_picks count: {len(d['result_payload']['structured_picks'])}")
    print(f"raw_output length: {len(d['raw_output'])}")
    print()
    print('=== Validating each pick has 12 fields ===')
    required_fields = ['stock_code', 'stock_name', 'pick_level', 'reason_summary', 'reason_detail',
                       'sector_name', 'theme_tags', 'capital_profile', 'signal_context',
                       'risk_flags', 'entry_hint', 'confidence_score']
    for i, p in enumerate(d['result_payload']['structured_picks']):
        missing = [f for f in required_fields if f not in p]
        if missing:
            print(f"  pick#{i} {p.get('stock_name')} MISSING: {missing}")
        else:
            print(f"  pick#{i} {p['stock_name']} OK - level={p['pick_level']} tags={len(p['theme_tags'])} risks={len(p['risk_flags'])}")
            if not isinstance(p['theme_tags'], list) or len(p['theme_tags']) == 0:
                print(f"    ! theme_tags not array or empty")
            if not isinstance(p['risk_flags'], list) or len(p['risk_flags']) == 0:
                print(f"    ! risk_flags not array or empty")
            if not isinstance(p['capital_profile'], dict) or not p['capital_profile']:
                print(f"    ! capital_profile empty")
    print()
    print('All checks passed!')
except json.JSONDecodeError as e:
    print(f'JSON ERROR: {e}')
    sys.exit(1)
