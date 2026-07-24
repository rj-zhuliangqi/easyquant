import json

raw_html = """<h2>📊 14:50 尾盘盘面快照（2026-06-24）</h2>
<p>三大指数收盘出现明显分化：<b>指数上涨但市场赚钱效应较弱</b>。全市场涨跌家数 <span class="up">1348</span> : <span class="down">3822</span>，涨停 <span class="limit-up">147</span> 家，跌停 <span class="limit-down">15</span> 家。<b>半导体产业链一枝独秀</b>，构成今日资金主战场。</p>

<div class="alert-good">尾盘 14:50 时点资金强吸 <span class="sector">半导体</span> 板块净流入 <span class="inflow">+303.73亿</span>，<span class="sector">消费电子</span> 净流入 <span class="inflow">+114.71亿</span>，板块龙头悉数封死涨停，呈现典型「主线极致+其他熄火」格局。</div>

<hr>

<h2>🔥 行业涨幅榜 TOP 10</h2>
<table>
<tr><th>排名</th><th>板块</th><th>涨跌幅</th></tr>
<tr><td>1</td><td><span class="sector">能源金属</span></td><td><span class="up">+4.27%</span></td></tr>
<tr><td>2</td><td><span class="sector">半导体</span></td><td><span class="up">+3.46%</span></td></tr>
<tr><td>3</td><td><span class="sector">元件</span></td><td><span class="up">+2.89%</span></td></tr>
<tr><td>4</td><td><span class="sector">电子化学品</span></td><td><span class="up">+2.88%</span></td></tr>
<tr><td>5</td><td><span class="sector">化学纤维</span></td><td><span class="up">+1.14%</span></td></tr>
<tr><td>6</td><td><span class="sector">军工电子</span></td><td><span class="up">+0.69%</span></td></tr>
<tr><td>7</td><td><span class="sector">消费电子</span></td><td><span class="up">+0.49%</span></td></tr>
<tr><td>8</td><td><span class="sector">医疗服务</span></td><td><span class="up">+0.38%</span></td></tr>
<tr><td>9</td><td><span class="sector">光学光电子</span></td><td><span class="up">+0.35%</span></td></tr>
<tr><td>10</td><td><span class="sector">其他电子</span></td><td><span class="up">+0.09%</span></td></tr>
</table>

<h3>📉 行业跌幅榜（避雷）</h3>
<p><span class="sector">影视院线</span> <span class="down">-4.67%</span>、<span class="sector">旅游酒店</span> <span class="down">-3.94%</span>、<span class="sector">煤炭开采</span> <span class="down">-3.58%</span>、<span class="sector">房地产</span> <span class="down">-3.30%</span>、<span class="sector">多元金融</span> <span class="down">-3.18%</span> ——<b>消费、地产、周期、低位题材集体杀跌</b>，存量资金抽水主线。</p>

<hr>

<h2>💰 行业净流入榜（资金真实流向）</h2>
<table>
<tr><th>排名</th><th>板块</th><th>净流入</th></tr>
<tr><td>1</td><td><span class="sector">半导体</span></td><td><span class="inflow">+303.73亿</span></td></tr>
<tr><td>2</td><td><span class="sector">消费电子</span></td><td><span class="inflow">+114.71亿</span></td></tr>
<tr><td>3</td><td><span class="sector">能源金属</span></td><td><span class="inflow">+32.49亿</span></td></tr>
<tr><td>4</td><td><span class="sector">计算机设备</span></td><td><span class="inflow">+27.60亿</span></td></tr>
<tr><td>5</td><td><span class="sector">电子化学品</span></td><td><span class="inflow">+25.93亿</span></td></tr>
<tr><td>6</td><td><span class="sector">光学光电子</span></td><td><span class="inflow">+21.39亿</span></td></tr>
<tr><td>7</td><td><span class="sector">元件</span></td><td><span class="inflow">+15.90亿</span></td></tr>
<tr><td>8</td><td><span class="sector">医疗服务</span></td><td><span class="inflow">+12.65亿</span></td></tr>
</table>

<div class="alert-good">全市场净流出 <span class="outflow">-687亿</span>，但 <b>半导体一个板块吸金 303 亿，占主线全部资金 70% 以上</b>。这是典型「抱团式主升」，明日延续概率高，但需提防尾盘获利盘抛压。</div>

<hr>

<h2>🎯 选股逻辑（14:50 尾盘承接）</h2>
<p>尾盘选股核心要解决两个问题：<b>① 谁还能涨</b>，<b>② 次日如何应对</b>。今日盘面给出非常清晰的答案：</p>
<ol>
<li><b>主线已经明牌</b>：<span class="tag">半导体</span> <span class="tag">存储</span> <span class="tag">封测</span> <span class="tag">设备</span> <span class="tag">材料</span> 全产业链共振，板块净流入 303 亿，<b>主升仍在初期</b>。</li>
<li><b>排除高位接力风险</b>：<span class="stock">臻宝科技</span> 单日 <span class="up">+1100%</span> 属于新股/重组高溢价个例，不可类比常规龙头。</li>
<li><b>优选龙头+次龙头组合</b>：避开烂板/连板高位股，选今日<b>首次封板放量</b>或<b>大涨未封板</b>的核心标的，<b>明日预期：高开承接、再次冲板或主升延续</b>。</li>
<li><b>规避领域</b>：消费、地产、周期、低位中小盘——资金抽离明显。</li>
</ol>

<hr>

<h2>🌟 候选股票池（按确定性排序）</h2>
<h3>🥇 强推（次日高开承接预期）</h3>
<p><b><span class="stock">立讯精密 (002475)</span></b>：消费电子龙头/AI 硬件 + 苹果链 + 服务器电源链。今日 <span class="up">+8.04%</span>，净流入 <span class="inflow">+47.12亿</span>（全市场 TOP1），成交 <span class="highlight">286.60亿</span>，换手 5.38%。<b>未封板放量主升，明日续涨概率极高</b>。</p>
<p><b><span class="stock">中芯国际 (688981)</span></b>：晶圆代工龙头/国产替代核心资产。今日 <span class="up">+6.82%</span>，净流入 <span class="inflow">+30.67亿</span>，成交 <span class="highlight">198.80亿</span>。<b>北向+机构合力，权重股带动板块</b>。</p>
<p><b><span class="stock">通富微电 (002156)</span></b>：封测三巨头，AMD 唯一国内合作方/AI 算力封装。今日 <span class="up">+8.26%</span>，净 <span class="inflow">+19.61亿</span>，换手 12.61%。<b>板块内同行（长电、深科技）皆涨停，明日补涨概率大</b>。</p>
<p><b><span class="stock">深科技 (000021)</span></b>：封测+存储双题材。今日 <span class="limit-up">涨停</span>，净 <span class="inflow">+16.40亿</span>，成交 <span class="highlight">91.22亿</span>，换手 12.08%。<b>首板放量封死，明日有冲二板预期</b>。</p>

<h3>🥈 确认（板块共振+龙二接力）</h3>
<p><b><span class="stock">长电科技 (600584)</span></b>：封测全球 TOP3，A 股封测一哥。今日 <span class="limit-up">涨停</span>，成交 <span class="highlight">236.75亿</span>（板块第一），净 <span class="inflow">+13.00亿</span>，换手 14.31%。<b>高换手封板，明日波动加大但仍是龙头主线</b>。</p>
<p><b><span class="stock">兆易创新 (603986)</span></b>：存储设计龙头。今日 <span class="up">+8.48%</span>，成交 <span class="highlight">363.03亿</span>（板块最大），净 <span class="inflow">+12.04亿</span>。<b>资金分歧但日内强势，明日如能站稳即可顺势接力</b>。</p>

<h3>🥉 候选（产业链扩散+二线弹性）</h3>
<p><b><span class="stock">海光信息 (688041)</span></b>：国产 CPU/GPU 龙头。今日 <span class="up">+5.58%</span>，净 <span class="inflow">+13.07亿</span>，<b>换手仅 1.82%，机构筹码锁定良好</b>，明日有补涨空间。</p>
<p><b><span class="stock">天华新能 (300390)</span></b>：锂矿/锂电正极上游，板块仅次于半导体的反弹主线。今日 <span class="up">+12.19%</span> 直接涨停，净 <span class="inflow">+13.22亿</span>，<b>能源金属板块涨幅 +4.27% 居首，明日有望延续修复行情</b>。</p>

<hr>

<h2>⚠️ 风险提示</h2>
<div class="risk-box">
<b>1. 主线过热风险</b>：半导体已连续主升，<span class="stock">长电科技</span>/<span class="stock">兆易创新</span> 单日成交均超 200 亿，<b>明日如出现大幅高开（+5% 以上）需警惕一日游</b>。<br>
<b>2. 系统性风险</b>：跌停 <span class="limit-down">15</span> 家，跌停股多集中在消费、地产、低位题材。<b>全市场净流出 687 亿</b>，存量资金博弈下，<b>非主线票应坚决回避</b>。<br>
<b>3. 高位接力风险</b>：<span class="stock">臻宝科技</span> +1100% 属于特殊个例，<span class="stock">聚辰股份</span> <span class="up">+20%</span>、<span class="stock">宏景科技</span> <span class="up">+20%</span>、<span class="stock">一博科技</span> <span class="up">+19.99%</span> 等 20cm 涨停股<b>明日波动率极大，不建议尾盘追买</b>。<br>
<b>4. 仓位建议</b>：建议 <b>3-5 成仓位</b>，集中在 1-2 只主线龙头，分散度控制在 3 只以内；<b>明日若高开 3% 以上，可考虑兑现一部分</b>；若平开或低开承接，可加仓持有。
</div>

<hr>

<h2>📝 操作策略（次日预期）</h2>
<ol>
<li><b>开盘观察</b>：重点关注 <span class="stock">立讯精密</span>、<span class="stock">中芯国际</span> 开盘竞价，<b>高开 3% 以内为最佳承接窗口</b>。</li>
<li><b>主线确认</b>：09:30-10:00 观察半导体板块整体表现，若板块涨幅 +1.5% 以上则确认延续，可加仓主线票。</li>
<li><b>止盈纪律</b>：龙头股若早盘冲高超 <span class="up">+5%</span>，<b>建议止盈 1/2</b>；尾盘如再次走强可回补。</li>
<li><b>止损纪律</b>：买入后若跌破 <b>-3%</b> 或板块跌幅扩大至 -1.5% 以下，<b>无条件止损</b>。</li>
<li><b>核心仓位</b>：建议组合 = 50% <span class="stock">立讯精密</span>/<span class="stock">中芯国际</span> + 30% <span class="stock">通富微电</span>/<span class="stock">深科技</span> + 20% <span class="stock">海光信息</span>/<span class="stock">天华新能</span>。</li>
</ol>
"""

payload = {
    "trading_date": "2026-06-24",
    "skill_name": "14:50 尾盘选股",
    "job_name": "14:50 尾盘选股",
    "job_type": "stock_pick",
    "run_type": "production",
    "source_input_ref": "claude-code-cli",
    "_meta": {
        "schema_version": "3.0",
        "engine_type": "claude-code",
        "data_sources_used": [
            "prefetched_market_data:/tmp/easyquant_market_data_2026-06-24.json",
            "eastmoney:sector_rankings",
            "eastmoney:individual_rankings",
            "eastmoney:limit_up_pool"
        ]
    },
    "summary": {
        "market_phase": "主线极致分化：半导体一枝独秀+大部分板块杀跌",
        "hot_sectors": [
            {"name": "半导体", "change_pct": 3.46, "net_inflow_yi": 303.73, "rank": 1},
            {"name": "消费电子", "change_pct": 0.49, "net_inflow_yi": 114.71, "rank": 2},
            {"name": "能源金属", "change_pct": 4.27, "net_inflow_yi": 32.49, "rank": 3},
            {"name": "电子化学品", "change_pct": 2.88, "net_inflow_yi": 25.93, "rank": 4},
            {"name": "元件", "change_pct": 2.89, "net_inflow_yi": 15.90, "rank": 5}
        ],
        "risk_signals": [
            "全市场净流出-687亿,跌停15家,跌:涨=3822:1348,赚钱效应弱",
            "影视/旅游/地产/煤炭/多元金融集体跌超3%,杀跌资金抽水主线",
            "20cm涨停股(聚辰/宏景/一博/精测)已属于高位接力,次日波动大",
            "半导体连续主升,部分龙头单日成交超200亿,需防获利盘抛压"
        ]
    },
    "result_payload": {
        "structured_picks": [
            {
                "stock_code": "002475",
                "stock_name": "立讯精密",
                "pick_level": "strong_recommend",
                "reason_summary": "消费电子+AI硬件双轮驱动,全市场资金净流入TOP1,放量主升未封板",
                "reason_detail": "今日收涨+8.04%,成交286.60亿,净流入47.12亿(全A第1),换手5.38%。苹果产业链核心+AI服务器电源/液冷+折叠屏新机周期。半导体/消费电子板块共振下,作为消费电子绝对龙头,明日具备高开承接基础,且未封板留有上行空间。机构-北向合力,主线第一龙头确认。",
                "sector_name": "消费电子",
                "theme_tags": ["苹果产业链", "AI硬件", "服务器电源", "消费电子龙头", "折叠屏"],
                "capital_profile": {"net_inflow": 47.12, "main_force_signal": "strong", "turnover_pct": 5.38, "amount_yi": 286.60},
                "signal_context": "板块净流入114亿(消费电子第二)+立讯个股净47亿,主升中段未封板,明日高开3%以内为最佳承接位",
                "risk_flags": ["权重票波动可控但弹性有限", "若大盘指数高开冲高回落需警惕"],
                "entry_hint": "次日开盘竞价高开0-3%承接,跌破-3%止损,冲高+5%以上止盈1/2",
                "confidence_score": 0.88
            },
            {
                "stock_code": "688981",
                "stock_name": "中芯国际",
                "pick_level": "strong_recommend",
                "reason_summary": "晶圆代工龙头+国产替代核心,板块权重股带动,机构筹码稳定",
                "reason_detail": "今日收涨+6.82%,成交198.80亿,净流入30.67亿,换手6.64%,价151.37元。作为A股半导体最大权重股,在国产替代逻辑+AI算力需求双重催化下,资金抱团特征明显。板块净流入303亿背景下,权重股龙头明日有进一步催涨指数空间,确定性最高。",
                "sector_name": "半导体",
                "theme_tags": ["晶圆代工", "国产替代", "AI芯片代工", "权重龙头"],
                "capital_profile": {"net_inflow": 30.67, "main_force_signal": "strong", "turnover_pct": 6.64, "amount_yi": 198.80},
                "signal_context": "半导体板块净流入303亿+个股净30亿,机构持续加仓,明日预期续涨3-6%",
                "risk_flags": ["大权重股弹性低于二线题材", "若指数回落则承压"],
                "entry_hint": "次日竞价高开0-3%承接,目标位+5-8%,止损-3%",
                "confidence_score": 0.85
            },
            {
                "stock_code": "002156",
                "stock_name": "通富微电",
                "pick_level": "strong_recommend",
                "reason_summary": "封测三巨头+AMD唯一国内合作伙伴,同板块涨停补涨预期强",
                "reason_detail": "今日收涨+8.26%,成交137.92亿,净流入19.61亿,换手12.61%,价74.07元。封测板块当日多家涨停(长电/华天/深科技/甬矽),通富作为AMD CPU/GPU封装核心代工方,直接受益AI算力扩产周期。今日未涨停但放巨量,明日补涨封板概率极高。",
                "sector_name": "半导体(封测)",
                "theme_tags": ["半导体封测", "AMD合作", "AI算力封装", "Chiplet"],
                "capital_profile": {"net_inflow": 19.61, "main_force_signal": "strong", "turnover_pct": 12.61, "amount_yi": 137.92},
                "signal_context": "板块同行长电/深科技/华天涨停形成共振,通富未封板存在补涨预期,换手12%筹码活跃",
                "risk_flags": ["高换手筹码不稳", "封板前波动较大"],
                "entry_hint": "次日竞价高开2-5%承接,首选缺口回补点位,止损-3.5%",
                "confidence_score": 0.83
            },
            {
                "stock_code": "000021",
                "stock_name": "深科技",
                "pick_level": "strong_recommend",
                "reason_summary": "封测+存储双题材首板涨停,净流入板块第一,二板预期",
                "reason_detail": "今日收报涨停+10.00%,成交91.22亿,净流入16.40亿(涨停股中TOP1),换手12.08%,价50.27元。封测/存储双线题材,中国电子集团旗下国资背景,机构关注度高。今日首板放量封死,资金共识强,明日有冲击二板预期,即使开板也具备承接基础。",
                "sector_name": "半导体(封测/存储)",
                "theme_tags": ["半导体封测", "存储模组", "国资改革", "中国电子"],
                "capital_profile": {"net_inflow": 16.40, "main_force_signal": "strong", "turnover_pct": 12.08, "amount_yi": 91.22},
                "signal_context": "首板放量封死+板块共振,二板逻辑顺畅,次日竞价价格区间53-55元",
                "risk_flags": ["首板二板转换率约40%,如开板需快速判断", "高换手需警惕主力出货"],
                "entry_hint": "次日竞价高开3-7%可承接(对应价51.8-53.8元),开板若快速回封可继续持有,无法回封则止损出局",
                "confidence_score": 0.78
            },
            {
                "stock_code": "600584",
                "stock_name": "长电科技",
                "pick_level": "confirm",
                "reason_summary": "封测A股一哥,涨停板成交全板块第一,高换手分歧封板",
                "reason_detail": "今日收报涨停+10.00%,成交236.75亿(板块第一),净流入13.00亿,换手14.31%,价94.7元。封测板块全球TOP3、A股绝对龙头。今日成交巨量封板说明资金存在分歧,但仍以多头力量为主。明日预期波动较大,但作为板块龙头不会轻易破位。",
                "sector_name": "半导体(封测)",
                "theme_tags": ["半导体封测", "全球TOP3", "板块龙头"],
                "capital_profile": {"net_inflow": 13.00, "main_force_signal": "strong", "turnover_pct": 14.31, "amount_yi": 236.75},
                "signal_context": "涨停成交236亿(板块第一)显示资金高度博弈,明日二板/分歧/补跌三种走势均可能,顺势而为",
                "risk_flags": ["高换手筹码涣散", "二板成功率受大盘影响大", "高位股波动剧烈"],
                "entry_hint": "次日竞价低开-1~+2%承接,如直接冲板则放弃追涨;开板回落则止损-3%",
                "confidence_score": 0.72
            },
            {
                "stock_code": "603986",
                "stock_name": "兆易创新",
                "pick_level": "confirm",
                "reason_summary": "存储设计龙头,巨量成交,日内强势但未封板,明日可顺势承接",
                "reason_detail": "今日收涨+8.48%,成交363.03亿(板块最大),净流入12.04亿,换手8.16%,价695.37元。存储设计绝对龙头,NOR Flash全球前三,DRAM/MCU产品线齐全。AI存力需求+HBM国产化双驱动,机构持仓密集。今日巨量未封板,资金分歧但情绪仍偏强。",
                "sector_name": "半导体(存储设计)",
                "theme_tags": ["存储芯片", "NOR Flash", "DRAM", "HBM", "AI存力"],
                "capital_profile": {"net_inflow": 12.04, "main_force_signal": "moderate", "turnover_pct": 8.16, "amount_yi": 363.03},
                "signal_context": "巨量未封板存在两种解读:获利盘+主升中继,需结合次日开盘判断;板块整体强势支撑下,中位预期+2-5%",
                "risk_flags": ["巨量未封板存在头部嫌疑", "高价股波动金额大", "次日如低开-2%以上需警惕"],
                "entry_hint": "次日开盘+2%以内可承接,以涨停价(764.9)的95%(727)为短线目标,止损-3.5%",
                "confidence_score": 0.70
            },
            {
                "stock_code": "688041",
                "stock_name": "海光信息",
                "pick_level": "candidate",
                "reason_summary": "国产CPU/GPU龙头,机构锁仓筹码稳定,补涨弹性强",
                "reason_detail": "今日收涨+5.58%,成交137.52亿,净流入13.07亿,换手仅1.82%(板块最低),价334.69元。国产CPU/DCU(类GPU)双龙头,中科曙光体系。今日涨幅落后于板块,但筹码极度稳定(换手1.82%),机构未减仓。明日如板块持续走强,具备补涨条件。",
                "sector_name": "半导体(设计)",
                "theme_tags": ["国产CPU", "DCU/GPU", "AI算力芯片", "信创"],
                "capital_profile": {"net_inflow": 13.07, "main_force_signal": "moderate", "turnover_pct": 1.82, "amount_yi": 137.52},
                "signal_context": "换手1.82%为板块最低,机构锁筹完美;主线扩散到设计端时该股弹性最大",
                "risk_flags": ["未涨停说明短线资金关注度不及封测", "高价股弹性需要题材发酵配合"],
                "entry_hint": "次日竞价开盘+0-2%承接,目标位+5-8%,持仓周期2-3日,止损-3%",
                "confidence_score": 0.68
            },
            {
                "stock_code": "300390",
                "stock_name": "天华新能",
                "pick_level": "candidate",
                "reason_summary": "锂矿/锂电上游反弹龙头,能源金属板块涨幅居首",
                "reason_detail": "今日收涨+12.19%涨停,成交69.40亿,净流入13.22亿,换手11.05%,价98.31元。能源金属板块涨幅+4.27%排名全市场第一,锂电产业链在底部蛰伏数月后迎来反弹。天华新能锂矿+正极材料布局完整,弹性大。注意此为板块反弹而非半导体主线,定位为多元化配置标的。",
                "sector_name": "能源金属(锂)",
                "theme_tags": ["锂矿", "碳酸锂", "锂电池上游", "新能源反弹"],
                "capital_profile": {"net_inflow": 13.22, "main_force_signal": "moderate", "turnover_pct": 11.05, "amount_yi": 69.40},
                "signal_context": "锂电板块超跌反弹首日,板块涨4.27%但持续性待观察,作为对冲半导体仓位的弹性补充",
                "risk_flags": ["锂电反弹持续性不确定,需关注次日板块跟随度", "若板块次日不能延续则容易冲高回落", "20cm非主板品种波动大"],
                "entry_hint": "次日竞价高开3-7%承接,如锂电板块整体走弱则放弃,严格止损-4%",
                "confidence_score": 0.62
            }
        ]
    },
    "raw_output": raw_html
}

out_path = '/Users/jwkj/easyquant/data/ai_center/inbox/1450_尾盘选股_2026-06-24_20260624_145024.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

import os
print(f'Written: {out_path}')
print(f'Size: {os.path.getsize(out_path)} bytes')

# Validate JSON & required fields
with open(out_path, encoding='utf-8') as f:
    reloaded = json.load(f)
print('Valid JSON. Picks count:', len(reloaded['result_payload']['structured_picks']))
required = ['stock_code','stock_name','pick_level','reason_summary','reason_detail','sector_name','theme_tags','capital_profile','signal_context','risk_flags','entry_hint','confidence_score']
for p in reloaded['result_payload']['structured_picks']:
    missing = [k for k in required if k not in p]
    assert not missing, f"missing {missing} in {p['stock_code']}"
    assert p['theme_tags'], 'theme_tags empty'
    assert p['risk_flags'], 'risk_flags empty'
    assert p['capital_profile'], 'capital_profile empty'
print('All 12 required fields present in every pick.')
