"""Adjust auction JSON: cap total picks to 10, drop 1 watch entry."""
import json
src = "/Users/jwkj/easyquant/data/ai_center/inbox/0926_集合竞价分析_2026-07-03_20260703_092621.json"
with open(src, 'r', encoding='utf-8') as f:
    data = json.load(f)

picks = data['result_payload']['structured_picks']
# 当前 11 只: 1 strong + 2 confirm + 3 candidate + 5 watch
# 目标 10 只: 1 strong + 2 confirm + 2 candidate + 5 watch  -> 10 只
# 或: 1 strong + 2 confirm + 3 candidate + 4 watch  -> 10 只
# 优先保留 candidate（候选信号更有价值），删 1 个 watch
by_level = {}
for p in picks:
    by_level.setdefault(p['pick_level'], []).append(p)

# 调整: 保留 1+2+3 candidate(若在), 其余 watch 留 4 只
strong_n = 1
confirm_n = 2
candidate_n = 3
watch_n = 4

new_picks = []
for level, n in [('strong_recommend', strong_n), ('confirm', confirm_n), ('candidate', candidate_n), ('watch', watch_n)]:
    new_picks.extend(by_level.get(level, [])[:n])

data['result_payload']['structured_picks'] = new_picks

# 同步 raw_output 中的选股表：重渲染 <h3>九</h3>
import re
old_h3 = '<h3>九、选股清单'
end_h3 = '<h3>十、'
if old_h3 in data['raw_output']:
    start = data['raw_output'].index(old_h3)
    end = data['raw_output'].index(end_h3)
    head = data['raw_output'][:start]
    tail = data['raw_output'][end:]

    def pct_html(v):
        cls = 'up' if v > 0 else ('down' if v < 0 else 'highlight')
        sign = '+' if v > 0 else ''
        return f'<span class="{cls}">{sign}{v:.2f}%</span>'

    def stock_html(name):
        return f'<span class="stock">{name}</span>'

    def sector_html(name):
        return f'<span class="sector">{name}</span>'

    def tag_html(s):
        return f'<span class="tag">{s}</span>'

    table = '<table><tr><th>代码</th><th>名称</th><th>竞价涨幅</th><th>净流入</th><th>板块</th><th>级别</th><th>主题</th></tr>'
    for p in new_picks:
        try:
            auction_pct = float(p['reason_summary'].split('竞价高开')[1].split('%')[0])
        except Exception:
            auction_pct = 0
        table += (
            f'<tr>'
            f'<td>{p["stock_code"]}</td>'
            f'<td>{stock_html(p["stock_name"])}</td>'
            f'<td>{pct_html(auction_pct)}</td>'
            f'<td>{pct_html(p["capital_profile"]["net_inflow"])}</td>'
            f'<td>{sector_html(p["sector_name"])}</td>'
            f'<td>{p["pick_level"]}</td>'
            f'<td>{" ".join(tag_html(t) for t in p["theme_tags"])}</td>'
            f'</tr>'
        )
    table += '</table>'

    new_section = f'<h3>九、选股清单（共 {len(new_picks)} 只）</h3>\n{table}\n\n'
    data['raw_output'] = head + new_section + tail

with open(src, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f'调整后总数: {len(new_picks)}')
for p in new_picks:
    print(f'  [{p["pick_level"]}] {p["stock_code"]} {p["stock_name"]}')
print(f'已重写: {src}')
