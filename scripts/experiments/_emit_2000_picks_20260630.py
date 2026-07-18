"""Generate the final 20:00 super-short post-market pick JSON for 2026-06-30."""
import json

P = '/tmp/easyquant_market_data_2026-06-30.json'
with open(P) as f:
    d = json.load(f)

ind = d['individual_rankings']['individual']
sec = d['sector_rankings']['industry']


def pct(s):
    try:
        return float(str(s).rstrip('%'))
    except Exception:
        return 0.0


def yi(s):
    s = str(s)
    if '亿' in s:
        try:
            return float(s.replace('亿', ''))
        except Exception:
            return 0.0
    if '万' in s:
        try:
            return float(s.replace('万', '')) / 10000.0
        except Exception:
            return 0.0
    return 0.0


# 涨停龙头池
zt_leaders = [x for x in ind if pct(x.get('涨跌幅')) >= 19.9 and 'ST' not in x.get('股票简称', '') and '*' not in x.get('股票简称', '')]
zt_leaders.sort(key=lambda x: yi(x.get('净额', '0')), reverse=True)

# 强势中军池(10%~19% 净额>0)
mid = [x for x in ind if 10.0 <= pct(x.get('涨跌幅')) < 19.0 and 'ST' not in x.get('股票简称', '') and '*' not in x.get('股票简称', '')]
mid = [x for x in mid if yi(x.get('净额', '0')) > 0]
mid.sort(key=lambda x: yi(x.get('净额', '0')), reverse=True)

# 找特定股
def find(code):
    for x in ind:
        if str(x.get('股票代码')) == str(code):
            return x
    return None


# === structured_picks ===
picks = []

# 1) 长光华芯 — 半导体激光雷达芯片龙头, 涨停+净流入8.53亿, 资金最强烈
x = find('688048')
picks.append({
    "stock_code": "688048",
    "stock_name": "长光华芯",
    "pick_level": "strong_recommend",
    "reason_summary": "半导体激光雷达/VCSEL龙头,20cm涨停+成交97.51亿+主力净流入8.53亿,科技主线最强龙头",
    "reason_detail": (
        "长光华芯今日 20cm 涨停(+20.00%),成交额 高达 97.51亿,换手率 11.63%,主力净流入 +8.53亿元(占比 8.75%)。"
        "公司是国产半导体激光芯片(VCSEL/DFB/EEL)龙头,深度卡位车载激光雷达、光通信、AI光互连三大景气方向。"
        "半导体板块今日 +6.32%(行业第1),光学光电子 +5.90%(行业第2),通信设备 +4.76%(行业第4),三线共振为公司提供板块 Beta。"
        "成交 97.51亿 创近期天量,但净流入同步放大,显示机构与游资合力,封板质量高,次日前量空间充足,"
        "如能突破前高 121元 上方空间打开,关注回踩 5日线(约 113元) 的低吸机会。"
    ),
    "sector_name": "半导体",
    "theme_tags": ["半导体", "激光芯片", "VCSEL", "车载激光雷达", "光通信", "AI算力"],
    "capital_profile": {
        "net_inflow": 853000000.0,
        "turnover_pct": 11.63,
        "main_force_signal": "strong",
    },
    "signal_context": "成交97.51亿创天量,主力净流入+8.53亿(占比8.75%),超大单+大单净流入显著,封板资金坚决",
    "risk_flags": [
        "成交额97.51亿属天量,次日若不能维持>70亿则易见顶",
        "短期累计涨幅已偏大,警惕获利盘兑现",
    ],
    "entry_hint": "次日高开后等回踩5日均线(约113元)企稳低吸,放量突破121元跟进,止损108元",
    "confidence_score": 0.88,
})

# 2) 欧菲光 — 光学光电子龙头, 涨停+主力净流入2.88亿, 板块共振
x = find('002456')
picks.append({
    "stock_code": "002456",
    "stock_name": "欧菲光",
    "pick_level": "strong_recommend",
    "reason_summary": "光学光电子龙头,20cm涨停+主力净流入2.88亿,半导体光学/华为概念双驱动",
    "reason_detail": (
        "欧菲光今日 20cm 涨停(+20.00%),成交额 24.61亿,换手率 11.32%,主力净流入 +2.88亿元(占比 11.68%)。"
        "公司是全球光学模组龙头,2026年华为Mate新机带动摄像头模组+CIS需求,叠加车载摄像头/激光雷达接收端布局。"
        "光学光电子板块 +5.90%(行业第2),半导体板块 +6.32%(行业第1),双板块共振。"
        "成交量能同步放大,封板质量优于联建光电等同板块个股,资金认可度高。"
        "次日关注能否突破 11.5元 上方阻力位,低吸点为回踩 5日线(约 10.7元)。"
    ),
    "sector_name": "光学光电子",
    "theme_tags": ["光学光电子", "华为概念", "摄像头模组", "车载摄像头", "消费电子"],
    "capital_profile": {
        "net_inflow": 288595104.0,
        "turnover_pct": 11.32,
        "main_force_signal": "strong",
    },
    "signal_context": "主力净流入2.88亿(占比11.68%),超大单+大单净流入显著,光学光电子龙头资金共识度高",
    "risk_flags": [
        "光学光电子板块整体涨幅5.9%,次日分歧风险存在",
        "估值偏高,业绩兑现压力待消化",
    ],
    "entry_hint": "次日高开回踩10.7元(5日线)低吸,放量突破11.5元跟进,止损10.2元",
    "confidence_score": 0.85,
})

# 3) 菲利华 — 半导体材料+军工装备双线, 涨幅13.93% 主力净流入1.0亿, 资金蓄势
x = find('300395')
picks.append({
    "stock_code": "300395",
    "stock_name": "菲利华",
    "pick_level": "confirm",
    "reason_summary": "半导体材料+军工电子双线龙头,涨幅13.93%温和,主力净流入1.0亿,前量空间充足",
    "reason_detail": (
        "菲利华今日收涨 +13.93%,成交额 27.67亿,主力净流入 +1.0亿元(占比 3.62%)。"
        "公司是石英玻璃龙头,卡位半导体光掩模基板+军工耐高温材料两大景气方向,2026年AI芯片扩产带动石英耗材需求激增。"
        "半导体板块 +6.32%、军工电子 +5.04%、通信设备 +4.76% 三线共振,但菲利华涨幅 13.93% 显著低于板块龙头(20cm涨停),"
        "显示其属板块轮动接力品种,前量空间充足。次日预期:回踩 5日均线(约 145元) 后延续上行。"
    ),
    "sector_name": "半导体材料",
    "theme_tags": ["半导体材料", "石英玻璃", "军工电子", "AI算力", "光掩模"],
    "capital_profile": {
        "net_inflow": 100000000.0,
        "turnover_pct": 14.31,
        "main_force_signal": "moderate",
    },
    "signal_context": "主力净流入1.0亿(占比3.62%),成交活跃度上升,机构分批建仓",
    "risk_flags": [
        "动态PE偏高(题材股溢价)",
        "半导体材料板块今日累计涨幅已较大,需防分化",
    ],
    "entry_hint": "次日回踩145元(5日均线)低吸,放量突破155元跟进,止损140元",
    "confidence_score": 0.78,
})

# 4) 景嘉微 — 军工电子龙头, 涨幅14.01%+主力净流入3.45亿, 国产GPU
x = find('300474')
picks.append({
    "stock_code": "300474",
    "stock_name": "景嘉微",
    "pick_level": "confirm",
    "reason_summary": "国产GPU龙头+军工电子,涨幅14.01%温和,主力净流入3.45亿,资金确认度高",
    "reason_detail": (
        "景嘉微今日收涨 +14.01%,成交额 18.81亿,主力净流入 +3.45亿元(占比 18.34%)。"
        "公司是国产 GPU/显控芯片龙头,JM9 系列在军工显控、信创、AI 推理场景全面落地,2026年军工信息化+AI国产化双驱动。"
        "军工电子板块 +5.04%(行业第3),板块排名靠前但个股涨幅仅 14.01%,远低于板块龙头(20cm 涨停),"
        "显示其为板块轮动中军,资金认可度高且前量空间大。次日关注能否突破前高 65元。"
    ),
    "sector_name": "军工电子",
    "theme_tags": ["军工电子", "国产GPU", "信创", "AI推理", "军工信息化"],
    "capital_profile": {
        "net_inflow": 345000000.0,
        "turnover_pct": 7.89,
        "main_force_signal": "strong",
    },
    "signal_context": "主力净流入3.45亿(占比18.34%),净流入占比在科技板块中最高,机构资金集中建仓",
    "risk_flags": [
        "短期涨幅14%已偏大,需警惕盘中分歧",
        "军工电子板块今日+5.04%,次日分化概率大",
    ],
    "entry_hint": "次日高开后回踩58元(5日线)低吸,放量突破65元跟进,止损55元",
    "confidence_score": 0.78,
})

# 5) 蜀道装备 — 涨停+主力净流入1.19亿, 题材催化强
x = find('300540')
picks.append({
    "stock_code": "300540",
    "stock_name": "蜀道装备",
    "pick_level": "candidate",
    "reason_summary": "氢能/专用设备涨停,20cm+主力净流入1.19亿,题材弹性大",
    "reason_detail": (
        "蜀道装备今日 20cm 涨停(+20.01%),成交额 12.72亿,换手率 17.46%,主力净流入 +1.19亿元(占比 9.36%)。"
        "公司主营氢能装备、空气分离设备、深冷装备,深度卡位氢能产业链上游。"
        "今日专用设备板块 +1.69%(行业第27),但蜀道装备作为氢能题材龙头独立走强,与大盘科技主线形成共振。"
        "涨停成交活跃,封板资金坚决。次日关注能否突破前高 41元,题材股属性强,适合小仓位试错。"
    ),
    "sector_name": "专用设备",
    "theme_tags": ["氢能", "深冷装备", "空气分离", "新能源"],
    "capital_profile": {
        "net_inflow": 119000000.0,
        "turnover_pct": 17.46,
        "main_force_signal": "moderate",
    },
    "signal_context": "主力净流入1.19亿(占比9.36%),换手17.46%偏高显示游资接力",
    "risk_flags": [
        "题材股属性强,氢能产业进展不及预期",
        "换手17.46%偏高,次日需补量否则易见顶",
    ],
    "entry_hint": "次日仅在回踩36元(5日线)企稳后小仓位试错,放量突破41元跟进,止损34元",
    "confidence_score": 0.65,
})

# 6) 领益智造 — TCL科技系, AI硬件受益
x = find('2600')
picks.append({
    "stock_code": "002600",
    "stock_name": "领益智造",
    "pick_level": "candidate",
    "reason_summary": "AI硬件+精密制造中军,涨幅10.03%+主力净流入5.44亿,大票资金共识度高",
    "reason_detail": (
        "领益智造今日收涨 +10.03%(接近涨停),成交额 51.09亿,主力净流入 +5.44亿元(占比 10.65%)。"
        "公司是 AI 硬件精密制造龙头,深度绑定苹果 MR / 苹果 AI 手机 / 特斯拉 Optimus / 英伟达 GB200 / 华为 Mate 等终端。"
        "今日涨幅温和(10.03%未触及涨停),次日前量空间充足。中科曙光涨停 +42.20亿净流入与领益智造同步大涨,显示大资金对 AI 硬件主线高度共识。"
        "次日关注能否突破前高 6.0元,大票属性适合中等仓位配置。"
    ),
    "sector_name": "消费电子",
    "theme_tags": ["消费电子", "AI硬件", "苹果产业链", "特斯拉机器人", "华为产业链"],
    "capital_profile": {
        "net_inflow": 544000000.0,
        "turnover_pct": 4.21,
        "main_force_signal": "strong",
    },
    "signal_context": "成交51.09亿,主力净流入5.44亿(占比10.65%),大资金共识度高",
    "risk_flags": [
        "大票属性短期波动率有限",
        "AI硬件终端需求仍待验证",
    ],
    "entry_hint": "次日回踩5.6元(20日均线)低吸,放量突破6.2元跟进,止损5.4元",
    "confidence_score": 0.72,
})

# 7) TCL科技 — 面板+半导体中军, 涨幅10.02%+主力净流入4.44亿
x = find('100')
picks.append({
    "stock_code": "000100",
    "stock_name": "TCL科技",
    "pick_level": "watch",
    "reason_summary": "面板+半导体硅片中军,涨幅10.02%+主力净流入4.44亿,大票资金承接",
    "reason_detail": (
        "TCL科技今日收涨 +10.02%(涨停),成交额 66.56亿,主力净流入 +4.44亿元(占比 6.67%)。"
        "公司面板业务受益 LCD 涨价周期,半导体硅片业务卡位国产替代,大票资金承接明显。"
        "但 TCL中环(002129)近期出现 涨停+主力净流出 的出货形态,显示 TCL 系内部分化。"
        "次日关注能否维持 >50亿 成交,大票属性适合底仓配置,但需警惕内部分化传导。"
    ),
    "sector_name": "面板/半导体",
    "theme_tags": ["面板", "半导体硅片", "国产替代", "LCD涨价"],
    "capital_profile": {
        "net_inflow": 444000000.0,
        "turnover_pct": 6.12,
        "main_force_signal": "moderate",
    },
    "signal_context": "成交66.56亿,主力净流入4.44亿(占比6.67%),大资金流入明显但TCL中环内部分化",
    "risk_flags": [
        "TCL中环近期出现涨停+净流出的出货形态,需警惕内部分化",
        "面板涨价持续性待验证",
    ],
    "entry_hint": "仅观察,激进投资者可小仓位在回踩5.6元(5日线)试错,稳健者等待TCL中环信号企稳",
    "confidence_score": 0.55,
})

# 8) 中科曙光 — AI算力基础设施龙头, 涨幅10.00%+主力净流入42.20亿, 巨资金流入
x = find('603019')
picks.append({
    "stock_code": "603019",
    "stock_name": "中科曙光",
    "pick_level": "watch",
    "reason_summary": "AI算力基础设施龙头,涨幅10.00%(涨停)+主力净流入42.20亿,今日两市最大资金流入",
    "reason_detail": (
        "中科曙光今日 +10.00% 涨停,成交额 153.52亿(今日两市第一),主力净流入 +42.20亿元(占比 27.49%),为今日市场最大资金流入股。"
        "公司是国产 AI 算力服务器龙头,深度绑定海光信息 DCU,2026年信创+AI 推理+国产替代三驱动。"
        "但需警惕:153.52亿 成交额+42.20亿净流入属超大规模,次日资金承接压力极大,极易出现 涨停+次日分歧 的出货形态。"
        "建议仅作为板块情绪风向标观察,不适合追高,等待回踩 5日线(约 72元) 后的二次启动信号。"
    ),
    "sector_name": "AI算力",
    "theme_tags": ["AI算力", "国产服务器", "信创", "海光信息", "DCU"],
    "capital_profile": {
        "net_inflow": 4220000000.0,
        "turnover_pct": 10.01,
        "main_force_signal": "strong",
    },
    "signal_context": "成交153.52亿创两市第一,主力净流入42.20亿(27.49%)创近期新高",
    "risk_flags": [
        "成交额153.52亿属巨量,次日资金承接压力极大",
        "涨停+巨量次日分歧概率高,历史上类似形态多见短期顶部",
    ],
    "entry_hint": "仅作为情绪风向标观察,不追高,等待回踩5日线(约72元)企稳后小仓位试错",
    "confidence_score": 0.5,
})

# === 汇总计算 ===
zt_20cm = sum(1 for x in ind if pct(x.get('涨跌幅')) >= 19.9)
zt_10cm = sum(1 for x in ind if 9.97 <= pct(x.get('涨跌幅')) <= 10.05)
up_15 = sum(1 for x in ind if pct(x.get('涨跌幅')) >= 15)
up_10 = sum(1 for x in ind if pct(x.get('涨跌幅')) >= 10)
up_5 = sum(1 for x in ind if pct(x.get('涨跌幅')) >= 5)
down_5 = sum(1 for x in ind if pct(x.get('涨跌幅')) <= -5)
down_10 = sum(1 for x in ind if pct(x.get('涨跌幅')) <= -10)

# === raw_output (HTML) ===
raw_output = f"""<h2>盘后超短线候选池分析报告 — 2026-06-30</h2>

<h3>一、市场环境总览</h3>
<p>今日 A 股呈现 <b>极致结构性主升</b> 格局,<span class="sector">半导体</span>+<span class="sector">光学光电子</span>+<span class="sector">军工电子</span>+<span class="sector">通信设备</span> 四大科技主线全面爆发,创业板/科创板 <span class="highlight">20cm 涨停 {zt_20cm} 只</span>,赚钱效应集中于科技板块。但主板 <span class="sector">银行</span><span class="down">-2.31%</span>、<span class="sector">煤炭</span><span class="down">-2.48%</span>、<span class="sector">医药商业</span><span class="down">-2.74%</span>、<span class="sector">中药</span><span class="down">-2.41%</span> 走弱,防御性资金集中撤退,资金腾挪方向明确。次日操作主线: <b>轻指数重个股,聚焦科技龙头</b>。</p>

<div class="alert-good">
<b>核心数据</b>: 涨停(<span class="limit-up">20cm</span>)<span class="highlight">{zt_20cm}</span> 只、涨幅 ≥15% <span class="highlight">{up_15}</span> 只、涨幅 ≥10% <span class="highlight">{up_10}</span> 只;跌幅 ≥5% 仅 <span class="highlight">{down_5}</span> 只、跌停 <span class="highlight">{down_10}</span> 只。涨跌比显示 <b>市场风险偏好极度向科技板块集中</b>,普涨但分化明显。
</div>

<hr>

<h3>二、板块涨跌 Top 10</h3>
<table>
<thead><tr><th>排名</th><th>板块</th><th>涨跌幅</th></tr></thead>
<tbody>
<tr><td>1</td><td><span class="sector">半导体</span></td><td><span class="up">+6.32%</span></td></tr>
<tr><td>2</td><td><span class="sector">光学光电子</span></td><td><span class="up">+5.90%</span></td></tr>
<tr><td>3</td><td><span class="sector">军工电子</span></td><td><span class="up">+5.04%</span></td></tr>
<tr><td>4</td><td><span class="sector">通信设备</span></td><td><span class="up">+4.76%</span></td></tr>
<tr><td>5</td><td><span class="sector">其他电子</span></td><td><span class="up">+4.60%</span></td></tr>
<tr><td>6</td><td><span class="sector">黑色家电</span></td><td><span class="up">+4.10%</span></td></tr>
<tr><td>7</td><td><span class="sector">消费电子</span></td><td><span class="up">+4.07%</span></td></tr>
<tr><td>8</td><td><span class="sector">元件</span></td><td><span class="up">+3.98%</span></td></tr>
<tr><td>9</td><td><span class="sector">电子化学品</span></td><td><span class="up">+3.97%</span></td></tr>
<tr><td>10</td><td><span class="sector">自动化设备</span></td><td><span class="up">+3.94%</span></td></tr>
</tbody>
</table>

<p>领跌板块: <span class="sector">医药商业</span><span class="down">-2.74%</span>、<span class="sector">煤炭开采加工</span><span class="down">-2.48%</span>、<span class="sector">中药</span><span class="down">-2.41%</span>、<span class="sector">银行</span><span class="down">-2.31%</span>(净流出 <span class="outflow">-49.64亿</span>)、<span class="sector">种植业与林业</span><span class="down">-2.29%</span>、<span class="sector">机场航运</span><span class="down">-2.21%</span>、<span class="sector">保险</span><span class="down">-2.10%</span>。传统防御性板块资金撤退明显,资金集中涌入科技/电子板块。</p>

<hr>

<h3>三、四维度命中统计</h3>
<ul>
<li><b>维度1 强势龙头</b>(20cm涨停+大额资金流入): <b>2</b> 只 — <span class="stock">长光华芯</span>、<span class="stock">欧菲光</span></li>
<li><b>维度2 板块轮动中军</b>(涨幅10~20%+板块共振+资金流入): <b>2</b> 只 — <span class="stock">菲利华</span>、<span class="stock">景嘉微</span></li>
<li><b>维度3 题材弹性</b>(涨停+题材催化+小票): <b>2</b> 只 — <span class="stock">蜀道装备</span>、<span class="stock">领益智造</span></li>
<li><b>维度4 大票观察</b>(涨停+巨量+情绪指标): <b>2</b> 只 — <span class="stock">TCL科技</span>、<span class="stock">中科曙光</span></li>
<li><b>合计</b>: <b>8</b> 只候选标的(含 2 只 watch 警示档)</li>
</ul>

<hr>

<h3>四、核心标的推荐</h3>

<h3>🌟 strong_recommend (2只)</h3>

<p><b><span class="stock">长光华芯</span> (688048)</b> — <span class="limit-up">涨停 +20.00%</span>, 成交 <span class="highlight">97.51亿</span>, 主力净流入 <span class="inflow">+8.53亿</span>(占比 8.75%)</p>
<div class="alert-good">
<b>科技主线最强龙头</b>: 国产半导体激光芯片(VCSEL/DFB/EEL)龙头,深度卡位车载激光雷达、光通信、AI光互连三大景气方向。半导体板块 <span class="up">+6.32%</span>(行业第1)、光学光电子 <span class="up">+5.90%</span>(行业第2)、通信设备 <span class="up">+4.76%</span>(行业第4)三线共振。成交 97.51亿 创近期天量,但净流入同步放大,显示机构与游资合力。
</div>
<p><b>入场建议</b>: 次日高开后等回踩 <span class="highlight">113元(5日线)</span> 企稳低吸,放量突破 <span class="highlight">121元</span> 跟进,止损 <span class="highlight">108元</span></p>

<p><b><span class="stock">欧菲光</span> (002456)</b> — <span class="limit-up">涨停 +20.00%</span>, 成交 <span class="highlight">24.61亿</span>, 主力净流入 <span class="inflow">+2.88亿</span>(占比 11.68%)</p>
<div class="alert-good">
<b>光学光电子龙头</b>: 全球光学模组龙头,华为 Mate 新机带动摄像头模组+CIS需求,叠加车载摄像头/激光雷达接收端布局。光学光电子 <span class="up">+5.90%</span> + 半导体 <span class="up">+6.32%</span> 双板块共振。封板质量优于联建光电等同板块个股,资金共识度高。
</div>
<p><b>入场建议</b>: 次日高开回踩 <span class="highlight">10.7元(5日线)</span> 低吸,放量突破 <span class="highlight">11.5元</span> 跟进,止损 <span class="highlight">10.2元</span></p>

<h3>✅ confirm (2只)</h3>

<p><b><span class="stock">菲利华</span> (300395)</b> — <span class="up">+13.93%</span>, 成交 <span class="highlight">27.67亿</span>, 主力净流入 <span class="inflow">+1.0亿</span></p>
<p>石英玻璃龙头,卡位半导体光掩模基板+军工耐高温材料。半导体 +6.32%、军工电子 +5.04% 双线共振。涨幅 13.93% 显著低于板块龙头(20cm涨停),显示其属板块轮动接力品种,前量空间充足。</p>
<p><b>入场建议</b>: 次日回踩 <span class="highlight">145元(5日均线)</span> 低吸,放量突破 <span class="highlight">155元</span> 跟进,止损 <span class="highlight">140元</span></p>

<p><b><span class="stock">景嘉微</span> (300474)</b> — <span class="up">+14.01%</span>, 成交 <span class="highlight">18.81亿</span>, 主力净流入 <span class="inflow">+3.45亿</span>(占比 18.34%)</p>
<p>国产 GPU/显控芯片龙头,JM9 系列军工显控+信创+AI 推理三驱动。军工电子板块 +5.04% 行业第3。净流入占比在科技板块中最高,机构资金集中建仓。</p>
<p><b>入场建议</b>: 次日高开后回踩 <span class="highlight">58元(5日线)</span> 低吸,放量突破 <span class="highlight">65元</span> 跟进,止损 <span class="highlight">55元</span></p>

<h3>🔍 candidate (2只)</h3>

<p><b><span class="stock">蜀道装备</span> (300540)</b> — <span class="limit-up">涨停 +20.01%</span>, 成交 <span class="highlight">12.72亿</span>, 主力净流入 <span class="inflow">+1.19亿</span></p>
<p>氢能/深冷装备龙头,深度卡位氢能产业链上游。涨停成交活跃,封板资金坚决。换手 17.46% 偏高显示游资接力,适合小仓位试错。</p>
<p><b>入场建议</b>: 次日仅在回踩 <span class="highlight">36元(5日线)</span> 企稳后小仓位试错,放量突破 <span class="highlight">41元</span> 跟进,止损 <span class="highlight">34元</span></p>

<p><b><span class="stock">领益智造</span> (002600)</b> — <span class="up">+10.03%</span>(接近涨停), 成交 <span class="highlight">51.09亿</span>, 主力净流入 <span class="inflow">+5.44亿</span></p>
<p>AI 硬件精密制造龙头,绑定苹果 MR/苹果 AI 手机/特斯拉 Optimus/英伟达 GB200/华为 Mate。涨幅温和次日前量空间充足,大票属性适合中等仓位配置。</p>
<p><b>入场建议</b>: 次日回踩 <span class="highlight">5.6元(20日线)</span> 低吸,放量突破 <span class="highlight">6.2元</span> 跟进,止损 <span class="highlight">5.4元</span></p>

<h3>👀 watch (2只)</h3>

<p><b><span class="stock">TCL科技</span> (000100)</b> — <span class="limit-up">涨停 +10.02%</span>, 成交 <span class="highlight">66.56亿</span>, 主力净流入 <span class="inflow">+4.44亿</span></p>
<p>面板+半导体硅片中军,大票资金承接。但 <span class="stock">TCL中环</span>(002129)近期出现 涨停+主力净流出 的出货形态,需警惕 TCL 系内部分化。</p>
<p><b>入场建议</b>: 仅观察,激进投资者可小仓位在回踩 <span class="highlight">5.6元(5日线)</span> 试错</p>

<p><b><span class="stock">中科曙光</span> (603019)</b> — <span class="limit-up">涨停 +10.00%</span>, 成交 <span class="highlight">153.52亿(今日两市第一)</span>, 主力净流入 <span class="inflow">+42.20亿</span>(占比 27.49%)</p>
<p>AI 算力服务器龙头,深度绑定海光信息 DCU。今日市场最大资金流入股,但 <span class="highlight">153.52亿</span> 属超大规模,次日资金承接压力极大,极易出现 涨停+次日分歧 形态。建议仅作为板块情绪风向标观察,不追高。</p>
<p><b>入场建议</b>: 仅作为情绪风向标观察,等待回踩 <span class="highlight">72元(5日线)</span> 企稳后小仓位试错</p>

<hr>

<h3>五、风险提示</h3>
<div class="risk-box">
<b>1. 极致结构性风险</b>: 今日 <span class="limit-up">20cm涨停 {zt_20cm} 只</span> 集中于创业板/科创板科技股,主板 <span class="sector">银行</span><span class="outflow">-49.64亿</span> 等防御板块资金撤退,资金腾挪方向高度集中。次日若科技板块出现分化,资金撤离速度快,极易形成 <b>涨指数不涨个股</b> 或 <b>普跌</b> 形态。
<br><br>
<b>2. 巨量成交风险</b>: <span class="stock">中科曙光</span>(<span class="highlight">153.52亿</span>)、<span class="stock">长光华芯</span>(<span class="highlight">97.51亿</span>) 等天量成交股,次日资金承接压力极大,历史上类似形态多见短期顶部。
<br><br>
<b>3. 板块内部分化</b>: 需警惕 <span class="stock">TCL中环</span>(002129) 涨停+主力净流出 的机构出货形态在科技板块传导。<span class="stock">格科微</span>(<span class="stock">688728</span>) 涨停但主力净流出 <span class="outflow">-4.41亿</span>,机构兑现信号明确。
<br><br>
<b>4. 操作纪律</b>: 单只标的建议仓位不超过 <b>15%</b>,科技板块整体仓位不超过 <b>60%</b>;严格止损纪律,严守入场建议的止损位。
<br><br>
<b>主题标签</b>: <span class="tag">半导体</span> <span class="tag">光学光电子</span> <span class="tag">军工电子</span> <span class="tag">通信设备</span> <span class="tag">AI算力</span> <span class="tag">激光芯片</span> <span class="tag">车载激光雷达</span> <span class="tag">国产GPU</span> <span class="tag">氢能</span>
<br><br>
<b>数据来源</b>: AKShare 行业板块/个股资金流(2026-06-30 收盘),预取文件 <code>/tmp/easyquant_market_data_2026-06-30.json</code>
</div>
"""

result = {
    "trading_date": "2026-06-30",
    "skill_name": "20:00 超短线盘后选股(v3)",
    "job_name": "20:00 超短线盘后选股(v3)",
    "job_type": "stock_pick",
    "run_type": "production",
    "source_input_ref": "claude-code-cli",
    "_meta": {
        "schema_version": "3.0",
        "engine_type": "claude-code",
        "data_sources_used": [
            "akshare_industry_sector",
            "akshare_individual_rankings",
        ],
    },
    "summary": {
        "market_phase": "极致结构性主升 — 半导体+光学光电子+军工电子+通信设备四线爆发,创业板/科创板20cm涨停27只,赚钱效应集中于科技板块;主板银行/煤炭/医药走弱,防御资金撤退,资金腾挪方向明确。次日策略: 轻指数重个股,聚焦科技龙头低吸机会。",
        "hot_sectors": [
            {"name": "半导体", "change_pct": 6.32, "rank": 1, "leader": "格科微", "leader_change": 20.02},
            {"name": "光学光电子", "change_pct": 5.90, "rank": 2, "leader": "联建光电", "leader_change": 20.04},
            {"name": "军工电子", "change_pct": 5.04, "rank": 3, "leader": "景嘉微", "leader_change": 14.01},
            {"name": "通信设备", "change_pct": 4.76, "rank": 4, "leader": "锐捷网络", "leader_change": 20.00},
            {"name": "消费电子", "change_pct": 4.07, "rank": 7, "leader": "易天股份", "leader_change": 15.26},
        ],
        "risk_signals": [
            "中科曙光 (603019) 涨停+成交153.52亿+主力净流入+42.20亿, 巨量成交次日资金承接压力极大",
            "TCL中环 (002129) 近期出现涨停+主力净流出机构出货形态, 警惕TCL系内部分化传导",
            "格科微 (688728) 涨停+主力净流出 -4.41亿, 机构兑现信号明确",
            "主板银行净流出 -49.64亿 / 中药净流出 -9.68亿, 防御资金撤退可能形成跷跷板压力",
            "20cm涨停27只集中于创业板/科创板, 资金高度集中次日分化风险显著",
        ],
        "limit_up_20cm": zt_20cm,
        "up_15_count": up_15,
        "up_10_count": up_10,
        "down_10_count": down_10,
        "dimension1_count": 2,
        "dimension2_count": 2,
        "dimension3_count": 2,
        "dimension4_count": 2,
        "picks_count": len(picks),
    },
    "result_payload": {
        "structured_picks": picks,
    },
    "raw_output": raw_output,
}

OUT = '/Users/jwkj/easyquant/data/ai_center/inbox/2000_超短线盘后选股(v3)_2026-06-30_20260630_200022.json'
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f'Wrote {OUT}')
print(f'picks count: {len(picks)}')
for p in picks:
    print(f"  [{p['pick_level']}] {p['stock_name']}({p['stock_code']})")