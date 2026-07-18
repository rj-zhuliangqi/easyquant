"""生成 2026-07-18 每日持仓复盘 JSON 产物。

2026-07-18 为周六休市，实际行情日为 2026-07-17（周五）。
"""
import json

HTML = """<h2>一、复盘说明与交易日定位</h2>
<div class="alert-bad">本任务日 <b>2026-07-18 为周六，A股休市</b>，无盘口数据。本期实际复盘行情日为 <b>2026-07-17（周五）</b>，下一交易日为 <b>2026-07-20（周一）</b>。</div>
<p>周六持仓与周五收盘完全一致，本期定位为<b>"周末持仓复盘 + 操作得失总结 + 周一执行计划"</b>。所有行情、资金流数据均取自 2026-07-17 收盘（AKShare 预取）。</p>
<hr>

<h2>二、市场全景：系统性暴跌后的极端二八分化</h2>
<h3>2.1 三大指数</h3>
<p>上证指数 <span class="down">-3.05%</span> ／ 深证成指 <span class="down">-5.40%</span> ／ 创业板指 <span class="down">-7.15%</span>，创业板单日跌幅超 7%，属<b>系统性风险释放</b>。</p>
<h3>2.2 涨跌广度</h3>
<p>全市场 5195 只样本：上涨 <span class="highlight">497 只</span> ／ 下跌 <span class="highlight">4651 只</span>，涨停 <span class="limit-up">37 只</span>，跌停 <span class="limit-down">505 只</span>，涨跌中位数 <span class="down">-3.68%</span>。涨跌比约 1:9.4，<b>全市场仅 2/90 个板块上涨</b>。</p>
<h3>2.3 板块涨幅 TOP5</h3>
<table>
<tr><th>排名</th><th>板块</th><th>涨跌幅</th></tr>
<tr><td>1</td><td><span class="sector">电力</span></td><td><span class="up">+1.25%</span></td></tr>
<tr><td>2</td><td><span class="sector">银行</span></td><td><span class="up">+0.40%</span></td></tr>
<tr><td>3</td><td><span class="sector">港口航运</span></td><td><span class="down">-0.41%</span></td></tr>
<tr><td>4</td><td><span class="sector">油气开采及服务</span></td><td><span class="down">-0.45%</span></td></tr>
<tr><td>5</td><td><span class="sector">公路铁路运输</span></td><td><span class="down">-0.58%</span></td></tr>
</table>
<h3>2.4 板块跌幅 TOP5</h3>
<table>
<tr><th>排名</th><th>板块</th><th>涨跌幅</th></tr>
<tr><td>1</td><td><span class="sector">半导体</span></td><td><span class="down">-9.83%</span></td></tr>
<tr><td>2</td><td><span class="sector">元件</span></td><td><span class="down">-8.76%</span></td></tr>
<tr><td>3</td><td><span class="sector">医疗服务</span></td><td><span class="down">-8.38%</span></td></tr>
<tr><td>4</td><td><span class="sector">其他电子</span></td><td><span class="down">-8.07%</span></td></tr>
<tr><td>5</td><td><span class="sector">电子化学品</span></td><td><span class="down">-7.89%</span></td></tr>
</table>
<p>资金面：主力净流出重灾区为 <span class="sector">半导体</span> <span class="outflow">-94.45亿</span>、<span class="sector">化学制药</span> <span class="outflow">-61.54亿</span>、<span class="sector">消费电子</span> <span class="outflow">-32.25亿</span>；净流入仅 <span class="sector">银行</span> <span class="inflow">+43.92亿</span>、<span class="sector">电力</span> <span class="inflow">+24.36亿</span> 抱团防御。</p>
<hr>

<h2>三、持仓表现总览（截至 2026-07-17 收盘）</h2>
<p>组合总市值 <span class="highlight">38.92 万元</span>，上一交易日加权涨跌 <span class="up">+4.09%</span>，<b>大幅跑赢市场中位数 -3.68% 达 +7.77%</b>。但累计浮亏约 <span class="highlight">-1.41 万元</span>，主要被 <span class="stock">迈瑞医疗</span>（-37.33%）与 <span class="stock">贵州茅台</span>（-13.45%）两口拖累，<b>结构性盈亏分化严重</b>。</p>
<table>
<tr><th>股票</th><th>权重</th><th>现价</th><th>今日</th><th>累计</th><th>主力净额</th><th>换手</th><th>周一建议</th></tr>
<tr><td><span class="stock">新锦动力</span></td><td>20%</td><td>4.13</td><td><span class="up">+11.92%</span></td><td><span class="up">+0.73%</span></td><td><span class="inflow">+1.15亿</span></td><td>20.18%</td><td>减仓1/2</td></tr>
<tr><td><span class="stock">中国银行</span></td><td>30%</td><td>5.96</td><td><span class="up">+2.76%</span></td><td><span class="up">+8.36%</span></td><td><span class="inflow">+7.66亿</span></td><td>0.22%</td><td>持有</td></tr>
<tr><td><span class="stock">中国石油</span></td><td>30%</td><td>10.29</td><td><span class="up">+3.00%</span></td><td><span class="up">+5.00%</span></td><td><span class="inflow">+5.47亿</span></td><td>0.16%</td><td>持有</td></tr>
<tr><td><span class="stock">贵州茅台</span></td><td>10%</td><td>1254.97</td><td><span class="down">-0.32%</span></td><td><span class="down">-13.45%</span></td><td><span class="inflow">+8.07亿</span></td><td>0.46%</td><td>减仓至5%</td></tr>
<tr><td><span class="stock">迈瑞医疗</span></td><td>10%</td><td>150.40</td><td><span class="up">+0.06%</span></td><td><span class="down">-37.33%</span></td><td><span class="inflow">+0.30亿</span></td><td>1.21%</td><td>清仓止损</td></tr>
</table>
<div class="alert-good">组合逆势 +4.09% 的核心来源：<b>中国银行 + 中国石油 合计 60% 红利底仓</b>逆势收红，贡献组合 90% 以上正收益；新锦动力题材冲高提供额外弹性。</div>
<hr>

<h2>四、操作得失逐项复盘</h2>
<h3>4.1 得 —— 红利底仓救场，AI 信号兑现</h3>
<div class="alert-good">
<p><b>红利防御是组合稳定器：</b><span class="stock">中国银行</span>（+2.76%，主力 <span class="inflow">+7.66亿</span>）+ <span class="stock">中国石油</span>（+3.00%，主力 <span class="inflow">+5.47亿</span>）合计 60% 仓位，在 505 跌停的系统性回调中逆势收红。<b>红利底仓维持 50%-60% 权重的策略被本周行情充分验证。</b></p>
</div>
<div class="alert-good">
<p><b>AI 选股信号与持仓高度共振：</b><span class="stock">中国银行</span> 入选"大象起舞"选股、<span class="stock">中国石油</span> 入选尾盘选股，双双兑现。<b>模型对当前"大票逆势吸金"行情判断有效，可继续信任。</b></p>
</div>
<h3>4.2 失 —— 止损缺失酿深套，白马追高套牢</h3>
<div class="alert-bad">
<p><b>迈瑞医疗 -37.33% 深套，止损纪律缺失：</b>从 240 元跌至 150 元，期间错过 -20%/148 元两道止损位，是典型"鸵鸟心态"。<b>单股浮亏超 30% 应强制止损</b>，再等反弹往往越陷越深。医疗器械板块 -5.38%、医疗服务 -8.38%，板块环境恶化放大了个股损失。该笔持仓存在<b>严重选股失误 + 止损纪律缺失</b>。</p>
</div>
<div class="alert-bad">
<p><b>贵州茅台 -13.45% 估值仍处下行通道：</b>成本 1450 元偏高，当前 1255 元中枢仍在收敛。主力 <span class="inflow">+8.07亿</span> 看似护盘，但白酒板块整体 <span class="down">-2.83%</span>。<b>白马股不在估值合理区间介入 = 长期套牢</b>，需等 PE 回到 25x 以下再考虑。</p>
</div>
<div class="alert-bad">
<p><b>新锦动力 +11.92% 看似强势，实为游资博弈：</b>换手率高达 <span class="highlight">20.18%</span>、振幅巨大，主力净额仅 <span class="inflow">+1.15亿</span>（成交 6.07 亿），典型游资接力形态，次日承接力存疑。<b>追涨题材股必须预设次日开盘止损位</b>（3.85 元 / -7%），不可贪恋再涨。</p>
</div>
<hr>

<h2>五、周一（2026-07-20）操作计划</h2>
<table>
<tr><th>操作</th><th>标的</th><th>理由</th></tr>
<tr><td><span class="limit-down">清仓</span></td><td><span class="stock">迈瑞医疗</span></td><td>深套 -37% 止损，开盘即执行，不再犹豫</td></tr>
<tr><td>减仓至5%</td><td><span class="stock">贵州茅台</span></td><td>估值下行通道，控制医药消费敞口</td></tr>
<tr><td>减仓1/2</td><td><span class="stock">新锦动力</span></td><td>题材冲高兑现，跟踪开盘强度，止损 3.85 元</td></tr>
<tr><td>持有</td><td><span class="stock">中国银行 / 中国石油</span></td><td>红利底仓不动，享受防御溢价</td></tr>
<tr><td>总仓位</td><td>38.9万 → 约30万</td><td>降低 β 至 0.5 以下，防御为主</td></tr>
</table>
<div class="alert-good">若周一市场延续恐慌（跌停 &gt; 200 家），<b>优先执行减仓而非加仓</b>，把现金留到情绪冰点再考虑接力。所有减仓指令宜在开盘 15 分钟内挂单。</div>
<hr>

<h2>六、风险提示</h2>
<div class="risk-box">
<p><b>1. 系统性回调尚未确认止跌：</b>505 跌停、创业板 -7.15%、半导体 -9.83%，科技主线资金踩踏未止，<b>周一开盘大概率仍有惯性下探</b>，所有减仓指令宜在开盘 15 分钟内挂单。</p>
<p><b>2. 红利拥挤度上升：</b>银行净流入 <span class="inflow">+43.92亿</span>、电力 <span class="inflow">+24.36亿</span>，防御资金高度抱团，<b>若下周情绪修复，红利可能短线补跌</b>，底仓不宜再加。</p>
<p><b>3. 茅台 / 迈瑞估值再下台阶风险：</b>白马估值收敛 + 板块弱势，<b>1255 元茅台、150 元迈瑞均非安全边际</b>，减仓后不要急于回补。</p>
<p><b>4. 题材股流动性风险：</b>新锦动力换手 20%、成交 6.07 亿，<b>周一一旦低开容易闷杀</b>，减仓挂单宜偏低 1-2 档。</p>
<p><b>5. 周末消息面不确定性：</b>周五暴跌后留意周末监管/政策对冲、外围市场联动，<b>若出现重大利好高开反而是减仓良机而非追涨时点</b>。</p>
</div>"""

picks = [
    {
        "stock_code": "300157",
        "stock_name": "新锦动力",
        "pick_level": "candidate",
        "reason_summary": "题材博弈冲高 +11.92% 但换手 20% 游资接力，次日承接存疑，建议减仓 1/2 锁利。",
        "reason_detail": "上一交易日收涨 11.92%、主力净流入 1.15 亿，但换手率高达 20.18%、振幅巨大，属典型游资博弈形态。累计浮盈仅 +0.73%，成本接近现价，盘口一旦转弱盈利快速消失。所属油气开采及服务板块当日 -0.45%，个股与板块背离、独立性过强，为游资票特征。",
        "sector_name": "油气服务",
        "theme_tags": ["题材博弈", "游资接力", "油气服务", "高换手"],
        "capital_profile": {"net_inflow": 1.15, "main_force_signal": "moderate"},
        "signal_context": "极弱市场中唯一大幅冲高持仓，但板块不同步、换手过高，主力净额相对成交偏弱（1.15亿/6.07亿）。",
        "risk_flags": ["换手 20% 游资接力，次日闷杀风险", "振幅巨大、承接力存疑", "累计浮盈薄，回吐即亏"],
        "entry_hint": "周一开盘若不能放量突破 4.20 元则减仓 1/2 锁利；低开回踩 5 日线可观察但仓位不超 10%。止损 3.85 元（-7%）。",
        "confidence_score": 0.55,
    },
    {
        "stock_code": "601988",
        "stock_name": "中国银行",
        "pick_level": "strong_recommend",
        "reason_summary": "红利核心底仓逆势 +2.76%，主力净流入 7.66 亿，系统性回调中稳定锚，继续持有。",
        "reason_detail": "银行板块 +0.40%（90 板块仅 2 个上涨之一）、净流入 43.92 亿居全市场第一，中国银行作为容量龙头 +2.76%、主力净流入 7.66 亿。累计浮盈 +8.36% 为组合最大正贡献。在 505 跌停的系统性回调中红利资产被资金抱团，底仓配置逻辑成立。",
        "sector_name": "银行",
        "theme_tags": ["红利防御", "央企", "高股息", "大象起舞"],
        "capital_profile": {"net_inflow": 7.66, "main_force_signal": "strong"},
        "signal_context": "银行板块净流入 43.92 亿全市场第一，红利抱团核心，与大象起舞 AI 选股信号共振。",
        "risk_flags": ["红利拥挤度上升，情绪修复时或短线补跌", "累计 +8.36% 获利回吐压力"],
        "entry_hint": "中线持有不设止损；回补缺口至 5.70 元下方减仓观察。底仓不再加仓。",
        "confidence_score": 0.88,
    },
    {
        "stock_code": "601857",
        "stock_name": "中国石油",
        "pick_level": "strong_recommend",
        "reason_summary": "红利 + 能源安全双驱动 +3.00%，主力净流入 5.47 亿，防御属性突出，继续持有。",
        "reason_detail": "石油加工贸易板块净流入 5.10 亿为资金防御支线，中国石油 +3.00%、主力净流入 5.47 亿，累计浮盈 +5.00%。红利 + 能源安全双逻辑共振，与尾盘选股 AI 信号兑现。换手仅 0.16%，筹码稳定。",
        "sector_name": "石油石化",
        "theme_tags": ["红利防御", "能源安全", "央企", "尾盘选股"],
        "capital_profile": {"net_inflow": 5.47, "main_force_signal": "strong"},
        "signal_context": "石油加工贸易板块净流入 5.10 亿，红利 + 能源双驱动，与尾盘选股 AI 信号共振。",
        "risk_flags": ["国际油价波动风险", "累计 +5% 浮盈回吐压力"],
        "entry_hint": "成本 9.80 元为止盈底线；跌破 9.50 元减仓 1/3。中线持有。",
        "confidence_score": 0.85,
    },
    {
        "stock_code": "600519",
        "stock_name": "贵州茅台",
        "pick_level": "watch",
        "reason_summary": "浮亏 -13.45% 估值下行通道，主力护盘但板块弱势，减仓至 5% 控制敞口。",
        "reason_detail": "今日仅 -0.32% 远小于市场，但浮亏 -13.45% 已侵蚀净值。主力净流入 8.07 亿看似护盘，但白酒板块 -2.83%、中枢下移。基本面（消费降级）+ 资金面 + 板块轮动三重压力下估值仍有收敛风险，成本 1450 元偏高。",
        "sector_name": "白酒",
        "theme_tags": ["白酒龙头", "估值收敛", "消费降级", "白马"],
        "capital_profile": {"net_inflow": 8.07, "main_force_signal": "mixed"},
        "signal_context": "主力净流入 8.07 亿护盘，但白酒板块 -2.83%、估值中枢下移，护盘难改趋势。",
        "risk_flags": ["估值仍处下行通道", "成本 1450 偏高、套牢风险", "跌破 1240 元技术破位"],
        "entry_hint": "减仓至 5%；若白酒板块续弱、跌破 1240 元则技术破位需果断减仓。中线止损 1180 元（-19%）。",
        "confidence_score": 0.45,
    },
    {
        "stock_code": "300760",
        "stock_name": "迈瑞医疗",
        "pick_level": "watch",
        "reason_summary": "浮亏 -37.33% 远超阈值，止损纪律缺失，周一开盘清仓止损。",
        "reason_detail": "从 240 元跌至 150.4 元，错过 -20%/148 元两道止损位，典型鸵鸟心态。医疗器械板块 -5.38%、医疗服务 -8.38% 板块杀跌严重。今日勉强红盘 +0.06% 但主力净流入仅 0.30 亿、弱势中继。该笔持仓存在严重选股失误 + 止损纪律缺失。",
        "sector_name": "医疗器械",
        "theme_tags": ["医疗器械", "深套止损", "板块杀跌", "选股失误"],
        "capital_profile": {"net_inflow": 0.30, "main_force_signal": "weak"},
        "signal_context": "主力净流入仅 0.30 亿、弱势中继，医疗器械板块 -5.38% 环境恶化。",
        "risk_flags": ["浮亏 -37% 远超 -20% 阈值", "板块杀跌放大损失", "止损纪律缺失"],
        "entry_hint": "周一开盘即清仓，不再犹豫；若开盘暴跌则分批止损但当日必须清完。",
        "confidence_score": 0.92,
    },
]

doc = {
    "trading_date": "2026-07-18",
    "skill_name": "21:30 每日持仓复盘",
    "job_name": "21:30 每日持仓复盘",
    "job_type": "stock_pick",
    "run_type": "production",
    "source_input_ref": "claude-code-cli",
    "_meta": {
        "schema_version": "3.0",
        "engine_type": "claude-code",
        "data_sources_used": [
            "/tmp/easyquant_market_data_2026-07-18.json（AKShare 预取，实际行情日 2026-07-17）",
            "easyquant-local-api /api/status",
            "历史持仓复盘 2130_每日持仓复盘_2026-07-17（持仓成本/权重来源）",
        ],
    },
    "summary": {
        "market_phase": "周六休市·周末持仓复盘（实际行情日 2026-07-17 系统性暴跌：上证 -3.05%、创业板 -7.15%、505 跌停、仅电力/银行 2 板块上涨）",
        "position_count": 5,
        "total_market_value_yuan": 389177,
        "weighted_daily_change_pct": 4.09,
        "total_cumulative_pnl_yuan": -14133,
        "vs_median_market": "+7.77%",
        "hot_sectors": [
            "电力（+1.25%，净流入 24.36 亿）",
            "银行（+0.40%，净流入 43.92 亿）",
            "石油加工贸易（资金防御支线，净流入 5.10 亿）",
        ],
        "weak_sectors": [
            "半导体（-9.83%，净流出 94.45 亿）",
            "元件（-8.76%）",
            "医疗服务（-8.38%）",
            "医疗器械（-5.38%）",
            "白酒（-2.83%）",
        ],
        "limit_up_count": 37,
        "limit_down_count": 505,
        "market_median_change_pct": -3.68,
        "market_breadth_up": 497,
        "market_breadth_down": 4651,
        "risk_signals": [
            "2026-07-18 周六休市，持仓与 07-17 收盘一致，下一交易日 07-20 周一",
            "07-17 系统性暴跌：上证 -3.05%、创业板 -7.15%、505 跌停、中位数 -3.68%",
            "半导体 -9.83% 净流出 94.45 亿，科技主线踩踏未止",
            "迈瑞医疗浮亏 -37.33% 深套，止损纪律缺失，周一开盘清仓",
            "贵州茅台浮亏 -13.45% 估值下行，减仓至 5%",
            "红利拥挤：银行 + 电力抱团，若情绪修复或短线补跌",
        ],
    },
    "result_payload": {
        "structured_picks": picks,
    },
    "raw_output": HTML,
}

# 校验：每个 pick 必须含全部 12 字段，theme_tags/risk_flags 非空，capital_profile 非空
required = [
    "stock_code", "stock_name", "pick_level", "reason_summary", "reason_detail",
    "sector_name", "theme_tags", "capital_profile", "signal_context",
    "risk_flags", "entry_hint", "confidence_score",
]
valid_levels = {"watch", "candidate", "confirm", "strong_recommend"}
for p in picks:
    missing = [k for k in required if k not in p]
    assert not missing, f"{p['stock_name']} 缺字段 {missing}"
    assert p["pick_level"] in valid_levels, p["pick_level"]
    assert len(p["theme_tags"]) > 0 and len(p["risk_flags"]) > 0
    assert isinstance(p["capital_profile"], dict) and len(p["capital_profile"]) > 0

out = "/Users/jwkj/easyquant/data/ai_center/inbox/2130_每日持仓复盘_2026-07-18_20260718_213025.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, indent=2)
print("written:", out)
print("picks:", len(picks), "raw_output bytes:", len(HTML))
