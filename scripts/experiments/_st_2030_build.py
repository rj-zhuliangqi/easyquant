"""Build final ST 20:30 JSON output."""
import json
from pathlib import Path

# Source data
local = json.load(open("/Users/jwkj/easyquant/scripts/_st_2030_full.json"))
tencent = json.load(open("/Users/jwkj/easyquant/scripts/_st_2030_tencent.json"))

# index tencent by code
tx = {r["code"]: r for r in tencent}

# Backend's ST sector list (top 10 by % change)
api_stocks = local["st_top_gain"]["stocks"]
sector_meta = local["st_top_gain"]

# Sector-level inflow summary
total_inflow = sum(s["今日主力净流入-净额"] for s in api_stocks) / 1e6
inflow_pos = sum(1 for s in api_stocks if s["今日主力净流入-净额"] > 0)
inflow_neg = sum(1 for s in api_stocks if s["今日主力净流入-净额"] < 0)
print(f"sector inflow sum: {total_inflow:.2f}M positive={inflow_pos} negative={inflow_neg}")

# Total amount & limit-up count
total_amt = sum(tx[s["代码"]]["amount_yi"] for s in api_stocks if s["代码"] in tx)
limit_up_count = sum(1 for s in api_stocks if s["代码"] in tx and tx[s["代码"]]["is_limit_up"])
print(f"total amt: {total_amt:.2f}亿 limit_up={limit_up_count}/10")

# Build raw_output HTML
html_parts = []

# Section 1: 市场概览
html_parts.append("<h2>📊 ST 板块 20:30 盘后扫描</h2>")
html_parts.append(
    f'<p>交易日: <span class="highlight">2026-06-24</span> · 数据来源: 后端API聚合(东方财富) + 腾讯行情 · '
    f'ST 板块异动榜 TOP10: <span class="highlight">{limit_up_count}</span> 只涨停，'
    f'总成交 <span class="highlight">{total_amt:.2f}亿</span>，'
    f'主力资金合计净'
    + (f'流入 <span class="inflow">+{total_inflow:.1f}百万</span>' if total_inflow >= 0 else f'流出 <span class="outflow">{total_inflow:.1f}百万</span>')
    + "。</p>"
)

# Section 2: 异动榜表格
html_parts.append("<hr>")
html_parts.append("<h2>🔥 ST 板块异动榜（按涨幅排序）</h2>")
html_parts.append("<table>")
html_parts.append("<thead><tr><th>排名</th><th>代码</th><th>股票</th><th>最新价</th><th>涨跌幅</th><th>成交额</th><th>换手</th><th>流通市值</th><th>主力净流入</th><th>状态</th></tr></thead><tbody>")
for i, s in enumerate(api_stocks, 1):
    code = s["代码"]
    name = s["名称"]
    chg = s["今日涨跌幅"]
    inflow_m = s["今日主力净流入-净额"] / 1e6
    t = tx.get(code, {})
    cur = t.get("cur", s["最新价"])
    amt = t.get("amount_yi", 0)
    turn = t.get("turnover_pct", 0)
    fmc = t.get("float_mc_yi", 0)
    is_limit = t.get("is_limit_up", False)
    chg_str = f'<span class="up">+{chg:.2f}%</span>' if chg > 0 else f'<span class="down">{chg:.2f}%</span>'
    inflow_str = f'<span class="inflow">+{inflow_m:.1f}M</span>' if inflow_m > 0 else f'<span class="outflow">{inflow_m:.1f}M</span>'
    flag = '<span class="limit-up">涨停</span>' if is_limit else (
        '<span class="tag">异动放量</span>' if chg > 5 else '<span class="tag">小幅上涨</span>'
    )
    html_parts.append(
        f"<tr><td>{i}</td><td>{code}</td>"
        f'<td><span class="stock">{name}</span></td>'
        f"<td>{cur:.2f}</td><td>{chg_str}</td><td>{amt:.2f}亿</td><td>{turn:.2f}%</td>"
        f"<td>{fmc:.1f}亿</td><td>{inflow_str}</td><td>{flag}</td></tr>"
    )
html_parts.append("</tbody></table>")

# Section 3: 异常观察
html_parts.append("<hr>")
html_parts.append("<h2>🔬 异常观察 — 限制突破信号</h2>")
html_parts.append(
    '<div class="alert-good">'
    "<b>关键发现</b>：今日 ST 板块前 2 只标的涨幅突破常规 5% 限制 — "
    '<span class="stock">ST长方</span> <span class="up">+17.48%</span>（封涨停3.71元，意味当日适用 <b>20%</b> 涨跌限制）、'
    '<span class="stock">*ST泉为</span> <span class="up">+7.96%</span>（封涨停26.68元 ≈ +10% 限制）。'
    '这通常对应 <span class="tag">摘帽脱星预案</span>/<span class="tag">重大事项复牌</span> 后交易规则切换，'
    '同时两只标的主力净流入榜前 2 — ST长方 <span class="inflow">+44.2M</span>、*ST泉为 <span class="inflow">+23.5M</span>，'
    "资金面与价格面同步释放摘帽预期信号。"
    "</div>"
)

html_parts.append(
    '<div class="alert-bad">'
    '<b>警惕分化</b>：7 只 5% 一字/封板个股中资金流向严重分化 — '
    '<span class="stock">ST东尼</span>涨停但主力<span class="outflow">净流出 -53.6百万</span>（板内最大流出），'
    '<span class="stock">*ST帅电</span>涨停但净流出<span class="outflow">-10.7百万</span>，'
    '<span class="stock">*ST华鹏</span>涨停但净流出<span class="outflow">-6.4百万</span>。'
    "涨停封板与资金外撤同步，反映游资接力意愿弱化、次日炸板/获利兑现风险高。"
    "</div>"
)

# Section 4: 风险提示
html_parts.append("<hr>")
html_parts.append("<h2>⚠️ 风险提示</h2>")
html_parts.append(
    '<div class="risk-box">'
    "<b>ST 板块特有风险</b>："
    "<ol>"
    '<li><b>退市风险</b>：*ST 前缀股存在退市预警，财务报告/审计意见落地前不确定性极高；本次 7 只 *ST 标的均需核对年报披露进度。</li>'
    "<li><b>流动性风险</b>：<span class=\"stock\">ST中装</span>当日成交仅 <span class=\"highlight\">0.03亿</span>（330万元）、换手 0.10%，无法承接任何机构资金；类似 <span class=\"stock\">*ST帅电</span>成交 0.17亿亦偏低。</li>"
    '<li><b>规则切换风险</b>：摘帽前后涨跌停限制由 5% 切换至 10%/20%，单日波动放大 4 倍，止损纪律必须严格。</li>'
    '<li><b>消息真空风险</b>：本扫描基于盘面数据，未交叉核对公告/重组进度；执行前必须复核交易所/巨潮最新公告。</li>'
    '<li><b>仓位纪律</b>：ST 标的合计仓位建议 ≤ 总仓位 10%，单标的 ≤ 2%。</li>'
    "</ol></div>"
)

# Section 5: 选股结论
html_parts.append("<hr>")
html_parts.append("<h2>🎯 选股结论（按等级排序）</h2>")
html_parts.append(
    "<p>基于 <b>限制突破信号 + 主力净流入</b> 双重过滤，从异动榜 10 只中筛出 <span class=\"highlight\">3 只 confirm + 3 只 watch</span>，"
    "其余 4 只因 <b>资金净流出 / 流动性不足</b> 剔除。</p>"
)

html_parts.append("<h3>🟢 confirm 级别（限制突破 + 资金净流入）</h3>")
html_parts.append("<ul>")
html_parts.append(
    '<li><b>300301 <span class="stock">ST长方</span></b> · '
    '<span class="up">+17.48%</span> · 主力<span class="inflow">+44.2M</span> · 流通市值 30亿 · 换手 4.19% · '
    '突破 5% 涨跌限制 → <span class="tag">摘帽预期</span>实质性触发；成交 1.11亿稀释充分，资金接力强度位列板块第一。</li>'
)
html_parts.append(
    '<li><b>300716 <span class="stock">*ST泉为</span></b> · '
    '<span class="up">+7.96%</span> · 主力<span class="inflow">+23.5M</span> · 流通市值 38亿 · 换手 4.52% · '
    '涨幅突破 5% 上限至约 10% 区间 → <span class="tag">摘星脱帽</span>规则切换；流通盘适中，封板未完全锁筹，资金仍在介入。</li>'
)
html_parts.append(
    '<li><b>002713 <span class="stock">*ST东易</span></b> · '
    '<span class="up">+5.01%</span> <span class="limit-up">涨停</span> · 主力<span class="inflow">+12.3M</span> · 流通市值 <span class="highlight">109.7亿</span> · 换手 2.87% · '
    'ST 板块最大权重股一字封板 + 资金净流入，</li>'
)
html_parts.append("</ul>")

html_parts.append("<h3>🟡 watch 级别（涨停 + 微弱净流入，跟踪明日承接）</h3>")
html_parts.append("<ul>")
html_parts.append(
    '<li><b>600289 <span class="stock">ST信通</span></b> · '
    '<span class="up">+5.01%</span> <span class="limit-up">涨停</span> · 主力<span class="inflow">+5.7M</span> · 流通 34亿 · '
    "成交仅 0.34亿，封板换手低，需观察次日是否放量。</li>"
)
html_parts.append(
    '<li><b>000838 <span class="stock">*ST发展</span></b> · '
    '<span class="up">+5.33%</span> <span class="limit-up">涨停</span> · 主力<span class="inflow">+0.9M</span> · 价格 <span class="highlight">1.58元</span> · '
    "低价 ST 弹性大但面值退市边际，仅作短期博弈。</li>"
)
html_parts.append(
    '<li><b>300831 <span class="stock">ST派瑞</span></b> · '
    '<span class="up">+5.86%</span> · 主力<span class="outflow">-3.0M</span> · 成交 3.11亿 · 换手 <span class="highlight">7.71%</span> · '
    "高换手放量但资金面微负，标记观察、非买点。</li>"
)
html_parts.append("</ul>")

html_parts.append("<h3>🔴 不推荐（涨停 + 主力净流出 / 流动性不足）</h3>")
html_parts.append(
    "<p style=\"color:#888\">"
    '<span class="stock">603595 ST东尼</span>（涨停但净流出<span class="outflow">-53.6M</span>）、'
    '<span class="stock">605336 *ST帅电</span>（流出 -10.7M）、'
    '<span class="stock">603021 *ST华鹏</span>（流出 -6.4M）、'
    '<span class="stock">002822 ST中装</span>（成交 0.03亿，<b>流动性枯竭</b>）。</p>'
)

# Section 6: 操作纪律
html_parts.append("<hr>")
html_parts.append("<h2>📋 操作纪律</h2>")
html_parts.append(
    "<ul>"
    "<li><b>开仓</b>：confirm 级别次日竞价分歧时择机介入，封板买入需配合放量；ST长方/泉为 已破限制，参考 10%/20% 弹性。</li>"
    "<li><b>止损</b>：ST 标的统一硬止损 -7%，触发即出，不与基本面纠缠。</li>"
    "<li><b>止盈</b>：confirm 标的滚动止盈，跌破 5 日线减半仓；连板兑现一半。</li>"
    "<li><b>规避</b>：成交 < 0.1亿、换手 < 1% 的 ST 一律剔除（如 ST中装）。</li>"
    "<li><b>事件核对</b>：盘前 8:00 前查阅巨潮最新公告，确认无暂停上市/退市风险警示更新。</li>"
    "</ul>"
)

raw_output = "\n".join(html_parts)

# Structured picks
def make_pick(code, name, level, reason_summary, reason_detail, theme, capital, signal, risks, hint, conf):
    return {
        "stock_code": code,
        "stock_name": name,
        "pick_level": level,
        "reason_summary": reason_summary,
        "reason_detail": reason_detail,
        "sector_name": "ST板块",
        "theme_tags": theme,
        "capital_profile": capital,
        "signal_context": signal,
        "risk_flags": risks,
        "entry_hint": hint,
        "confidence_score": conf,
    }


picks = [
    make_pick(
        "300301", "ST长方", "confirm",
        "突破5%涨跌限制+主力资金净流入板块第一，摘帽预期实质性触发",
        "ST长方今日收涨17.48%，封板价3.71元对应20%涨跌限制规则；成交1.11亿元、换手4.19%、流通市值30.12亿，主力资金净流入44.2百万为ST板块第一。结合5%限制被突破，盘面已切换至摘帽后交易模式，资金面与价格面共振释放强信号。",
        ["摘帽预期", "ST板块异动", "限制突破", "主力净流入"],
        {"net_inflow": 44197900.0, "main_force_signal": "strong", "st_type": "ST/摘帽预期", "delist_risk": "中"},
        "ST板块TOP1异动，主力净流入板块最大，5%限制已切换至20%，技术面与资金面均确认",
        ["ST风险", "摘帽落地不确定性", "波动幅度放大至20%", "次日分歧风险"],
        "次日竞价回踩或分歧时介入，止损-7%；首仓不超过总仓位2%",
        0.72,
    ),
    make_pick(
        "300716", "*ST泉为", "confirm",
        "涨幅7.96%突破5%上限，主力净流入板块第二，摘星脱帽规则切换",
        "*ST泉为今日收涨7.96%至24.00元，封板价26.68元对应约10%涨跌限制；成交1.69亿元、换手4.52%、流通市值38.4亿，主力资金净流入23.5百万为板块第二。涨幅已穿透5%限制，市场用价格表态摘星脱帽预案存在。",
        ["摘星脱帽", "ST板块异动", "限制突破", "主力净流入"],
        {"net_inflow": 23547400.0, "main_force_signal": "strong", "st_type": "*ST/摘星预期", "delist_risk": "中"},
        "板块第二资金流入，封板未完全锁筹，市场对摘星脱帽预案定价中",
        ["ST风险", "*ST退市警示", "摘星方案不确定", "波动放大至10%"],
        "次日10:00前观察是否再封涨停，若回踩28元上方介入，跌破24硬止损",
        0.68,
    ),
    make_pick(
        "002713", "*ST东易", "confirm",
        "ST板块最大权重一字涨停+主力净流入，板块旗手地位",
        "*ST东易今日5.01%一字涨停于11.53元，流通市值109.7亿为ST板块第一权重，成交1.69亿、换手2.87%（封板锁筹充分），主力资金净流入12.3百万。作为板块最大流通市值标的，对ST板块情绪有锚定作用，次日带动板块联动概率高。",
        ["ST大权重", "一字涨停", "板块旗手", "主力净流入"],
        {"net_inflow": 12349400.0, "main_force_signal": "strong", "st_type": "*ST/重整预期", "delist_risk": "中"},
        "板内最大流通市值+一字封板+资金净流入三重共振",
        ["ST风险", "*ST退市警示", "封板高度需次日验证", "重整方案不确定"],
        "次日竞价高开>3%可少量跟进，开盘炸板即放弃；硬止损-7%",
        0.65,
    ),
    make_pick(
        "600289", "ST信通", "watch",
        "板内涨停+主力小幅净流入，但成交萎缩需观察次日承接",
        "ST信通今日5.01%一字涨停于5.45元，流通市值34.4亿，但成交仅0.34亿元、换手1.14%偏低，主力净流入5.7百万为温和水平。封板未充分换手，次日是否放量是关键观察点。",
        ["ST板块异动", "一字涨停", "低换手封板"],
        {"net_inflow": 5739500.0, "main_force_signal": "moderate", "st_type": "ST/摘帽预期", "delist_risk": "中"},
        "封板但换手低，需次日放量验证",
        ["ST风险", "成交不足", "封板高度不足"],
        "纯跟踪，次日若放量回踩5.20元上方可尝试，否则不操作",
        0.50,
    ),
    make_pick(
        "000838", "*ST发展", "watch",
        "低价*ST涨停弹性大，但1.58元接近面值退市边际",
        "*ST发展5.33%涨停于1.58元，主力小幅净流入0.9百万。低价ST弹性高但价格距1元面值退市仅37%缓冲，存在退市倒计时风险，仅适合极小仓位短期博弈。",
        ["低价ST", "一字涨停", "面值边际"],
        {"net_inflow": 890100.0, "main_force_signal": "weak", "st_type": "*ST/低价警戒", "delist_risk": "高"},
        "低价ST涨停，但面值退市风险叠加",
        ["ST风险", "*ST退市警示", "面值退市风险", "1元保壳压力"],
        "极小仓位博弈，单只≤0.5%总仓位；硬止损1.50元",
        0.35,
    ),
    make_pick(
        "300831", "ST派瑞", "watch",
        "高换手放量但资金面微负，标记跟踪而非买点",
        "ST派瑞涨5.86%至22.40元，成交3.11亿元、换手7.71%为板块第一高，但主力资金净流出3.0百万。放量+资金外撤反映散户接力游资派发，技术面看似活跃实则筹码松动，标记watch而非买点。",
        ["ST板块异动", "高换手", "散户接力"],
        {"net_inflow": -2958100.0, "main_force_signal": "weak", "st_type": "ST/异动", "delist_risk": "中"},
        "放量异动但主力净流出，警惕游资派发",
        ["ST风险", "主力资金外撤", "筹码松动"],
        "不主动开仓，跟踪次日是否回补；若主力反向净流入再考虑",
        0.35,
    ),
]

summary = {
    "market_phase": "ST 板块异动放大 — 10 只 TOP 标的中 7 只一字封板、2 只突破 5% 限制（摘帽规则切换），但资金分化严重，仅 6 只主力净流入。",
    "hot_sectors": ["ST摘帽预期", "ST摘星脱帽", "ST重整预期", "低价ST弹性"],
    "risk_signals": [
        "ST板块涨停股中过半主力净流出，游资接力意愿弱化",
        "ST中装成交仅0.03亿，流动性枯竭",
        "*ST发展价格1.58元，距面值退市仅37%缓冲",
        "限制突破至10%/20%档位，单日波动放大4倍",
    ],
}

output = {
    "trading_date": "2026-06-24",
    "skill_name": "20:30 ST股挖掘",
    "job_name": "20:30 ST股挖掘",
    "job_type": "stock_pick",
    "run_type": "production",
    "source_input_ref": "claude-code-cli",
    "_meta": {
        "schema_version": "3.0",
        "engine_type": "claude-code",
        "data_sources_used": [
            "easyquant-backend://api/sector-stocks?sector_name=ST",
            "easyquant-backend://api/sector-stocks?sector_name=ST摘帽",
            "easyquant-backend://api/sector-stocks?sector_name=摘星脱帽",
            "tencent-qt://qt.gtimg.cn/q=ST-top10",
        ],
    },
    "summary": summary,
    "result_payload": {"structured_picks": picks},
    "raw_output": raw_output,
}

out_path = Path("/Users/jwkj/easyquant/data/ai_center/inbox/2030_ST股挖掘_2026-06-24_20260624_203023.json")
out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
print("WROTE", out_path, out_path.stat().st_size, "bytes")
print("picks:", len(picks))
