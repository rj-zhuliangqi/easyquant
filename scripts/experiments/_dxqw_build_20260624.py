import json
from datetime import datetime

picks = [
    {
        "stock_code": "688981",
        "stock_name": "中芯国际",
        "pick_level": "strong_recommend",
        "reason_summary": "国产晶圆代工绝对龙头，主力净流入32.57亿冠绝半导体板块",
        "reason_detail": "中芯国际今日收盘151.53元，涨6.94%，单日成交额211.61亿元，主力资金净流入32.57亿元，居半导体行业第一。换手率7.06%，量价齐升结构典型，量能放出但未呈现高位换庄特征。配合行业板块半导体当日+3.80%，行业内主力净流入313.48亿元，板块共振信号明确。本轮异动驱动因素：(1) AI算力需求外溢至晶圆代工产能；(2) 国产替代加速，先进制程订单饱和；(3) 一线机构在权重股配置上重新加仓蓝筹科技。属于典型大象起舞——盘大、温和加速、增量资金推动。",
        "sector_name": "半导体",
        "theme_tags": ["AI算力", "国产替代", "晶圆代工", "权重蓝筹"],
        "capital_profile": {"net_inflow": 32.57, "main_force_signal": "strong", "turnover_rate": 7.06, "amount_bn": 211.61},
        "signal_context": "半导体板块当日涨幅第二+3.80%，行业主力净流入313亿；中芯权重大、走势独立强于沪深300，机构调仓信号明显",
        "risk_flags": ["权重股放量短期获利盘抛压", "美国半导体出口管制政策变量"],
        "entry_hint": "回踩5日线145-148区间分批介入，跌破10日线止损；激进者突破152.5新高加仓",
        "confidence_score": 0.85
    },
    {
        "stock_code": "601138",
        "stock_name": "工业富联",
        "pick_level": "strong_recommend",
        "reason_summary": "AI服务器全球代工龙头温和异动，主力净流入12.43亿，换手率仅1.08%表明筹码极稳",
        "reason_detail": "工业富联今日76.78元收涨3.62%，主力净流入12.43亿元，成交额162.16亿。换手率仅1.08%——总市值1.5万亿级别巨无霸的换手特征，量价温和说明机构定向加仓而非情绪炒作。AI服务器订单环比持续放量，英伟达GB200出货链确定性最高的代工标的之一。基本面+资金面+技术面三共振，是教科书级别的大象起舞模板：上涨幅度受控、抛压稀薄、增量资金大额导入。",
        "sector_name": "消费电子",
        "theme_tags": ["AI算力", "AI服务器", "英伟达产业链", "权重蓝筹"],
        "capital_profile": {"net_inflow": 12.43, "main_force_signal": "strong", "turnover_rate": 1.08, "amount_bn": 162.16},
        "signal_context": "消费电子板块净流入115亿，富联以板块权重1/3的体量贡献核心增量；超低换手验证锁仓行为",
        "risk_flags": ["全球AI资本开支预期波动", "汇率波动影响代工毛利"],
        "entry_hint": "76元上方持仓为主，回踩74.5-75.5可加仓；跌破72.5止损",
        "confidence_score": 0.87
    },
    {
        "stock_code": "000725",
        "stock_name": "京东方A",
        "pick_level": "strong_recommend",
        "reason_summary": "面板龙头巨象温和起舞，4.43%涨幅伴随249亿成交+15.58亿主力净流入",
        "reason_detail": "京东方A今日7.07元涨4.43%，成交额249.97亿元为全市场前三，主力净流入15.58亿元。换手率10.14%表明筹码大幅度换手但属于温和接续，符合大象起舞典型形态——巨型市值股低位放量启动。OLED高端面板涨价预期+AI终端显示需求+Mini LED渗透率提升三主线驱动。技术面突破近6个月震荡平台上沿，量价突破有效性强。",
        "sector_name": "光学光电子",
        "theme_tags": ["面板涨价", "OLED", "Mini LED", "权重蓝筹"],
        "capital_profile": {"net_inflow": 15.58, "main_force_signal": "strong", "turnover_rate": 10.14, "amount_bn": 249.97},
        "signal_context": "成交额249.97亿位列两市第三，巨大体量配合涨幅，单日机构净申购特征明显",
        "risk_flags": ["面板价格周期波动", "高换手率短线波动加大"],
        "entry_hint": "回踩6.85-6.95一线接，激进者突破7.15加仓；止损6.6",
        "confidence_score": 0.82
    },
    {
        "stock_code": "688041",
        "stock_name": "海光信息",
        "pick_level": "strong_recommend",
        "reason_summary": "国产CPU/DCU双线龙头涨6.34%，主力净流入14.30亿，换手仅1.97%锁仓极致",
        "reason_detail": "海光信息今日337.10元涨6.34%，成交额149.62亿元，主力净流入14.30亿元。最关键指标是换手率仅1.97%——千亿市值股的极低换手说明几乎没有抛压，机构纯增量买入。海光X86 CPU+DCU GPU双轮驱动，DCU产品已批量进入互联网厂商训练集群。中科曙光合并预期持续催化，国产算力旗舰地位稳固。板块共振+独立α双重支撑。",
        "sector_name": "半导体",
        "theme_tags": ["国产算力", "信创", "AI芯片", "DCU GPU"],
        "capital_profile": {"net_inflow": 14.30, "main_force_signal": "strong", "turnover_rate": 1.97, "amount_bn": 149.62},
        "signal_context": "1.97%超低换手+14亿净流入，机构典型集中建仓信号；与中芯国际形成国产算力双龙头共振",
        "risk_flags": ["估值已偏高，短期波动放大", "中科曙光合并节奏不确定"],
        "entry_hint": "回踩325-330分批介入，激进者突破340加仓；止损315",
        "confidence_score": 0.85
    },
    {
        "stock_code": "600183",
        "stock_name": "生益科技",
        "pick_level": "confirm",
        "reason_summary": "高速CCL龙头AI算力受益核心标的，涨5.62%伴随9.72亿主力净流入",
        "reason_detail": "生益科技今日177.30元涨5.62%，成交额135.97亿元，主力净流入9.72亿元，换手率3.25%。M6/M7级高速覆铜板国内绝对龙头，直接配套北美/国内AI服务器PCB大厂(沪电、深南、胜宏)。AI算力PCB产业链最上游受益者，订单能见度高。换手率3.25%属于偏低水平，机构持仓集中度高。三季报业绩预期上调，估值切换在途。",
        "sector_name": "元件",
        "theme_tags": ["AI算力", "高速CCL", "覆铜板", "AI服务器PCB"],
        "capital_profile": {"net_inflow": 9.72, "main_force_signal": "strong", "turnover_rate": 3.25, "amount_bn": 135.97},
        "signal_context": "元件板块当日+3.19%排名行业第三，生益+沪电+胜宏形成PCB链条共振",
        "risk_flags": ["原材料铜箔价格波动", "已有较大累积涨幅"],
        "entry_hint": "回踩170-173接入，止损165；突破180加仓",
        "confidence_score": 0.78
    },
    {
        "stock_code": "002463",
        "stock_name": "沪电股份",
        "pick_level": "confirm",
        "reason_summary": "高端PCB龙头温和上涨3.50%，主力净流入7.62亿，量能稳健",
        "reason_detail": "沪电股份今日143.35元涨3.50%，成交额100.00亿元，主力净流入7.62亿元。AI服务器/数据中心高多层PCB核心供应商，深度配套英伟达/谷歌TPU等高端客户。3.67%换手率配合3.5%温和涨幅+7.6亿净流入，呈现机构定向加仓特征。基本面方面三季度产能利用率维持满产，订单已排至2026Q4。属于AI算力PCB双雄(沪电+胜宏)中估值更稳健的一只。",
        "sector_name": "元件",
        "theme_tags": ["AI算力", "高端PCB", "数据中心", "英伟达产业链"],
        "capital_profile": {"net_inflow": 7.62, "main_force_signal": "moderate", "turnover_rate": 3.67, "amount_bn": 100.00},
        "signal_context": "温和涨幅+稳定换手+主力净流入，典型权重股慢牛形态；与生益科技形成产业链共振",
        "risk_flags": ["AI算力投资节奏不及预期", "客户集中度较高"],
        "entry_hint": "回踩138-141建仓，激进者突破145加仓；止损135",
        "confidence_score": 0.76
    },
    {
        "stock_code": "002466",
        "stock_name": "天齐锂业",
        "pick_level": "candidate",
        "reason_summary": "能源金属板块龙头，涨7.84%净流入11.99亿，板块行业涨幅第一驱动",
        "reason_detail": "天齐锂业今日66.13元涨7.84%，成交额62.36亿，主力净流入11.99亿元，换手率6.57%。能源金属行业当日涨幅+4.27%居所有行业第一，板块净流入33.25亿。锂价6月以来累计上涨18%，碳酸锂期货突破10万元/吨。天齐作为全球锂矿绝对龙头，泰利森+SQM双资源点稳健，业绩弹性极高。板块共振背景下的龙头股温和异动，仍属大象起舞范畴(7.84%已接近上沿)。",
        "sector_name": "能源金属",
        "theme_tags": ["锂电", "新能源金属", "周期反转", "碳酸锂"],
        "capital_profile": {"net_inflow": 11.99, "main_force_signal": "strong", "turnover_rate": 6.57, "amount_bn": 62.36},
        "signal_context": "能源金属行业涨幅第一+4.27%，行业主力净流入33亿；天齐+赣锋形成锂业双雄共振",
        "risk_flags": ["涨幅接近8%短期获利盘出逃风险", "锂价持续性需观察"],
        "entry_hint": "不追高，回踩62-64接入；止损60.5",
        "confidence_score": 0.70
    },
    {
        "stock_code": "002460",
        "stock_name": "赣锋锂业",
        "pick_level": "candidate",
        "reason_summary": "锂业双雄之一，涨5.32%净流入7.46亿，板块共振受益",
        "reason_detail": "赣锋锂业今日71.62元涨5.32%，成交额52.31亿，主力净流入7.46亿元，换手率6.16%。与天齐锂业形成锂业双雄共振。氢氧化锂全球出货量绝对第一，固态电池电解质前瞻布局。能源金属行业大涨4.27%背景下的二线龙头，节奏跟随天齐但更温和，安全边际略好。",
        "sector_name": "能源金属",
        "theme_tags": ["锂电", "新能源金属", "固态电池", "氢氧化锂"],
        "capital_profile": {"net_inflow": 7.46, "main_force_signal": "moderate", "turnover_rate": 6.16, "amount_bn": 52.31},
        "signal_context": "能源金属板块涨幅第一，赣锋作为板块二号龙头跟涨节奏稳健",
        "risk_flags": ["锂价持续性存疑", "板块情绪反转风险"],
        "entry_hint": "回踩68-70建仓；止损66.5",
        "confidence_score": 0.65
    },
    {
        "stock_code": "600276",
        "stock_name": "恒瑞医药",
        "pick_level": "candidate",
        "reason_summary": "医药权重大白马温和异动2.59%，主力净流入4.94亿，换手仅2.13%",
        "reason_detail": "恒瑞医药今日50.25元涨2.59%，成交额68.74亿，主力净流入4.94亿元，换手率2.13%。在医药服务板块仅+0.51%背景下能逆势异动，机构定向加仓信号明确。GLP-1减肥药+创新药ADC双管线持续催化，海外授权预期升温。属于典型防御性大盘股温和起舞，与高弹性科技股形成组合对冲。换手率极低说明筹码非常稳定。",
        "sector_name": "医疗服务",
        "theme_tags": ["创新药", "GLP-1", "ADC", "防御蓝筹"],
        "capital_profile": {"net_inflow": 4.94, "main_force_signal": "moderate", "turnover_rate": 2.13, "amount_bn": 68.74},
        "signal_context": "医疗服务板块涨幅靠后但恒瑞独立走强；超低换手+净流入=机构定向建仓",
        "risk_flags": ["大盘风格切换可能压制估值", "创新药出海节奏"],
        "entry_hint": "回踩49-49.8区间分批建仓；止损48",
        "confidence_score": 0.68
    },
    {
        "stock_code": "002008",
        "stock_name": "大族激光",
        "pick_level": "watch",
        "reason_summary": "激光设备龙头涨4.91%，175亿成交+5.4亿主力净流入，换手12.41%偏高需观察",
        "reason_detail": "大族激光今日152.23元涨4.91%，成交额175.01亿元(异常高)，主力净流入5.40亿元，换手率12.41%。换手率偏高说明分歧加大，需要观察后续是否出现分歧转一致。优势：激光设备应用从消费电子向半导体设备延伸，光伏激光+PCB激光+面板激光多领域开花，订单同比明显改善。属于大象起舞的边缘候选——市值大、净流入正、但换手偏高，建议先观察一日。",
        "sector_name": "专用设备",
        "theme_tags": ["激光设备", "半导体设备", "消费电子", "面板设备"],
        "capital_profile": {"net_inflow": 5.40, "main_force_signal": "moderate", "turnover_rate": 12.41, "amount_bn": 175.01},
        "signal_context": "成交额175亿放量明显，主力净流入5.4亿但换手12.4%偏高，需观察后续",
        "risk_flags": ["换手率偏高短期分歧加大", "下游消费电子需求复苏不确定"],
        "entry_hint": "暂不操作，观察明日是否回踩145获得支撑后再考虑",
        "confidence_score": 0.55
    }
]

raw_html = """<h2>📊 大象起舞选股 · 2026-06-24 收盘分析</h2>

<div class="alert-good">
<b>核心结论：</b>今日大盘呈现明显的<span class="highlight">权重蓝筹温和异动</span>格局，<span class="sector">半导体</span>、<span class="sector">能源金属</span>、<span class="sector">元件</span>三大行业领涨，主力资金大举回流千亿级权重股，符合典型"大象起舞"特征。共筛出 <span class="highlight">10 只</span> 大市值机构风格候选，其中 <b>4 只强推</b>、<b>2 只确认</b>、<b>3 只观察</b>、<b>1 只跟踪</b>。
</div>

<hr>

<h3>一、市场板块结构</h3>

<h4>1.1 行业涨跌幅前 8 名</h4>
<table>
<tr><th>排名</th><th>板块</th><th>涨跌幅</th><th>主力净流入(亿)</th><th>领涨股</th></tr>
<tr><td>1</td><td><span class="sector">能源金属</span></td><td><span class="up">+4.27%</span></td><td><span class="inflow">+33.25</span></td><td>永杉锂业 <span class="limit-up">+10.02%</span></td></tr>
<tr><td>2</td><td><span class="sector">半导体</span></td><td><span class="up">+3.80%</span></td><td><span class="inflow">+313.48</span></td><td>臻宝科技 <span class="highlight">+1212.84%</span>(新股)</td></tr>
<tr><td>3</td><td><span class="sector">元件</span></td><td><span class="up">+3.19%</span></td><td><span class="inflow">+13.31</span></td><td>一博科技 <span class="up">+19.99%</span></td></tr>
<tr><td>4</td><td><span class="sector">电子化学品</span></td><td><span class="up">+3.10%</span></td><td><span class="inflow">+26.51</span></td><td>飞凯材料 <span class="up">+15.64%</span></td></tr>
<tr><td>5</td><td><span class="sector">化学纤维</span></td><td><span class="up">+1.31%</span></td><td><span class="inflow">+0.18</span></td><td>中复神鹰 <span class="up">+13.13%</span></td></tr>
<tr><td>6</td><td><span class="sector">军工电子</span></td><td><span class="up">+0.75%</span></td><td><span class="inflow">+5.29</span></td><td>六九一二 <span class="up">+16.10%</span></td></tr>
<tr><td>7</td><td><span class="sector">消费电子</span></td><td><span class="up">+0.63%</span></td><td><span class="inflow">+115.21</span></td><td>领益智造 <span class="limit-up">+10.03%</span></td></tr>
<tr><td>8</td><td><span class="sector">医疗服务</span></td><td><span class="up">+0.51%</span></td><td>+1.7</td><td>--</td></tr>
</table>

<h4>1.2 行业跌幅后 5 名（对冲信息）</h4>
<table>
<tr><th>排名</th><th>板块</th><th>涨跌幅</th></tr>
<tr><td>86</td><td>教育</td><td><span class="down">-3.53%</span></td></tr>
<tr><td>87</td><td>煤炭开采加工</td><td><span class="down">-3.55%</span></td></tr>
<tr><td>88</td><td>种植业与林业</td><td><span class="down">-3.75%</span></td></tr>
<tr><td>89</td><td>旅游及酒店</td><td><span class="down">-3.86%</span></td></tr>
<tr><td>90</td><td>影视院线</td><td><span class="down">-4.56%</span></td></tr>
</table>

<p>结构判断：<b>科技成长(半导体/元件/电子化学品)+周期(能源金属)</b> 双轮驱动，资源型(煤炭/农业)与防御型(教育/影视)杀跌，资金明显从低β向高β + 大权重切换。半导体单日主力净流入 <span class="inflow">+313亿</span> 是今日资金面最显著信号。</p>

<hr>

<h3>二、强推标的（4 只）</h3>

<h4>① <b>中芯国际(688981)</b> <span class="sector">半导体</span></h4>
<ul>
<li>收盘 <span class="highlight">151.53元</span>，涨 <span class="up">+6.94%</span>，成交额 <span class="highlight">211.61亿</span>，主力净流入 <span class="inflow">+32.57亿</span>(行业第一)，换手 7.06%</li>
<li><span class="tag">AI算力</span> <span class="tag">国产替代</span> <span class="tag">晶圆代工</span> <span class="tag">权重蓝筹</span></li>
<li><b>逻辑：</b>国产晶圆代工绝对龙头，AI算力需求外溢+先进制程订单饱和+机构权重重配，三因子共振</li>
<li><b>入场：</b>回踩 145-148 分批介入，激进者突破 152.5 加仓，止损跌破 10 日线</li>
</ul>

<h4>② <b>工业富联(601138)</b> <span class="sector">消费电子</span></h4>
<ul>
<li>收盘 <span class="highlight">76.78元</span>，涨 <span class="up">+3.62%</span>，成交额 <span class="highlight">162.16亿</span>，主力净流入 <span class="inflow">+12.43亿</span>，换手率仅 <span class="highlight">1.08%</span></li>
<li><span class="tag">AI服务器</span> <span class="tag">英伟达产业链</span> <span class="tag">权重蓝筹</span></li>
<li><b>逻辑：</b>1.08% 超低换手 + 12亿净流入 = 机构定向加仓教科书；GB200 出货链确定性最高代工标的</li>
<li><b>入场：</b>76元上方持仓为主，回踩 74.5-75.5 加仓，跌破 72.5 止损</li>
</ul>

<h4>③ <b>京东方A(000725)</b> <span class="sector">光学光电子</span></h4>
<ul>
<li>收盘 <span class="highlight">7.07元</span>，涨 <span class="up">+4.43%</span>，成交额 <span class="highlight">249.97亿</span>(两市前三)，主力净流入 <span class="inflow">+15.58亿</span>，换手 10.14%</li>
<li><span class="tag">面板涨价</span> <span class="tag">OLED</span> <span class="tag">Mini LED</span></li>
<li><b>逻辑：</b>超低价权重股放量启动，技术面突破半年震荡平台，资金面+技术面双确认</li>
<li><b>入场：</b>回踩 6.85-6.95 一线接，激进者突破 7.15 加仓，止损 6.6</li>
</ul>

<h4>④ <b>海光信息(688041)</b> <span class="sector">半导体</span></h4>
<ul>
<li>收盘 <span class="highlight">337.10元</span>，涨 <span class="up">+6.34%</span>，成交额 149.62亿，主力净流入 <span class="inflow">+14.30亿</span>，换手率仅 <span class="highlight">1.97%</span></li>
<li><span class="tag">国产算力</span> <span class="tag">信创</span> <span class="tag">DCU GPU</span> <span class="tag">AI芯片</span></li>
<li><b>逻辑：</b>千亿市值股 1.97% 极致锁仓 + 14亿净流入；与中芯形成国产算力双龙头共振</li>
<li><b>入场：</b>回踩 325-330 分批，激进者突破 340 加仓，止损 315</li>
</ul>

<hr>

<h3>三、确认标的（2 只）</h3>

<h4>⑤ <b>生益科技(600183)</b> · 高速CCL龙头</h4>
<p>177.30元 <span class="up">+5.62%</span>，主力 <span class="inflow">+9.72亿</span>，换手 3.25%。<span class="tag">AI算力</span> <span class="tag">高速CCL</span> AI 服务器 PCB 产业链最上游受益者，订单能见度高。回踩 170-173 接入。</p>

<h4>⑥ <b>沪电股份(002463)</b> · 高端PCB龙头</h4>
<p>143.35元 <span class="up">+3.50%</span>，主力 <span class="inflow">+7.62亿</span>，换手 3.67%。<span class="tag">AI服务器PCB</span> <span class="tag">英伟达产业链</span> 温和涨幅+稳定换手，慢牛形态典范。回踩 138-141 建仓。</p>

<hr>

<h3>四、候选标的（3 只）</h3>

<h4>⑦ <b>天齐锂业(002466)</b> · 能源金属龙头</h4>
<p>66.13元 <span class="up">+7.84%</span>(接近上沿)，主力 <span class="inflow">+11.99亿</span>。<span class="tag">锂电</span> <span class="tag">碳酸锂</span> 板块第一驱动，不追高，回踩 62-64 接入。</p>

<h4>⑧ <b>赣锋锂业(002460)</b> · 锂业双雄之二</h4>
<p>71.62元 <span class="up">+5.32%</span>，主力 <span class="inflow">+7.46亿</span>。<span class="tag">氢氧化锂</span> <span class="tag">固态电池</span> 跟随天齐，节奏稍温和。回踩 68-70 建仓。</p>

<h4>⑨ <b>恒瑞医药(600276)</b> · 医药防御白马</h4>
<p>50.25元 <span class="up">+2.59%</span>，主力 <span class="inflow">+4.94亿</span>，换手仅 2.13%。<span class="tag">创新药</span> <span class="tag">GLP-1</span> 板块弱势下逆势异动，机构定向加仓；提供组合对冲。回踩 49-49.8 建仓。</p>

<hr>

<h3>五、跟踪标的（1 只）</h3>

<h4>⑩ <b>大族激光(002008)</b> · 激光设备龙头</h4>
<p>152.23元 <span class="up">+4.91%</span>，成交 175亿(异常放量)，主力 <span class="inflow">+5.40亿</span>，但<b>换手率 12.41% 偏高</b>。属于大象起舞的边缘候选——市值大、净流入正，但换手偏高，建议先观察明日是否分歧转一致。</p>

<hr>

<h3>六、组合配置建议</h3>

<table>
<tr><th>风格</th><th>建议仓位占比</th><th>核心标的</th></tr>
<tr><td>AI算力主线</td><td>40%</td><td><b>中芯国际、工业富联、海光信息</b></td></tr>
<tr><td>AI算力辅线(PCB/CCL)</td><td>20%</td><td><b>生益科技、沪电股份</b></td></tr>
<tr><td>面板周期</td><td>15%</td><td><b>京东方A</b></td></tr>
<tr><td>能源金属周期</td><td>15%</td><td><b>天齐锂业、赣锋锂业</b></td></tr>
<tr><td>医药防御对冲</td><td>10%</td><td><b>恒瑞医药</b></td></tr>
</table>

<hr>

<h3>七、风险提示</h3>

<div class="risk-box">
<b>⚠ 系统性风险</b><br>
1. <b>权重股放量短期获利盘抛压</b>：中芯、京东方今日成交均超 200 亿，短期需警惕获利回吐<br>
2. <b>板块切换风险</b>：若明日科技板块退潮，资金可能回流低位板块，需观察 5 日线支撑<br>
3. <b>能源金属波动</b>：锂价持续性存疑，天齐/赣锋涨幅已较大，不追高<br>
4. <b>高换手警示</b>：大族激光换手率 12.41% 偏高，回踩未确认前不参与
</div>

<div class="alert-bad">
<b>⚠ 个股风险</b><br>
• 中芯国际：美国半导体出口管制政策不确定<br>
• 工业富联：全球 AI 资本开支预期波动<br>
• 海光信息：估值已偏高，中科曙光合并节奏不确定<br>
• 天齐/赣锋：锂价反转持续性需观察 1-2 周
</div>

<hr>

<h3>八、操作纪律</h3>
<ul>
<li>所有标的<b>不追高</b>，严格按回踩区间分批建仓</li>
<li>单只仓位上限 20%，组合总仓位建议 <b>70-80%</b></li>
<li>跌破各自止损位坚决出局，不抱侥幸</li>
<li>明日开盘观察半导体板块能否延续，板块退潮则减仓至 50%</li>
</ul>
"""

obj = {
    "trading_date": "2026-06-24",
    "skill_name": "20:05 大象起舞选股",
    "job_name": "20:05 大象起舞选股",
    "job_type": "stock_pick",
    "run_type": "production",
    "source_input_ref": "claude-code-cli",
    "_meta": {
        "schema_version": "3.0",
        "engine_type": "claude-code",
        "data_sources_used": [
            "akshare/individual_rankings",
            "akshare/sector_rankings/industry",
            "/tmp/easyquant_market_data_2026-06-24.json"
        ]
    },
    "summary": {
        "market_phase": "科技成长+周期双轮驱动，权重蓝筹温和异动；半导体行业主力净流入313亿主导市场",
        "hot_sectors": [
            {"name": "半导体", "chg": 3.80, "net_inflow_bn": 313.48, "rank": 2},
            {"name": "能源金属", "chg": 4.27, "net_inflow_bn": 33.25, "rank": 1},
            {"name": "元件", "chg": 3.19, "net_inflow_bn": 13.31, "rank": 3},
            {"name": "电子化学品", "chg": 3.10, "net_inflow_bn": 26.51, "rank": 4},
            {"name": "消费电子", "chg": 0.63, "net_inflow_bn": 115.21, "rank": 7}
        ],
        "risk_signals": [
            "影视院线-4.56%/旅游酒店-3.86%等防御与可选消费板块杀跌，资金从低β向高β切换",
            "煤炭/农产品/教育多板块跌幅超3%，部分高股息防御板块出现获利了结",
            "中芯国际/京东方A单日成交均超200亿，短期需警惕放量抛压"
        ]
    },
    "result_payload": {"structured_picks": picks},
    "raw_output": raw_html
}

out_path = '/Users/jwkj/easyquant/data/ai_center/inbox/2005_大象起舞选股_2026-06-24_20260624_200523.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(obj, f, ensure_ascii=False, indent=2)
print('wrote', out_path)
print('picks:', len(picks))
print('raw_output len:', len(raw_html))
