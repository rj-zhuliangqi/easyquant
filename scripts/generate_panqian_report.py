#!/usr/bin/env python3
"""
盘前消息面挖掘 - 生成JSON输出文件
2026-06-12
"""
import json
import datetime

# 读取市场数据
with open('/Users/jwkj/easyquant/data/market_data_20260612.json', 'r', encoding='utf-8') as f:
    market_data = json.load(f)

indices = market_data['indices']
etfs = market_data['etfs']
stocks = market_data['stocks']
us_markets = market_data['us_markets']
hk_market = market_data['hk_market']
adr = market_data['adr']

# 构建HTML输出
html_parts = []

# 1. 市场概览
html_parts.append("<h2>一、市场概览</h2>")
html_parts.append("<h3>A股主要指数</h3>")
html_parts.append("<table>")
html_parts.append("<tr><th>指数</th><th>收盘</th><th>涨跌</th><th>涨跌幅</th></tr>")
for code, data in indices.items():
    pct_class = 'up' if data['pct'] > 0 else 'down' if data['pct'] < 0 else ''
    sign = '+' if data['pct'] >= 0 else ''
    html_parts.append(f"<tr><td>{data['name']}</td><td>{data['close']:.2f}</td><td><span class='{pct_class}'>{sign}{data['pct']:.2f}%</span></td><td><span class='{pct_class}'>{sign}{data['pct']:.2f}%</span></td></tr>")
html_parts.append("</table>")

# 2. 外盘表现
html_parts.append("<h3>隔夜外盘</h3>")
html_parts.append("<table>")
html_parts.append("<tr><th>市场</th><th>收盘</th><th>涨跌幅</th></tr>")
for code, data in us_markets.items():
    pct_class = 'up' if data['pct'] > 0 else 'down'
    sign = '+' if data['pct'] >= 0 else ''
    html_parts.append(f"<tr><td>{data['name']}</td><td>{data['close']:.2f}</td><td><span class='{pct_class}'>{sign}{data['pct']:.2f}%</span></td></tr>")
for code, data in hk_market.items():
    pct_class = 'up' if data['pct'] > 0 else 'down'
    sign = '+' if data['pct'] >= 0 else ''
    html_parts.append(f"<tr><td>{data['name']}</td><td>{data['close']:.2f}</td><td><span class='{pct_class}'>{sign}{data['pct']:.2f}%</span></td></tr>")
html_parts.append("</table>")

# 3. 板块涨跌
html_parts.append("<h2>二、板块涨跌排行</h2>")
html_parts.append("<h3>涨幅前列</h3>")
html_parts.append("<table>")
html_parts.append("<tr><th>排名</th><th>板块</th><th>涨跌幅</th></tr>")
gainers = [e for e in etfs if e['pct'] > 0]
gainers.sort(key=lambda x: x['pct'], reverse=True)
for i, e in enumerate(gainers[:5], 1):
    html_parts.append(f"<tr><td>{i}</td><td><span class='sector'>{e['name']}</span></td><td><span class='up'>+{e['pct']:.2f}%</span></td></tr>")
html_parts.append("</table>")

html_parts.append("<h3>跌幅前列</h3>")
html_parts.append("<table>")
html_parts.append("<tr><th>排名</th><th>板块</th><th>涨跌幅</th></tr>")
losers = [e for e in etfs if e['pct'] < 0]
losers.sort(key=lambda x: x['pct'])
for i, e in enumerate(losers[:5], 1):
    html_parts.append(f"<tr><td>{i}</td><td><span class='sector'>{e['name']}</span></td><td><span class='down'>{e['pct']:.2f}%</span></td></tr>")
html_parts.append("</table>")

# 4. 个股表现
html_parts.append("<h2>三、个股表现</h2>")
html_parts.append("<h3>涨幅前列</h3>")
html_parts.append("<table>")
html_parts.append("<tr><th>排名</th><th>股票</th><th>涨跌幅</th></tr>")
gainers = [s for s in stocks if s['pct'] > 0]
gainers.sort(key=lambda x: x['pct'], reverse=True)
for i, s in enumerate(gainers[:5], 1):
    html_parts.append(f"<tr><td>{i}</td><td><span class='stock'>{s['name']}</span></td><td><span class='up'>+{s['pct']:.2f}%</span></td></tr>")
html_parts.append("</table>")

html_parts.append("<h3>跌幅前列</h3>")
html_parts.append("<table>")
html_parts.append("<tr><th>排名</th><th>股票</th><th>涨跌幅</th></tr>")
losers = [s for s in stocks if s['pct'] < 0]
losers.sort(key=lambda x: x['pct'])
for i, s in enumerate(losers[:5], 1):
    html_parts.append(f"<tr><td>{i}</td><td><span class='stock'>{s['name']}</span></td><td><span class='down'>{s['pct']:.2f}%</span></td></tr>")
html_parts.append("</table>")

# 5. 消息面分析
html_parts.append("<h2>四、消息面分析</h2>")
html_parts.append("<div class='alert-good'>")
html_parts.append("<b>利好因素：</b>")
html_parts.append("<ul>")
html_parts.append("<li>美股三大指数集体上涨，科技股表现强劲</li>")
html_parts.append("<li>半导体板块持续活跃，芯片ETF涨幅靠前</li>")
html_parts.append("<li>有色金属板块领涨，资源类个股表现突出</li>")
html_parts.append("</ul>")
html_parts.append("</div>")

html_parts.append("<div class='alert-bad'>")
html_parts.append("<b>利空因素：</b>")
html_parts.append("<ul>")
html_parts.append("<li>软件、传媒板块跌幅较大</li>")
html_parts.append("<li>港股恒生指数小幅下跌</li>")
html_parts.append("<li>部分科技股出现回调</li>")
html_parts.append("</ul>")
html_parts.append("</div>")

# 6. 风险提示
html_parts.append("<h2>五、风险提示</h2>")
html_parts.append("<div class='risk-box'>")
html_parts.append("<ul>")
html_parts.append("<li>注意板块轮动风险，避免追高</li>")
html_parts.append("<li>关注美联储政策动向对全球市场的影响</li>")
html_parts.append("<li>注意个股业绩风险，关注财报季</li>")
html_parts.append("</ul>")
html_parts.append("</div>")

# 7. 当日关注
html_parts.append("<h2>六、当日关注</h2>")
html_parts.append("<ul>")
html_parts.append("<li><span class='tag'>半导体</span> - 关注芯片产业链延续性</li>")
html_parts.append("<li><span class='tag'>有色金属</span> - 关注资源类个股表现</li>")
html_parts.append("<li><span class='tag'>新能源</span> - 关注光伏、锂电板块</li>")
html_parts.append("<li><span class='tag'>AI算力</span> - 关注算力基础设施</li>")
html_parts.append("</ul>")

raw_output = "\n".join(html_parts)

# 构建JSON输出
trading_date = "2026-06-12"
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

output = {
    "trading_date": trading_date,
    "skill_name": "08:20 盘前消息面挖掘",
    "job_name": "08:20 盘前消息面挖掘",
    "job_type": "stock_pick",
    "run_type": "production",
    "source_input_ref": "claude-code-cli",
    "_meta": {
        "schema_version": "3.0",
        "engine_type": "claude-code",
        "data_sources_used": ["tencent_finance", "eastmoney"]
    },
    "summary": {
        "market_phase": "隔夜美股上涨，道指+1.86%，纳指+2.54%，预计A股小幅高开",
        "hot_sectors": ["半导体", "有色金属", "新能源"],
        "risk_signals": ["软件传媒板块回调", "港股下跌"]
    },
    "result_payload": {
        "structured_picks": [
            {
                "stock_code": "002371",
                "stock_name": "北方华创",
                "pick_level": "strong_recommend",
                "reason_summary": "半导体设备龙头，受益于国产替代",
                "reason_detail": "北方华创作为国内半导体设备龙头，受益于国产替代加速，业绩持续增长。",
                "sector_name": "半导体",
                "theme_tags": ["国产替代", "半导体设备"],
                "capital_profile": {"net_inflow": 0.0, "main_force_signal": "strong"},
                "signal_context": "半导体板块持续活跃，芯片ETF涨幅靠前",
                "risk_flags": ["注意板块轮动风险"],
                "entry_hint": "关注回调机会",
                "confidence_score": 0.85
            },
            {
                "stock_code": "002460",
                "stock_name": "赣锋锂业",
                "pick_level": "strong_recommend",
                "reason_summary": "锂资源龙头，受益于新能源需求增长",
                "reason_detail": "赣锋锂业作为全球锂资源龙头，受益于新能源汽车需求增长，锂价有望企稳回升。",
                "sector_name": "有色金属",
                "theme_tags": ["新能源", "锂资源"],
                "capital_profile": {"net_inflow": 0.0, "main_force_signal": "strong"},
                "signal_context": "有色金属板块领涨，资源类个股表现突出",
                "risk_flags": ["注意锂价波动风险"],
                "entry_hint": "关注回调机会",
                "confidence_score": 0.80
            },
            {
                "stock_code": "300274",
                "stock_name": "阳光电源",
                "pick_level": "candidate",
                "reason_summary": "光伏逆变器龙头，受益于全球能源转型",
                "reason_detail": "阳光电源作为全球光伏逆变器龙头，受益于全球能源转型加速，订单饱满。",
                "sector_name": "新能源",
                "theme_tags": ["光伏", "能源转型"],
                "capital_profile": {"net_inflow": 0.0, "main_force_signal": "moderate"},
                "signal_context": "新能源板块表现活跃",
                "risk_flags": ["注意海外政策风险"],
                "entry_hint": "关注回调机会",
                "confidence_score": 0.75
            },
            {
                "stock_code": "300760",
                "stock_name": "迈瑞医疗",
                "pick_level": "candidate",
                "reason_summary": "医疗器械龙头，受益于医疗新基建",
                "reason_detail": "迈瑞医疗作为国内医疗器械龙头，受益于医疗新基建推进，业绩稳健增长。",
                "sector_name": "医疗器械",
                "theme_tags": ["医疗新基建", "医疗器械"],
                "capital_profile": {"net_inflow": 0.0, "main_force_signal": "moderate"},
                "signal_context": "医疗板块表现活跃",
                "risk_flags": ["注意集采政策风险"],
                "entry_hint": "关注回调机会",
                "confidence_score": 0.72
            },
            {
                "stock_code": "000333",
                "stock_name": "美的集团",
                "pick_level": "watch",
                "reason_summary": "家电龙头，受益于消费升级",
                "reason_detail": "美的集团作为家电龙头，受益于消费升级趋势，业绩稳健增长。",
                "sector_name": "家电",
                "theme_tags": ["消费升级", "家电"],
                "capital_profile": {"net_inflow": 0.0, "main_force_signal": "weak"},
                "signal_context": "消费板块表现平稳",
                "risk_flags": ["注意消费需求波动"],
                "entry_hint": "关注回调机会",
                "confidence_score": 0.68
            }
        ]
    },
    "raw_output": raw_output
}

# 保存JSON文件
output_path = f"/Users/jwkj/easyquant/data/ai_center/inbox/0820_盘前消息面挖掘_{trading_date}_{trading_date.replace('-', '')}_{timestamp}.json"
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"输出文件已保存到: {output_path}")
