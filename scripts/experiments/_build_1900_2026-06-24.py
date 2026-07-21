import json

raw_html = """<h2>盘后超短线复盘 · 2026-06-24</h2>

<h3>一、大盘环境与情绪温度</h3>
<p>今日 A 股出现典型的<b>"指数稳、个股惨"</b>结构分化：全市场 5192 只交易标的中，
仅 <span class="up">1382</span> 只上涨、<span class="down">3768</span> 只下跌、42 只平盘，
跌幅中位数显著大于涨幅中位数，<b>赚钱效应集中在极少数主线龙头</b>。</p>

<p>涨停潮聚焦：全市场达到 10% 涨停标的 <span class="highlight">105</span> 只、20cm 涨停
<span class="highlight">10</span> 只、跌停 <span class="down">19</span> 只；
20cm 与封板量给市场提供了情绪锚，但短线情绪温度计仍偏 <b>"结构性热、整体冷"</b>。</p>

<div class="alert-good">
  <b>积极信号：</b>半导体板块净流入 <span class="inflow">+313.48亿</span>，
  消费电子 <span class="inflow">+115.21亿</span>，主力资金对硬科技主线<b>态度坚决</b>。
</div>

<hr>

<h3>二、主线板块涨跌排行（行业前 10 / 后 5）</h3>
<table>
  <thead>
    <tr><th>排名</th><th>板块</th><th>涨跌幅</th><th>净额</th><th>领涨股</th></tr>
  </thead>
  <tbody>
    <tr><td>1</td><td><span class="sector">能源金属</span></td><td><span class="up">+4.27%</span></td><td><span class="inflow">+33.25亿</span></td><td><span class="stock">永杉锂业</span></td></tr>
    <tr><td>2</td><td><span class="sector">半导体</span></td><td><span class="up">+3.80%</span></td><td><span class="inflow">+313.48亿</span></td><td><span class="stock">臻宝科技</span></td></tr>
    <tr><td>3</td><td><span class="sector">元件</span></td><td><span class="up">+3.19%</span></td><td><span class="inflow">+13.31亿</span></td><td><span class="stock">一博科技</span></td></tr>
    <tr><td>4</td><td><span class="sector">电子化学品</span></td><td><span class="up">+3.10%</span></td><td><span class="inflow">+26.51亿</span></td><td><span class="stock">飞凯材料</span></td></tr>
    <tr><td>5</td><td><span class="sector">化学纤维</span></td><td><span class="up">+1.31%</span></td><td><span class="inflow">+0.18亿</span></td><td><span class="stock">中复神鹰</span></td></tr>
    <tr><td>6</td><td><span class="sector">军工电子</span></td><td><span class="up">+0.75%</span></td><td><span class="inflow">+5.29亿</span></td><td><span class="stock">六九一二</span></td></tr>
    <tr><td>7</td><td><span class="sector">消费电子</span></td><td><span class="up">+0.63%</span></td><td><span class="inflow">+115.21亿</span></td><td><span class="stock">领益智造</span></td></tr>
    <tr><td>8</td><td><span class="sector">医疗服务</span></td><td><span class="up">+0.51%</span></td><td><span class="inflow">+12.79亿</span></td><td><span class="stock">凯莱英</span></td></tr>
    <tr><td>9</td><td><span class="sector">光学光电子</span></td><td><span class="up">+0.49%</span></td><td><span class="inflow">+19.50亿</span></td><td><span class="stock">戈碧迦</span></td></tr>
    <tr><td>10</td><td><span class="sector">其他电子</span></td><td><span class="up">+0.27%</span></td><td><span class="outflow">-0.90亿</span></td><td><span class="stock">英唐智控</span></td></tr>
    <tr><td>86</td><td><span class="sector">教育</span></td><td><span class="down">-3.53%</span></td><td><span class="outflow">-1.08亿</span></td><td>科德教育</td></tr>
    <tr><td>87</td><td><span class="sector">煤炭开采</span></td><td><span class="down">-3.55%</span></td><td><span class="outflow">-10.20亿</span></td><td>电投能源</td></tr>
    <tr><td>88</td><td><span class="sector">种植林业</span></td><td><span class="down">-3.75%</span></td><td><span class="outflow">-1.97亿</span></td><td>润农节水</td></tr>
    <tr><td>89</td><td><span class="sector">旅游酒店</span></td><td><span class="down">-3.86%</span></td><td><span class="outflow">-4.16亿</span></td><td>岭南控股</td></tr>
    <tr><td>90</td><td><span class="sector">影视院线</span></td><td><span class="down">-4.56%</span></td><td><span class="outflow">-6.72亿</span></td><td>儒意电影</td></tr>
  </tbody>
</table>

<p><b>结论：</b>资金一边倒押注 <span class="tag">硬科技</span>，
<span class="tag">半导体</span> 板块 <span class="inflow">+313亿</span> 净流入是<b>全市场绝对核心主线</b>；
而消费、地产链、煤炭、影视、教育等顺周期/防御板块<b>集体闷杀</b>，
说明红利风格在今日被资金抛弃，呈现"风格切换日"特征。</p>

<hr>

<h3>三、主线龙头与赚钱效应核</h3>

<h4>主线 1：<span class="sector">半导体 / AI 算力</span>（核心主线）</h4>
<ul>
  <li><b>300857 <span class="stock">协创数据</span></b>：<span class="limit-up">+10.99%</span>，成交 <span class="highlight">100.61亿</span>，主力 <span class="inflow">+9.69亿</span> — <b>核心龙头、放量空间打开</b>。</li>
  <li><b>301396 <span class="stock">宏景科技</span></b>：<span class="limit-up">20cm 涨停</span>，成交 53.16亿，主力 <span class="inflow">+2.15亿</span> — AI 服务器 + 数据中心方向。</li>
  <li><b>688123 <span class="stock">聚辰股份</span></b>：<span class="limit-up">20cm 涨停</span>，主力 <span class="inflow">+5.16亿</span> — 半导体存储芯片。</li>
  <li><b>002600 <span class="stock">领益智造</span></b>：<span class="limit-up">+10.03%</span>，主力 <span class="inflow">+9.98亿</span>，消费电子+苹果链龙头。</li>
  <li><b>301366 <span class="stock">一博科技</span></b>：<span class="limit-up">20cm 涨停</span>，主力 <span class="inflow">+2.66亿</span> — PCB 设计。</li>
  <li>300480 <span class="stock">光力科技</span>、002364 <span class="stock">中恒电气</span> 跟随补涨。</li>
</ul>

<h4>主线 2：<span class="sector">能源金属 / 锂电池</span>（板块 +4.27% 涨幅第一）</h4>
<ul>
  <li>603399 <span class="stock">永杉锂业</span>：<span class="limit-up">+10.02%</span>，但主力 <span class="outflow">-0.70亿</span> — <b>封板伴随出货</b>。</li>
  <li>002497 雅化集团 / 002254 泰和新材：涨停但净额接近 0 或为负，板块强度<b>有"指数涨、个股弱"嫌疑</b>。</li>
  <li>688295 <span class="stock">中复神鹰</span>：+13.14% 主力 <span class="inflow">+1.27亿</span>，碳纤维/锂电材料逻辑。</li>
</ul>

<h4>主线 3：题材个股催化</h4>
<ul>
  <li>600246 <span class="stock">万通发展</span>：地产板块 <span class="down">-3.14%</span> 背景下逆势 <span class="limit-up">涨停</span>，主力 <span class="inflow">+4.29亿</span> — 纯<b>个股事件驱动</b>，非地产β。</li>
  <li>688797 <span class="stock">臻宝科技</span>：涨幅 1212.84% 系新股首日，不参与短线讨论。</li>
</ul>

<hr>

<h3>四、失败模式与陷阱榜（重点警示）</h3>

<div class="alert-bad">
  <b>失败模式 1：高位涨停 + 主力净流出 = 出货嫌疑</b>
</div>
<ul>
  <li>600909 <span class="stock">华安证券</span>：<span class="limit-up">涨停</span>，但主力 <span class="outflow">-12.98亿</span>，成交 58亿 — <b>典型出货板</b>，明日大概率冲高回落。</li>
  <li>688403 <span class="stock">汇成股份</span>：<span class="limit-up">20cm 涨停</span> 但主力 <span class="outflow">-2.57亿</span>，半导体跟风票，<b>位置高、博弈风险大</b>。</li>
  <li>002491 <span class="stock">通鼎互联</span>：涨停，主力 <span class="outflow">-9.65亿</span> — <b>巨量分歧</b>。</li>
  <li>600026 中远海能 涨停伴随 <span class="outflow">-3.74亿</span>；600141 兴发集团 +9.99% 净额 <span class="outflow">-2.48亿</span>。</li>
</ul>

<div class="alert-bad">
  <b>失败模式 2：跌停核心标的（情绪退潮代表）</b>
</div>
<ul>
  <li>688367 <span class="stock">工大高科</span>：<span class="limit-down">-14.94%</span>，前期强势股闪崩。</li>
  <li>300465 <span class="stock">高伟达</span>：<span class="limit-down">-11.29%</span>，软件题材熄火。</li>
  <li>300461 <span class="stock">田中精机</span>：<span class="limit-down">-10.16%</span>，<b>机器人题材龙头跌停</b>，板块情绪结冰信号。</li>
  <li>600977 <span class="stock">中国电影</span>：<span class="limit-down">跌停</span>，影视院线龙头崩塌，板块 -4.56%。</li>
  <li>600598 <span class="stock">北大荒</span>：<span class="limit-down">-10.02%</span>，农业板块连环杀跌。</li>
</ul>

<div class="alert-bad">
  <b>失败模式 3：板块整体走弱中的"高位连板"风险</b>
</div>
<p>影视院线 (<span class="down">-4.56%</span>)、旅游酒店 (<span class="down">-3.86%</span>)、
煤炭 (<span class="down">-3.55%</span>)、教育 (<span class="down">-3.53%</span>)、
房地产 (<span class="down">-3.14%</span>) 整体跌幅居前，任何在这些板块里"逆势涨停"的个股
都要警惕<b>事件型短炒、明日承接乏力</b>。</p>

<hr>

<h3>五、明日策略与关键观察点</h3>
<ol>
  <li><b>主线沿半导体/AI 算力做高低切</b>，盯紧 <span class="stock">协创数据</span>、<span class="stock">领益智造</span>
  的开盘强度，若高开放量则继续扩散补涨；若高开杀跌则<b>整个 AI 算力链当日转弱</b>。</li>
  <li>锂电池主线<b>需明日二次确认</b>。永杉锂业、雅化集团涨停但净流出，
  若明日不能放量再封，则板块为<b>"一日游"行情</b>。</li>
  <li>低吸位置股需要 <span class="sector">化学纤维</span>、<span class="sector">电子化学品</span> 等次主线提供
  补涨机会；避免在影视、旅游、地产中博弈反弹。</li>
  <li>跌停股 <span class="stock">工大高科</span>、<span class="stock">田中精机</span> 是<b>短线情绪温度计</b>，
  若明日继续闷跌则市场情绪进一步降温。</li>
</ol>

<div class="risk-box">
  <b>风险提示</b>：① 半导体板块单日 +313亿 净流入后，明日<b>有获利兑现压力</b>；
  ② 涨停潮中近半数主力净流出，<b>真假强势需 T+1 验证</b>；
  ③ 顺周期/红利风格集体杀跌，若延续 2 个交易日以上，需警惕<b>大盘风格扩散下跌</b>；
  ④ 跌停 19 只 + 跌幅榜多为前期热门股，<b>情绪退潮信号已出现</b>，仓位应控制在 5-7 成。
</div>
"""

picks = [
    {
        "stock_code": "300857",
        "stock_name": "协创数据",
        "pick_level": "strong_recommend",
        "reason_summary": "AI算力/数据中心核心龙头，放量主力净流入9.69亿",
        "reason_detail": "今日涨停 +10.99%，成交 100.61亿（全市场最高量之一），主力净流入 +9.69亿，量价齐升 + 主力坚决进场。板块半导体 +3.80% 主线龙头位置已确立。空间打开后明日有继续扩散预期。",
        "sector_name": "半导体/AI算力",
        "theme_tags": ["AI算力", "数据中心", "半导体"],
        "capital_profile": {"net_inflow": 9.69, "main_force_signal": "strong", "turnover_amount": 100.61, "turnover_rate_pct": 6.31},
        "signal_context": "涨停+主力净流入+全市场最高成交，半导体板块+313亿净流入背景下的核心龙头",
        "risk_flags": ["位置已不低", "短期获利盘较多", "板块过热需高低切"],
        "entry_hint": "明日观察竞价 0~3% 区间是否承接放量，回踩 5/10 日线低吸",
        "confidence_score": 0.85
    },
    {
        "stock_code": "002600",
        "stock_name": "领益智造",
        "pick_level": "strong_recommend",
        "reason_summary": "消费电子龙头涨停，主力净流入9.98亿，苹果链补涨预期",
        "reason_detail": "+10.03% 涨停，主力净流入 +9.98亿，成交 73.05亿，换手仅 6%。消费电子板块 +0.63% 净流入 +115亿，作为板块第一权重票封板质量高。M5/M10 已多头排列，主升浪初期信号。",
        "sector_name": "消费电子",
        "theme_tags": ["苹果链", "AI硬件", "消费电子"],
        "capital_profile": {"net_inflow": 9.98, "main_force_signal": "strong", "turnover_amount": 73.05, "turnover_rate_pct": 6.0},
        "signal_context": "板块龙头封板、低换手、强主力净流入，AI硬件需求外溢逻辑",
        "risk_flags": ["板块整体涨幅偏小,有补涨与冲高分化双向可能"],
        "entry_hint": "明日竞价不破 +3% 可加仓；若高开+5%以上谨慎追",
        "confidence_score": 0.78
    },
    {
        "stock_code": "688123",
        "stock_name": "聚辰股份",
        "pick_level": "confirm",
        "reason_summary": "半导体存储20cm涨停，主力净流入5.16亿",
        "reason_detail": "20% 涨停，成交 40.78亿，主力净流入 +5.16亿，换手 16.78%。半导体存储芯片+SPD 模组逻辑，受 AI 服务器需求驱动。封板质量较好（净流入而非流出），但 20cm 票次日波动大。",
        "sector_name": "半导体",
        "theme_tags": ["半导体存储", "SPD", "AI服务器"],
        "capital_profile": {"net_inflow": 5.16, "main_force_signal": "strong", "turnover_amount": 40.78, "turnover_rate_pct": 16.78},
        "signal_context": "20cm涨停伴随净流入，半导体板块共振",
        "risk_flags": ["20cm波动大", "高换手存在分歧"],
        "entry_hint": "回踩 5 日线低吸，竞价高开 +8% 以上不追",
        "confidence_score": 0.72
    },
    {
        "stock_code": "301396",
        "stock_name": "宏景科技",
        "pick_level": "candidate",
        "reason_summary": "AI算力20cm涨停，主力净流入2.15亿",
        "reason_detail": "20% 涨停，成交 53.16亿，主力净流入 +2.15亿，换手 13.49%。AI 服务器+智算中心+液冷题材交集。绝对位置较高（股价 297.6 元），明日波动率会显著放大。",
        "sector_name": "半导体/AI算力",
        "theme_tags": ["AI算力", "智算中心", "液冷"],
        "capital_profile": {"net_inflow": 2.15, "main_force_signal": "moderate", "turnover_amount": 53.16, "turnover_rate_pct": 13.49},
        "signal_context": "20cm涨停+主线题材+主力净流入但偏弱",
        "risk_flags": ["高价股波动大", "净流入相对成交量较小,主力可能正在出货"],
        "entry_hint": "仅做日内或竞价小仓位试错，止损设涨停价 -5%",
        "confidence_score": 0.6
    },
    {
        "stock_code": "600246",
        "stock_name": "万通发展",
        "pick_level": "candidate",
        "reason_summary": "地产板块整体杀跌中逆势涨停，纯个股事件驱动",
        "reason_detail": "+10.01% 涨停，成交 38.85亿，主力净流入 +4.29亿，地产板块 -3.14% 背景下罕见的逆势封板。属于纯个股事件驱动（数据中心/算力转型预期），脱离地产β。短线情绪票，连板预期存在但持续性不强。",
        "sector_name": "房地产(算力转型)",
        "theme_tags": ["算力转型", "数据中心", "个股事件"],
        "capital_profile": {"net_inflow": 4.29, "main_force_signal": "moderate", "turnover_amount": 38.85, "turnover_rate_pct": 11.16},
        "signal_context": "弱势板块中的强势个股,情绪票连板预期",
        "risk_flags": ["板块趋势向下", "题材兑现风险", "高位换手大"],
        "entry_hint": "仅做次日竞价或一进二打板，止损跌破涨停价 -3%",
        "confidence_score": 0.55
    },
    {
        "stock_code": "600909",
        "stock_name": "华安证券",
        "pick_level": "watch",
        "reason_summary": "涨停但主力大幅净流出12.98亿，典型出货板,反向警示",
        "reason_detail": "+10.04% 涨停，但主力净流出 <b>-12.98亿</b>，成交高达 58.25亿。证券板块今日并未走强，单票涨停疑似游资对倒拉升、机构出货。明日大概率冲高回落，<b>属于反向警示标的而非买入对象</b>。",
        "sector_name": "证券",
        "theme_tags": ["券商", "出货嫌疑"],
        "capital_profile": {"net_inflow": -12.98, "main_force_signal": "weak", "turnover_amount": 58.25, "main_outflow": True},
        "signal_context": "涨停伴随巨量主力净流出,失败模式典型案例",
        "risk_flags": ["主力大幅出货", "板块未共振", "高位假强势"],
        "entry_hint": "不参与买入；如有持仓建议次日竞价高开兑现",
        "confidence_score": 0.3
    }
]

payload = {
    "trading_date": "2026-06-24",
    "skill_name": "19:00 超短线复盘",
    "job_name": "19:00 超短线复盘",
    "job_type": "stock_pick",
    "run_type": "production",
    "source_input_ref": "claude-code-cli",
    "_meta": {
        "schema_version": "3.0",
        "engine_type": "claude-code",
        "data_sources_used": [
            "prefetch:/tmp/easyquant_market_data_2026-06-24.json",
            "akshare:industry-sector-rankings",
            "akshare:individual-flow-rankings",
            "internal:limit-up-pool"
        ]
    },
    "summary": {
        "market_phase": "结构性热点-风格切换日：半导体/AI算力一枝独秀,顺周期/红利集体闷杀；涨多于跌但跌停19只,情绪呈现退潮特征。",
        "hot_sectors": [
            {"name": "能源金属", "pct": 4.27, "net_inflow": 33.25, "leader": "永杉锂业"},
            {"name": "半导体", "pct": 3.80, "net_inflow": 313.48, "leader": "协创数据/聚辰股份"},
            {"name": "元件", "pct": 3.19, "net_inflow": 13.31, "leader": "一博科技"},
            {"name": "电子化学品", "pct": 3.10, "net_inflow": 26.51, "leader": "飞凯材料"},
            {"name": "消费电子", "pct": 0.63, "net_inflow": 115.21, "leader": "领益智造"}
        ],
        "risk_signals": [
            "跌停股达19只(工大高科-14.94%、田中精机-10.16%、中国电影跌停),情绪退潮信号显著",
            "影视/旅游/教育/煤炭/地产五大板块跌幅居前,顺周期/防御风格集体杀跌",
            "涨停潮中近半数主力净流出（华安证券-12.98亿/通鼎互联-9.65亿/汇成股份-2.57亿）,真假强势需验证",
            "锂电池板块指数+4.27%但永杉锂业/雅化集团/泰和新材涨停均净流出,有指数涨个股弱的隐患",
            "半导体单日净流入313亿后,次日存在获利兑现压力",
            "全市场涨跌家数1382/3768,赚钱效应集中在头部少数主线"
        ]
    },
    "result_payload": {"structured_picks": picks},
    "raw_output": raw_html
}

out_path = "/Users/jwkj/easyquant/data/ai_center/inbox/1900_超短线复盘_2026-06-24_20260624_190024.json"
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

# size check
import os
print(f"OK, wrote {os.path.getsize(out_path)} bytes")
print(f"picks: {len(picks)}")
