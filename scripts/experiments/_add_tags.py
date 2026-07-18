import json
path = '/Users/jwkj/easyquant/data/ai_center/inbox/2130_每日持仓复盘_2026-06-26_20260626_213023.json'
with open(path, 'r', encoding='utf-8') as f:
    d = json.load(f)

extra = '\n\n<h3>八、复盘主题标签</h3>\n<p>'
extra += '<span class="tag">光模块</span> '
extra += '<span class="tag">AI 算力</span> '
extra += '<span class="tag">1.6T</span> '
extra += '<span class="tag">CPO</span> '
extra += '<span class="tag">锂电池</span> '
extra += '<span class="tag">新能源车</span> '
extra += '<span class="tag">面板</span> '
extra += '<span class="tag">半导体设备</span> '
extra += '<span class="tag">军工电子</span> '
extra += '<span class="tag">防御性配置</span> '
extra += '<span class="tag">资金流向</span> '
extra += '<span class="tag">集中度风险</span>'
extra += '</p>'

d['raw_output'] += extra
with open(path, 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
print('OK, raw_output 长度:', len(d['raw_output']))
print('tag class 出现:', '<span class="tag">' in d['raw_output'])
