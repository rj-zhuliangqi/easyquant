#!/usr/bin/env python3
"""Generate morning market review JSON report for 2026-06-23."""
import json, os

out = '/Users/jwkj/easyquant/data/ai_center/inbox/1200_早盘复盘_2026-06-23_20260623_120022.json'
os.makedirs(os.path.dirname(out), exist_ok=True)

H = []
def a(s): H.append(s)

# === Section 1: Market Index Overview ===
a('<h2>一、大盘指数表现（截至午盘）</h2>')
a('<table>')
a('<tr><th>指数</th><th>最新价</th><th>涨跌幅</th><th>前收盘</th><th>日内高低</th></tr>')
a('<tr><td><b>上证指数</b></td><td><span class="highlight">4147.55</span></td><td><span class="down">-0.37%</span></td><td>4163.10</td><td>4138.42 / 4175.35</td></tr>')
a('<tr><td><b>深证成指</b></td><td><span class="highlight">16072.11</span></td><td><span class="down">-1.83%</span></td><td>16372.50</td><td>16014.06 / 16355.95</td></tr>')
a('<tr><td><b>创业板指</b></td><td><span class="highlight">4260.49</span></td><td><span class="down">-2.27%</span></td><td>4359.39</td><td>4241.54 / 4350.06</td></tr>')
a('<tr><td><b>科创50</b></td><td><span class="highlight">1940.65</span></td><td><span class="down">-0.42%</span></td><td>1948.93</td><td>1896.79 / 1982.91</td></tr>')
a('<tr><td><b>上证50</b></td><td><span class="highlight">2968.50</span></td><td><span class="down">-1.47%</span></td><td>3012.65</td><td>2963.54 / 3019.34</td></tr>')
a('<tr><td><b>沪深300</b></td><td><span class="highlight">4982.18</span></td><td><span class="down">-1.53%</span></td><td>5059.66</td><td>4969.52 / 5064.27</td></tr>')
a('</table>')
a('<p>市场涨跌家数：上涨 <span class="up"><b>3125</b></span> 家 | 下跌 <span class="down"><b>1971</b></span> 家 | 平盘 <b>96</b> 家</p>')
a('<p>涨停板 <span class="limit-up"><b>110</b></span> 只 | 跌停板 <span class="limit-down"><b>20</b></span> 只</p>')
a('<div class="alert-good">')
a('<b>核心判断：</b>权重指数走弱但个股活跃，涨跌家数比 <b>3125:1971</b>（约1.6:1），中小盘个股结构性行情延续。创业板领跌主要受新能源+金属板块拖累。市场处于<b>"指数弱、个股活"</b>的轮动格局，主力资金从有色/新能源撤出，转向<b>医药全产业链+半导体</b>。')
a('</div>')
a('<hr>')

# === Section 2: Sector Rankings ===
a('<h2>二、板块涨跌排行（涨幅前10）</h2>')
a('<table>')
a('<tr><th>排名</th><th>板块</th><th>涨跌幅</th><th>资金净额(亿)</th><th>领涨股</th></tr>')

top_up = [
    (1, "化学制药", 4.14, 11.18, "新赣江", 25.71),
    (2, "生物制品", 3.50, 2.61, "赛升药业", 18.07),
    (3, "医疗服务", 2.85, 4.79, "睿智医药", 19.95),
    (4, "中药", 2.83, 3.81, "粤万年青", 10.43),
    (5, "医药商业", 2.67, 0.49, "合富中国", 9.99),
    (6, "美容护理", 2.44, -0.24, "拉芳家化", 10.04),
    (7, "纺织制造", 2.29, 0.96, "兴业科技", 10.01),
    (8, "医疗器械", 2.16, -0.38, "爱迪特", 10.83),
    (13, "证券", 1.64, 6.93, "长江证券", 10.00),
    (15, "银行", 1.62, 27.22, "中信银行", 3.28),
]
for rank, name, pct, net, leader, leader_pct in top_up:
    nf = f'<span class="inflow">+{net:.2f}亿</span>' if net >= 0 else f'<span class="outflow">{net:.2f}亿</span>'
    a(f'<tr><td>{rank}</td><td><span class="sector">{name}</span></td><td><span class="up">+{pct:.2f}%</span></td><td>{nf}</td><td><span class="stock">{leader}</span> <span class="up">+{leader_pct:.2f}%</span></td></tr>')
a('</table>')

a('<h2>板块涨跌排行（跌幅前7）</h2>')
a('<table>')
a('<tr><th>排名</th><th>板块</th><th>涨跌幅</th><th>资金净流出(亿)</th><th>领涨股</th></tr>')
td_ = [
    (90, "贵金属", -6.82, 52.99, "株冶集团", 6.12),
    (89, "小金属", -4.02, 70.78, "长裕集团", 9.99),
    (88, "工业金属", -3.98, 93.31, "锌业股份", 10.05),
    (87, "能源金属", -3.98, 28.93, "*ST威领", 2.73),
    (86, "元件", -3.71, 87.45, "贤丰控股", 10.00),
    (85, "光伏设备", -1.78, 36.33, "琏升科技", 5.94),
    (84, "电子化学品", -1.63, 3.57, "华特气体", 13.50),
]
for rank, name, pct, out_flow, leader, leader_pct in td_:
    a(f'<tr><td>{rank}</td><td><span class="sector">{name}</span></td><td><span class="down">{pct:.2f}%</span></td><td><span class="outflow">-{out_flow:.2f}亿</span></td><td><span class="stock">{leader}</span> <span class="up">+{leader_pct:.2f}%</span></td></tr>')
a('</table>')

a('<div class="alert-good">')
a('<b>板块轮动总结：</b>')
a('<ul>')
a('<li><span class="tag">医药</span> 全产业链爆发：化学制药(+4.14%)、生物制品(+3.50%)、医疗服务(+2.85%)、中药(+2.83%)、医药商业(+2.67%) -- <b>5个子板块包揽涨幅前五</b>，资金净流入合计 <span class="inflow">+22.88亿</span></li>')
a('<li><span class="tag">金属崩盘</span> 贵金属 <span class="down">-6.82%</span>（净流出 <span class="outflow">-52.99亿</span>），小金属 <span class="down">-4.02%</span>（净流出 <span class="outflow">-70.78亿</span>），工业金属 <span class="down">-3.98%</span>（净流出 <span class="outflow">-93.31亿</span>），能源金属 <span class="down">-3.98%</span>（净流出 <span class="outflow">-28.93亿</span>）-- 四板块合计净流出 <span class="outflow">-246亿</span></li>')
a('<li><span class="tag">半导体</span> 逆势吸金 <span class="inflow">+45.19亿</span>，涨幅 <span class="up">+1.23%</span>，为全市场资金净流入最大板块</li>')
a('<li><span class="tag">证券+银行</span> 金融护盘，证券 <span class="up">+1.64%</span>（<span class="inflow">+6.93亿</span>），银行 <span class="up">+1.62%</span>（<span class="inflow">+27.22亿</span>）</li>')
a('</ul>')
a('</div>')
a('<hr>')

# === Section 3: Top 10 Stocks ===
a('<h2>三、涨幅榜前10个股</h2>')
a('<table>')
a('<tr><th>排名</th><th>股票</th><th>涨幅</th><th>现价</th><th>所属板块</th><th>资金净额(亿)</th><th>成交额(亿)</th></tr>')
g_ = [
    (1, "688179", "阿拉丁", 20.02, 27.34, "化学制品", 0.67, 8.86),
    (2, "300085", "银之杰", 20.00, 38.82, "软件开发", -11.25, 38.11),
    (3, "300835", "龙磁科技", 20.00, 234.31, "金属新材料", -4.73, 24.80),
    (4, "300077", "国民技术", 20.00, 27.72, "半导体", 2.12, 26.59),
    (5, "300721", "怡达股份", 19.99, 34.15, "化学制品", -1.37, 10.44),
    (6, "301211", "亨迪药业", 19.98, 11.29, "化学制药", -0.31, 1.26),
    (7, "300149", "睿智医药", 19.95, 9.14, "医疗服务", -0.47, 2.89),
    (8, "300167", "ST迪威迅", 19.91, 5.24, "IT服务", -0.15, 0.99),
    (9, "300485", "赛升药业", 18.07, 9.67, "生物制品", 0.34, 1.87),
    (10, "301687", "新广益", 17.02, 91.25, "塑料制品", 1.30, 7.67),
]
for i, (rank, code, name, pct, price, sector, net, amt) in enumerate(g_):
    nf = f'<span class="inflow">+{net:.2f}亿</span>' if net >= 0 else f'<span class="outflow">{net:.2f}亿</span>'
    pc = "limit-up" if pct >= 19.9 else "up"
    a(f'<tr><td>{i+1}</td><td><span class="stock"><b>{name}</b></span> ({code})</td><td><span class="{pc}">+{pct:.2f}%</span></td><td>{price}</td><td><span class="sector">{sector}</span></td><td>{nf}</td><td><span class="highlight">{amt:.2f}亿</span></td></tr>')
a('</table>')

a('<p><b>涨停特征分析：</b></p>')
a('<ul>')
a('<li>20cm涨停主要集中在 <span class="tag">医药</span>、<span class="tag">半导体</span>、<span class="tag">新材料</span> 三个方向</li>')
a('<li><span class="stock">阿拉丁</span>(688179) 化学制品龙头，20cm封板，资金净流入 <span class="inflow">+0.67亿</span>，换手率仅9.38%说明筹码锁定好</li>')
a('<li><span class="stock">国民技术</span>(300077) 半导体方向唯一20cm且资金净流入为正（<span class="inflow">+2.12亿</span>），成交额 <span class="highlight">26.59亿</span></li>')
a('<li><span class="stock">银之杰</span>(300085) 虽然20cm涨停但资金净流出 <span class="outflow">-11.25亿</span>，换手15.44%，多空分歧极大</li>')
a('</ul>')
a('<hr>')

# === Section 4: Deep Analysis ===
a('<h2>四、主线题材深度分析</h2>')

a('<h3>医药全产业链（今日最强主线）</h3>')
a('<div class="alert-good">')
a('<p><b>板块涨幅：</b>化学制药 <span class="up">+4.14%</span> | 生物制品 <span class="up">+3.50%</span> | 医疗服务 <span class="up">+2.85%</span> | 中药 <span class="up">+2.83%</span> | 医药商业 <span class="up">+2.67%</span></p>')
a('<p><b>资金流向：</b>5个子板块合计净流入 <span class="inflow">+22.88亿</span></p>')
a('<p><b>领涨品种：</b></p>')
a('<ul>')
a('<li><span class="stock">亨迪药业</span>(301211) <span class="limit-up">+19.98%</span> 涨停，化学制药+解热镇痛原料药，筹码集中换手仅2.79%</li>')
a('<li><span class="stock">赛升药业</span>(300485) <span class="up">+18.07%</span>，生物制品领涨股，资金净流入 <span class="inflow">+0.34亿</span></li>')
a('<li><span class="stock">睿智医药</span>(300149) <span class="up">+19.95%</span>，医疗服务+CRO概念</li>')
a('<li><span class="stock">诺唯赞</span>(688105) <span class="up">+15.81%</span>，生物试剂龙头</li>')
a('<li><span class="stock">新赣江</span> <span class="up">+25.71%</span>，化学制药板块领涨股（北交所）</li>')
a('</ul>')
a('<p><b>驱动逻辑：</b>集采政策边际放松预期 + 创新药出海加速 + 半年报业绩预增预期 + 医药板块估值处于历史底部 + 资金从周期股切换至防御性医药板块</p>')
a('</div>')

a('<h3>半导体（资金逆势流入第一）</h3>')
a('<div class="alert-good">')
a('<p><b>板块涨幅：</b><span class="up">+1.23%</span>，净流入 <span class="inflow">+45.19亿</span>（全市场第一）</p>')
a('<p><b>领涨品种：</b></p>')
a('<ul>')
a('<li><span class="stock"><b>国民技术</b></span>(300077) <span class="limit-up">涨停+20.00%</span>，资金净流入 <span class="inflow">+2.12亿</span>，成交额 <span class="highlight">26.59亿</span>，换手率18.05%</li>')
a('<li><span class="stock"><b>台基股份</b></span>(300046) <span class="up">+15.07%</span>，资金净流入 <span class="inflow">+2.94亿</span>，成交额 <span class="highlight">11.72亿</span></li>')
a('<li><span class="stock">华特气体</span>(688268) <span class="up">+13.50%</span>，电子特气龙头，成交额 <span class="highlight">30.12亿</span></li>')
a('</ul>')
a('<p><b>驱动逻辑：</b>国产替代加速 + AI算力芯片需求爆发 + 三期大基金预期 + 华特气体电子特气订单催化 + 半导体设备/材料国产化率持续提升</p>')
a('</div>')

a('<h3>证券+银行（护盘力量）</h3>')
a('<ul>')
a('<li><span class="stock">长江证券</span>(000783) <span class="limit-up">+10.00%</span> 涨停，券商领涨股</li>')
a('<li>银行板块净流入 <span class="inflow">+27.22亿</span>，<span class="stock">中信银行</span> 领涨 <span class="up">+3.28%</span></li>')
a('<li>金融护盘逻辑明显，资金从周期切换至金融防御，大资金避险+托底双重需求</li>')
a('</ul>')

a('<h3>金属崩盘（资金踩踏出逃）</h3>')
a('<div class="alert-bad">')
a('<p><b>跌幅排行：</b>贵金属 <span class="down">-6.82%</span> | 小金属 <span class="down">-4.02%</span> | 工业金属 <span class="down">-3.98%</span> | 能源金属 <span class="down">-3.98%</span></p>')
a('<p><b>资金出逃：</b>四板块合计净流出 <span class="outflow">-246亿</span></p>')
a('<p><b>重灾区个股：</b><span class="stock">江西铜业</span> <span class="down">-9.86%</span>、<span class="stock">铜陵有色</span> <span class="down">-9.84%</span>、<span class="stock">兴业银锡</span> <span class="down">-9.53%</span>、<span class="stock">湖南黄金</span> <span class="down">-9.37%</span></p>')
a('<p><b>崩盘逻辑：</b>美联储鹰派预期升温打压金价 + 全球经济放缓担忧压制工业金属需求 + 前期炒作资金获利了结集中出逃 + 期货市场联动下跌</p>')
a('</div>')
a('<hr>')

# === Section 5: Risk Signals ===
a('<h2>五、风险信号</h2>')
a('<div class="risk-box">')
a('<p><b>主要风险：</b></p>')
a('<ol>')
a('<li><b>金属板块踩踏式出逃：</b>贵金属 <span class="down">-6.82%</span>，四板块合计净流出 <span class="outflow">-246亿</span>，短期严格规避所有有色金属个股</li>')
a('<li><b>创业板领跌：</b>创业板指 <span class="down">-2.27%</span> 跌幅最大，成长股承压，需警惕午后创业板进一步下探至4200点附近</li>')
a('<li><b>元件板块大幅杀跌：</b>元件 <span class="down">-3.71%</span>，净流出 <span class="outflow">-87.45亿</span>，PCB/被动元件/连接器方向需回避</li>')
a('<li><b>光伏+电池持续走弱：</b>光伏设备 <span class="down">-1.78%</span>（净流出 <span class="outflow">-36.33亿</span>），电池 <span class="down">-1.27%</span>（净流出 <span class="outflow">-62.07亿</span>），产能过剩担忧持续发酵</li>')
a('<li><b>个别涨停股主力出逃：</b><span class="stock">银之杰</span>虽20cm涨停但净流出 <span class="outflow">-11.25亿</span>，<span class="stock">龙磁科技</span>净流出 <span class="outflow">-4.73亿</span>，警惕午后炸板风险</li>')
a('<li><b>深市缩量明显：</b>深成指成交额较昨日缩量，若午后不能补量，指数可能进一步走弱</li>')
a('</ol>')
a('</div>')
a('<hr>')

# === Section 6: Stock Picks ===
a('<h2>六、个股推荐</h2>')
a('<h3>强烈推荐（2只）</h3>')

a('<h4><span class="stock"><b>国民技术 (300077)</b></span> - 半导体安全芯片龙头</h4>')
a('<ul>')
a('<li>板块：<span class="sector">半导体</span>（资金净流入全市场第一 <span class="inflow">+45.19亿</span>）</li>')
a('<li>涨幅：<span class="limit-up">+20.00%</span> 涨停 | 成交额：<span class="highlight">26.59亿</span></li>')
a('<li>资金净流入：<span class="inflow">+2.12亿</span>（20cm涨停股中极少数正向流入）</li>')
a('<li>换手率：18.05%（涨停股中换手适中，筹码交换充分但没有过度分歧）</li>')
a('<li>主题标签：<span class="tag">半导体</span> <span class="tag">国产替代</span> <span class="tag">AI芯片</span> <span class="tag">安全芯片</span> <span class="tag">信创</span></li>')
a('<li><b>推荐逻辑：</b>半导体板块今日资金净流入全市场第一（+45.19亿），国民技术是板块内20cm涨停的唯一资金净流入正向标的。公司是国内安全芯片龙头，受益于信创国产替代+AI端侧安全需求。早盘封板坚决，午后有望延续强势。与其他20cm涨停股（银之杰净流出-11.25亿、龙磁科技净流出-4.73亿）形成鲜明对比。</li>')
a('<li>入场建议：若午后开板回踩26.5-27元可低吸，止损25.5元。若不打开直接封板到尾盘，可次日竞价关注</li>')
a('</ul>')

a('<h4><span class="stock"><b>赛升药业 (300485)</b></span> - 生物制品领涨股</h4>')
a('<ul>')
a('<li>板块：<span class="sector">生物制品</span>（行业涨幅第2 <span class="up">+3.50%</span>）</li>')
a('<li>涨幅：<span class="up">+18.07%</span> | 成交额：<span class="highlight">1.87亿</span></li>')
a('<li>资金净流入：<span class="inflow">+0.34亿</span></li>')
a('<li>换手率：7.52%（筹码锁定好，未出现大幅抛压）</li>')
a('<li>主题标签：<span class="tag">医药</span> <span class="tag">生物制品</span> <span class="tag">创新药</span> <span class="tag">免疫调节</span></li>')
a('<li><b>推荐逻辑：</b>医药板块今日包揽行业涨幅前五，赛升药业是生物制品板块领涨股。换手率仅7.52%表明筹码稳定，未被大幅炒作，且资金净流入为正。公司主营免疫调节类药物，受益于创新药政策边际改善。流通市值偏小弹性好，在医药全产业链爆发的背景下具备继续走强条件。</li>')
a('<li>入场建议：9.2-9.5元区间可低吸介入，止损8.8元。关注午后是否温和放量，放量上涨则更健康</li>')
a('</ul>')

a('<h3>确认关注（1只）</h3>')
a('<h4><span class="stock"><b>亨迪药业 (301211)</b></span> - 化学制药极低换手板</h4>')
a('<ul>')
a('<li>板块：<span class="sector">化学制药</span>（行业涨幅第1 <span class="up">+4.14%</span>）</li>')
a('<li>涨幅：<span class="limit-up">+19.98%</span> 涨停 | 成交额：<span class="highlight">1.26亿</span></li>')
a('<li>换手率：仅2.79%（极低换手，筹码高度集中）</li>')
a('<li>主题标签：<span class="tag">化学制药</span> <span class="tag">原料药</span> <span class="tag">解热镇痛</span> <span class="tag">医药</span></li>')
a('<li><b>推荐逻辑：</b>化学制药板块涨幅排名全市场第一（+4.14%），亨迪药业封板坚决且换手率极低（2.79%），说明筹码高度集中、市场一致性强，几乎没有抛压。公司主营解热镇痛原料药，细分赛道龙头。缺点是成交额偏小（1.26亿）和资金净流出（-0.31亿），流动性一般。</li>')
a('<li>入场建议：涨停板打开回封时可打板介入，或次日竞价高开不超过5%时参与。不建议追高打板（流动性偏弱，滑点大）</li>')
a('</ul>')

a('<h3>候选观察（2只）</h3>')
a('<h4><span class="stock"><b>台基股份 (300046)</b></span> - 半导体资金流入最高标的</h4>')
a('<ul>')
a('<li>板块：<span class="sector">半导体</span>（资金净流入全市场第一 <span class="inflow">+45.19亿</span>）</li>')
a('<li>涨幅：<span class="up">+15.07%</span> | 成交额：<span class="highlight">11.72亿</span></li>')
a('<li>资金净流入：<span class="inflow">+2.94亿</span>（板块内最高，超过涨停的国民技术）</li>')
a('<li>换手率：14.18%</li>')
a('<li>主题标签：<span class="tag">半导体</span> <span class="tag">功率器件</span> <span class="tag">IGBT</span> <span class="tag">新能源</span></li>')
a('<li><b>推荐逻辑：</b>半导体板块资金净流入全市场第一，台基股份资金净流入+2.94亿为板块内最高（超过涨停的国民技术），说明机构资金高度认可。公司主营功率半导体器件（晶闸管、IGBT模块），受益于新能源车+充电桩+储能需求拉动。虽未涨停但资金认可度极高，量价配合良好，午后有望继续走强。</li>')
a('<li>入场建议：34-35元区间低吸，止损32元。适合有耐心的投资者，不追高只低吸</li>')
a('</ul>')

a('<h4><span class="stock"><b>长江证券 (000783)</b></span> - 券商护盘先锋</h4>')
a('<ul>')
a('<li>板块：<span class="sector">证券</span>（涨幅 <span class="up">+1.64%</span>，净流入 <span class="inflow">+6.93亿</span>）</li>')
a('<li>涨幅：<span class="limit-up">+10.00%</span> 涨停</li>')
a('<li>主题标签：<span class="tag">券商</span> <span class="tag">金融</span> <span class="tag">护盘</span> <span class="tag">大盘蓝筹</span></li>')
a('<li><b>推荐逻辑：</b>证券板块整体资金净流入+6.93亿，长江证券领涨涨停。在市场弱势环境下（深成指-1.83%、创业板-2.27%），券商护盘逻辑明确。作为10cm主板涨停标的，封板相对20cm更稳固，适合稳健型投资者。但券商板块行情持续性存疑，建议作为防御配置而非主动进攻。</li>')
a('<li>入场建议：观察午后封板情况。若板块内出现第二只涨停股形成联动效应，可轻仓参与</li>')
a('</ul>')
a('<hr>')

# === Section 7: Afternoon Outlook ===
a('<h2>七、午后展望与策略</h2>')
a('<div class="alert-good">')
a('<p><b>积极因素：</b></p>')
a('<ul>')
a('<li>个股涨多跌少（3125:1971），赚钱效应仍在，结构性行情延续</li>')
a('<li>涨停家数110只，市场活跃度较高，短线资金充裕</li>')
a('<li>医药主线资金共识度高，5个子板块集体走强且有持续净流入</li>')
a('<li>半导体资金逆势大幅流入（+45.19亿），显示科技方向有主力积极布局</li>')
a('<li>上证指数仅微跌-0.37%，金融权重股有效支撑指数</li>')
a('</ul>')
a('</div>')

a('<div class="risk-box">')
a('<p><b>隐忧因素：</b></p>')
a('<ul>')
a('<li>深成指 <span class="down">-1.83%</span>、创业板 <span class="down">-2.27%</span> 跌幅较大，若午后不能企稳可能引发恐慌盘</li>')
a('<li>贵金属/工业金属跌幅过大（-4%~-7%），资金踩踏出逃迹象明显，风险偏好急剧下降</li>')
a('<li>部分20cm涨停股主力净流出（银之杰-11.25亿、龙磁科技-4.73亿），警惕午后炸板潮</li>')
a('<li>两市成交额分化，深市缩量明显，需关注午后量能变化</li>')
a('<li>今日涨停股中很多是ST或业绩不佳标的，质量参差不齐</li>')
a('</ul>')
a('</div>')

a('<p><b>午后策略：</b></p>')
a('<ol>')
a('<li><b>主线聚焦：</b>继续围绕 <span class="tag">医药</span>（化学制药/生物制品）和 <span class="tag">半导体</span>（安全芯片/功率器件）两大主线操作</li>')
a('<li><b>严格规避：</b>有色/贵金属/工业金属/能源金属/元件/光伏/电池 -- 这些板块资金持续出逃，短期无反弹基础</li>')
a('<li><b>关注券商：</b>若午后指数进一步走弱，券商可能加速护盘，长江证券可关注联动效应</li>')
a('<li><b>警惕炸板：</b>早盘主力净流出的涨停股不追，只做资金+涨幅共振的品种</li>')
a('<li><b>仓位建议：</b>半仓操作，不宜满仓。等待尾盘14:30后确认方向再加仓或减仓</li>')
a('<li><b>底线思维：</b>若创业板跌破4200点整数关口，建议减仓至三成以下</li>')
a('</ol>')

html = '\n'.join(H)

# === Structured Picks ===
picks = [
    {
        "stock_code": "300077",
        "stock_name": "国民技术",
        "pick_level": "strong_recommend",
        "reason_summary": "半导体板块20cm涨停龙头，板块资金净流入全市场第一(+45.19亿)，个股资金净流入+2.12亿为20cm涨停股中少数正向标的。安全芯片+国产替代双主线共振。",
        "reason_detail": "半导体板块今日资金净流入+45.19亿居全市场第一，国民技术是板块内20cm涨停的唯一资金净流入正向标的（+2.12亿）。成交额26.59亿，换手18.05%，涨停换手适中说明筹码交换充分但没有过度分歧。与其他20cm涨停股形成鲜明对比：银之杰净流出-11.25亿、龙磁科技净流出-4.73亿。公司是国内安全芯片龙头，受益于信创国产替代+AI端侧安全需求。早盘封板坚决，午后有望延续强势。",
        "sector_name": "半导体",
        "theme_tags": ["半导体", "国产替代", "AI芯片", "安全芯片", "信创"],
        "capital_profile": {"net_inflow": 2.12, "main_force_signal": "strong"},
        "signal_context": "半导体板块资金净流入全市场第一(+45.19亿)，板块涨幅+1.23%逆势走强。国民技术涨停封板坚决且是板块内唯一大资金净流入的20cm涨停股，主力资金认同度高。",
        "risk_flags": ["创业板领跌-2.27%或拖累个股情绪", "换手率18%偏高，需警惕午后分歧加大", "半导体板块内部分化大，元件子板块跌-3.71%", "若大盘加速下跌可能被动开板"],
        "entry_hint": "若午后开板回踩26.5-27元可低吸，止损25.5元。若不打开涨停则尾盘集合竞价关注封单量，封单大于5000万可次日竞价参与",
        "confidence_score": 0.82
    },
    {
        "stock_code": "300485",
        "stock_name": "赛升药业",
        "pick_level": "strong_recommend",
        "reason_summary": "生物制品板块领涨股(+18.07%)，医药全产业链爆发最强风口，换手低(7.52%)筹码锁定好，资金净流入为正(+0.34亿)，市值小弹性大",
        "reason_detail": "医药板块今日包揽行业涨幅前五（化学制药+4.14%、生物制品+3.50%、医疗服务+2.85%、中药+2.83%、医药商业+2.67%），是今日最强主线，资金共识度极高。赛升药业作为生物制品板块领涨股涨幅+18.07%，换手率仅7.52%表明筹码稳定未被大幅炒作，资金净流入+0.34亿为正。公司主营免疫调节类药物，受益于创新药政策边际改善。流通市值偏小弹性好，在医药主线持续发酵的背景下具备继续走强的条件。",
        "sector_name": "生物制品",
        "theme_tags": ["医药", "生物制品", "创新药", "免疫调节"],
        "capital_profile": {"net_inflow": 0.34, "main_force_signal": "moderate"},
        "signal_context": "生物制品板块涨幅+3.50%排名全行业第2，资金净流入+2.61亿。赛升药业作为板块领涨股涨幅+18.07%，换手率低(7.52%)筹码锁定好，医药主线资金共识度高。5个医药子板块集体走强且均有净流入，主线性明确",
        "risk_flags": ["医药板块连续走强后或有短期获利回吐", "个股流通市值较小，流动性一般(成交额1.87亿)", "若大盘加速下跌可能拖累医药板块情绪"],
        "entry_hint": "9.2-9.5元区间可低吸介入，止损8.8元。关注午后是否放量，若温和放量上涨则更健康。不建议追高，只低吸",
        "confidence_score": 0.78
    },
    {
        "stock_code": "301211",
        "stock_name": "亨迪药业",
        "pick_level": "confirm",
        "reason_summary": "化学制药板块涨停股(+19.98%)，板块涨幅全市场第一(+4.14%)，换手率极低(2.79%)筹码高度集中，市场一致性强",
        "reason_detail": "化学制药板块涨幅+4.14%排名全市场第一，资金净流入+11.18亿。亨迪药业封板+19.98%且换手率仅2.79%，说明筹码高度集中、市场一致性强，几乎没有抛压。公司主营解热镇痛原料药，细分赛道龙头。缺点是成交额偏小(1.26亿)和资金净流出(-0.31亿)，流动性一般。",
        "sector_name": "化学制药",
        "theme_tags": ["化学制药", "原料药", "解热镇痛", "医药"],
        "capital_profile": {"net_inflow": -0.31, "main_force_signal": "moderate"},
        "signal_context": "化学制药板块涨幅+4.14%全市场第一，资金净流入+11.18亿。医药全产业链爆发是今日最强主线，亨迪药业在最强板块中涨停且换手率极低(2.79%)，筹码锁定效果极佳。",
        "risk_flags": ["成交额仅1.26亿，流动性偏弱", "资金净流入为负(-0.31亿)，主力态度需进一步确认", "换手率过低，次日若放量开板可能回撤较大", "个股属于小盘股，不适合大资金参与"],
        "entry_hint": "涨停板打开回封时可打板介入，或次日竞价高开不超过5%时参与。小仓位试探为宜",
        "confidence_score": 0.72
    },
    {
        "stock_code": "300046",
        "stock_name": "台基股份",
        "pick_level": "candidate",
        "reason_summary": "半导体板块资金净流入最高标的(+2.94亿)，超过涨停的国民技术。涨幅+15.07%，IGBT功率器件龙头，量价配合良好",
        "reason_detail": "半导体板块资金净流入全市场第一(+45.19亿)，台基股份资金净流入+2.94亿为板块内最高（甚至超过涨停的国民技术的+2.12亿），说明机构资金高度认可。涨幅+15.07%，成交额11.72亿，换手14.18%。公司主营功率半导体器件（晶闸管、IGBT模块），受益于新能源车+充电桩+储能需求拉动。",
        "sector_name": "半导体",
        "theme_tags": ["半导体", "功率器件", "IGBT", "新能源"],
        "capital_profile": {"net_inflow": 2.94, "main_force_signal": "strong"},
        "signal_context": "半导体板块资金净流入+45.19亿全市场第一。台基股份板块内资金净流入最高(+2.94亿)，主力资金持续买入，机构关注度高。",
        "risk_flags": ["未涨停说明市场分歧仍存", "创业板指-2.27%可能拖累成长股情绪", "换手14.18%偏高，需警惕午后获利回吐", "功率半导体竞争格局分散，护城河不够深"],
        "entry_hint": "34-35元区间低吸，止损32元。适合有耐心的投资者，不追高只低吸。若午后放量突破35.6元可加仓",
        "confidence_score": 0.70
    },
    {
        "stock_code": "000783",
        "stock_name": "长江证券",
        "pick_level": "watch",
        "reason_summary": "证券板块涨停领涨股(+10.00%)，券商护盘逻辑明确，估值合理弹性好，适合防御配置",
        "reason_detail": "证券板块整体资金净流入+6.93亿，长江证券涨停+10.00%领涨。在市场弱势环境下（深成指-1.83%、创业板-2.27%），券商护盘逻辑明确。证券板块估值合理、弹性好，在市场需要护盘时往往率先启动。但券商板块连续性一般，需观察午后是否出现第二只涨停股形成联动。",
        "sector_name": "证券",
        "theme_tags": ["券商", "金融", "护盘", "大盘蓝筹"],
        "capital_profile": {"net_inflow": 0.0, "main_force_signal": "moderate"},
        "signal_context": "证券板块涨幅+1.64%，资金净流入+6.93亿。市场弱势环境下券商护盘逻辑明确，长江证券作为板块领涨股涨停封板。金融权重护盘+市场情绪修复预期双重支撑。",
        "risk_flags": ["券商板块行情持续性存疑", "若午后市场企稳，券商护盘逻辑可能弱化导致回落", "长江证券涨停封单情况未知，若午后炸板可能引发板块回调"],
        "entry_hint": "观察午后封板情况。若板块内出现第二只涨停股且封单稳定，可轻仓参与。适合稳健配置而非主动进攻",
        "confidence_score": 0.60
    }
]

# === Validation ===
print("=== VALIDATION ===")
for i, p in enumerate(picks):
    req = ["stock_code", "stock_name", "pick_level", "reason_summary", "reason_detail",
           "sector_name", "theme_tags", "capital_profile", "signal_context", "risk_flags",
           "entry_hint", "confidence_score"]
    missing = [f for f in req if f not in p]
    if missing:
        print(f"Pick {i} ({p.get('stock_name','?')}): MISSING {missing}")
    else:
        print(f"Pick {i} ({p['stock_name']}): ALL 12 FIELDS OK")
    if not isinstance(p.get("theme_tags"), list) or len(p.get("theme_tags",[]))==0:
        print(f"  WARN: theme_tags")
    if not isinstance(p.get("risk_flags"), list) or len(p.get("risk_flags",[]))==0:
        print(f"  WARN: risk_flags")
    if not isinstance(p.get("capital_profile"), dict) or len(p.get("capital_profile",{}))==0:
        print(f"  WARN: capital_profile")
    if p.get("pick_level") not in ["watch","candidate","confirm","strong_recommend"]:
        print(f"  WARN: pick_level")

# === Assemble and Write ===
report = {
    "trading_date": "2026-06-23",
    "skill_name": "12:00 早盘复盘",
    "job_name": "12:00 早盘复盘",
    "job_type": "stock_pick",
    "run_type": "production",
    "source_input_ref": "claude-code-cli",
    "_meta": {
        "schema_version": "3.0",
        "engine_type": "claude-code",
        "data_sources_used": [
            "akshare (预取数据: sector_rankings 90行业, individual_rankings 5192只个股)",
            "腾讯财经 qt.gtimg.cn (大盘指数实时数据: 上证/深证/创业板/科创50/上证50/沪深300)"
        ]
    },
    "summary": {
        "market_phase": "震荡偏弱，个股活跃。权重指数(上证50 -1.47%, 沪深300 -1.53%)走弱但中小盘个股涨多跌少(3125:1971)，涨停110只vs跌停20只。主力资金从有色/新能源恐慌性撤出(金属四板块净流出-246亿)，转向医药全产业链(+22.88亿)和半导体(+45.19亿)。创业板-2.27%领跌主要受金属和光伏拖累。",
        "hot_sectors": [
            "化学制药 +4.14% (净流入+11.18亿，行业涨幅第1)",
            "生物制品 +3.50% (净流入+2.61亿，行业涨幅第2)",
            "医疗服务 +2.85% (净流入+4.79亿，行业涨幅第3)",
            "中药 +2.83% (净流入+3.81亿，行业涨幅第4)",
            "半导体 +1.23% (净流入+45.19亿，全市场资金净流入第一)"
        ],
        "risk_signals": [
            "贵金属暴跌-6.82%净流出-52.99亿，有色四板块合计净流出-246亿，踩踏式出逃",
            "创业板指-2.27%领跌，成长股整体承压，4200点为关键支撑",
            "元件板块-3.71%净流出-87.45亿，PCB/被动元件方向崩溃",
            "部分20cm涨停股主力大幅净流出：银之杰-11.25亿、龙磁科技-4.73亿，警惕午后炸板潮",
            "光伏设备-1.78%持续走弱，电池-1.27%净流出-62.07亿，新能源产业链继续失血"
        ]
    },
    "result_payload": {
        "structured_picks": picks
    },
    "raw_output": html
}

with open(out, 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(f"\n=== OUTPUT ===")
print(f"Report: {out}")
print(f"Size: {os.path.getsize(out):,} bytes")
print(f"Picks: {len(picks)}")

with open(out) as f:
    json.load(f)
print("JSON validation: PASSED")
