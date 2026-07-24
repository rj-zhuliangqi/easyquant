#!/usr/bin/env python3
"""Build 集合竞价分析 JSON output for 2026-06-24."""
import json
from pathlib import Path

OUT = Path("/Users/jwkj/easyquant/data/ai_center/inbox/0926_集合竞价分析_2026-06-24_20260624_092623.json")

raw_html = """
<h2>📊 一、市场环境与竞价定调</h2>
<p>2026年6月24日开盘竞价结束（09:25-09:26 数据快照）。<b>市场呈现典型的"高低切+情绪退潮"格局</b>：90 个申万行业中仅 <span class="highlight">20 个上涨、69 个下跌</span>，普跌中带结构性炸板风险。涨停板 <span class="limit-up">约 97 家</span>，但 <span class="down">跌幅居前者集中在前期主流赛道（半导体、元件、贵金属、电子化学品、小金属）</span>，说明前期大幅获利盘正在兑现。</p>
<div class="alert-bad">
<b>关键警示：</b>开盘竞价阶段已有 <span class="down">50 家个股跌停或近跌停</span>，包括 <b>南亚新材 -11.35%</b>、<b>德福科技 -14.65%</b>、<b>联瑞新材 -11.66%</b>、<b>莱伯泰科 -14.13%</b> 等前期热门科技高位股，<span class="down">炸板效应明显</span>。今日强弱分化将极度悬殊，<b>切勿盲目追高位科技股</b>。
</div>
<hr>

<h2>🔥 二、板块涨跌排行（申万行业）</h2>
<h3>上涨 TOP 10</h3>
<table>
<thead><tr><th>排名</th><th>板块</th><th>涨跌幅</th></tr></thead>
<tbody>
<tr><td>1</td><td><span class="sector">造纸</span></td><td><span class="up">+0.65%</span></td></tr>
<tr><td>2</td><td><span class="sector">纺织制造</span></td><td><span class="up">+0.50%</span></td></tr>
<tr><td>3</td><td><span class="sector">汽车服务及其他</span></td><td><span class="up">+0.47%</span></td></tr>
<tr><td>4</td><td><span class="sector">保险</span></td><td><span class="up">+0.41%</span></td></tr>
<tr><td>5</td><td><span class="sector">化学制药</span></td><td><span class="up">+0.38%</span></td></tr>
<tr><td>6</td><td><span class="sector">港口航运</span></td><td><span class="up">+0.25%</span></td></tr>
<tr><td>7</td><td><span class="sector">石油加工贸易</span></td><td><span class="up">+0.23%</span></td></tr>
<tr><td>8</td><td><span class="sector">饮料制造</span></td><td><span class="up">+0.23%</span></td></tr>
<tr><td>9</td><td><span class="sector">汽车整车</span></td><td><span class="up">+0.16%</span></td></tr>
<tr><td>10</td><td><span class="sector">医药商业</span></td><td><span class="up">+0.15%</span></td></tr>
</tbody>
</table>
<h3>下跌 TOP 10（重灾区）</h3>
<table>
<thead><tr><th>排名</th><th>板块</th><th>涨跌幅</th></tr></thead>
<tbody>
<tr><td>81</td><td><span class="sector">非金属材料</span></td><td><span class="down">-1.16%</span></td></tr>
<tr><td>82</td><td><span class="sector">能源金属</span></td><td><span class="down">-1.17%</span></td></tr>
<tr><td>83</td><td><span class="sector">工业金属</span></td><td><span class="down">-1.20%</span></td></tr>
<tr><td>84</td><td><span class="sector">其他电子</span></td><td><span class="down">-1.42%</span></td></tr>
<tr><td>85</td><td><span class="sector">通信设备</span></td><td><span class="down">-1.46%</span></td></tr>
<tr><td>86</td><td><span class="sector">半导体</span></td><td><span class="down">-1.62%</span></td></tr>
<tr><td>87</td><td><span class="sector">元件</span></td><td><span class="down">-1.99%</span></td></tr>
<tr><td>88</td><td><span class="sector">贵金属</span></td><td><span class="down">-2.02%</span></td></tr>
<tr><td>89</td><td><span class="sector">电子化学品</span></td><td><span class="down">-2.06%</span></td></tr>
<tr><td>90</td><td><span class="sector">小金属</span></td><td><span class="down">-2.69%</span></td></tr>
</tbody>
</table>
<div class="alert-good"><b>主题主线：</b><span class="tag">医药板块异动</span>——化学制药、医药商业双双红盘，板块内涨停超 15 家，<b>是今日最具持续性的低位接力主线</b>。</div>
<div class="alert-bad"><b>主题塌方：</b><span class="tag">半导体/电子化学品</span> 全面跳水，<b>前期主升浪明显走完</b>，今日资金高低切迹象极重。</div>
<hr>

<h2>💰 三、竞价强弱与资金面验证</h2>
<h3>1️⃣ 强势竞价 — 真量真价（医药主线）</h3>
<ul>
<li><span class="stock">亨迪药业(301211)</span> 竞价 <span class="up">+19.98%</span>（昨涨停延续），换手仅 <span class="highlight">3.20%</span>，<b>封单结实、抛压轻，T字板潜质</b>。资金净流 <span class="outflow">-4991 万</span>，但量能极小，<b>显示卖盘有限</b>。</li>
<li><span class="stock">新华制药(000756)</span> 竞价 <span class="up">+9.98%</span>，换手 <span class="highlight">2.12%</span>，<b>一字封板</b>，量能干净。资金 <span class="outflow">-4630 万</span>但属正常一字撤单。</li>
<li><span class="stock">海南海药(000566)</span> 竞价 <span class="up">+9.97%</span>，换手 <span class="highlight">2.01%</span>，<b>一字结构</b>，连板预期强烈。</li>
<li><span class="stock">合富中国(603122)</span> 竞价 <span class="up">+9.99%</span>，医药商业方向龙头，<b>低位首板 / 二板接力位</b>。</li>
</ul>

<h3>2️⃣ 强势竞价 — 量价异常（高位需警惕）</h3>
<ul>
<li><span class="stock">银之杰(300085)</span> 竞价 <span class="up">+20.00%</span>，<span class="down">资金净流 -14.84 亿</span>，成交 <span class="highlight">46.28 亿</span>，<b>巨量出货嫌疑极大</b>，高位接盘风险高。</li>
<li><span class="stock">龙磁科技(300835)</span> 竞价 <span class="up">+20.00%</span>，<span class="outflow">净流 -6.62 亿</span>，<b>主力撤退迹象</b>。</li>
<li><span class="stock">飞鹿股份(300665)</span> 竞价 <span class="up">+20.00%</span>，换手 <span class="highlight">29.66%</span>，<b>炸板风险大</b>。</li>
<li><span class="stock">国民技术(300077)</span> 竞价 <span class="up">+15.71%</span>，半导体唯一红盘但 <b>板块整体 -1.62%</b>，孤军作战。</li>
</ul>

<h3>3️⃣ 弱势竞价 — 高位塌方（明确回避）</h3>
<div class="alert-bad">
<b>电子化学品/半导体高位股集体跳水：</b><span class="stock">南亚新材</span> <span class="down">-11.35%</span>、<span class="stock">联瑞新材</span> <span class="down">-11.66%</span>、<span class="stock">铜冠铜箔</span> <span class="down">-12.56%</span>、<span class="stock">莱伯泰科</span> <span class="down">-14.13%</span>、<span class="stock">德福科技</span> <span class="down">-14.65%</span>、<span class="stock">强瑞技术</span> <span class="down">-11.40%</span>。<b>前期赛道龙头集体闷杀，今日切勿介入，谨防加速补跌</b>。
</div>

<h3>4️⃣ 资金面综合判断</h3>
<p>整体看，<b>大盘资金流入有限</b>（市场指数数据未传回，从行业资金"流入/流出/净额"全 0 看，开盘竞价资金尚未实质成交）。<b>结构性资金已通过竞价表态：</b></p>
<ul>
<li>📈 <span class="inflow">主动流入</span>方向：<span class="tag">化学制药</span>（低位/事件驱动）、<span class="tag">医药商业</span>、<span class="tag">造纸</span>、<span class="tag">保险</span>（防御）</li>
<li>📉 <span class="outflow">主动流出</span>方向：<span class="tag">半导体</span>、<span class="tag">电子化学品</span>、<span class="tag">小金属</span>、<span class="tag">贵金属</span>、<span class="tag">通信设备</span></li>
</ul>
<hr>

<h2>🎯 四、情绪强度评估</h2>
<table>
<thead><tr><th>指标</th><th>数值</th><th>解读</th></tr></thead>
<tbody>
<tr><td>涨停家数（含竞价一字）</td><td><span class="highlight">约 97 家</span></td><td>偏强，主要来自医药接力</td></tr>
<tr><td>跌停家数</td><td><span class="down">约 50 家</span></td><td>偏多，前排科技股闷杀严重</td></tr>
<tr><td>红盘行业</td><td>20 / 90</td><td><b>赚钱效应明显收缩</b></td></tr>
<tr><td>主流热门赛道竞价</td><td>半导体/电子化学品<span class="down">深绿</span></td><td><b>退潮明确</b></td></tr>
<tr><td>低位接力方向</td><td>医药全方位<span class="up">红盘</span></td><td><b>新主线雏形</b></td></tr>
</tbody>
</table>
<p><b>结论：</b>市场进入 <b>"主线切换日"</b>——高位科技闷杀、低位医药接力。<span class="highlight">情绪温度中性偏冷，但医药局部火热</span>。</p>
<hr>

<h2>📌 五、操作策略与重点票池</h2>
<h3>🟢 强烈推荐（医药低位接力）</h3>
<ul>
<li><b><span class="stock">合富中国(603122)</span></b>——医药商业龙头，竞价 <span class="up">+9.99%</span>低吸位，板块龙头属性，<b>关注首板</b>。</li>
<li><b><span class="stock">海南海药(000566)</span></b>——一字封板，量能极小，<b>T字板预期</b>。</li>
<li><b><span class="stock">新华制药(000756)</span></b>——一字封板，化学制药主流方向。</li>
</ul>

<h3>🟡 候选关注（医药主线发散）</h3>
<ul>
<li><span class="stock">亨迪药业(301211)</span>——昨日 20cm 涨停，竞价继续封板，<b>资金试连板高度</b>。</li>
<li><span class="stock">睿智医药(300149)</span>、<span class="stock">赛升药业(300485)</span>——竞价 +18~19%，<b>高度跟随但需警惕换手过快</b>。</li>
<li><span class="stock">灵康药业(603669)</span>、<span class="stock">特一药业(002728)</span>、<span class="stock">双鹭药业(002038)</span>——板块小弟，<b>低吸首板候选</b>。</li>
</ul>

<h3>⚪ 观望（高位科技/资源股）</h3>
<ul>
<li>所有半导体、电子化学品、小金属、贵金属高位股 <b>均不参与</b>。</li>
<li><span class="stock">银之杰</span>、<span class="stock">龙磁科技</span>、<span class="stock">飞鹿股份</span> 等竞价 20cm 但资金巨幅流出，<b>禁追</b>。</li>
</ul>
<hr>

<h2>⚠️ 六、风险提示</h2>
<div class="risk-box">
<b>1. 主线切换风险：</b>医药行情可持续性需观察盘中是否出现板块龙头连板效应，若首板涨停股盘中开板率高，则可能是"诱多"假主线。
<br><b>2. 高位科技闷杀传染：</b>南亚新材/德福科技/联瑞新材等大幅跌停，可能引发 <span class="tag">PCB</span>/<span class="tag">铜箔</span>/<span class="tag">玻纤</span> 等扩散性补跌，仓位需控制在 <span class="highlight">三成以下</span>。
<br><b>3. 普跌风险：</b>69/90 行业下跌，<b>市场赚钱效应偏冷</b>，今日宜以低吸为主、不宜追高。
<br><b>4. 数据时效：</b>本次分析基于 09:26:23 竞价快照，资金流字段尚未完全成交，盘中需结合实际开盘 5 分钟量能再次确认。
</div>
"""

picks = [
    {
        "stock_code": "603122",
        "stock_name": "合富中国",
        "pick_level": "strong_recommend",
        "reason_summary": "医药商业方向龙头，竞价封板低位首板",
        "reason_detail": "化学制药/医药商业双双成为今日唯二红盘的医药赛道，合富中国位居医药商业领涨股，竞价+9.99%首板封板，换手仅3.63%，封单结构干净。当前价12.77，距前高有空间，低位属性明显。在大盘普跌、半导体闷杀的高低切环境下，作为低位首板龙头存在二板预期。",
        "sector_name": "医药商业",
        "theme_tags": ["医药商业", "低位首板", "板块龙头"],
        "capital_profile": {"net_inflow": -0.014, "main_force_signal": "neutral_strong", "成交额_亿": 1.79, "换手率": 3.63},
        "signal_context": "申万医药商业板块+0.15%红盘，板块内涨停集中，合富中国为板块涨幅领头羊；高低切环境下低位医药承接资金",
        "risk_flags": ["医药行情持续性待验证", "需观察盘中是否炸板"],
        "entry_hint": "竞价封板成功后等开盘量能确认；开盘若一字直接观望T字，开板可低吸",
        "confidence_score": 0.82
    },
    {
        "stock_code": "000566",
        "stock_name": "海南海药",
        "pick_level": "strong_recommend",
        "reason_summary": "一字封板，化学制药低位龙头，T字板预期",
        "reason_detail": "竞价+9.97%一字封板，换手率仅2.01%、成交1.05亿，量能极小说明卖压有限。化学制药板块在今日90个行业中位列上涨第5（+0.38%），是仅有的医药红盘主线。海南海药当前价仅4.08元，绝对低位，主升空间充足。封板净流出-4341万属于一字撤单正常现象，不构成出货信号。",
        "sector_name": "化学制药",
        "theme_tags": ["化学制药", "一字板", "低价低位"],
        "capital_profile": {"net_inflow": -0.043, "main_force_signal": "strong", "成交额_亿": 1.05, "换手率": 2.01},
        "signal_context": "化学制药+0.38%，板块涨停超10家，海药一字结构干净，资金惜售明显",
        "risk_flags": ["盘中若开板需警惕巨量换手", "医药联动需持续验证"],
        "entry_hint": "一字板不可追，若盘中开板回踩可低吸；炸板止损位 +5%以下",
        "confidence_score": 0.80
    },
    {
        "stock_code": "000756",
        "stock_name": "新华制药",
        "pick_level": "strong_recommend",
        "reason_summary": "化学制药一字封板，量能干净",
        "reason_detail": "竞价+9.98%一字封板，换手2.12%，成交1.40亿。化学制药主流方向，板块今日红盘，新华制药作为板块内大票具有指数效应。一字净流出-4630万属一字撤单。当前价13.44元，处于中低位区间。",
        "sector_name": "化学制药",
        "theme_tags": ["化学制药", "一字板", "板块大票"],
        "capital_profile": {"net_inflow": -0.046, "main_force_signal": "strong", "成交额_亿": 1.40, "换手率": 2.12},
        "signal_context": "板块同步发力，与海南海药、亨迪药业、特一药业等形成连板梯队",
        "risk_flags": ["一字板需警惕开板抛压", "若板块龙头炸板则补跌风险大"],
        "entry_hint": "一字封板不追；若日内打开可在 +5% 附近评估介入",
        "confidence_score": 0.78
    },
    {
        "stock_code": "301211",
        "stock_name": "亨迪药业",
        "pick_level": "confirm",
        "reason_summary": "20cm涨停延续，封单结实，连板高度试探",
        "reason_detail": "昨日已涨停，今日竞价继续封板+19.98%，换手仅3.20%。作为创业板20cm个股，连板高度若打开将引领医药情绪。但成交1.46亿、净流出-4991万，资金面中性偏弱。可观察其能否承担医药板块情绪龙头角色。",
        "sector_name": "化学制药",
        "theme_tags": ["20cm弹性", "连板梯队", "化学制药"],
        "capital_profile": {"net_inflow": -0.0499, "main_force_signal": "neutral", "成交额_亿": 1.46, "换手率": 3.20},
        "signal_context": "化学制药红盘叠加连板梯队效应，但20cm品种风险收益比放大",
        "risk_flags": ["20cm波动剧烈", "若开板则可能-10%以内剧烈震荡"],
        "entry_hint": "保守做法：观察封板稳固性，不追高；激进做法盘中开板低吸控制仓位",
        "confidence_score": 0.65
    },
    {
        "stock_code": "603669",
        "stock_name": "灵康药业",
        "pick_level": "candidate",
        "reason_summary": "化学制药小盘股，低位首板候选",
        "reason_detail": "竞价+10.10%涨停，换手5.19%，资金净流入1462万，成交1.97亿。化学制药板块小弟，低价低位股，板块联动属性强。若医药主线持续，灵康药业作为板块发散品种具有补涨预期。",
        "sector_name": "化学制药",
        "theme_tags": ["化学制药", "低位发散", "小盘股"],
        "capital_profile": {"net_inflow": 0.0146, "main_force_signal": "weak_positive", "成交额_亿": 1.97, "换手率": 5.19},
        "signal_context": "板块普涨环境下小盘补涨逻辑，资金小幅净流入",
        "risk_flags": ["小票流动性风险", "板块炸板易被带飞"],
        "entry_hint": "板块龙头确认后跟随介入，止损位 -3%",
        "confidence_score": 0.55
    },
    {
        "stock_code": "300149",
        "stock_name": "睿智医药",
        "pick_level": "watch",
        "reason_summary": "竞价+19.95%但换手7.94%，量能偏热需观察",
        "reason_detail": "20cm品种竞价接近涨停，换手率达7.94%，净流出-8781万，明显高于其他医药票。短期跟随性强，但若医药板块情绪反转，回撤幅度会更大。",
        "sector_name": "化学制药",
        "theme_tags": ["20cm弹性", "化学制药", "高换手"],
        "capital_profile": {"net_inflow": -0.0878, "main_force_signal": "neutral", "成交额_亿": 3.30, "换手率": 7.94},
        "signal_context": "医药板块跟随性强，但量能放大显示分歧",
        "risk_flags": ["换手偏高出现分歧迹象", "20cm波动放大风险"],
        "entry_hint": "观望优先，盘中若回封再做评估",
        "confidence_score": 0.50
    }
]

out = {
    "trading_date": "2026-06-24",
    "skill_name": "09:26 集合竞价分析",
    "job_name": "09:26 集合竞价分析",
    "job_type": "stock_pick",
    "run_type": "production",
    "source_input_ref": "claude-code-cli",
    "_meta": {
        "schema_version": "3.0",
        "engine_type": "claude-code",
        "data_sources_used": ["akshare", "eastmoney", "prefetch_snapshot"]
    },
    "summary": {
        "market_phase": "高低切+情绪退潮：医药接力、半导体闷杀",
        "hot_sectors": ["化学制药", "医药商业", "造纸", "纺织制造", "保险"],
        "risk_signals": [
            "90个行业仅20个上涨，普跌格局",
            "前期主线半导体/电子化学品/小金属深度回撤(-1.6%~-2.7%)",
            "高位科技股集体闷杀(南亚新材、德福科技、联瑞新材跌停)",
            "跌停约50家，赚钱效应收缩",
            "竞价资金未实际成交，需开盘5分钟量能再验证"
        ]
    },
    "result_payload": {"structured_picks": picks},
    "raw_output": raw_html
}

OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"WROTE: {OUT}")
print(f"BYTES: {OUT.stat().st_size}")
print(f"PICKS: {len(picks)}")
