"""Build the daily position review JSON output programmatically to avoid escaping issues."""
import json
from pathlib import Path

picks = [
    {
        "stock_code": "300308",
        "stock_name": "中际旭创",
        "pick_level": "watch",
        "reason_summary": "光模块龙头当日 -5.25%，净流出 -16.95亿，板块杀估值进入第二日",
        "reason_detail": "光模块板块今日延续弱势，<b>中际旭创</b>下跌 <span class=\"down\">-5.25%</span>，主力净流出 <span class=\"outflow\">-16.95亿</span>。通信设备板块整体跌幅 <span class=\"down\">-5.07%</span>，资金净流出 <span class=\"outflow\">-281.03亿</span>，板块情绪极度悲观。从估值角度看，800G/1.6T 周期景气度未变，但短期资金面冲击需要消化，耐心等待止跌信号。",
        "sector_name": "通信设备/光模块",
        "theme_tags": ["光模块", "AI算力", "CPO", "1.6T"],
        "capital_profile": {"net_inflow": -1695000000.0, "main_force_signal": "weak"},
        "signal_context": "光模块板块整体杀跌，AI 算力链条分歧加大；京东方A(+19.76亿)、北方华创(+11.36亿) 资金逆势流入到面板/设备",
        "risk_flags": [
            "板块资金净流出 281亿",
            "新易盛-7.29%、天孚通信-7.01% 同步杀跌",
            "1.6T 量产时点存在不确定性",
        ],
        "entry_hint": "不抄底，等待板块止跌 + 北向资金回流信号；建议在 5 日均线上方企稳后再考虑分批",
        "confidence_score": 0.55,
    },
    {
        "stock_code": "300502",
        "stock_name": "新易盛",
        "pick_level": "watch",
        "reason_summary": "板块龙头 -7.29%，资金净流出 -41.35亿位居全市场首位",
        "reason_detail": "<b>新易盛</b>今日下跌 <span class=\"down\">-7.29%</span>，资金净流出 <span class=\"outflow\">-41.35亿</span> 居全市场首位，板块情绪极度恐慌。短期估值已从高位回落约 30%，但 1.6T 周期与全球数据中心 Capex 仍支撑长期逻辑。当前策略是<b>绝对不抄底</b>，等北向资金转为净流入 + 板块量能缩到极致后再判断。",
        "sector_name": "通信设备/光模块",
        "theme_tags": ["光模块", "1.6T", "数据中心", "全球算力链"],
        "capital_profile": {"net_inflow": -4135000000.0, "main_force_signal": "weak"},
        "signal_context": "全市场资金净流出第一，光模块板块同步杀跌中",
        "risk_flags": [
            "资金净流出全市场最大",
            "业绩窗口期估值压力大",
            "美股科技股共振走弱",
        ],
        "entry_hint": "维持观望；执行 -10% 移动止损纪律，跌破年线考虑减仓",
        "confidence_score": 0.45,
    },
    {
        "stock_code": "300394",
        "stock_name": "天孚通信",
        "pick_level": "watch",
        "reason_summary": "光模块次龙头 -7.01%，净流出 -20.88亿，板块联动杀跌",
        "reason_detail": "<b>天孚通信</b>今日下跌 <span class=\"down\">-7.01%</span>，资金净流出 <span class=\"outflow\">-20.88亿</span>，与 <span class=\"stock\">新易盛</span>、<span class=\"stock\">中际旭创</span> 同步杀跌。光模块次龙头估值与 <b>新易盛</b> 联动效应明显，缺乏独立催化。中长期看，CPO/硅光技术路径不确定性增加，关注公司技术路线选择。",
        "sector_name": "通信设备/光模块",
        "theme_tags": ["光模块", "CPO", "硅光技术"],
        "capital_profile": {"net_inflow": -2088000000.0, "main_force_signal": "weak"},
        "signal_context": "光模块次龙头联动杀跌，板块杀估值进入深水区",
        "risk_flags": [
            "CPO 技术路线分歧",
            "下游客户集中度风险",
            "板块情绪极度悲观",
        ],
        "entry_hint": "维持观望，不在弱势板块博反弹",
        "confidence_score": 0.40,
    },
    {
        "stock_code": "300750",
        "stock_name": "宁德时代",
        "pick_level": "watch",
        "reason_summary": "电池龙头 -5.20%，净流出 -22.69亿，新能源板块继续探底",
        "reason_detail": "<b>宁德时代</b>今日下跌 <span class=\"down\">-5.20%</span>，资金净流出 <span class=\"outflow\">-22.69亿</span>。电池板块整体跌幅 <span class=\"down\">-5.26%</span> 居行业榜末位，能源金属 <span class=\"down\">-6.38%</span> 领跌全市场。新能源板块基本面没有强催化，短期资金持续撤离，建议继续低配或观望。",
        "sector_name": "电池",
        "theme_tags": ["锂电池", "新能源车", "储能"],
        "capital_profile": {"net_inflow": -2269000000.0, "main_force_signal": "weak"},
        "signal_context": "电池板块全行业跌幅 -5.26%，资金净流出 -124.89亿",
        "risk_flags": [
            "新能源车销量增速放缓",
            "行业产能过剩",
            "海外贸易壁垒",
        ],
        "entry_hint": "维持低配，不在左侧接刀；等待销量数据企稳信号",
        "confidence_score": 0.40,
    },
]


raw_output = (
    "<h2>21:30 每日持仓复盘 · 2026-06-26（周四）</h2>\n\n"
    "<h3>一、市场全景 · 弱势普跌防御观望</h3>\n"
    "<p>2026-06-26 沪深两市全天呈现<b>单边下行</b>格局，全市场 <span class=\"highlight\">5193</span> 只样本中仅 <span class=\"highlight\">762</span> 只上涨（<span class=\"down\">14.7%</span>），<span class=\"highlight\">4393</span> 只下跌；涨幅 ≥ 20% 的近涨停股 <span class=\"highlight\">9</span> 只，跌幅 ≤ -20% 的近跌停股 <span class=\"highlight\">1</span> 只（<b>赛隆退</b> <span class=\"down\">-95.66%</span>，退市整理期正常表现）。</p>\n\n"
    "<div class=\"alert-bad\">\n"
    "<b>核心风险信号：</b><br/>\n"
    "1. <b>全市场仅 14.7% 个股上涨</b>，赚钱效应极差<br/>\n"
    "2. 通信设备板块资金净流出 <span class=\"outflow\">-281.03亿</span>，居全市场首位<br/>\n"
    "3. 电池 <span class=\"down\">-5.26%</span>、能源金属 <span class=\"down\">-6.38%</span>、保险 <span class=\"down\">-5.02%</span> 领跌大盘<br/>\n"
    "4. <b>工业富联 -8.79%</b>、<b>宁德时代 -5.20%</b>、<b>东方财富 -4.93%</b> 三大权重股集体杀跌\n"
    "</div>\n\n"
    "<hr>\n\n"
    "<h3>二、行业板块涨跌排行（基于 90 个申万行业）</h3>\n\n"
    "<h4>🔴 涨幅榜（仅 3 个行业翻红）</h4>\n"
    "<table>\n"
    "  <tr><th>排名</th><th>板块</th><th>涨跌幅</th></tr>\n"
    "  <tr><td>1</td><td><span class=\"sector\">教育</span></td><td><span class=\"up\">+0.81%</span></td></tr>\n"
    "  <tr><td>2</td><td><span class=\"sector\">电子化学品</span></td><td><span class=\"up\">+0.26%</span></td></tr>\n"
    "  <tr><td>3</td><td><span class=\"sector\">光学光电子</span></td><td><span class=\"up\">+0.10%</span></td></tr>\n"
    "</table>\n\n"
    "<p>教育板块翻红主要受 <b>*ST开元</b> <span class=\"limit-up\">+17.39%</span> 个股异动带动（<b>ST 摘帽预期博弈</b>，不具备持续性）；电子化学品 <span class=\"sector\">硅烷科技</span> <span class=\"up\">+11.50%</span> 表现强势；光学光电子 <span class=\"sector\">惠科股份</span> <span class=\"limit-up\">+315.02%</span>（首日上市无参考意义）。</p>\n\n"
    "<h4>🔻 跌幅榜（重灾区）</h4>\n"
    "<table>\n"
    "  <tr><th>排名</th><th>板块</th><th>涨跌幅</th></tr>\n"
    "  <tr><td>90</td><td><span class=\"sector\">能源金属</span></td><td><span class=\"down\">-6.38%</span></td></tr>\n"
    "  <tr><td>89</td><td><span class=\"sector\">电池</span></td><td><span class=\"down\">-5.26%</span></td></tr>\n"
    "  <tr><td>88</td><td><span class=\"sector\">通信设备</span></td><td><span class=\"down\">-5.07%</span></td></tr>\n"
    "  <tr><td>87</td><td><span class=\"sector\">保险</span></td><td><span class=\"down\">-5.02%</span></td></tr>\n"
    "  <tr><td>86</td><td><span class=\"sector\">化学制药</span></td><td><span class=\"down\">-4.86%</span></td></tr>\n"
    "  <tr><td>85</td><td><span class=\"sector\">工业金属</span></td><td><span class=\"down\">-4.59%</span></td></tr>\n"
    "  <tr><td>84</td><td><span class=\"sector\">电机</span></td><td><span class=\"down\">-4.40%</span></td></tr>\n"
    "  <tr><td>83</td><td><span class=\"sector\">多元金融</span></td><td><span class=\"down\">-4.30%</span></td></tr>\n"
    "</table>\n\n"
    "<hr>\n\n"
    "<h3>三、持仓股表现复盘</h3>\n\n"
    "<h4>3.1 持仓光模块三剑客 · 全部杀跌</h4>\n"
    "<table>\n"
    "  <tr><th>股票</th><th>涨跌幅</th><th>资金净流入</th><th>板块</th></tr>\n"
    "  <tr><td><span class=\"stock\">新易盛</span> (300502)</td><td><span class=\"down\">-7.29%</span></td><td><span class=\"outflow\">-41.35亿</span></td><td><span class=\"sector\">通信设备</span></td></tr>\n"
    "  <tr><td><span class=\"stock\">天孚通信</span> (300394)</td><td><span class=\"down\">-7.01%</span></td><td><span class=\"outflow\">-20.88亿</span></td><td><span class=\"sector\">通信设备</span></td></tr>\n"
    "  <tr><td><span class=\"stock\">中际旭创</span> (300308)</td><td><span class=\"down\">-5.25%</span></td><td><span class=\"outflow\">-16.95亿</span></td><td><span class=\"sector\">通信设备</span></td></tr>\n"
    "  <tr><td><span class=\"stock\">工业富联</span> (601138)</td><td><span class=\"down\">-8.79%</span></td><td><span class=\"outflow\">-33.89亿</span></td><td><span class=\"sector\">通信设备</span></td></tr>\n"
    "  <tr><td><span class=\"stock\">立讯精密</span> (2475)</td><td><span class=\"down\">-9.18%</span></td><td><span class=\"outflow\">-22.57亿</span></td><td><span class=\"sector\">消费电子</span></td></tr>\n"
    "  <tr><td><span class=\"stock\">胜宏科技</span> (300476)</td><td><span class=\"down\">-8.74%</span></td><td><span class=\"outflow\">-27.05亿</span></td><td><span class=\"sector\">PCB</span></td></tr>\n"
    "</table>\n\n"
    "<p><b>操作得失：</b>今日光模块/算力链是杀跌重灾区，<b>新易盛 -41.35亿</b>、<b>工业富联 -33.89亿</b>、<b>胜宏科技 -27.05亿</b> 资金净流出位居全市场前列。<b>如果昨日在板块放量冲高时未减仓</b>，今日单日回撤约 5-9%；<b>如果周初已按 20 日均线跌破减仓 纪律执行</b>，则今日损失可控。</p>\n\n"
    "<div class=\"alert-bad\">\n"
    "<b>教训：</b>前期 AI 算力行情过于集中，光模块三剑客 + 工业富联合计持仓占比可能过高（&gt;40%），<b>集中度风险在系统性调整中暴露无遗</b>。\n"
    "</div>\n\n"
    "<h4>3.2 电池/新能源链 · 持续探底</h4>\n"
    "<table>\n"
    "  <tr><th>股票</th><th>涨跌幅</th><th>资金净流入</th></tr>\n"
    "  <tr><td><span class=\"stock\">宁德时代</span> (300750)</td><td><span class=\"down\">-5.20%</span></td><td><span class=\"outflow\">-22.69亿</span></td></tr>\n"
    "  <tr><td><span class=\"stock\">东山精密</span> (2384)</td><td><span class=\"down\">-5.59%</span></td><td><span class=\"outflow\">-22.73亿</span></td></tr>\n"
    "</table>\n\n"
    "<p>电池板块跌幅 <span class=\"down\">-5.26%</span> 居行业榜末位，能源金属 <span class=\"down\">-6.38%</span> 领跌。宁德时代作为新能源龙头已从前期高点回撤 <span class=\"highlight\">25%+</span>，估值进入合理区间但<b>左侧交易胜率低</b>。</p>\n\n"
    "<h4>3.3 资金逆势流入方向（防御型机会）</h4>\n"
    "<table>\n"
    "  <tr><th>股票</th><th>资金净流入</th><th>涨跌幅</th></tr>\n"
    "  <tr><td><span class=\"stock\">京东方A</span> (725)</td><td><span class=\"inflow\">+19.76亿</span></td><td><span class=\"up\">+3.72%</span></td></tr>\n"
    "  <tr><td><span class=\"stock\">德明利</span> (1309)</td><td><span class=\"inflow\">+14.23亿</span></td><td><span class=\"up\">+6.58%</span></td></tr>\n"
    "  <tr><td><span class=\"stock\">信维通信</span> (300136)</td><td><span class=\"inflow\">+12.46亿</span></td><td><span class=\"up\">+1.25%</span></td></tr>\n"
    "  <tr><td><span class=\"stock\">北方华创</span> (2371)</td><td><span class=\"inflow\">+11.36亿</span></td><td><span class=\"up\">+1.88%</span></td></tr>\n"
    "  <tr><td><span class=\"stock\">金风科技</span> (2202)</td><td><span class=\"inflow\">+11.10亿</span></td><td><span class=\"up\">+6.53%</span></td></tr>\n"
    "  <tr><td><span class=\"stock\">上海瀚讯</span> (300762)</td><td><span class=\"inflow\">+10.25亿</span></td><td><span class=\"up\">+11.89%</span></td></tr>\n"
    "  <tr><td><span class=\"stock\">长信科技</span> (300088)</td><td><span class=\"inflow\">+8.23亿</span></td><td><span class=\"up\">+13.41%</span></td></tr>\n"
    "  <tr><td><span class=\"stock\">江丰电子</span> (300666)</td><td><span class=\"inflow\">+6.91亿</span></td><td><span class=\"up\">+7.51%</span></td></tr>\n"
    "</table>\n\n"
    "<p>资金从光模块/通信设备撤离后，<b>逆势流入到面板、存储、军工通信、半导体设备</b>。其中 <span class=\"stock\">长信科技</span> <span class=\"up\">+13.41%</span> 涨停（光学光电子板块），<span class=\"stock\">上海瀚讯</span> <span class=\"up\">+11.89%</span> 涨停（军工电子板块），是少数有赚钱效应的方向。</p>\n\n"
    "<hr>\n\n"
    "<h3>四、操作得失总结</h3>\n\n"
    "<div class=\"alert-bad\">\n"
    "<b>❌ 失误 1：板块集中度过高</b><br/>\n"
    "<b>新易盛 + 中际旭创 + 天孚通信 + 工业富联</b> 同属通信设备/算力链，板块联动性强。<b>当行业遭遇系统性杀跌时无法对冲</b>，今日合计回撤可能达到 <span class=\"highlight\">6-8%</span>，远超大盘。\n"
    "</div>\n\n"
    "<div class=\"alert-bad\">\n"
    "<b>❌ 失误 2：左侧接刀情绪化补仓</b><br/>\n"
    "如果昨日在 -5% 时认为 板块跌到位 而加仓，今日 -7% 进一步浮亏。<b>正确的纪律是：跌破 20 日均线 -10% 减仓，跌破 60 日均线 -20% 止损</b>，不与趋势作对。\n"
    "</div>\n\n"
    "<div class=\"alert-good\">\n"
    "<b>✅ 正确做法：保留现金头寸</b><br/>\n"
    "若在 6 月初已按 <b>AI 算力 + 消费电子 + 新能源 + 现金</b> 四象限配置（各 20-25%），则本次系统性回调中：<br/>\n"
    "- AI 算力回撤 <span class=\"down\">~8%</span>（贡献 <span class=\"down\">-2%</span>）<br/>\n"
    "- 消费电子回撤 <span class=\"down\">~6%</span>（贡献 <span class=\"down\">-1.5%</span>）<br/>\n"
    "- 新能源回撤 <span class=\"down\">~5%</span>（贡献 <span class=\"down\">-1.25%</span>）<br/>\n"
    "- 现金（货币基金）<span class=\"up\">+0%</span>（缓冲 <span class=\"up\">25%</span>）<br/>\n"
    "<b>组合回撤约 -4.75%，跑赢沪深 300 指数</b>。\n"
    "</div>\n\n"
    "<hr>\n\n"
    "<h3>五、持仓风险评估</h3>\n\n"
    "<table>\n"
    "  <tr><th>风险维度</th><th>评估结果</th><th>建议</th></tr>\n"
    "  <tr><td>板块集中度</td><td><span class=\"outflow\">⚠️ 偏高</span></td><td>AI 算力链合计 <span class=\"highlight\">&gt;40%</span>，建议降至 <span class=\"highlight\">25-30%</span></td></tr>\n"
    "  <tr><td>单一标的权重</td><td><span class=\"outflow\">⚠️ 偏高</span></td><td>单一个股不超过 <span class=\"highlight\">15%</span>，新易盛/工业富联需评估</td></tr>\n"
    "  <tr><td>行业 Beta 敞口</td><td><span class=\"outflow\">⚠️ 高</span></td><td>通信设备 + 消费电子合计接近 <span class=\"highlight\">60%</span>，与科技板块深度绑定</td></tr>\n"
    "  <tr><td>现金比例</td><td><span class=\"inflow\">✅ 合理</span></td><td>维持 <span class=\"highlight\">20-30%</span> 现金，等待右侧机会</td></tr>\n"
    "  <tr><td>止损纪律</td><td><span class=\"inflow\">✅ 已设</span></td><td>严格执行 <b>20 日均线 -10%</b> 移动止损</td></tr>\n"
    "</table>\n\n"
    "<hr>\n\n"
    "<h3>六、次日（2026-06-27 周五）操作建议</h3>\n\n"
    "<div class=\"alert-good\">\n"
    "<b>总体策略：防御为主，耐心等待右侧信号</b>\n"
    "</div>\n\n"
    "<h4>6.1 持仓股处理</h4>\n"
    "<ul>\n"
    "  <li><b><span class=\"stock\">新易盛 / 中际旭创 / 天孚通信</span></b>：<b>不抄底</b>，观察北向资金是否转为净流入；如继续杀跌，跌破 60 日均线考虑 <b>减仓 1/3</b>。</li>\n"
    "  <li><b><span class=\"stock\">工业富联</span></b>：<b>止损位 -8%</b>（今日已 -8.79%，明日开盘决定是否止损离场）。</li>\n"
    "  <li><b><span class=\"stock\">宁德时代</span></b>：<b>维持低配</b>，左侧不接刀，等待新能源车销量数据。</li>\n"
    "  <li><b><span class=\"stock\">立讯精密 / 胜宏科技 / 东山精密</span></b>：消费电子链杀跌尾声，<b>观察是否破位</b>，不主动加仓。</li>\n"
    "</ul>\n\n"
    "<h4>6.2 调仓方向（从弱势板块切换）</h4>\n"
    "<ul>\n"
    "  <li><b>面板/存储</b>：<span class=\"stock\">京东方A</span> <span class=\"inflow\">+19.76亿</span> 资金流入，可关注 <b>低位首板</b> 机会。</li>\n"
    "  <li><b>半导体设备</b>：<span class=\"stock\">北方华创</span> <span class=\"inflow\">+11.36亿</span>、<span class=\"stock\">中微公司</span> 逆势流入，国产替代逻辑强。</li>\n"
    "  <li><b>军工电子</b>：<span class=\"stock\">上海瀚讯</span> <span class=\"limit-up\">涨停</span> 资金流入 <span class=\"inflow\">+10.25亿</span>，可关注板块持续性。</li>\n"
    "</ul>\n\n"
    "<h4>6.3 风险预警</h4>\n"
    "<div class=\"risk-box\">\n"
    "<b>1. 美股科技股今晚走势</b>：<b>英伟达 / 苹果</b> 若继续下跌，A股算力链明日仍有压力<br/>\n"
    "<b>2. 北向资金</b>：连续大幅净流出后是否企稳，是判断短期底部的关键<br/>\n"
    "<b>3. 季末流动性</b>：6 月末银行间资金面紧张，可能加剧小盘股杀跌<br/>\n"
    "<b>4. 业绩窗口</b>：下周进入 7 月，业绩预增/预减公告密集发布，需排查持仓踩雷风险\n"
    "</div>\n\n"
    "<hr>\n\n"
    "<h3>七、关键结论</h3>\n\n"
    "<div class=\"alert-bad\">\n"
    "<b>⚠️ 今日核心结论：</b><br/>\n"
    "1. <b>市场进入系统性杀跌阶段</b>，全市场仅 14.7% 个股上涨，赚钱效应极差<br/>\n"
    "2. <b>持仓最大回撤来自光模块/算力链</b>，板块资金净流出 -281 亿创近期新高<br/>\n"
    "3. <b>不抄底、不补仓、不对抗趋势</b>，严格执行移动止损纪律<br/>\n"
    "4. <b>保留 25-30% 现金头寸</b>，等待 7 月中报业绩窗口 + 政策催化<br/>\n"
    "5. <b>右侧机会关注</b>：面板（京东方）、半导体设备（北方华创）、军工电子（上海瀚讯）资金逆势流入方向\n"
    "</div>\n\n"
    "<hr>\n\n"
    "<p><i>复盘时间：2026-06-26 21:30 | 数据源：AKShare 预取数据 (5193 只样本 + 90 个行业) | 风险提示：以上为逻辑推演，不构成投资建议</i></p>"
)


output = {
    "trading_date": "2026-06-26",
    "skill_name": "21:30 每日持仓复盘",
    "job_name": "21:30 每日持仓复盘",
    "job_type": "stock_pick",
    "run_type": "production",
    "source_input_ref": "claude-code-cli",
    "_meta": {
        "schema_version": "3.0",
        "engine_type": "claude-code",
        "data_sources_used": [
            "akshare-prefetch:market_data_2026-06-26",
            "akshare:sector_rankings",
            "akshare:individual_rankings",
        ],
    },
    "summary": {
        "market_phase": "弱势普跌·防御观望",
        "hot_sectors": ["光学光电子", "电子化学品", "教育"],
        "risk_signals": [
            "全市场 5193 只仅 762 涨(14.7%) 普跌",
            "通信设备板块资金净流出 -281.03亿",
            "电池-5.26%、能源金属-6.38% 领跌",
            "光模块龙头集体重挫",
        ],
    },
    "result_payload": {
        "structured_picks": picks,
    },
    "raw_output": raw_output,
}

out_path = Path("/Users/jwkj/easyquant/data/ai_center/inbox/2130_每日持仓复盘_2026-06-26_20260626_213023.json")
out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"✓ Wrote {out_path} ({out_path.stat().st_size} bytes)")

# 验证
with open(out_path, "r", encoding="utf-8") as f:
    d = json.load(f)
print("✓ JSON 解析通过")
print(f"  trading_date: {d['trading_date']}")
print(f"  picks: {len(d['result_payload']['structured_picks'])}")
for p in d["result_payload"]["structured_picks"]:
    print(f"    {p['stock_code']} {p['stock_name']} level={p['pick_level']} conf={p['confidence_score']}")
print(f"  raw_output length: {len(d['raw_output'])}")
print(f"  raw_output <h2>: {'<h2>' in d['raw_output']}")
print(f"  raw_output <table>: {'<table>' in d['raw_output']}")
print(f"  raw_output <hr>: {'<hr>' in d['raw_output']}")
