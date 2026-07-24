import json
from pathlib import Path

D = json.load(open('/tmp/easyquant_market_data_2026-07-16.json'))
rows = {r['f12']: r for r in D['individual_rankings']['data']['diff']}
configs = [
    ('000938', 'confirm', '通信/算力设备', ['AI算力', '资金反转', '早盘观察'], 0.76),
    ('000063', 'confirm', '通信设备', ['AI算力', '资金反转', '早盘观察'], 0.76),
    ('002475', 'confirm', '消费电子', ['AI终端', '资金反转', '早盘观察'], 0.76),
    ('603993', 'candidate', '工业金属', ['有色金属', '资金反转', '早盘观察'], 0.66),
    ('603327', 'candidate', '消费电子', ['AI终端', '资金反转', '早盘观察'], 0.58),
    ('002045', 'candidate', '消费电子', ['AI终端', '资金反转', '早盘观察'], 0.58),
]

picks = []
for code, level, sector, tags, score in configs:
    r = rows[code]
    name = r['f14']
    current = r['f62'] / 1e8
    prior = r['f164'] / 1e8
    pct = r['f3']
    d5 = r['f75']
    d10 = r['f81']
    turnover = r['f184']
    risks = ['早盘快照可能随市场情绪变化，需观察资金净流入能否持续']
    if code in {'000938', '000063'}:
        risks.append('前1-3日逐日资金与量能未完整回溯，不能视为完全确认')
    if code == '603993':
        risks.append('板块涨幅仅小幅为正，板块共振强度弱于科技方向')
    if pct >= 8:
        risks.append('早盘涨幅接近涨停，追高与冲高回落风险较高')
    detail = (
        f'预取数据09:40快照显示，{name}今日主力净流入{current:.2f}亿元，'
        f'早盘涨跌幅{pct:+.2f}%，近5日涨跌幅{d5:+.2f}%、近10日涨跌幅{d10:+.2f}%。'
        f' 东方财富字段f164（近阶段资金流代理）为{prior:.2f}亿元，呈现前期流出、今日回流的弱转强代理信号。'
        ' 但预取文件没有开盘价、前1-3日逐日资金和前日全天成交量，故量能放大与“由跌转涨”只能作不完全确认，建议盘中补验。'
    )
    picks.append({
        'stock_code': code,
        'stock_name': name,
        'pick_level': level,
        'reason_summary': f'今日主力净流入约{current:.2f}亿，前期资金流代理为{prior:.2f}亿，价格上涨{pct:+.2f}%，短线弱势后出现资金与价格同步修复',
        'reason_detail': detail,
        'sector_name': sector,
        'theme_tags': tags,
        'capital_profile': {
            'net_inflow': round(current, 3),
            'main_force_signal': 'strong' if current >= 1 else 'positive',
            'prior_flow_proxy': round(prior, 3),
            'turnover_proxy': round(turnover, 2),
            'volume_ratio': None,
        },
        'signal_context': f'前期资金流代理{prior:.2f}亿，今日早盘主力净流入{current:.2f}亿；今日涨跌幅{pct:+.2f}%，近5日{d5:+.2f}%，近10日{d10:+.2f}%；量能字段未提供，换手/活跃度代理f184={turnover:.2f}%',
        'risk_flags': risks,
        'entry_hint': '不追高；等待回踩分时均线/前收附近承接，若主力净流入持续且板块强度不降再小仓试错；跌破早盘低点止损',
        'confidence_score': score,
    })

up = lambda n: f'<span class="up">{n:+.2f}%</span>'
highlight = lambda n: f'<span class="highlight">{n:.2f}亿</span>'
parts = [
    '<h2>09:40 弱转强候选筛选</h2>',
    '<p>基于2026-07-16 09:40预取快照。模型优先寻找前期资金流出、今日主力回流、价格修复且板块资金改善的标的。由于数据包缺少开盘价、逐日1-3日资金和前日成交量，以下为<b>弱转强代理信号</b>，不是完整确认。</p>',
    '<h3>一、市场与板块</h3>',
    f'<p>消费电子方向在板块涨幅榜中排名靠前，品牌消费电子涨幅{up(1.79)}，消费电子涨幅{up(0.81)}，消费电子零部件及组装涨幅{up(0.68)}。本地监控显示半导体净额约{highlight(60.68)}、消费电子净额约{highlight(14.60)}，但部分板块价格仍偏弱，属于资金先行回流。</p>',
    '<table><thead><tr><th>排名</th><th>板块</th><th>涨跌幅</th></tr></thead><tbody>',
]
for i, (sector, value) in enumerate([('品牌消费电子', 1.79), ('消费电子', 0.81), ('消费电子零部件及组装', 0.68), ('机器人', 0.11), ('肉制品', 2.39)], 1):
    parts.append(f'<tr><td>{i}</td><td><span class="sector">{sector}</span></td><td>{up(value)}</td></tr>')
parts += [
    '</tbody></table>',
    '<hr>',
    '<h3>二、候选清单</h3>',
    '<table><thead><tr><th>股票</th><th>评级</th><th>今日主力净流入</th><th>涨跌幅</th><th>信号</th></tr></thead><tbody>',
]
for p in picks:
    r = rows[p['stock_code']]
    parts.append(f'<tr><td><span class="stock"><b>{p["stock_name"]}</b>（{p["stock_code"]}）</span></td><td>{p["pick_level"]}</td><td><span class="inflow">+{p["capital_profile"]["net_inflow"]:.2f}亿</span></td><td>{up(r["f3"])}</td><td>{p["sector_name"]}资金回流代理</td></tr>')
parts += [
    '</tbody></table>',
    '<hr>',
    '<h3>三、模型结论</h3>',
    '<p><b>优先观察紫光股份、中兴通讯、立讯精密。</b>三者同时具备今日主力净流入超过5000万元、近5日弱势/震荡与今日价格修复特征。洛阳钼业为低弹性备选；福蓉科技、国光电器涨幅已接近涨停，列为候选而非追涨推荐。</p>',
    '<div class="risk-box"><b>风险提示：</b>预取数据没有逐日历史资金、开盘涨跌幅、前日成交量/量比，无法严格证明“前1-3日净流出”“开盘跌转涨”“早盘成交量超过前日50%”。所有候选必须在盘中复核量能和资金持续性；涨停附近标的禁止追高。</div>',
]

payload = {
    'trading_date': '2026-07-16',
    'skill_name': '09:40 弱转强-候选筛选',
    'job_name': '09:40 弱转强-候选筛选',
    'job_type': 'stock_pick',
    'run_type': 'production',
    'source_input_ref': 'claude-code-cli',
    '_meta': {
        'schema_version': '3.0',
        'engine_type': 'claude-code',
        'data_sources_used': ['prefetch:eastmoney', 'local_api:/api/overview', 'local_api:/api/individual-rankings', 'local_api:/api/monitor-signals', 'local_api:/api/sector-stocks'],
    },
    'summary': {
        'market_phase': '早盘资金回流，消费电子/半导体资金先行但价格分化；弱转强处于观察确认阶段',
        'hot_sectors': ['消费电子', '品牌消费电子', '半导体', '通信服务'],
        'risk_signals': ['缺少逐日历史资金与成交量字段', '部分科技板块资金流与价格背离', '高涨幅标的追高风险'],
    },
    'result_payload': {'structured_picks': picks},
    'raw_output': '\n'.join(parts),
}

out = Path('/Users/jwkj/easyquant/data/ai_center/inbox/0940_弱转强-候选筛选_2026-07-16_20260716_094006.json')
out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
print(out)
print('picks', len(picks), 'bytes', out.stat().st_size)
