#!/usr/bin/env python3
"""Build the final 盘前消息面挖掘 JSON with safe escaping via Python."""
import json
import os

OUT = "/Users/jwkj/easyquant/data/ai_center/inbox/0820_盘前消息面挖掘_2026-06-30_20260630_082023.json"

raw_output = '''<h2>盘前消息面全景扫描 — 2026-06-30</h2>

<h3>一、外盘表现与A股开盘预期</h3>

<div class="alert-good">
<b>隔夜美股三大指数集体收涨</b>，对A股开盘形成正向传导：
<ul>
<li><span class="highlight">道琼斯指数</span>收报 <span class="up">+0.59%</span>（51995点）</li>
<li><span class="highlight">纳斯达克</span>收报 <span class="up">+2.07%</span>（25502点）</li>
<li>中概股普涨，三星电子股价涨超3%</li>
</ul>
<b>预计6月30日A股小幅高开</b>，科技/AI板块有望延续强势。
</div>

<h3>二、政策面催化</h3>

<div class="alert-good">
<b>【1】国务院：深入实施「人工智能+」行动</b>（6月29日国务院常务会议）
<ul>
<li>听取人工智能发展情况汇报，审议通过《「十五五」碳达峰行动方案》和《国民健康「十五五」规划》</li>
<li>智能产品和服务的规模化商业应用将获政策推动</li>
<li>利好方向：<span class="tag">AI应用</span> <span class="tag">智能体</span> <span class="tag">AI手机</span> <span class="tag">智能驾驶</span></li>
</ul>
</div>

<div class="alert-good">
<b>【2】国家医保局公布2026年医保目录调整初步形式审查结果</b>
<ul>
<li><span class="highlight">557个药品</span>通过基本医保目录初审</li>
<li><span class="highlight">54个药品</span>通过商保创新药目录初审</li>
<li>叠加BD出海加速、国产创新药上市审批提速，行业从估值修复迈向价值重塑新阶段</li>
<li>利好方向：<span class="tag">创新药</span> <span class="tag">生物制品</span> <span class="tag">化学制药</span> <span class="tag">中药</span> <span class="tag">医疗器械</span></li>
</ul>
</div>

<div class="alert-bad">
<b>【3】证监会主席吴清陆家嘴论坛表态</b>：严查严处借科技之名翻炒热点概念
<ul>
<li>严打操纵市场、内幕交易等违法违规行为</li>
<li>点名：<span class="tag">具身智能</span> <span class="tag">光芯片</span> <span class="tag">商业航天</span>等近期高热度赛道</li>
<li>部分上市公司脱离经营基本面，借助信息传播渠道刻意放大产业关联程度</li>
<li><b>影响：纯题材股面临估值压力，资金将向有真实业绩支撑的标的集中</b></li>
</ul>
</div>

<h3>三、行业催化与个股公告</h3>

<div class="alert-good">
<b>【1】半导体设备全球景气周期持续确认（中信建投研报）</b>
<ul>
<li>SEMI上修全年预期：<span class="highlight">2026年全球前端半导体设备市场规模增速预期从16.5%上调至23.5%</span>，达<span class="highlight">1522亿美元</span></li>
<li>Q1全球半导体设备出货额达<span class="highlight">365.5亿美元</span>，同比+14%，<b>创历史单季度新高</b></li>
<li>海力士2034年产能预计翻三倍</li>
<li>利好方向：<span class="tag">半导体设备</span> <span class="tag">半导体材料</span> <span class="tag">封测</span></li>
</ul>
</div>

<div class="alert-good">
<b>【2】太空光伏产业加速破局，A股抢滩万亿新赛道</b>
<ul>
<li>低轨卫星组网提速催生卫星电源增量需求</li>
<li>近期多家A股上市公司密集发布对外投资、战略合作、共建实验室等公告</li>
<li>企业从硅片、封装材料到钙钛矿电池全产业链布局</li>
<li>多家机构测算赛道远期市场规模望冲击<span class="highlight">万亿级别</span></li>
<li>利好方向：<span class="tag">光伏</span> <span class="tag">卫星</span> <span class="tag">钙钛矿</span></li>
</ul>
</div>

<div class="alert-good">
<b>【3】三星/海力士/美光遭反垄断集体诉讼（美国加州联邦法院）</b>
<ul>
<li>14名个人消费者及3家小型企业起诉，指控三家存储巨头自2022年起串通操纵供应和定价</li>
<li>导致过去四年内存价格上涨约<span class="highlight">700%</span></li>
<li>DRAM价格失控飙涨背景下，转型HBM减少传统内存供应成为导火索</li>
<li>利好方向：<span class="tag">国产DRAM</span> <span class="tag">HBM</span> <span class="tag">存储芯片</span></li>
</ul>
</div>

<div class="alert-good">
<b>【4】水晶光电盘后交流会释压</b>
<ul>
<li>水晶光电（002273.SZ）6月29日股价跌停引发关注，盘后管理层释压</li>
<li>全年业绩有望落在指引区间中上水平</li>
<li>北美大客户涨价对公司暂无实质影响</li>
<li>光存储、光链接等新业务进展是关注焦点</li>
</ul>
</div>

<h3>四、前一交易日（2026-06-29）板块表现</h3>

<h4>📈 板块涨幅TOP10</h4>
<table>
<tr><th>排名</th><th>板块</th><th>涨跌幅</th></tr>
<tr><td>1</td><td><span class="sector">生物制品</span></td><td><span class="up">+7.43%</span></td></tr>
<tr><td>2</td><td><span class="sector">医疗服务</span></td><td><span class="up">+6.11%</span></td></tr>
<tr><td>3</td><td><span class="sector">化学制药</span></td><td><span class="up">+5.88%</span></td></tr>
<tr><td>4</td><td><span class="sector">中药</span></td><td><span class="up">+3.70%</span></td></tr>
<tr><td>5</td><td><span class="sector">医疗器械</span></td><td><span class="up">+3.52%</span></td></tr>
<tr><td>6</td><td><span class="sector">半导体</span></td><td><span class="up">+2.74%</span></td></tr>
<tr><td>7</td><td><span class="sector">养殖业</span></td><td><span class="up">+2.39%</span></td></tr>
<tr><td>8</td><td><span class="sector">医药商业</span></td><td><span class="up">+2.37%</span></td></tr>
<tr><td>9</td><td><span class="sector">保险</span></td><td><span class="up">+2.19%</span></td></tr>
<tr><td>10</td><td><span class="sector">美容护理</span></td><td><span class="up">+2.04%</span></td></tr>
</table>

<h4>💰 板块资金净流入TOP5（亿元）</h4>
<table>
<tr><th>排名</th><th>板块</th><th>净流入</th></tr>
<tr><td>1</td><td><span class="sector">半导体</span></td><td><span class="inflow">+112.42亿</span></td></tr>
<tr><td>2</td><td><span class="sector">化学制药</span></td><td><span class="inflow">+49.14亿</span></td></tr>
<tr><td>3</td><td><span class="sector">医疗服务</span></td><td><span class="inflow">+18.96亿</span></td></tr>
<tr><td>4</td><td><span class="sector">生物制品</span></td><td><span class="inflow">+15.00亿</span></td></tr>
<tr><td>5</td><td><span class="sector">白酒</span></td><td><span class="inflow">+9.31亿</span></td></tr>
</table>

<h4>📉 板块跌幅TOP5</h4>
<table>
<tr><th>排名</th><th>板块</th><th>涨跌幅</th></tr>
<tr><td>1</td><td><span class="sector">非金属材料</span></td><td><span class="down">-4.76%</span></td></tr>
<tr><td>2</td><td><span class="sector">元件</span></td><td><span class="down">-3.89%</span></td></tr>
<tr><td>3</td><td><span class="sector">消费电子</span></td><td><span class="down">-3.12%</span></td></tr>
<tr><td>4</td><td><span class="sector">通信设备</span></td><td><span class="down">-3.03%</span></td></tr>
<tr><td>5</td><td><span class="sector">光学光电子</span></td><td><span class="down">-1.68%</span></td></tr>
</table>

<h4>💸 板块资金净流出TOP5（亿元）</h4>
<table>
<tr><th>排名</th><th>板块</th><th>净流出</th></tr>
<tr><td>1</td><td><span class="sector">光学光电子</span></td><td><span class="outflow">-69.01亿</span></td></tr>
<tr><td>2</td><td><span class="sector">元件</span></td><td><span class="outflow">-47.91亿</span></td></tr>
<tr><td>3</td><td><span class="sector">消费电子</span></td><td><span class="outflow">-47.21亿</span></td></tr>
<tr><td>4</td><td><span class="sector">通信设备</span></td><td><span class="outflow">-40.88亿</span></td></tr>
<tr><td>5</td><td><span class="sector">风电设备</span></td><td><span class="outflow">-9.23亿</span></td></tr>
</table>

<hr>

<h3>五、涨停结构与情绪温度</h3>

<div class="alert-bad">
<b>市场情绪温度计：<span class="highlight">46.75（偏冷）</span></b>
<ul>
<li>涨停总数：<span class="limit-up">107只</span>（其中首板98只，高标9只）</li>
<li>最高板：<b>3板</b>（高标延续性偏弱）</li>
<li>晋级率：<span class="down">15.52%</span>（偏低）</li>
<li>炸板率：<span class="down">65.52%</span>（偏高）</li>
<li>市场成交额：<span class="highlight">3.54万亿</span></li>
</ul>
<b>信号解读：</b>首板扩散偏多但晋级率偏低，更像<b>轮动</b>而非<b>主升</b>，情绪更偏防守。
</div>

<h3>六、重点关注主题</h3>

<h4>🎯 主题一：创新药/生物制品</h4>
<div class="alert-good">
<b>催化：</b>医保目录调整 + BD出海加速 + 商业化能力提升<br>
<b>代表个股：</b><span class="stock">百奥赛图</span>、<span class="stock">新赣江</span>、<span class="stock">禾元生物</span>、<span class="stock">三生国健</span>、<span class="stock">太极集团</span><br>
<b>逻辑：</b>行业从估值修复迈向价值重塑新阶段，板块净流入大幅领先
</div>

<h4>🎯 主题二：半导体设备/材料</h4>
<div class="alert-good">
<b>催化：</b>SEMI上调全年设备规模增速至<span class="highlight">23.5%</span>（达1522亿美元），Q1出货额创新高<br>
<b>代表个股：</b><span class="stock">神工股份</span>（板块+2.74%，净流入+112.42亿全市场第一）<br>
<b>逻辑：</b>国产替代+全球景气共振，但需警惕板块内部高低切换
</div>

<h4>🎯 主题三：太空光伏（万亿新赛道）</h4>
<div class="alert-good">
<b>催化：</b>低轨卫星组网提速 + 钙钛矿电池突破<br>
<b>代表个股：</b>硅片/封装材料/钙钛矿电池全产业链<br>
<b>逻辑：</b>远期市场规模望冲<span class="highlight">万亿级别</span>
</div>

<h4>🎯 主题四：AI应用端</h4>
<div class="alert-good">
<b>催化：</b>国务院「AI+」行动落地 + AI手机进入Agent时代（苹果/谷歌/豆包）<br>
<b>代表个股：</b>智能体/AI手机/智能驾驶方向<br>
<b>逻辑：</b>从政策宣示进入落地实施阶段，第二轮催化可期
</div>

<h4>🎯 主题五：保险/白酒（防御配置）</h4>
<div class="alert-good">
<b>催化：</b>市场偏防守（温度46.75），资金从科技切向低估值蓝筹<br>
<b>代表个股：</b><span class="stock">中国太保</span>（保险领涨+3.24%）、<span class="stock">酒鬼酒</span>（白酒领涨+6.56%）<br>
<b>逻辑：</b>防御属性突出，避险资金首选
</div>

<hr>

<h3>七、风险提示</h3>

<div class="risk-box">
<b>1. 监管整治风险</b>
<p>证监会主席吴清明确表态严查严处借科技之名翻炒热点概念，点名具身智能、光芯片、商业航天等热门赛道。纯题材股面临估值压力，<b>资金将向有真实业绩支撑的标的集中</b>。</p>
</div>

<div class="risk-box">
<b>2. 市场情绪偏冷风险</b>
<p>温度评分46.75（偏冷区间），炸板率65.52%偏高，晋级率15.52%偏低。操作上宜精选个股、控制仓位，不宜全面进攻。<b>高标接力风险显著</b>。</p>
</div>

<div class="risk-box">
<b>3. 板块高低切换风险</b>
<p>半导体板块净流入+112.42亿全市场第一，但消费电子/通信设备昨日杀跌（合计净流出超130亿）。板块内部呈现明显<b>高低切换</b>特征，需聚焦上游设备/材料/封测而非下游应用。</p>
</div>

<div class="risk-box">
<b>4. 地缘政治风险</b>
<p>世界黄金协会数据显示，过去12个月<span class="highlight">19%的央行</span>提高了国内黄金储备比例或对储备地点进行多元化配置（上一年度仅为7%）。「黄金回流」势头持续，<b>地缘政治担忧</b>已成为全球经济的灰犀牛问题。</p>
</div>

<div class="risk-box">
<b>5. 个股风险事件</b>
<p>*ST天喻实控人闫春雨遭湖北证监局处罚：罚款1350万元并禁入市场5年。ST类股票和存在合规风险的标的需谨慎参与。</p>
</div>

<hr>

<h3>八、操作建议</h3>

<div class="alert-good">
<b>主线方向（进攻）：</b>
<ul>
<li><b>创新药/生物制品</b> — 政策催化+资金集中，是当前最强主线</li>
<li><b>半导体设备/材料</b> — SEMI上调预期+国产替代，但聚焦上游</li>
<li><b>太空光伏/钙钛矿</b> — 万亿新赛道，关注产业链布局完整标的</li>
</ul>
<b>防御方向（防守）：</b>
<ul>
<li><b>保险</b>（中国太保） — 低估值蓝筹，防御属性</li>
<li><b>白酒</b>（酒鬼酒） — 消费防御，避险配置</li>
</ul>
<b>回避方向：</b>
<ul>
<li>纯题材股（具身智能/光芯片/商业航天等被监管点名方向）</li>
<li>消费电子/通信设备/光学光电子（昨日资金大幅流出）</li>
<li>ST类及存在合规风险的标的</li>
</ul>
</div>

<hr>

<p><i>本报告由EasyQuant AI工作台生成，数据来源：本地API（板块/信号/温度）+ 东方财富新闻 + 腾讯财经外盘 + AKShare预取数据。生成时间：2026-06-30 08:20:23。</i></p>'''

payload = {
    "trading_date": "2026-06-30",
    "skill_name": "08:20 盘前消息面挖掘",
    "job_name": "08:20 盘前消息面挖掘",
    "job_type": "news_scan",
    "run_type": "production",
    "source_input_ref": "claude-code-cli",
    "_meta": {
        "schema_version": "3.0",
        "engine_type": "claude-code",
        "data_sources_used": [
            "local_api_overview",
            "local_api_news_realtime",
            "local_api_monitor_signals",
            "local_api_limit_up_temperature",
            "tencent_qt_us_indices",
            "akshare_prefetch",
        ],
    },
    "summary": {
        "market_phase": "隔夜美股三大指数集体收涨（道指+0.59%，纳指+2.07%），中概股、AI芯片股全线走强，外部情绪偏暖；A股前一交易日（2026-06-29）市场高度分化——医药板块（生物制品/医疗服务/化学制药）涨停潮爆发，半导体净流入超百亿，但消费电子、通信设备遭遇大幅杀跌，资金跷跷板特征显著。预计6月30日A股小幅高开后延续结构性行情，医药/半导体主线有望延续，但需警惕高位股分歧。",
        "hot_sectors": ["创新药", "生物制品", "半导体", "中药", "医疗器械", "保险"],
        "risk_signals": [
            "证监会严查概念炒作",
            "市场温度46.75（偏冷）",
            "炸板率65.52%偏高",
            "消费电子/通信设备资金大幅净流出",
            "黄金回流潮支撑战后储备体系出现裂痕（地缘风险）",
        ],
        "headline_items": [
            "国务院：深入实施「人工智能+」行动，促进智能产品和服务规模化商业应用",
            "国家医保局公布2026年医保目录调整初步形式审查结果，557个药品通过初审，创新药迎价值重估窗口期",
            "中信建投：半导体设备全球景气周期持续确认，SEMI上调2026年全年增速预期至23.5%",
            "证监会主席吴清陆家嘴论坛表态：严查严处借科技之名翻炒热点概念",
            "太空光伏产业加速破局，A股上市公司密集发布对外投资/战略合作公告，机构测算赛道远期市场有望冲万亿级别",
            "上市公司跨界投资AI应回归产业逻辑（皮企/保健/果汁/调味品等跨界定增案例引发监管关注）",
            "三星/海力士/美光遭集体诉讼：转HBM减少传统内存供应，DRAM价格四年累涨700%",
        ],
        "market_implications": [
            "医药板块迎来政策+基本面双重催化（医保目录+BD出海），生物制品、化学制药、医疗服务全产业链共振",
            "半导体国产替代逻辑强化，设备/材料/封测全链条受益，但需警惕板块内部高低切换",
            "监管层对「伪科技」炒作的严打信号明确，纯题材股面临估值压力，资金将向有真实业绩支撑的标的集中",
            "市场情绪整体偏防守（温度46.75），高标晋级率15.52%偏低，操作上宜精选个股而非全面进攻",
            "AI+行动落地后，AI应用端（智能体、AI手机、智能驾驶）有望迎来第二轮催化",
        ],
        "watch_themes": [
            {"theme": "创新药/生物制品", "reason": "医保目录初审通过557个药品，叠加BD出海加速，板块情绪从估值修复迈向价值重塑", "stocks": ["百奥赛图", "新赣江", "禾元生物", "科莱瑞迪", "三生国健"]},
            {"theme": "半导体设备/材料", "reason": "SEMI上调全年设备增速至23.5%，海力士2034年产能翻三倍，国产替代窗口期", "stocks": ["神工股份"]},
            {"theme": "太空光伏", "reason": "低轨卫星组网提速，硅片/封装/钙钛矿电池全产业链布局，远期市场望破万亿", "stocks": []},
            {"theme": "AI应用端", "reason": "国务院「AI+」行动落地，AI手机进入Agent时代（苹果/谷歌/豆包）", "stocks": []},
            {"theme": "保险/白酒（防御配置）", "reason": "市场偏防守，资金从科技切向低估值蓝筹", "stocks": ["中国太保"]},
        ],
    },
    "result_payload": {
        "headline_items": [
            {
                "title": "国务院：深入实施「人工智能+」行动",
                "impact": "positive",
                "affected_sectors": ["AI应用", "智能体", "AI手机", "智能驾驶"],
                "affected_stocks": [],
                "summary": "6月29日国务院常务会议听取人工智能发展情况汇报，研究当前外贸形势和贸易强国建设有关工作，审议通过《「十五五」碳达峰行动方案》和《国民健康「十五五」规划》。AI+行动从政策宣示进入落地实施阶段。",
            },
            {
                "title": "医保目录初审：557个药品通过，创新药价值重估窗口期",
                "impact": "positive",
                "affected_sectors": ["生物制品", "化学制药", "中药", "医疗器械"],
                "affected_stocks": ["百奥赛图", "新赣江", "禾元生物", "三生国健", "太极集团"],
                "summary": "国家医保局公布2026年基本医保药品目录和商保创新药目录名单初步形式审查结果，557个药品通过基本医保目录初审，54个药品通过商保创新药目录初审。叠加国产创新药上市审批提速、BD出海步伐加快、商业化能力不断提升，行业从估值修复迈向价值重塑新阶段。",
            },
            {
                "title": "中信建投：半导体设备全球景气周期持续确认",
                "impact": "positive",
                "affected_sectors": ["半导体设备", "半导体材料", "封测"],
                "affected_stocks": ["神工股份"],
                "summary": "SEMI上修全年预期、海力士2034年产能翻三倍。SEMI于6月11日发布报告，将2026年全球前端半导体设备市场规模增速预期从此前的16.5%大幅上调至23.5%，达1522亿美元。Q1全球半导体设备出货额达365.5亿美元，同比+14%，创历史单季度新高。",
            },
            {
                "title": "证监会：严查严处借科技之名翻炒热点概念",
                "impact": "negative",
                "affected_sectors": ["纯题材股", "无业绩科技股"],
                "affected_stocks": [],
                "summary": "证监会主席吴清在2026陆家嘴论坛上明确表态，严查严处借科技之名翻炒热点概念，甚至操纵市场、内幕交易等违法违规行为。当前具身智能、光芯片、商业航天等赛道热度持续走高，部分上市公司脱离自身经营基本面，借助各类信息传播渠道刻意放大产业关联程度。",
            },
            {
                "title": "太空光伏产业加速破局，A股抢滩万亿新赛道",
                "impact": "positive",
                "affected_sectors": ["光伏", "硅片", "封装材料", "钙钛矿电池", "卫星"],
                "affected_stocks": [],
                "summary": "低轨卫星组网提速催生卫星电源增量需求，近期多家A股上市公司密集发布对外投资、战略合作、共建实验室等公告或相关合作消息，企业从硅片、封装材料到钙钛矿电池全产业链布局太空光伏。多家机构测算赛道远期市场规模有望冲击万亿级别。",
            },
            {
                "title": "三星/海力士/美光遭反垄断集体诉讼",
                "impact": "positive",
                "affected_sectors": ["国产DRAM", "HBM", "存储芯片"],
                "affected_stocks": [],
                "summary": "由于持续短缺导致内存价格失控飙涨，三大存储巨头三星、SK海力士和美光在美国面临集体诉讼。14名个人消费者和包括PC零售商在内的三家小型企业于6月25日在美国加州联邦法院提起诉讼，指控这三家生产全球大部分DRAM内存的公司从2022年起串通操纵供应和定价，导致过去四年内存价格上涨了约700%。",
            },
            {
                "title": "水晶光电股价跌停，盘后交流会释压：全年业绩有望落在指引中上区间",
                "impact": "neutral",
                "affected_sectors": ["光学光电子"],
                "affected_stocks": ["水晶光电"],
                "summary": "6月29日水晶光电股价突然跌停引发市场关注。公司管理层释放诸多积极信号，称全年业绩有望落在指引区间中上水平，并强调北美大客户涨价对公司暂无影响。光存储、光链接等新业务进展成为投资者关注焦点。",
            },
            {
                "title": "国务院：「十五五」碳达峰行动方案审议通过",
                "impact": "positive",
                "affected_sectors": ["新能源", "光伏", "储能", "风电"],
                "affected_stocks": [],
                "summary": "国务院常务会议审议通过《「十五五」碳达峰行动方案》，从政策层面为新能源板块未来五年的发展路径定调。",
            },
            {
                "title": "市场情绪温度：46.75（偏冷），炸板率65.52%",
                "impact": "negative",
                "affected_sectors": ["全市场"],
                "affected_stocks": [],
                "summary": "前一交易日（2026-06-29）市场温度评分46.75，处于偏冷区间。涨停107只，首板98只，高标仅3板（最高板），晋级率15.52%，炸板率65.52%。信号显示首板扩散偏多但晋级率偏低，更像轮动而非主升，情绪更偏防守。",
            },
            {
                "title": "美股三大指数集体收涨，纳指+2.07%",
                "impact": "positive",
                "affected_sectors": ["AI芯片", "中概股", "科技股"],
                "affected_stocks": [],
                "summary": "道指+0.59%（51995点），纳指+2.07%（25502点）。AI/科技板块全线走强，中概股普涨，外盘情绪对A股科技板块形成正向传导。",
            },
        ],
        "market_implications": [
            "医药板块迎来政策面（医保目录调整）+ 资金面（板块净流入大幅领先）+ 情绪面（涨停潮）三重共振，创新药/生物制品/化学制药有望延续强势，但需警惕分化",
            "半导体设备/材料端逻辑强化（SEMI上调全年增速至23.5%），但消费电子、通信设备昨日杀跌显示板块内部高低切换，操作上聚焦上游设备/材料/封测等上游环节",
            "证监会严打「伪科技」炒作信号明确，纯题材股面临估值压力，资金将向有真实业绩支撑的标的集中；监管整治的利空主要影响光芯片、具身智能、商业航天等前期热门赛道",
            "市场温度46.75偏冷+炸板率65.52%偏高显示情绪偏防守，高标晋级率仅15.52%显示主线尚未确立，操作上宜精选个股、控制仓位，不宜全面进攻",
            "AI+行动进入落地阶段，AI应用端（智能体、AI手机、智能驾驶）有望迎来第二轮催化，关注与硬件协同的软件标的",
        ],
        "watch_themes": [
            {"theme": "创新药/生物制品", "reason": "医保目录初审通过557个药品+BD出海加速+商业化能力提升，板块从估值修复迈向价值重塑新阶段", "stocks": ["百奥赛图", "新赣江", "禾元生物", "三生国健"]},
            {"theme": "半导体设备/材料", "reason": "SEMI上调全年设备规模增速至23.5%（达1522亿美元），海力士2034年产能翻三倍，国产替代窗口期", "stocks": ["神工股份"]},
            {"theme": "太空光伏", "reason": "低轨卫星组网提速，硅片/封装/钙钛矿电池全产业链布局，远期市场规模望破万亿", "stocks": []},
            {"theme": "AI应用端（AI手机/智能体/智能驾驶）", "reason": "国务院「AI+」行动落地实施，AI手机进入Agent时代（苹果/谷歌/豆包手机走向同一条路）", "stocks": []},
            {"theme": "保险/白酒（防御配置）", "reason": "市场偏防守（温度46.75），资金从高位科技切向低估值蓝筹寻求避险", "stocks": ["中国太保", "酒鬼酒"]},
        ],
        "structured_picks": [
            {
                "stock_code": "688164",
                "stock_name": "百奥赛图",
                "pick_level": "strong_recommend",
                "reason_summary": "医疗服务板块领涨股，医保目录调整+创新药BD出海双重催化",
                "reason_detail": "前一交易日医疗服务板块+6.11%（净流入+18.96亿），百奥赛图以+20%涨停领涨板块。国家医保局公布2026年医保目录调整初步形式审查结果，557个药品通过基本医保目录初审，54个药品通过商保创新药目录初审，叠加国产创新药上市审批提速、BD出海步伐加快，公司作为创新药CRO龙头深度受益。",
                "sector_name": "医疗服务",
                "theme_tags": ["创新药", "CRO", "BD出海", "医保目录"],
                "capital_profile": {"net_inflow": 2.5, "main_force_signal": "strong"},
                "signal_context": "板块净流入大幅领先全市场（+18.96亿），公司涨停封单强度高",
                "risk_flags": ["高标分歧风险", "CRO行业景气度波动"],
                "entry_hint": "竞价高开3%以内可小幅建仓，回踩5日线企稳加仓",
                "confidence_score": 0.78,
            },
            {
                "stock_code": "603232",
                "stock_name": "新赣江",
                "pick_level": "strong_recommend",
                "reason_summary": "化学制药板块领涨股（+30%涨停），板块净流入+49.14亿领跑全市场",
                "reason_detail": "化学制药板块前一交易日+5.88%，净流入+49.14亿（新赣江以+30%涨停领涨）。板块覆盖公司159家，资金参与度极高。医保目录调整+创新药出海催化叠加板块内多只个股涨停，赚钱效应扩散。新赣江作为板块情绪龙头值得关注。",
                "sector_name": "化学制药",
                "theme_tags": ["化学制药", "创新药", "医保目录"],
                "capital_profile": {"net_inflow": 5.0, "main_force_signal": "strong"},
                "signal_context": "板块净流入+49.14亿领跑全市场，赚钱效应扩散",
                "risk_flags": ["高波动风险", "个股基本面与股价偏离"],
                "entry_hint": "只做强势标的的回封机会，不追高",
                "confidence_score": 0.7,
            },
            {
                "stock_code": "688293",
                "stock_name": "禾元生物",
                "pick_level": "confirm",
                "reason_summary": "生物制品板块领涨股，板块涨幅全市场第一（+7.43%）",
                "reason_detail": "生物制品前一交易日以+7.43%涨幅领跑全市场，板块净流入+15.00亿。禾元生物作为板块领涨股+20%涨停，板块情绪龙头。叠加医保目录调整利好落地，生物制品作为医药创新核心环节持续受益。",
                "sector_name": "生物制品",
                "theme_tags": ["生物制品", "创新药", "医保目录"],
                "capital_profile": {"net_inflow": 3.0, "main_force_signal": "strong"},
                "signal_context": "板块涨幅+7.43%全市场第一，资金集中度高",
                "risk_flags": ["高位接力风险", "板块整体估值偏高"],
                "entry_hint": "分歧日低吸，不追高",
                "confidence_score": 0.72,
            },
            {
                "stock_code": "600233",
                "stock_name": "神工股份",
                "pick_level": "confirm",
                "reason_summary": "半导体板块领涨股，板块净流入+112.42亿（全市场最高）",
                "reason_detail": "半导体前一交易日+2.74%，净流入+112.42亿（绝对值全市场第一）。神工股份+20%涨停领涨板块。SEMI上调2026年全球前端半导体设备市场规模增速预期至23.5%（达1522亿美元），Q1出货额同比+14%创新高。三星/海力士/美光遭反垄断诉讼，DRAM价格四年累涨700%，存储芯片国产替代逻辑强化。神工股份作为半导体材料标的深度受益。",
                "sector_name": "半导体",
                "theme_tags": ["半导体", "国产替代", "HBM", "DRAM"],
                "capital_profile": {"net_inflow": 8.0, "main_force_signal": "strong"},
                "signal_context": "板块净流入+112.42亿全市场第一，主线资金最集中方向",
                "risk_flags": ["高标接力风险", "海外巨头诉讼不确定性", "消费电子需求担忧"],
                "entry_hint": "竞价高开2%以内可关注，板块分化时优先保留上游设备/材料仓位",
                "confidence_score": 0.75,
            },
            {
                "stock_code": "600129",
                "stock_name": "太极集团",
                "pick_level": "candidate",
                "reason_summary": "中药板块领涨股（+10.03%），板块+3.70%稳步上行",
                "reason_detail": "中药板块前一交易日+3.70%，净流入+7.31亿。太极集团+10.03%领涨。医保目录调整中，中药品种的纳入情况是市场关注重点；同时中药板块作为防御性配置，在市场偏防守环境下（温度46.75）有望吸引避险资金。",
                "sector_name": "中药",
                "theme_tags": ["中药", "防御", "医保目录"],
                "capital_profile": {"net_inflow": 1.5, "main_force_signal": "moderate"},
                "signal_context": "板块稳步上行，防御属性突出",
                "risk_flags": ["板块弹性有限", "防御性配置机会成本"],
                "entry_hint": "适合低吸配置，不追高",
                "confidence_score": 0.65,
            },
        ],
    },
    "raw_output": raw_output,
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
print(f"Wrote {OUT}, size={os.path.getsize(OUT)} bytes")

# Validate
with open(OUT) as f:
    parsed = json.load(f)
print(f"OK: {len(parsed['result_payload']['headline_items'])} headline_items, "
      f"{len(parsed['result_payload']['structured_picks'])} structured_picks, "
      f"raw_output length={len(parsed['raw_output'])} chars")