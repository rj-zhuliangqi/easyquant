"""构建 2030_ST股挖掘_2026-06-30_20260630_203022.json"""
import json
import os

structured_picks = [
    {
        "stock_code": "002175",
        "stock_name": "*ST东智",
        "pick_level": "confirm",
        "reason_summary": "6/30复牌叠加控股股东变更落地,主板ST首日封板+5.12%,成交活跃,重组题材兑现窗口",
        "reason_detail": "公司公告显示,控股股东科翔高新拟转让14.76%股份,股票6月30日复牌。今日开盘后迅速封住主板ST涨停(+5.12%,封顶),收盘价2.26元。属于'复牌+控制权变更+首日封板'三重催化共振,日内题材兑现度高。风险在于主板ST 5%上限弹性有限,需观察次日是否连板;新股东入主后业务重整路径尚不明朗。",
        "sector_name": "ST板块",
        "theme_tags": ["控制权变更", "复牌首日", "重组预期", "主板ST"],
        "capital_profile": {
            "net_inflow": -3066300.0,
            "main_force_signal": "moderate",
            "st_type": "*ST",
            "delist_risk": "中",
        },
        "signal_context": "控股权变更(科翔高新拟转让14.76%)+ 复牌首日 + 主板ST涨停价 2.26元(5%上限)",
        "risk_flags": ["ST风险", "重组失败风险", "新股东业务路径不明", "5%涨跌幅限制弹性低"],
        "entry_hint": "次日开盘不追涨,观察 2.20-2.30 元承接;若回踩 5 日均线企稳可小仓介入,跌破 2.10 元止损",
        "confidence_score": 0.62,
    },
    {
        "stock_code": "300044",
        "stock_name": "*ST赛为",
        "pick_level": "candidate",
        "reason_summary": "创业板ST +17.29% 强势封板,主力净流入 1987万,弹性最大且为板块今日涨幅龙头",
        "reason_detail": "创业板 ST 涨跌停限制 20%,为 ST 板块内最大弹性品种。今日 *ST赛为 收盘 5.02 元,涨幅 +17.29%(逼近 20% 涨停),主力净流入约 +1987 万元,在 ST 板块涨幅榜居前(仅次于 ST 银江 +20%)。今日 ST 板块指数 +0.78% 整体走平,该股逆势走强说明资金在板块内部出现明显分化,资金集中流向少数高弹性标的。需注意创业板 ST 个股退市风险等级普遍较高,务必控制仓位。",
        "sector_name": "ST板块",
        "theme_tags": ["创业板ST", "高弹性", "资金流入", "智能机器"],
        "capital_profile": {
            "net_inflow": 19875100.0,
            "main_force_signal": "strong",
            "st_type": "*ST",
            "delist_risk": "高",
        },
        "signal_context": "创业板ST涨幅榜前列 + 主力净流入 +1987万 + 板块龙头属性",
        "risk_flags": ["ST风险", "创业板20%涨跌停高波动", "退市风险", "题材降温风险"],
        "entry_hint": "创业板 ST 波动剧烈,建议仅在次日平开或小幅低开(回踩 4.80 元附近)小仓博弈,跌破 4.50 元坚决止损",
        "confidence_score": 0.55,
    },
    {
        "stock_code": "603559",
        "stock_name": "*ST通脉",
        "pick_level": "candidate",
        "reason_summary": "7月2日起撤销其他风险警示(摘帽),涨跌幅限制由5%变10%,摘帽套利窗口明确",
        "reason_detail": "公司公告明确:'7月2日起复牌并撤销其他风险警示,股票简称变更为中通国脉'。这意味着摘帽前后会有:1)估值修复(机构可买入);2)涨跌幅限制由 5% 扩大至 10%(弹性翻倍);3)ST 标签资金松绑。今日股价 8.19 元,涨 +5.00% 封住 5% 上限,说明已有先知资金潜伏。可博弈摘帽兑现日的'修复性跳空',但需警惕利好兑现即出货。",
        "sector_name": "ST板块",
        "theme_tags": ["摘帽兑现", "5%变10%弹性扩张", "通信工程", "复牌"],
        "capital_profile": {
            "net_inflow": -2430900.0,
            "main_force_signal": "weak",
            "st_type": "*ST(7月2日摘帽)",
            "delist_risk": "低",
        },
        "signal_context": "摘帽时点确定(7/2) + 涨跌幅 5%→10% + 简称变更 + 今日封 5% 上限",
        "risk_flags": ["ST风险", "摘帽兑现即出货风险", "历史经验套利空间有限"],
        "entry_hint": "摘帽前一日(7月1日)尾盘或摘帽当日(7月2日)开盘博弈弹性扩张,建议轻仓为主,设 7.80 元为止损",
        "confidence_score": 0.58,
    },
    {
        "stock_code": "300301",
        "stock_name": "ST长方",
        "pick_level": "watch",
        "reason_summary": "创业板ST +7.80% 延续强势,主力净流入 2703万,6/27已观察到候选池,跟踪趋势延续",
        "reason_detail": "今日收盘 3.87 元,涨 +7.80%(未封 20% 涨停,但相对 5% 主板 ST 已是 4 倍弹性),主力净流入约 +2702 万元。6/27 AI 已纳入候选池,理由为'摘帽预期+主力资金净流入板块第一'。今日继续放量上行,显示趋势仍在延续。但需注意创业板 ST 个股波动大,且该股未传出明确摘帽公告,主题催化偏弱,建议保持观察而非追涨。",
        "sector_name": "ST板块",
        "theme_tags": ["创业板ST", "趋势延续", "光学跨界", "资金流入"],
        "capital_profile": {
            "net_inflow": 27029200.0,
            "main_force_signal": "moderate",
            "st_type": "ST",
            "delist_risk": "中",
        },
        "signal_context": "创业板ST +7.80% + 主力净流入 +2703万 + 6/27已在候选池",
        "risk_flags": ["ST风险", "无明确摘帽催化", "创业板高波动"],
        "entry_hint": "仅作跟踪观察,3.60-3.80 元区间缩量回踩时小仓介入,跌破 3.50 元止损",
        "confidence_score": 0.50,
    },
    {
        "stock_code": "000056",
        "stock_name": "*ST皇庭",
        "pick_level": "watch",
        "reason_summary": "连续两日 +5% 上限(6/27+5.08%、今日+5.07%),技术面温和走强,但主力净流出 1985万警示兑现",
        "reason_detail": "今日收盘 2.28 元,涨 +5.07% 封住主板 ST 涨停价,连续两个交易日累计涨幅超 10%,中期上行趋势明确。但需要警惕:1)今日主力净流出 -1985 万元,与 6/27 当日主力净流入的格局相反,显示资金面出现兑现迹象;2)股价绝对价位低(2.28 元),虽远离面值退市红线(1.00 元),但弹性受限;3)历史上 ST 股连续两日封板后第三日分歧概率高。",
        "sector_name": "ST板块",
        "theme_tags": ["连续涨停", "低价ST", "资金背离"],
        "capital_profile": {
            "net_inflow": -19854500.0,
            "main_force_signal": "weak",
            "st_type": "*ST",
            "delist_risk": "中",
        },
        "signal_context": "连续两日 +5% 涨停 + 主力净流出 -1985万(兑现迹象) + 中期趋势温和",
        "risk_flags": ["ST风险", "主力资金背离", "5%涨跌幅弹性低", "面值退市担忧"],
        "entry_hint": "仅观察,不建议追涨;若回踩 2.10 元(5日均线)不破可小仓,跌破 2.00 元止损",
        "confidence_score": 0.40,
    },
]

raw_output = (
    '<h2>ST 方向主题催化与风格观察 (2026-06-30 盘后)</h2>\n'
    '<h3>一、市场整体风格</h3>\n'
    '<p>今日 A 股呈现 <b>小盘成长强、价值偏弱</b> 的明显分化格局,'
    '主要指数收盘:</p>\n'
    '<table>\n'
    '<tr><th>指数</th><th>涨跌幅</th><th>风格特征</th></tr>\n'
    '<tr><td>创业板指</td><td><span class="up">+2.99%</span></td><td>高弹性小盘成长</td></tr>\n'
    '<tr><td>中证 500</td><td><span class="up">+2.38%</span></td><td>中小盘普涨</td></tr>\n'
    '<tr><td>沪深 300</td><td><span class="up">+1.07%</span></td><td>权重蓝筹温和</td></tr>\n'
    '<tr><td>上证指数</td><td><span class="up">+0.50%</span></td><td>主板窄幅</td></tr>\n'
    '<tr><td>上证 50</td><td><span class="down">-0.06%</span></td><td>大盘价值偏弱</td></tr>\n'
    '<tr><td>深证成指</td><td><span class="down">-0.80%</span></td><td>深市整体偏弱</td></tr>\n'
    '</table>\n'
    '<p>结论:今日 <b>风险偏好显著回升</b>,资金从小盘成长风格涌入,'
    '这种环境对 ST 板块中的 <span class="tag">创业板 ST</span> '
    '<span class="tag">小市值摘帽博弈</span> 标的相对友好。</p>\n'
    '<hr>\n'
    '<h3>二、ST 板块整体表现</h3>\n'
    '<p>ST 板块指数收盘 <span class="highlight">459.547</span>,'
    '涨幅 <span class="up">+0.78%</span>,'
    '主力净流出 <span class="outflow">-2.08亿</span>。</p>\n'
    '<p>板块内部呈现 <b>"少数标的暴涨 + 多数标的滞涨"</b> 的极端分化:</p>\n'
    '<ul>\n'
    '<li>涨幅榜前列(>5%): <span class="stock">ST银江</span> '
    '<span class="limit-up">+20.00%</span>、'
    '<span class="stock">*ST赛为</span> <span class="limit-up">+17.29%</span>、'
    '<span class="stock">*ST天宜</span> +8.82%、'
    '<span class="stock">ST臻镭</span> +7.94%、'
    '<span class="stock">ST长方</span> +7.80%</li>\n'
    '<li>跌停/暴跌: <span class="stock">ST荃银</span> '
    '<span class="limit-down">-20.06%</span>、'
    '<span class="stock">ST荣科</span> '
    '<span class="limit-down">-19.98%</span>、'
    '<span class="stock">*ST宝实</span> '
    '<span class="limit-down">-4.98%</span>(逼近跌停)</li>\n'
    '<li>封板家数(主板 ≥5% / 创业板 ≥20%): 约 <b>30 只</b>,'
    '较昨日(6/27)显著增加</li>\n'
    '</ul>\n'
    '<p>资金面信号:板块整体净流出但内部分化严重,'
    '<b>资金集中流向高弹性创业板 ST 与摘帽兑现标的</b>,'
    '传统低价 ST 反而呈现资金背离。</p>\n'
    '<hr>\n'
    '<h3>三、核心主题催化</h3>\n'
    '<div class="alert-good">'
    '<h4>摘帽催化(最确定)</h4>'
    '<ul>'
    '<li><b>*ST亚振</b>: 7月1日撤销退市风险警示,简称变更为"亚振家居"</li>'
    '<li><b>*ST大晟</b>: 7月1日撤销退市风险警示,简称变更为"大晟文化"</li>'
    '<li><b>*ST艾艾</b>: 7月1日撤销退市风险警示,简称变更为"艾艾精工"</li>'
    '<li><b>*ST通脉</b>: 7月2日起撤销其他风险警示,简称变更为"中通国脉",'
    '涨跌幅由 5% 变 10%</li>'
    '</ul>'
    '<p>上述 4 只标的构成 7 月初 <span class="tag">摘帽兑现</span> 主线,'
    '其中 <span class="stock">*ST通脉</span> 弹性扩张幅度最大。</p>'
    '</div>\n'
    '<div class="alert-good">'
    '<h4>重组/控股权变更催化</h4>'
    '<ul>'
    '<li><b>*ST东智(002175)</b>: 控股股东科翔高新拟转让 14.76% 股份导致控制权变更,'
    '<span class="tag">6月30日复牌</span>,首日封板</li>'
    '<li><b>ST西王</b>: 部分董事高管拟增持 300-600 万元(信号偏弱)</li>'
    '<li><b>*ST京化</b>: 子公司获政府补助 3388.81 万元</li>'
    '</ul>'
    '</div>\n'
    '<div class="alert-bad">'
    '<h4>退市/利空风险</h4>'
    '<ul>'
    '<li><span class="stock">*ST天喻</span>: 实控人闫春雨被湖北证监局罚款 1350 万 + '
    '市场禁入 5 年(<span class="risk-box">实控人风险</span>)</li>'
    '<li><span class="stock">*ST瑞茂</span>: 控股股东所持股份 100% 被司法标记/冻结'
    '(今日仍封板,纯粹博弈资金)</li>'
    '<li><span class="stock">ST龙元</span>: 股价 0.92 元,'
    '<b>低于面值退市红线</b>,提示终止上市风险</li>'
    '<li><span class="stock">*ST香雪</span>: 今日大跌 2.76%,主力净流出 2359 万</li>'
    '<li><span class="stock">*ST闻泰</span>: 大跌 4.86%,主力净流出 2.32 亿,'
    '<span class="tag">前期龙头</span>降温明显</li>'
    '</ul>'
    '</div>\n'
    '<hr>\n'
    '<h3>四、5 只推荐标的速览</h3>\n'
    '<table>'
    '<tr><th>代码</th><th>名称</th><th>评级</th><th>收盘</th><th>涨幅</th><th>主力净流入</th></tr>'
    '<tr><td>002175</td><td>*ST东智</td><td><b>confirm</b></td>'
    '<td>2.26</td><td><span class="limit-up">+5.12%</span></td>'
    '<td><span class="outflow">-307万</span></td></tr>'
    '<tr><td>300044</td><td>*ST赛为</td><td><b>candidate</b></td>'
    '<td>5.02</td><td><span class="up">+17.29%</span></td>'
    '<td><span class="inflow">+1988万</span></td></tr>'
    '<tr><td>603559</td><td>*ST通脉</td><td><b>candidate</b></td>'
    '<td>8.19</td><td><span class="limit-up">+5.00%</span></td>'
    '<td><span class="outflow">-243万</span></td></tr>'
    '<tr><td>300301</td><td>ST长方</td><td><b>watch</b></td>'
    '<td>3.87</td><td><span class="up">+7.80%</span></td>'
    '<td><span class="inflow">+2703万</span></td></tr>'
    '<tr><td>000056</td><td>*ST皇庭</td><td><b>watch</b></td>'
    '<td>2.28</td><td><span class="limit-up">+5.07%</span></td>'
    '<td><span class="outflow">-1985万</span></td></tr>'
    '</table>\n'
    '<p>详细选股逻辑与买卖建议见各标的 <code>reason_detail</code> 字段。</p>\n'
    '<hr>\n'
    '<h3>五、风格观察要点</h3>\n'
    '<ol>\n'
    '<li><b>小盘成长 vs ST 板块</b>:今日创业板 +2.99% 强势,'
    'ST 板块 +0.78% 跟随,但 <span class="tag">创业板 ST</span> 个股弹性远大于主板 ST,'
    '应优先关注 300 系列 ST。</li>\n'
    '<li><b>摘帽 vs 重组</b>:7 月初摘帽兑现潮(亚振/大晟/艾艾/通脉 4 只)确定性高于重组,'
    '但弹性低于重组;可组合配置。</li>\n'
    '<li><b>资金集中度</b>:今日板块净流出 -2.08 亿但仍有 30+ 涨停,'
    '说明资金在板块内部腾挪到少数高弹性标的,'
    '<b>不可无差别扫货所有 ST,必须精选标的</b>。</li>\n'
    '<li><b>退市风险</b>:ST 龙元 0.92 元已破面值 1 元心理线,'
    '近期需高度警惕其它低价 ST(皇庭 2.28、发展 1.58、易购 1.17、'
    '美丽 1.69)。</li>\n'
    '<li><b>前期龙头回调</b>:*ST闻泰作为 6/27-6/30 的 ST 板块龙头,'
    '今日大跌 4.86%,主力净流出 2.32 亿,显示 <b>板块龙头易主</b>,'
    '下一波行情将由新标的(赛为、长方、东智)主导。</li>\n'
    '</ol>\n'
    '<hr>\n'
    '<div class="risk-box">'
    '<h3>风险提示</h3>'
    '<ul>'
    '<li><b>ST 股退市风险高</b>:不推荐持仓超过总仓位 5% 的 ST 股,'
    '单只 ST 个股仓位不超过 2%。</li>'
    '<li><b>5% / 20% 涨跌停限制</b>:主板 ST 弹性仅为主板正常股的 1/2,'
    '创业板 ST 波动是主板的 4 倍,务必严设止损。</li>'
    '<li><b>主力资金背离</b>:今日多只 ST 个股出现价格强势但主力净流出的背离信号'
    '(*ST皇庭、*ST通脉、*ST美芝),后续分歧概率高。</li>'
    '<li><b>流动性风险</b>:ST 股成交额普遍 < 1 亿,大资金进出冲击大,'
    '避免在尾盘集合竞价抢筹。</li>'
    '<li><b>政策风险</b>:交易所对 ST 股的摘星摘帽标准趋严,'
    '历史经验不可简单外推。</li>'
    '</ul>'
    '</div>\n'
    '<p style="color: gray; font-size: 0.9em;">'
    '数据来源:本地 <code>sector_fund_monitor.db</code>(individual_stock_snapshots / '
    'fund_flow_snapshots / news_items / ai_picks 历史)、'
    '腾讯财经行情 API(主要指数 + 个股实时)、'
    '巨潮资讯网公告(摘帽/重组)。'
    '运行时间 2026-06-30 20:30 (盘后)。</p>\n'
)

payload = {
    "trading_date": "2026-06-30",
    "skill_name": "ST股挖掘",
    "job_name": "20:30 ST股挖掘",
    "job_type": "stock_pick",
    "run_type": "production",
    "source_input_ref": "claude-code-cli",
    "_meta": {
        "schema_version": "3.0",
        "engine_type": "claude-code",
        "data_sources_used": [
            "local_db:individual_stock_snapshots",
            "local_db:fund_flow_snapshots",
            "local_db:news_items",
            "local_db:ai_picks(history)",
            "tencent:qt.gtimg.cn(stock+index)",
        ],
    },
    "summary": {
        "market_phase": "小盘成长强、价值偏弱;ST 板块内部分化加剧,资金集中流向高弹性创业板 ST 与摘帽兑现标的",
        "hot_sectors": [
            "ST板块",
            "创业板ST",
            "摘帽兑现",
            "控制权变更",
        ],
        "risk_signals": [
            "ST龙元低于面值退市风险",
            "*ST天喻实控人禁入",
            "*ST瑞茂控股股东100%冻结",
            "*ST闻泰前期龙头回调(-4.86%,主力净流出2.32亿)",
            "板块整体净流出-2.08亿但内部分化加剧",
        ],
    },
    "result_payload": {
        "structured_picks": structured_picks,
    },
    "raw_output": raw_output,
}

OUT = "data/ai_center/inbox/2030_ST股挖掘_2026-06-30_20260630_203022.json"
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

# 校验字段
for p in payload["result_payload"]["structured_picks"]:
    assert len(p) == 12, f"missing fields: {p}"
    assert p["theme_tags"], "theme_tags empty"
    assert p["risk_flags"], "risk_flags empty"
    assert p["capital_profile"], "capital_profile empty"

print(f"Wrote {OUT}")
print(f"Picks: {len(payload['result_payload']['structured_picks'])}")
print(f"raw_output length: {len(raw_output)}")
print(f"File size: {os.path.getsize(OUT)} bytes")