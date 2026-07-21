import json

with open('/tmp/easyquant_market_data_2026-07-02.json') as f:
    d = json.load(f)
indivs = d['individual_rankings']['data']['diff']
scored = []
for s in indivs:
    code = s['f12']
    name = s['f14']
    pct = s['f3']
    main_in = s['f62']
    super_v = s['f66']
    big = s['f72']
    if main_in <= 0:
        continue
    if pct >= 9.5:
        continue
    if pct < 0.5:
        continue
    score = main_in / 1e8
    if super_v > 0 and big > 0:
        score += 0.5
    if super_v / main_in > 0.5:
        score += 0.3
    scored.append({'code': code, 'name': name, 'pct': pct, 'main_in': main_in, 'super': super_v, 'big': big, 'score': score})
scored.sort(key=lambda x: -x['score'])
print('=== Top 30 by score ===')
for c in scored[:30]:
    print(f"{c['code']} {c['name']:<8} pct={c['pct']:>5.2f}% main={c['main_in']/1e8:>6.3f}Y sup={c['super']/1e8:>5.2f}Y big={c['big']/1e8:>5.2f}Y score={c['score']:>5.2f}")
