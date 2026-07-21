import json
import os

raw = '''<h2>ST 方向主题催化与风格观察</h2>
<p><b>报告周期：</b>2026-07-11(周五,7/10 收盘复盘基准)｜<b>执行时间：</b>20:30</p>
<hr>
<h3>一、市场整体情绪</h3>
<p>今日(2026-07-10 收盘,A 股市场)普涨反弹,
<span class="up">医疗服务 +5.59%</span>、
<span class="up">影视院线 +3.94%</span>、
<span class="up">白酒 +3.77%</span>、
<span class="up">军工装备 +3.77%</span>、
<span class="up">生物制品 +3.33%</span> 同列涨幅榜前列。
涨停家数 <span class="highlight">92</span> 只、连板高度 <b>2 板</b>、市场温度 <span class="highlight">121</span>,
情绪强度处于中性偏热区间。从风格看,大消费(白酒+影视+医疗服务)与成长(军工+生物)同涨,典型的低位修复+主题轮动形态。</p>
<hr>
<h3>二、ST 板块全景</h3>
<p>ST 概念板块样本 <span class="highlight">211 家</span>,当日板块涨幅 <span class="up">+0.77%</span>,
净额 <span class="outflow">-4.07 亿</span>(整体流出但分化大)。
<b>领涨股：</b><span class="stock">*ST发展</span><span class="limit-up">涨停</span>(+9.95%),
<b>资金净流入榜首：</b><span class="stock">*ST闻泰</span><span class="inflow">+3674 万</span>。</p>
<table>
<thead><tr><th>排名</th><th>股票</th><th>涨幅</th><th>主力净额</th></tr></thead>
<tbody>
<tr><td>1</td><td><span class="stock">*ST发展</span></td><td><span class="up">+9.95%</span></td><td><span class="inflow">+1188万</span></td></tr>
<tr><td>2</td><td><span class="stock">ST龙元</span></td><td><span class="up">+9.80%</span></td><td><span class="outflow">-83.5万</span></td></tr>
<tr><td>3</td><td><span class="stock">*ST闻泰</span></td><td><span class="up">+7.92%</span></td><td><span class="inflow">+3674万</span></td></tr>
<tr><td>4</td><td><span class="stock">ST围海</span></td><td><span class="up">+7.05%</span></td><td><span class="inflow">+476万</span></td></tr>
<tr><td>5</td><td><span class="stock">ST思科瑞</span></td><td><span class="up">+6.24%</span></td><td><span class="inflow">+343万</span></td></tr>
<tr><td>6</td><td><span class="stock">*ST大立</span></td><td><span class="up">+5.81%</span></td><td><span class="inflow">+2156万</span></td></tr>
<tr><td>7</td><td><span class="stock">*ST三房</span></td><td><span class="up">+5.81%</span></td><td><span class="inflow">+1381万</span></td></tr>
<tr><td>8</td><td><span class="stock">*ST美芝</span></td><td><span class="up">+5.65%</span></td><td><span class="inflow">+2247万</span></td></tr>
<tr><td>9</td><td><span class="stock">*ST尼雅</span></td><td><span class="up">+5.37%</span></td><td><span class="inflow">+802万</span></td></tr>
<tr><td>10</td><td><span class="stock">*ST宝馨</span></td><td><span class="up">+5.18%</span></td><td><span class="inflow">+680万</span></td></tr>
</tbody></table>
<hr>
<h3>三、摘帽方向梳理</h3>
<p>摘帽概念样本 <span class="highlight">71 家</span>,板块涨幅 <span class="up">+0.81%</span>,
<b>领涨股：</b><span class="stock">中通国脉</span><span class="limit-up">涨停</span>(+10.03%),
与 <span class="stock">双成药业</span><span class="limit-up">+10.00%</span>、<span class="stock">天微电子</span><span class="limit-up">+10.15%</span>
共同构成「摘帽三剑客」涨停阵型。</p>
<table>
<thead><tr><th>排名</th><th>股票</th><th>涨幅</th><th>所属行业</th><th>主力净额</th></tr></thead>
<tbody>
<tr><td>1</td><td><span class="stock">天微电子</span></td><td><span class="up">+10.15%</span></td><td><span class="sector">军工电子</span></td><td><span class="inflow">+779万</span></td></tr>
<tr><td>2</td><td><span class="stock">中通国脉</span></td><td><span class="up">+10.03%</span></td><td>通信</td><td><span class="outflow">-1887万</span></td></tr>
<tr><td>3</td><td><span class="stock">双成药业</span></td><td><span class="up">+10.00%</span></td><td><span class="sector">化学制药</span></td><td><span class="outflow">-6079万</span></td></tr>
<tr><td>4</td><td><span class="stock">冀衡医药</span></td><td><span class="up">+6.03%</span></td><td><span class="sector">医药</span></td><td><span class="inflow">+372万</span></td></tr>
<tr><td>5</td><td><span class="stock">天山生物</span></td><td><span class="up">+5.13%</span></td><td><span class="sector">农业</span></td><td><span class="inflow">+1177万</span></td></tr>
</tbody></table>
<hr>
<h3>四、催化主题归因</h3>
<p><b>主题一:摘帽兑现预期</b><span class="tag">摘帽</span> —
随着中报披露季临近(<b>7/15-8/30</b>),市场对 ST 股摘帽预期升温,头部标的已率先涨停。
<span class="stock">双成药业</span>借化学制药行业 +3.20% 顺势封板,体现<b>行业 × 摘帽</b>双逻辑共振优势。</p>
<p><b>主题二:重组与重整进程</b><span class="tag">重组</span> —
<span class="stock">*ST闻泰</span>作为当日 ST 板块资金净流入榜首(+3674 万),背后是市场对其闻泰科技借壳重整进程的预期博弈。
低价股 <span class="stock">*ST发展</span>/<span class="stock">ST龙元</span> 涨停更多是<b>板块情绪修复 + 超跌反弹</b>的纯博弈属性。</p>
<p><b>主题三:行业联动共振</b><span class="tag">主线共振</span> —
<span class="stock">天微电子</span>(摘帽 + 军工电子)享受军工装备 +3.77% 板块联动红利;
<span class="stock">*ST美芝</span>(家电产业链)沾厨卫电器 +2.76% 板块涨势。
摘帽/重组方向与行业主线的乘数效应是今日选股核心 alpha。</p>
<hr>
<h3>五、风险信号</h3>
<div class="alert-bad">
<b>1. 高位接盘风险:</b>
<span class="stock">双成药业</span>、<span class="stock">中通国脉</span>、<span class="stock">华微电子</span>涨停但主力净流出,显示短线博弈为主、机构派发筹码,追高风险高。
</div>
<div class="alert-bad">
<b>2. 低价 ST 高弹性双向风险:</b>
<span class="stock">ST龙元</span>(1.12元)、<span class="stock">*ST发展</span>(2.21元)、<span class="stock">*ST三房</span>(1.82元)
三大超低价 ST 个股涨幅均超 5%,但同时具备最高退市风险与最低流动性,涨得快跌得更快,无实质催化前不宜重仓。
</div>
<div class="alert-bad">
<b>3. 摘帽兑现不及预期风险:</b>
ST 摘帽需以年报扣非+审计意见为门槛,本周仅是中报预告季早期,最终能否摘帽存在不确定性,情绪溢价可能快速回吐。
</div>
<div class="risk-box">
<b>整体提示:</b>ST 板块即便当日情绪修复,仍属<b>高弹性高风险</b>博弈品种,本质风险(退市、流动性、估值)未消除,任何标的入场均需设置<b>严格止损(建议 5%)</b>并控制总仓位不超过 10%。
</div>
<hr>
<h3>六、操作建议汇总</h3>
<p><b>核心结论:</b>当前 ST 方向以<b>「板块情绪修复 + 个股分化」</b>为主要特征,资金开始从低价 ST 博弈向<b>「摘帽 + 主线共振」</b>集中。
<b>重点关注</b>具备实质催化(摘帽/重组)且与行业主线共振的标的,如 <b>*ST闻泰</b>(重组+资金)和 <b>双成药业</b>(摘帽+化学制药)。
建议候选池:</p>
<ul>
<li><b>candidate</b>(可建仓候选):<span class="stock">*ST闻泰</span>、<span class="stock">双成药业</span></li>
<li><b>watch</b>(仅作风向标):<span class="stock">*ST发展</span>、<span class="stock">天微电子</span>、<span class="stock">*ST美芝</span>、<span class="stock">ST龙元</span></li>
</ul>
<p><b>优先级排序:</b>重组+资金(<span class="stock">*ST闻泰</span>)&gt; 摘帽+主线(<span class="stock">双成药业</span>)&gt; 摘帽首板(<span class="stock">天微电子</span>)&gt; 板块风向(<span class="stock">*ST发展</span>)&gt; 家电摘帽(<span class="stock">*ST美芝</span>)&gt; 超低价博弈(<span class="stock">ST龙元</span>)</p>
'''

output = {
    "trading_date": "2026-07-11",
    "skill_name": "20:30 ST股挖掘",
    "job_name": "20:30 ST股挖掘",
    "job_type": "stock_pick",
    "run_type": "production",
    "source_input_ref": "claude-code-cli",
    "_meta": {
        "schema_version": "3.0",
        "engine_type": "claude-code",
        "data_sources_used": [
            "akshare.cache",
            "internal.sector_stocks_api",
            "internal.sector_detail_api",
            "internal.limit_up_summary_api",
            "/tmp/easyquant_market_data_2026-07-11.json"
        ]
    },
    "summary": {
        "market_phase": "震荡走强",
        "hot_sectors": [
            "医疗服务(+5.59%)",
            "影视院线(+3.94%)",
            "白酒(+3.77%)",
            "军工装备(+3.77%)",
            "生物制品(+3.33%)",
            "化学制药(+3.20%)"
        ],
        "risk_signals": [
            "ST板块尾盘上攻明显(211家,领涨*ST发展涨停),板块整体活跃但分化大",
            "*ST闻泰单日 +7.92% 流入 3674万,但价位 20.84 处于高位,追高风险高",
            "*ST美芝 流入 2247万 涨幅 +5.65%,需警惕冲高回落",
            "摘帽方向双成药业(+10.00%)、华微电子(+5%)主力净流出,部分高位摘帽股筹码派发",
            "中通国脉(+10.03%)净流出 1887万,高位接盘风险显著",
            "低价 ST 股(*ST三房 1.82元/ST龙元 1.12元/*ST发展 2.21元)弹性大但退市风险并存"
        ]
    },
    "result_payload": {
        "structured_picks": [
            {
                "stock_code": "000838",
                "stock_name": "*ST发展",
                "pick_level": "watch",
                "reason_summary": "ST板块领涨股,今日涨停(+9.95%),板块情绪标杆,但价位超低弹性大、退市风险并存,仅作风向标观察",
                "reason_detail": "*ST发展今日封涨停,价 2.21 元低价小盘弹性最大,主力净流入 1188 万;作为 ST 板块 211 家样本的领涨股,体现板块当日情绪修复力度。但 2 元 区间低价 ST 个股历来伴随高退市风险和流动性折价,且其当前 ST 状态反映基本面尚未根本改善,无摘帽实质催化前只宜做情绪标的不宜真金白银建仓。",
                "sector_name": "ST板块",
                "theme_tags": ["ST板块", "低价股", "情绪修复"],
                "capital_profile": {
                    "net_inflow": 11881600.0,
                    "main_force_signal": "moderate",
                    "st_type": "*ST",
                    "delist_risk": "高"
                },
                "signal_context": "ST 板块当日整体涨幅 +0.77%,领涨股 *ST发展涨停形成板块情绪正向反馈",
                "risk_flags": ["ST风险", "退市风险高", "流动性不足", "纯情绪博弈"],
                "entry_hint": "不建仓,仅作风向观察;若周一继续涨停可小仓试探但不隔夜",
                "confidence_score": 0.30
            },
            {
                "stock_code": "002693",
                "stock_name": "双成药业",
                "pick_level": "candidate",
                "reason_summary": "摘帽方向+10%涨停,医药主线+摘帽预期双催化,但主力净流出 6079万,高位接盘风险显著",
                "reason_detail": "双成药业今日 +10.00% 涨停,价 10.45 元,属摘帽概念核心标的;盘中主力净流出 -6079 万说明今日封板多为短线博弈而非主力建仓。摘帽方向当日 71 家、领涨股 +10.03%,板块情绪积极;化学制药行业 +3.20% 同向支撑。技术面若能延续两板以上强势,且伴随成交量放大、主力重新回流,可升级至 confirm。当前阶段保持关注,等回调企稳或二板确认。",
                "sector_name": "化学制药",
                "theme_tags": ["摘帽", "化学制药", "涨停接力"],
                "capital_profile": {
                    "net_inflow": -60792700.0,
                    "main_force_signal": "weak",
                    "st_type": "摘帽预期",
                    "delist_risk": "中"
                },
                "signal_context": "摘帽板块当日 +0.81%,化学制药行业 +3.20%,医药大板块共振",
                "risk_flags": ["ST风险", "摘帽兑现不确定", "主力净流出", "高位接盘风险"],
                "entry_hint": "等回踩 5 日线企稳或二板放量确认;不追首板",
                "confidence_score": 0.55
            },
            {
                "stock_code": "600745",
                "stock_name": "*ST闻泰",
                "pick_level": "candidate",
                "reason_summary": "ST方向资金净流入最大标的,今日 +7.92%,大资金进场迹象,闻泰科技重组背景仍是核心催化",
                "reason_detail": "*ST闻泰今日 +7.92%,主力净流入 +3674 万,为 ST 板块 10 家样本中流入金额第一,大资金进场明显。公司源自原闻泰科技借壳,半导体+消费电子概念,具备产业重组+摘帽逻辑,虽然主体已退市但重整进程仍是市场关注点。价 20.84 元处相对中高位,需警惕短期资金获利了结。建议观察次日能否站稳 5 日线、放量换手,具备则 upgrade 至 confirm。",
                "sector_name": "ST板块",
                "theme_tags": ["ST板块", "重组预期", "半导体", "资金净流入Top"],
                "capital_profile": {
                    "net_inflow": 36740000.0,
                    "main_force_signal": "strong",
                    "st_type": "*ST",
                    "delist_risk": "中"
                },
                "signal_context": "ST板块当日资金虽净流出 4 亿,但 *ST闻泰 单独大幅净流入,板块内分化",
                "risk_flags": ["ST风险", "重组进度不确定", "退市风险中", "高位获利回吐"],
                "entry_hint": "回踩分批低吸,不追涨;设严格止损 5%",
                "confidence_score": 0.58
            },
            {
                "stock_code": "688511",
                "stock_name": "天微电子",
                "pick_level": "watch",
                "reason_summary": "摘帽方向涨停(+10.15%),军工电子主线强共振,资金净流入 779万,观察是否走出连板",
                "reason_detail": "天微电子隶属摘帽概念+军工电子双标签,今日 +10.15% 涨停,主力净流入 +779 万。军工装备板块当日 +3.77%、军工电子 +2.74% 同向配合,主线情绪支撑较强。但作为科创板个股流动性偏好、首板是否能走出连板需要次日验证。当前仅作风向观察。",
                "sector_name": "军工电子",
                "theme_tags": ["摘帽", "军工电子", "首板观察"],
                "capital_profile": {
                    "net_inflow": 7794100.0,
                    "main_force_signal": "moderate",
                    "st_type": "摘帽预期",
                    "delist_risk": "低"
                },
                "signal_context": "摘帽板块当日 +0.81%,军工装备 +3.77%,双主线共振",
                "risk_flags": ["ST风险", "科创板波动大", "首板连板不确定"],
                "entry_hint": "二板放量跟进;首板不追",
                "confidence_score": 0.45
            },
            {
                "stock_code": "002856",
                "stock_name": "*ST美芝",
                "pick_level": "watch",
                "reason_summary": "ST方向资金净流入第二,今日 +5.65%,家电产业链协同,基本面修复预期催化",
                "reason_detail": "*ST美芝今日 +5.65%,主力净流入 +2247 万,10 只 ST 样本中流入第二。厨卫电器行业 +2.76% 共振配合,体现产业链情绪修复。基本面需进一步公告层面验证摘帽条件,目前属资金试探性建仓阶段,建议跟踪后续公告与成交量变化。",
                "sector_name": "家用电器",
                "theme_tags": ["ST板块", "家电产业链", "摘帽预热"],
                "capital_profile": {
                    "net_inflow": 22474100.0,
                    "main_force_signal": "moderate",
                    "st_type": "*ST",
                    "delist_risk": "中"
                },
                "signal_context": "厨卫电器行业 +2.76% 涨幅第一,家电产业链整体走强",
                "risk_flags": ["ST风险", "摘帽进度不确定", "退市风险中"],
                "entry_hint": "等待公告催化或放量突破,小仓位跟随",
                "confidence_score": 0.42
            },
            {
                "stock_code": "600491",
                "stock_name": "ST龙元",
                "pick_level": "watch",
                "reason_summary": "ST板块 +9.80% 接近涨停,但主力净流出 83.5万,显示高位接力意愿弱,仅作情绪标",
                "reason_detail": "ST龙元今日 +9.80%,价 1.12 元属最低价梯队,弹性极大。但主力净流出 -835 万,显示当前价位买盘枯竭、卖盘释放。低价 ST 股历来是高风险高弹性双向标的,在未确认摘帽或重组催化前,只作风向指标跟踪,不宜重仓。",
                "sector_name": "ST板块",
                "theme_tags": ["ST板块", "超低价股", "高弹性"],
                "capital_profile": {
                    "net_inflow": -835000.0,
                    "main_force_signal": "weak",
                    "st_type": "ST",
                    "delist_risk": "高"
                },
                "signal_context": "ST板块情绪修复涨停潮,ST龙元接近涨停但资金分歧大",
                "risk_flags": ["ST风险", "退市风险高", "主力净流出", "流动性差"],
                "entry_hint": "不建仓,观察板块情绪强度",
                "confidence_score": 0.25
            }
        ]
    },
    "raw_output": raw
}

out_path = "/Users/jwkj/easyquant/data/ai_center/inbox/2030_ST股挖掘_2026-07-11_20260711_203024.json"
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"已写入: {out_path}")
print(f"bytes: {os.path.getsize(out_path)}")
# 字段校验
print(f"structured_picks 数量: {len(output['result_payload']['structured_picks'])}")
print(f"raw_output 长度: {len(raw)} chars")
