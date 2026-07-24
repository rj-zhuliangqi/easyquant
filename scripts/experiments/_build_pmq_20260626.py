import json, datetime
ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
filepath = f'/Users/jwkj/easyquant/data/ai_center/inbox/0820_盘前消息面挖掘_2026-06-26_{ts}.json'

raw_output = """<h2>一、隔夜外盘表现与 A 股开盘影响</h2>
<p>北京时间 2026-06-25 收盘，美股三大指数<span class="highlight">窄幅震荡</span>，<b>纳斯达克领跌</b>，<b>中概股普跌</b>，预计今日 A 股<span class="highlight">小幅承压、低开概率较大</span>。</p>
<table>
<tr><th>指数 / 标的</th><th>收盘点位</th><th>涨跌幅</th></tr>
<tr><td><span class="stock">道琼斯工业</span></td><td>51920.62</td><td><span class="up">+0.14%</span></td></tr>
<tr><td><span class="stock">纳斯达克</span></td><td>25358.60</td><td><span class="down">-0.46%</span></td></tr>
<tr><td><span class="stock">标普500</span></td><td>7357.49</td><td><span class="down">-0.01%</span></td></tr>
<tr><td>USD/CNH（在岸人民币）</td><td>6.8018</td><td><span class="down">-0.04%</span></td></tr>
</table>
<table>
<tr><th>中概股</th><th>涨跌幅</th></tr>
<tr><td><span class="stock">阿里巴巴 BABA</span></td><td><span class="down">-4.74%</span></td></tr>
<tr><td><span class="stock">拼多多 PDD</span></td><td><span class="down">-3.22%</span></td></tr>
<tr><td><span class="stock">京东 JD</span></td><td><span class="down">-1.14%</span></td></tr>
<tr><td><span class="stock">百度 BIDU</span></td><td><span class="down">-3.55%</span></td></tr>
</table>
<div class="alert-bad">亚太股市<span class="highlight">早盘集体走弱</span>：日经225 跌幅扩大至 <span class="down">-2.0%</span>，韩国综指跌幅扩大至 <span class="down">-2.0%</span>，恒指期货同步承压，对今日 A 股形成情绪压制。</div>

<hr>

<h2>二、上一交易日（2026-06-25）盘面回顾</h2>
<h3>板块涨跌排行</h3>
<table>
<tr><th>排名</th><th>板块</th><th>涨跌幅</th><th>资金净流入</th><th>领涨股</th></tr>
<tr><td>1</td><td><span class="sector">机场航运</span></td><td><span class="up">+4.05%</span></td><td><span class="inflow">+12.85亿</span></td><td><span class="stock">华夏航空</span> <span class="limit-up">涨停</span></td></tr>
<tr><td>2</td><td><span class="sector">元件</span></td><td><span class="up">+3.14%</span></td><td><span class="inflow">+112.24亿</span></td><td><span class="stock">三环集团</span> +12.64%</td></tr>
<tr><td>3</td><td><span class="sector">证券</span></td><td><span class="up">+3.06%</span></td><td><span class="inflow">+57.78亿</span></td><td><span class="stock">长江证券</span> <span class="limit-up">涨停</span></td></tr>
<tr><td>4</td><td><span class="sector">半导体</span></td><td><span class="up">+2.21%</span></td><td><span class="inflow">+80.68亿</span></td><td><span class="stock">北京君正</span> <span class="limit-up">涨停</span></td></tr>
<tr><td>5</td><td><span class="sector">保险</span></td><td><span class="up">+2.19%</span></td><td><span class="inflow">+2.72亿</span></td><td><span class="stock">中国人保</span> +4.18%</td></tr>
<tr><td>6</td><td><span class="sector">白酒</span></td><td><span class="up">+1.64%</span></td><td><span class="inflow">+6.09亿</span></td><td><span class="stock">酒鬼酒</span> +7.20%</td></tr>
<tr><td>7</td><td><span class="sector">游戏</span></td><td><span class="up">+1.51%</span></td><td><span class="inflow">+6.80亿</span></td><td><span class="stock">巨人网络</span> +10.00%</td></tr>
<tr><td>8</td><td><span class="sector">通信设备</span></td><td><span class="down">-0.42%</span></td><td><span class="inflow">+73.44亿</span></td><td><span class="stock">利尔达</span> +29.99%</td></tr>
<tr><td>9</td><td><span class="sector">消费电子</span></td><td><span class="down">-0.47%</span></td><td><span class="outflow">-9.18亿</span></td><td><span class="stock">信濠光电</span> +13.52%</td></tr>
<tr><td>10</td><td><span class="sector">银行</span></td><td><span class="down">-0.66%</span></td><td><span class="outflow">-29.45亿</span></td><td><span class="stock">中信银行</span> +0.42%</td></tr>
<tr><td>11</td><td><span class="sector">汽车整车</span></td><td><span class="down">-0.92%</span></td><td><span class="outflow">-1.20亿</span></td><td><span class="stock">福田汽车</span> +2.64%</td></tr>
<tr><td>12</td><td><span class="sector">光伏设备</span></td><td><span class="down">-0.95%</span></td><td><span class="outflow">-13.83亿</span></td><td><span class="stock">横店东磁</span> +10.02%</td></tr>
</table>
<p><b>资金主线</b>：<span class="sector">半导体/元件/通信设备</span>昨日合计净流入超 <span class="highlight">266 亿</span>，是绝对主战场；<span class="sector">银行</span>逆势净流出 <span class="outflow">-29.45亿</span>，金融板块内部出现<b>券商强、银行弱</b>的明显分化。</p>

<hr>

<h2>三、涨停焦点（昨日 2026-06-25 收盘）</h2>
<p>昨日涨停/大涨高度集中在<span class="sector">半导体 + AI 算力 + 存储</span>产业链，龙头放量走强但分歧同步放大：</p>
<table>
<tr><th>股票</th><th>收盘价</th><th>涨跌幅</th><th>成交额</th><th>主力净额</th></tr>
<tr><td><span class="stock">北京君正 300223</span></td><td>237.36</td><td><span class="limit-up">+20.00%</span></td><td><span class="highlight">126.58亿</span></td><td><span class="outflow">-13.82亿</span></td></tr>
<tr><td><span class="stock">佰维存储 688525</span></td><td>480.30</td><td><span class="up">+15.18%</span></td><td><span class="highlight">224.71亿</span></td><td><span class="inflow">+21.26亿</span></td></tr>
<tr><td><span class="stock">斯迪克 300806</span></td><td>117.88</td><td><span class="up">+17.77%</span></td><td><span class="highlight">39.44亿</span></td><td><span class="inflow">+3.62亿</span></td></tr>
<tr><td><span class="stock">帝奥微 688381</span></td><td>51.90</td><td><span class="limit-up">+20.00%</span></td><td>15.07亿</td><td><span class="inflow">+0.85亿</span></td></tr>
<tr><td><span class="stock">中微半导 688380</span></td><td>61.74</td><td><span class="limit-up">+20.00%</span></td><td>14.38亿</td><td><span class="inflow">+1.58亿</span></td></tr>
<tr><td><span class="stock">美埃科技 688376</span></td><td>101.52</td><td><span class="limit-up">+20.00%</span></td><td>7.80亿</td><td><span class="outflow">-0.09亿</span></td></tr>
<tr><td><span class="stock">汇成股份 688403</span></td><td>41.30</td><td><span class="up">+14.09%</span></td><td><span class="highlight">68.40亿</span></td><td><span class="inflow">+1.65亿</span></td></tr>
<tr><td><span class="stock">兴福电子 688545</span></td><td>125.70</td><td><span class="up">+14.01%</span></td><td>37.60亿</td><td><span class="inflow">+4.33亿</span></td></tr>
<tr><td><span class="stock">杰普特 688025</span></td><td>498.29</td><td><span class="up">+18.94%</span></td><td>36.62亿</td><td><span class="inflow">+6.16亿</span></td></tr>
<tr><td><span class="stock">长江证券 000783</span></td><td>10.15</td><td><span class="limit-up">+9.97%</span></td><td>—</td><td>—</td></tr>
</table>
<div class="risk-box"><b>分歧警示</b>：<span class="stock">北京君正</span>虽 <span class="limit-up">涨停</span>，但主力净流出 <span class="outflow">-13.82亿</span>，且全天 <span class="highlight">126.58亿</span> 巨量换手，短期高位筹码不稳，谨防今日分化。</div>

<hr>

<h2>四、政策面与机构观点</h2>
<div class="alert-good">
<b>【央行政策】</b>《中国人民银行法》时隔 <span class="highlight">23 年</span> 启动修订，专家解读三大突破性亮点，<b>货币政策框架</b>与<b>宏观审慎监管</b>有望进一步细化，利好大金融板块估值修复。
</div>
<div class="alert-good">
<b>【中信证券 06-26 盘前观点】</b><br>
• 展望 2026-27 年，<b>银行板块步入风险周期尾部区间</b>，红利价值再受关注；<br>
• <b>坚定看好电子板块后续表现</b>，<span class="tag">半导体</span> <span class="tag">元件</span> <span class="tag">消费电子</span> 仍是主线；<br>
• 与昨日盘面 <span class="sector">证券</span> +3.06% / <span class="sector">银行</span> -0.66% 的 <b>"券强银弱"</b> 分化相互印证。
</div>
<div class="alert-good">
<b>【国资银行】</b><span class="stock">招商银行</span>成立<span class="highlight">市值管理小组</span>，拟任行长王小青首提"<b>四个定力</b>"，标志国有大行进入主动价值管理阶段。
</div>
<div class="alert-good">
<b>【医保集采】</b>第 12 批国家组织药品集采启动，<span class="highlight">纳入 65 个品种</span>，仿制药/医药流通继续承压，<span class="sector">创新药</span>相对受益。
</div>

<hr>

<h2>五、行业催化与个股公告</h2>
<h3>AI / 半导体 主线</h3>
<div class="alert-good">
<b>【DeepSeek 英雄帖】</b>"所有部门规模至少扩大一倍"，公司判断 <b>人类正处于 AGI 前夜</b>，进一步强化国产 AI 算力需求预期；<br>
<b>【存储芯片】</b><span class="stock">时创意</span>冲击 IPO，2025 年净利暴增超 <span class="highlight">18 倍</span>，客户涵盖三星/美光/SK海力士供应链。<br>
<b>【人形机器人】</b><span class="stock">智元旗下灵巧手</span>估值 <span class="highlight">10亿美元</span>，成立仅 5 个月即首季盈利。<br>
<b>【AI 散热】</b>AI 散热成为<span class="sector">培育钻石</span>行业新增长极，多数公司处于"<b>有产品、缺订单</b>"早期阶段。
</div>

<h3>资源 / 新能源</h3>
<div class="alert-good">
<b>【锂铜双扩】</b><span class="stock">中矿资源</span>一季业绩赚超去年全年，立下三年净利润 <span class="highlight">90 亿元</span>目标，对锂、铜都有产能扩建计划。<br>
<b>【油价】</b>霍尔木兹海峡重开增加供应，<b>布伦特原油抹去战时全部涨幅</b>，<span class="sector">石油化工</span>承压、航空航运反向受益（与昨日 <span class="up">+4.05%</span> 板块表现一致）。
</div>

<h3>房地产 / 城市更新</h3>
<div class="alert-neutral">
<b>【深圳土拍】</b>深圳拍出 <span class="highlight">105 亿</span>宅地，与腾讯"<span class="stock">企鹅岛</span>"隔海对望，<b>核心地段溢价成交</b>显示一线城市优质资产仍受追捧。
</div>

<h3>消费 / 出海</h3>
<div class="alert-bad">
<b>【携程 Q1】</b>净利近<span class="highlight">腰斩</span>，<b>反垄断调查 + 增速放缓</b>致股价重挫，<span class="sector">OTA</span>板块情绪承压。
</div>

<hr>

<h2>六、热点主题跟踪</h2>
<table>
<tr><th>主题</th><th>驱动</th><th>代表个股</th></tr>
<tr><td><span class="tag">AI 算力</span></td><td>DeepSeek 扩编 + 存储芯片 IPO</td><td><span class="stock">佰维存储</span>、<span class="stock">汇成股份</span>、<span class="stock">北京君正</span></td></tr>
<tr><td><span class="tag">半导体设备/材料</span></td><td>资金净流入 +80亿，中信看多</td><td><span class="stock">中微半导</span>、<span class="stock">兴福电子</span></td></tr>
<tr><td><span class="tag">人形机器人</span></td><td>智元灵巧手估值 10亿美元</td><td>板块联动关注</td></tr>
<tr><td><span class="tag">券商</span></td><td>板块 +3.06%，资金净流入 +57.78亿</td><td><span class="stock">长江证券</span></td></tr>
<tr><td><span class="tag">银行高股息</span></td><td>中信：风险周期尾部</td><td><span class="stock">招商银行</span>、<span class="stock">中信银行</span></td></tr>
<tr><td><span class="tag">存储芯片</span></td><td>时创意 IPO，净利 +18 倍</td><td><span class="stock">佰维存储</span>、<span class="stock">北京君正</span></td></tr>
<tr><td><span class="tag">机场航运</span></td><td>油价回调 + 板块 +4.05%</td><td><span class="stock">华夏航空</span></td></tr>
<tr><td><span class="tag">培育钻石/AI 散热</span></td><td>跨界新增长极</td><td>处于早期阶段，<b>观望</b></td></tr>
</table>

<hr>

<h2>七、风险提示</h2>
<div class="risk-box">
<b>1. 海外地缘 + 流动性风险</b>：日韩股市早盘 <span class="down">-2%</span>，中概股 <span class="down">-3% ~ -5%</span>，纳指 <span class="down">-0.46%</span>，外围情绪偏空，今日 A 股或<span class="highlight">低开</span>。<br>
<b>2. 高位题材分化风险</b>：<span class="stock">北京君正</span>等龙头昨日涨停伴随主力净流出，今日若不能延续放量，<span class="sector">半导体</span>内部可能出现"<b>去弱留强</b>"切换。<br>
<b>3. 银行 / 高股息跷跷板风险</b>：<span class="sector">证券</span> +3% 与 <span class="sector">银行</span> -0.66% 同时发生，说明资金并非简单"<b>加仓金融</b>"，而是结构性博弈，<b>不要盲目追涨券商</b>。<br>
<b>4. 反垄断与监管风险</b>：<span class="stock">携程</span>遭反垄断调查、<span class="stock">苹果</span>在华再被举报，平台经济/OTA 短期情绪受抑。<br>
<b>5. 油价与通胀</b>：布伦特原油已抹去战时涨幅，但 <b>霍尔木兹</b>局势反复仍是扰动项，关注 <span class="sector">航空航运</span> 持续性。<br>
<b>6. 流动性风险</b>：知名基金公司一 ETF 成立近 5 年收益率仍为负、清盘，提示<b>主题 ETF 流动性</b>风险。<br>
<b>7. 业绩兑现风险</b>：<span class="stock">汇绿生态</span>年内涨 184% 被股民催改名，公司回应——典型<b>主题炒作高位</b>信号。
</div>

<hr>

<h2>八、今日策略结论</h2>
<div class="alert-good">
<b>核心判断</b>：隔夜外盘<span class="highlight">偏空 + 日韩早盘 -2%</span>，预计今日 A 股<b>小幅低开</b>，但 <span class="sector">半导体 / AI 算力</span>主线仍在惯性中，可观察开盘 30 分钟资金确认后再决定加减仓。<br>
<b>关注重点</b>：① <span class="tag">半导体</span> 高位龙头能否承接（关注 <span class="stock">佰维存储</span>、<span class="stock">北京君正</span>）；② <span class="tag">证券</span> 是否延续（<span class="stock">长江证券</span>）；③ <span class="tag">银行</span> 是否在"<b>风险周期尾部</b>"逻辑下反弹；④ <span class="tag">AI 散热/培育钻石</span> 等新主题的接力意愿。<br>
<b>操作建议</b>：防御优先，控仓观望开盘情绪；待 <span class="highlight">9:30-10:00</span> 资金流向明朗后再做跟随，<b>忌在低开时恐慌性杀跌</b>。
</div>
"""

payload = {
    "trading_date": "2026-06-26",
    "skill_name": "08:20 盘前消息面挖掘",
    "job_name": "08:20 盘前消息面挖掘",
    "job_type": "stock_pick",
    "run_type": "production",
    "source_input_ref": "claude-code-cli",
    "_meta": {
        "schema_version": "3.0",
        "engine_type": "claude-code",
        "data_sources_used": [
            "akshare:stock_info_global_em",
            "akshare:stock_news_em",
            "tencent:qt.gtimg.cn",
            "eastmoney:push2",
            "prefetch:/tmp/easyquant_market_data_2026-06-26.json"
        ]
    },
    "summary": {
        "market_phase": "隔夜美股窄幅震荡（纳指 -0.46%，道指 +0.14%），中概股普跌（-1%~-5%），日韩早盘齐跌 -2%，预计今日 A 股小幅低开",
        "hot_sectors": ["半导体", "元件", "证券", "AI 算力", "存储芯片"],
        "risk_signals": ["外围普跌", "中概弱势", "日韩低开 -2%", "高位题材分化", "反垄断监管"],
        "headline_items": [
            "中信证券：坚定看好电子板块后续表现",
            "中信证券：银行板块步入风险周期尾部区间",
            "央行法 23 年首次大修，三大突破性亮点",
            "DeepSeek 全面扩编：处于 AGI 前夜",
            "招商银行成立市值管理小组"
        ],
        "market_implications": [
            "外围偏空施压，A 股或低开",
            "半导体主惯性仍在但需谨防分化",
            "券强银弱说明是结构性而非普涨金融",
            "央行法修订利好大金融估值修复",
            "AI/机器人主题持续催化国产替代"
        ],
        "watch_themes": [
            {"theme": "AI 算力", "reason": "DeepSeek 扩编 + 存储芯片 IPO + 资金主战场", "stocks": ["佰维存储", "北京君正", "汇成股份", "中微半导"]},
            {"theme": "半导体", "reason": "昨日板块 +2.21%，净流入 +80.68 亿，中信坚定看多", "stocks": ["帝奥微", "中微半导", "美埃科技", "兴福电子"]},
            {"theme": "券商", "reason": "板块 +3.06%，长江证券涨停，券强银弱分化", "stocks": ["长江证券"]},
            {"theme": "银行高股息", "reason": "中信判断风险周期尾部，招行市值管理小组", "stocks": ["招商银行", "中信银行"]},
            {"theme": "人形机器人", "reason": "智元灵巧手估值 10 亿美元，5 个月首季盈利", "stocks": []}
        ]
    },
    "result_payload": {
        "headline_items": [
            {"title": "中信证券：坚定看好电子板块后续表现", "impact": "positive", "affected_sectors": ["半导体", "元件", "消费电子"], "affected_stocks": ["北京君正", "佰维存储", "中微半导"]},
            {"title": "中信证券：银行板块步入风险周期尾部区间", "impact": "positive", "affected_sectors": ["银行"], "affected_stocks": ["招商银行", "中信银行"]},
            {"title": "央行法 23 年大修三大突破", "impact": "positive", "affected_sectors": ["银行", "证券", "保险"], "affected_stocks": []},
            {"title": "DeepSeek 全面扩编：处于 AGI 前夜", "impact": "positive", "affected_sectors": ["AI 算力", "半导体"], "affected_stocks": ["北京君正", "佰维存储"]},
            {"title": "中矿资源三年净利 90 亿目标", "impact": "positive", "affected_sectors": ["锂矿", "铜"], "affected_stocks": ["中矿资源"]},
            {"title": "霍尔木兹海峡重开，原油抹去战时涨幅", "impact": "neutral", "affected_sectors": ["石油化工", "机场航运"], "affected_stocks": ["华夏航空"]},
            {"title": "携程 Q1 净利腰斩 + 反垄断调查", "impact": "negative", "affected_sectors": ["OTA", "平台经济"], "affected_stocks": ["携程"]},
            {"title": "苹果在华再遭反垄断举报", "impact": "negative", "affected_sectors": ["苹果产业链"], "affected_stocks": []},
            {"title": "招商银行成立市值管理小组", "impact": "positive", "affected_sectors": ["银行"], "affected_stocks": ["招商银行"]},
            {"title": "第 12 批国家药品集采启动（65 个品种）", "impact": "negative", "affected_sectors": ["仿制药", "医药流通"], "affected_stocks": []}
        ],
        "market_implications": [
            "外围美股震荡 + 中概普跌 -1%~-5%，预计今日 A 股小幅低开",
            "日韩早盘 -2% 形成情绪传导，开盘 30 分钟是关键观察窗",
            "昨日半导体 + 元件 + 通信设备合计净流入 266 亿，主线仍在惯性中",
            "券强 (+3.06%) 银弱 (-0.66%) 是结构性而非普涨金融行情",
            "央行法修订利好大金融板块估值修复，是中期积极信号",
            "AI/机器人主题持续获得事件催化，国产替代逻辑强化"
        ],
        "watch_themes": [
            {"theme": "AI 算力/存储", "reason": "DeepSeek 全面扩编 + 时创意 IPO 净利 +18 倍 + 昨日资金主战场", "stocks": ["佰维存储", "北京君正", "汇成股份", "中微半导", "兴福电子"]},
            {"theme": "半导体设备/材料", "reason": "中信坚定看多，板块 +2.21%，净流入 +80.68 亿", "stocks": ["帝奥微", "中微半导", "美埃科技"]},
            {"theme": "券商", "reason": "板块 +3.06% + 长江证券涨停 + 央行法修订利好", "stocks": ["长江证券"]},
            {"theme": "银行高股息", "reason": "中信判断风险周期尾部 + 招行主动市值管理", "stocks": ["招商银行", "中信银行"]},
            {"theme": "人形机器人", "reason": "智元灵巧手 5 个月估值 10 亿美元首季盈利", "stocks": []},
            {"theme": "机场航运", "reason": "布伦特回调 + 板块昨日 +4.05% + 华夏航空涨停", "stocks": ["华夏航空"]},
            {"theme": "锂铜资源", "reason": "中矿资源三年净利 90 亿目标 + 铜冠铜箔 17 倍神话", "stocks": ["中矿资源"]}
        ]
    },
    "raw_output": raw_output
}

with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

print(f"Written: {filepath}")
print(f"Size: {len(json.dumps(payload, ensure_ascii=False))} bytes")