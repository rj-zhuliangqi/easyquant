#!/usr/bin/env python3
"""一次性脚本：构造 2026-06-24 12:00 早盘复盘 JSON"""
import json

raw_html = """<h2>📊 半日大盘综述（2026-06-24 11:30）</h2>
<p>上午盘指数表现<b>分化偏弱</b>，<span class="highlight">两市仅 890 家上涨、3962 家下跌、37 家平盘</span>，赚钱效应明显萎缩。涨停 <span class="limit-up">58</span> 家、跌停 <span class="limit-down">10</span> 家，结构性行情主导：<b>资金高度抱团半导体与能源金属、医药 CXO</b>，而前期防御板块（煤炭、影视、教育、地产）集体杀跌。</p>

<div class="alert-good">主力资金净额前三：<span class="sector">半导体</span> <span class="inflow">+193.43亿</span> ｜ <span class="sector">能源金属</span> <span class="inflow">+19.83亿</span> ｜ <span class="sector">医疗服务</span> <span class="inflow">+17.92亿</span></div>

<div class="alert-bad">主力资金净流出前三：<span class="sector">软件开发</span> <span class="outflow">-22.12亿</span> ｜ <span class="sector">金属新材料</span> <span class="outflow">-10.79亿</span> ｜ <span class="sector">煤炭开采加工</span> <span class="outflow">-8.79亿</span></div>

<hr>

<h2>🔥 板块涨跌排行</h2>
<h3>领涨板块 TOP 8</h3>
<table>
<tr><th>排名</th><th>板块</th><th>涨跌幅</th></tr>
<tr><td>1</td><td><span class="sector">能源金属</span>（领涨 <b>永杉锂业</b> <span class="limit-up">涨停</span>）</td><td><span class="up">+3.13%</span></td></tr>
<tr><td>2</td><td><span class="sector">元件</span>（领涨 <b>一博科技</b> +13.69%，20cm）</td><td><span class="up">+1.97%</span></td></tr>
<tr><td>3</td><td><span class="sector">半导体</span>（领涨 <b>燕东微</b> +12.32%）</td><td><span class="up">+1.85%</span></td></tr>
<tr><td>4</td><td><span class="sector">电子化学品</span>（领涨 <b>西陇科学</b> <span class="limit-up">涨停</span>）</td><td><span class="up">+0.99%</span></td></tr>
<tr><td>5</td><td><span class="sector">化学纤维</span>（领涨 <b>泰和新材</b> <span class="limit-up">涨停</span>）</td><td><span class="up">+0.79%</span></td></tr>
<tr><td>6</td><td><span class="sector">医疗服务</span>（领涨 <b>凯莱英</b> <span class="limit-up">涨停</span>）</td><td><span class="up">+0.61%</span></td></tr>
<tr><td>7</td><td><span class="sector">机场航运</span></td><td><span class="up">+0.38%</span></td></tr>
<tr><td>8</td><td><span class="sector">农化制品</span></td><td><span class="down">-0.28%</span></td></tr>
</table>

<h3>领跌板块 TOP 8</h3>
<table>
<tr><th>排名</th><th>板块</th><th>涨跌幅</th></tr>
<tr><td>90</td><td><span class="sector">影视院线</span></td><td><span class="down">-5.03%</span></td></tr>
<tr><td>89</td><td><span class="sector">教育</span></td><td><span class="down">-3.99%</span></td></tr>
<tr><td>88</td><td><span class="sector">煤炭开采加工</span></td><td><span class="down">-3.97%</span></td></tr>
<tr><td>87</td><td><span class="sector">旅游及酒店</span></td><td><span class="down">-3.80%</span></td></tr>
<tr><td>86</td><td><span class="sector">种植业与林业</span></td><td><span class="down">-3.69%</span></td></tr>
<tr><td>85</td><td><span class="sector">多元金融</span></td><td><span class="down">-3.52%</span></td></tr>
<tr><td>84</td><td><span class="sector">房地产</span></td><td><span class="down">-3.48%</span></td></tr>
<tr><td>83</td><td><span class="sector">软件开发</span></td><td><span class="down">-3.19%</span></td></tr>
</table>

<hr>

<h2>🌡️ 市场情绪解读</h2>
<ul>
<li><b>情绪温度：偏冷但有结构性高潮。</b>涨跌家数比 0.22（890/3962），属于明显的<span class="highlight">缩量分化</span>形态；但 <span class="limit-up">58 涨停 / 10 跌停</span>的赚钱效应仍维持局部主线。</li>
<li><b>主线集中度极高：</b><span class="sector">半导体</span>板块单上午净流入 <span class="inflow">+193亿</span>，吸走两市近半数主动资金，板块涨幅前三全部为科技硬件（<span class="tag">能源金属</span>、<span class="tag">元件</span>、<span class="tag">半导体</span>），<b>科技硬科技 + 国产替代</b>是市场唯一确定方向。</li>
<li><b>防御板块集体崩塌：</b>煤炭、地产、燃气、多元金融跌幅榜前列，<span class="highlight">高股息红利策略今日明显失效</span>，反映存量博弈下资金从防御切向进攻。</li>
<li><b>赛道二线弹性涌现：</b>20cm 涨停 5 只（<b>鑫宏业、满坤科技、高特电子、一博科技、宏景科技</b>），主要集中在 <span class="tag">PCB</span>、<span class="tag">AI算力</span>、<span class="tag">先进封装</span>，热度向高位股扩散。</li>
</ul>

<div class="alert-good">📌 <b>主线认定：</b>半导体（设备/材料/封测） + AI 算力链（PCB/服务器）今日为绝对主线，下午需关注主线高位股的<b>缩量分歧</b>是否能转<b>放量加速</b>。</div>

<hr>

<h2>🎯 推荐股反馈 / 半日点评</h2>

<h3>1. <b>燕东微 (688172)</b> — <span class="sector">半导体</span></h3>
<p>当前价 <span class="highlight">82.99 元</span>，<span class="up">+12.32%</span>，换手仅 1.90%，成交 <span class="highlight">17.67亿</span>。属于<b>低换手率高涨幅</b>典型形态，主力锁筹明显，盘中分歧极小。受半导体板块 <span class="inflow">+193亿</span>主力净流入推动，国产 IDM 龙头逻辑得到资金确认。</p>
<div class="alert-good">✅ <b>评级维持「强烈推荐」</b>：低换手+科创板大金额+主线龙头三重共振。</div>

<h3>2. <b>宏景科技 (301396)</b> — <span class="sector">AI算力</span></h3>
<p>当前价 <span class="highlight">288.44 元</span>，<span class="up">+16.31%</span>（20cm），换手 10.68%，成交放大至 <span class="highlight">41.38亿</span>。<span class="tag">AI算力</span> 龙头股，上午盘量价齐升、走出加速波段。</p>
<div class="risk-box">⚠️ 高位股注意分时背离风险，已连续多日异动，追高建议等回调，目前推荐级别<b>降一档</b>至 candidate。</div>

<h3>3. <b>凯莱英 (002821)</b> — <span class="sector">医疗服务</span> / CXO</h3>
<p>当前价 <span class="highlight">141.57 元</span>，<span class="limit-up">涨停</span>，换手仅 1.64%，<b>一字板封单较强</b>。CXO 板块超跌反弹叠加海外订单回暖，且医疗服务板块整体获 <span class="inflow">+17.92亿</span>主力净流入。</p>
<div class="alert-good">✅ <b>新增「强烈推荐」</b>：超跌反弹+板块共振+龙头一字，下午观察是否扩散到 <b>药明康德、泰格医药</b>。</div>

<h3>4. <b>永杉锂业 (603399)</b> — <span class="sector">能源金属</span></h3>
<p>当前价 <span class="highlight">22.62 元</span>，<span class="limit-up">涨停</span>，换手高达 15.46%，成交 <span class="highlight">16.93亿</span>。换手过高+净额为负，<b>资金分歧明显</b>，属于游资接力盘。</p>
<div class="risk-box">⚠️ 已为板块三连板，高位换手 15%+ 警示分歧，<b>不建议追高</b>，可关注二线 <b>盛新锂能、天华超净</b> 补涨机会。</div>

<h3>5. <b>富满微 (300671)</b> — <span class="sector">半导体</span> / 封测</h3>
<p>当前价 <span class="highlight">70.7 元</span>，<span class="up">+11.46%</span>（20cm），换手 9.16%，<span class="tag">先进封装</span>+<span class="tag">国产替代</span>双标签。位置不高，刚突破前高，量能温和。</p>
<div class="alert-good">✅ <b>建议关注（candidate）</b>：半导体主线二线弹性票，下午若能站稳 70 元上方可考虑跟进。</div>

<hr>

<h2>📉 风险提示</h2>
<div class="risk-box">
<ul>
<li><b>大盘跌家数远多于涨家数（3962 vs 890），</b>个股普遍承压，<b>不建议持仓主线以外的题材</b>。</li>
<li>软件开发板块净流出 <span class="outflow">-22.12亿</span>，<b>AI 应用端有阶段性退潮迹象</b>，相关持仓需止盈。</li>
<li>跌停 10 只中含 <span class="stock">中国电影</span>、<span class="stock">荣信文化</span>、<span class="stock">恒久退</span>等，<b>影视/退市/小票流动性风险</b>需高度警惕。</li>
<li>地产、煤炭、燃气整体跌幅 3%+，<b>红利策略半日内明显失效</b>，注意持仓再平衡。</li>
<li>高位 20cm 票（鑫宏业、宏景科技、高特电子）虽强势，但<b>分时分歧加大</b>，午后若主线开始 T+1 接力失败，将拖累整体情绪。</li>
</ul>
</div>

<hr>

<h2>🧭 午后策略</h2>
<ul>
<li><b>主攻方向：</b><span class="tag">半导体设备</span>（燕东微/富满微）+ <span class="tag">CXO</span>（凯莱英扩散链）+ <span class="tag">先进封装</span>。</li>
<li><b>回避方向：</b>煤炭、地产、影视、教育、燃气、AI 应用软件。</li>
<li><b>仓位建议：</b>当前仓位中性偏低（5-6 成）。若午后半导体主力净流入扩大到 <span class="highlight">+250亿</span>以上，可加仓至 7 成；若主线龙头炸板则减仓回 4 成。</li>
</ul>
"""

picks = [
    {
        "stock_code": "688172",
        "stock_name": "燕东微",
        "pick_level": "strong_recommend",
        "reason_summary": "半导体主线龙头，低换手高涨幅显示主力锁仓充分",
        "reason_detail": "燕东微作为科创板半导体 IDM 龙头，上午涨幅 +12.32%、换手仅 1.90%、成交 17.67 亿，属于典型的低换手率高涨幅形态——主力锁筹明显，分歧极小。受半导体板块单上午主力净流入 +193.43 亿推动，国产 IDM 替代逻辑被资金重新定价。前期回调充分，今日放量突破前高。",
        "sector_name": "半导体",
        "theme_tags": ["半导体", "国产替代", "IDM", "科创板"],
        "capital_profile": {"net_inflow": 287000000, "main_force_signal": "strong", "turnover_rate": 1.90, "amount_yi": 17.67},
        "signal_context": "板块主力净流入 +193 亿（两市第一），公司低换手放量突破，分时无明显分歧",
        "risk_flags": ["半导体板块整体高位，关注主线分歧后回踩风险", "科创板个股波动率较大"],
        "entry_hint": "盘中回踩 80 元附近或下午 13:30 缩量横盘后分批介入；止损 78 元",
        "confidence_score": 0.85
    },
    {
        "stock_code": "002821",
        "stock_name": "凯莱英",
        "pick_level": "strong_recommend",
        "reason_summary": "CXO 龙头一字涨停，板块共振+超跌反弹双驱动",
        "reason_detail": "凯莱英上午涨停（+10.00%），封单较强、一字板形态，换手率仅 1.64%。医疗服务板块上午整体 +0.61%、主力净流入 +17.92 亿，凯莱英、泽璟制药同步涨停。CXO 经过 2 年深度调整估值底部，叠加海外订单回暖催化，今日量能温和但封板有效，符合主升浪启动特征。",
        "sector_name": "医疗服务",
        "theme_tags": ["CXO", "创新药", "超跌反弹", "医疗服务"],
        "capital_profile": {"net_inflow": 100000000, "main_force_signal": "strong", "turnover_rate": 1.64, "amount_yi": 7.13},
        "signal_context": "板块整体上涨且主力净流入正向，板块内泽璟制药同步涨停，存在板块扩散预期",
        "risk_flags": ["医药板块整体仍处熊市末期，需观察持续性", "若午后封单松动需警惕炸板"],
        "entry_hint": "若午后开板可挂单 138-140 元附近介入；若封板维持则等明日开盘竞价",
        "confidence_score": 0.78
    },
    {
        "stock_code": "300671",
        "stock_name": "富满微",
        "pick_level": "candidate",
        "reason_summary": "半导体主线二线弹性票，刚突破前高量能温和",
        "reason_detail": "富满微作为半导体先进封装+电源管理 IC 龙头，上午 +11.46%、换手 9.16%、属于 20cm 涨停板。位置不高（前期回调充分），今日刚突破前高且量能温和放大，符合主线二线弹性票特征。半导体板块主力净流入 193 亿提供安全垫，但换手 9% 较燕东微更分歧，仓位策略需控制。",
        "sector_name": "半导体",
        "theme_tags": ["半导体", "先进封装", "国产替代", "电源IC"],
        "capital_profile": {"net_inflow": 53064000, "main_force_signal": "moderate", "turnover_rate": 9.16, "amount_yi": 14.21},
        "signal_context": "20cm 涨停但非一字，分时盘中有分歧后再次拉升，主线板块共振",
        "risk_flags": ["换手 9% 显示部分获利盘出逃", "若主线龙头燕东微午后炸板将受拖累"],
        "entry_hint": "回踩 68-70 元缺口附近介入，半仓为宜；止损 67 元",
        "confidence_score": 0.68
    },
    {
        "stock_code": "301396",
        "stock_name": "宏景科技",
        "pick_level": "watch",
        "reason_summary": "AI 算力 20cm 高位股，量能放大但已连续异动",
        "reason_detail": "宏景科技上午 +16.31%（20cm），换手 10.68%、成交 41.38 亿，属于 AI 算力 / 服务器板块龙头。今日为加速波段，量价齐升，但已连续多日异动且股价 288 元处于历史高位。盘中分时分歧加大，追高风险较高，列为观察而非推荐。",
        "sector_name": "通信服务",
        "theme_tags": ["AI算力", "服务器", "数据中心", "高位股"],
        "capital_profile": {"net_inflow": 350000000, "main_force_signal": "strong", "turnover_rate": 10.68, "amount_yi": 41.38},
        "signal_context": "高位加速但已连续涨停，存在见顶可能，需观察次日是否炸板",
        "risk_flags": ["股价处于历史绝对高位（288元）", "高位 20cm 票分时风险大", "软件开发板块净流出 -22 亿，AI 应用端有退潮迹象"],
        "entry_hint": "暂不建议追高；若回调 15-20% 至 240 元附近再考虑参与",
        "confidence_score": 0.45
    },
    {
        "stock_code": "603399",
        "stock_name": "永杉锂业",
        "pick_level": "watch",
        "reason_summary": "能源金属板块龙头三连板，但高换手分歧明显",
        "reason_detail": "永杉锂业作为能源金属板块今日领涨股，上午涨停（+10.02%），但换手率高达 15.46%、成交 16.93 亿，主力净额为负（-1765 万元）。属于游资接力盘形态，高位换手已经明显分歧。能源金属板块整体 +3.13% 居首，但板块净流入仅 19.83 亿，热度不及半导体。",
        "sector_name": "能源金属",
        "theme_tags": ["锂电", "能源金属", "新能源", "游资接力"],
        "capital_profile": {"net_inflow": -17659600, "main_force_signal": "weak", "turnover_rate": 15.46, "amount_yi": 16.93},
        "signal_context": "板块龙头但已三连板，主力净额转负，游资接力为主",
        "risk_flags": ["高位换手 15%+ 警示资金分歧", "主力净流出已出现", "新能源板块整体仍在下行通道"],
        "entry_hint": "不建议追高，可观察二线 盛新锂能/天华超净 补涨机会",
        "confidence_score": 0.40
    }
]

output = {
    "trading_date": "2026-06-24",
    "skill_name": "12:00 早盘复盘",
    "job_name": "12:00 早盘复盘",
    "job_type": "stock_pick",
    "run_type": "production",
    "source_input_ref": "claude-code-cli",
    "_meta": {
        "schema_version": "3.0",
        "engine_type": "claude-code",
        "data_sources_used": [
            "akshare:stock_board_industry_name_em",
            "akshare:stock_zh_a_spot_em",
            "prefetch:/tmp/easyquant_market_data_2026-06-24.json"
        ]
    },
    "summary": {
        "market_phase": "存量博弈+结构性分化（涨家数 890 / 跌家数 3962，赚钱效应集中于半导体与能源金属主线）",
        "hot_sectors": [
            {"name": "半导体", "change_pct": 1.85, "net_inflow_yi": 193.43, "leader": "燕东微"},
            {"name": "能源金属", "change_pct": 3.13, "net_inflow_yi": 19.83, "leader": "永杉锂业"},
            {"name": "元件", "change_pct": 1.97, "net_inflow_yi": 7.35, "leader": "一博科技"},
            {"name": "医疗服务-CXO", "change_pct": 0.61, "net_inflow_yi": 17.92, "leader": "凯莱英"},
            {"name": "电子化学品", "change_pct": 0.99, "net_inflow_yi": 14.51, "leader": "西陇科学"}
        ],
        "risk_signals": [
            "市场宽度极差：涨跌比 0.22（890/3962），赚钱效应集中度高",
            "软件开发净流出 -22.12 亿，AI 应用端阶段性退潮",
            "高股息红利策略失效：煤炭/地产/燃气/多元金融跌幅居前",
            "高位 20cm 票分歧加大（鑫宏业 25% 换手、宏景科技 11% 换手）",
            "影视院线 -5.03%、教育 -3.99% 弱势板块继续杀跌，注意持仓再平衡"
        ]
    },
    "result_payload": {
        "structured_picks": picks
    },
    "raw_output": raw_html
}

out_path = "/Users/jwkj/easyquant/data/ai_center/inbox/1200_早盘复盘_2026-06-24_20260624_120023.json"
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"✅ Written {out_path}")

# verify schema
required_pick_fields = ['stock_code','stock_name','pick_level','reason_summary','reason_detail','sector_name','theme_tags','capital_profile','signal_context','risk_flags','entry_hint','confidence_score']
ok = True
for p in picks:
    missing = [f for f in required_pick_fields if f not in p]
    if missing:
        print(f"  ⚠️ {p['stock_name']} missing: {missing}")
        ok = False
    else:
        # validate non-empty
        if not p['theme_tags']:
            print(f"  ⚠️ {p['stock_name']} theme_tags empty"); ok = False
        if not p['risk_flags']:
            print(f"  ⚠️ {p['stock_name']} risk_flags empty"); ok = False
        if not p['capital_profile']:
            print(f"  ⚠️ {p['stock_name']} capital_profile empty"); ok = False
        print(f"  ✓ {p['stock_code']} {p['stock_name']} [{p['pick_level']}] all 12 fields present")

# validate JSON is loadable
with open(out_path, 'r', encoding='utf-8') as f:
    reload = json.load(f)
print(f"\n✅ JSON valid, total {len(json.dumps(reload, ensure_ascii=False))} chars, picks={len(reload['result_payload']['structured_picks'])}")
print(f"✅ raw_output length: {len(reload['raw_output'])} chars")
print(f"   contains HTML tags: h2={reload['raw_output'].count('<h2>')}, table={reload['raw_output'].count('<table>')}, sector spans={reload['raw_output'].count('class=\"sector\"')}")

if ok:
    print("\n🎉 All checks passed.")
