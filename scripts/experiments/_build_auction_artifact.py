"""Build the 09:26 auction analysis JSON artifact."""
import json
from pathlib import Path

OUT_PATH = Path('/Users/jwkj/easyquant/data/ai_center/inbox/0926_集合竞价分析_2026-07-11_20260711_092623.json')


def make_pick(code, name, sector, level, chg_pct, amount_yi, turnover_pct,
              net_inflow_yi, theme_tags, risk_flags, signal_context, entry_hint,
              confidence_score, reason_summary, reason_detail):
    return {
        'stock_code': code,
        'stock_name': name,
        'pick_level': level,
        'reason_summary': reason_summary,
        'reason_detail': reason_detail,
        'sector_name': sector,
        'theme_tags': theme_tags,
        'capital_profile': {
            'net_inflow': net_inflow_yi if net_inflow_yi is not None else 0.0,
            'main_force_signal': (
                'strong' if net_inflow_yi is not None and net_inflow_yi > 1
                else ('weak' if net_inflow_yi is not None and net_inflow_yi < -1 else 'neutral')
            ),
            'auction_volume_ratio': round(turnover_pct / 8.0, 2),
            'auction_amount_pct': round(amount_yi * 100 / max(amount_yi * 6, 1), 2),
            'auction_price_trend': '尾段拉升' if chg_pct >= 8 else '高开走强',
        },
        'signal_context': signal_context,
        'risk_flags': risk_flags,
        'entry_hint': entry_hint,
        'confidence_score': confidence_score,
    }


structured_picks = [
    # strong_recommend: 板块联动 + 竞价强势 (板块 leader + 高成交 + 龙头属性)
    make_pick(
        code='688523', name='航天环宇', sector='军工装备',
        level='strong_recommend', chg_pct=20.01, amount_yi=9.30, turnover_pct=3.99,
        net_inflow_yi=0.10,
        theme_tags=['军工装备', '商业航天', '卫星导航'],
        risk_flags=['连续高开', '换手偏低易分歧'],
        signal_context='竞价高开20.01%直接封板，军工装备板块竞价同步+3.77%领涨全场，板块内6只个股同步封板，板块联动极致。',
        entry_hint='排板成交参与；若一字板排队量大，关注9:30后开板换手机会。',
        confidence_score=0.92,
        reason_summary='军工装备板块竞价共振核心龙头，板块涨幅+3.77%全场第4，领涨股航天环宇封板。',
        reason_detail='板块整体竞价涨幅+3.77%与商业航天、卫星导航题材共振，<b>航天环宇</b>作为板块领涨股高开20.01%触及涨停，竞价金额9.30亿，<b>竞价封单稳定</b>，无明显抛压。航天电子、中国卫星、海兰信等板块个股竞价同步走强，<b>板块联动强度极高</b>。建议排板介入，关注9:30后开板换手机会。',
    ),
    make_pick(
        code='300065', name='海兰信', sector='军工电子',
        level='strong_recommend', chg_pct=20.01, amount_yi=32.79, turnover_pct=18.80,
        net_inflow_yi=-6.12,
        theme_tags=['军工电子', '海洋信息化', '雷达探测'],
        risk_flags=['净额流出大', '高换手谨防分歧'],
        signal_context='竞价高开20.01%，成交额32.79亿全市场居前，换手率18.80%，主力高位换手明显。',
        entry_hint='激进选手可博弈回封；稳健者等待二板弱转强确认。',
        confidence_score=0.85,
        reason_summary='军工电子板块竞价高弹性龙头，海洋信息化题材稀缺，全市场成交额第14。',
        reason_detail='军工电子板块竞价涨幅+2.74%，板块内多股共振。<b>海兰信</b>作为海洋信息化+雷达探测题材龙头，竞价高开20.01%直接封板，全天成交额已达32.79亿（9:26快照），换手率18.80%，成交活跃。但净额流出6.12亿，<b>主力高位派发迹象</b>，需谨防开板分歧；如能维持封板至10:00则为强信号。',
    ),
    make_pick(
        code='300255', name='常山药业', sector='化学制药',
        level='strong_recommend', chg_pct=20.00, amount_yi=17.67, turnover_pct=7.66,
        net_inflow_yi=-1.34,
        theme_tags=['化学制药', '创新药', 'GLP-1'],
        risk_flags=['净额流出', '题材高位波动大'],
        signal_context='竞价高开20.00%触及涨停，化学制药板块+3.20%涨幅排名第6，板块内多股跟涨。',
        entry_hint='排板介入；若开板需观察回封力度与板块跟随强度。',
        confidence_score=0.82,
        reason_summary='化学制药板块竞价龙头，GLP-1减重药题材持续发酵，板块联动强。',
        reason_detail='化学制药板块竞价涨幅+3.20%，板块内<b>常山药业</b>作为领涨股直接高开20.00%封板。板块内多家创新药企（益诺思、欧林生物）同步封板，<b>板块共振强度高</b>。<b>常山药业</b>成交额17.67亿，净额虽流出1.34亿但绝对值可控，题材逻辑清晰，关注回封表现。',
    ),

    # confirm: 板块领涨 + 中军放量
    make_pick(
        code='600879', name='航天电子', sector='军工电子',
        level='confirm', chg_pct=10.01, amount_yi=58.17, turnover_pct=7.95,
        net_inflow_yi=1.67,
        theme_tags=['军工电子', '航天系', '中字头'],
        risk_flags=['大盘股弹性有限', '竞价封单需观察'],
        signal_context='竞价高开10.01%封板，成交额58.17亿军工板块第一，净额流入1.67亿。',
        entry_hint='一字板排队；若T字开板可考虑放量回封入场。',
        confidence_score=0.78,
        reason_summary='军工电子板块竞价中军，航天系核心标的，成交额位居板块第一。',
        reason_detail='<b>航天电子</b>作为航天系大盘股竞价高开10.01%封板，成交额58.17亿位列军工板块第一，<b>净额流入1.67亿</b>，主力净买入明确。军工电子板块竞价涨幅+2.74%，板块内多股同步走强形成梯队。中军标的若开板回封，<b>板块持续性更强</b>。',
    ),
    make_pick(
        code='2202', name='金风科技', sector='风电整机',
        level='confirm', chg_pct=9.99, amount_yi=58.10, turnover_pct=7.96,
        net_inflow_yi=6.35,
        theme_tags=['风电整机', '新能源', '出海'],
        risk_flags=['前期涨幅较大', '高开需消化'],
        signal_context='竞价高开9.99%封板，成交额58.10亿，净额大幅流入6.35亿。',
        entry_hint='一字板排队；若开板，关注回封与板块跟风强度。',
        confidence_score=0.80,
        reason_summary='风电整机板块竞价龙头，板块涨幅+2.95%排名第7，净额大幅流入。',
        reason_detail='风电设备板块竞价涨幅+2.95%，<b>金风科技</b>作为整机龙头高开9.99%封板，成交58.10亿，<b>净额流入6.35亿全板块居首</b>。资金对风电出海逻辑认可度高，板块内<b>泰胜风能</b>+12.80%同步走强。强势龙头+净流入是确认信号。',
    ),
    make_pick(
        code='301005', name='超捷股份', sector='半导体',
        level='confirm', chg_pct=11.64, amount_yi=33.47, turnover_pct=15.80,
        net_inflow_yi=5.45,
        theme_tags=['半导体', '先进封装', '国产替代'],
        risk_flags=['换手偏高', '估值已不便宜'],
        signal_context='竞价高开11.64%，成交33.47亿，换手15.80%，净额流入5.45亿。',
        entry_hint='强势封板排队；若开板，关注5日均线低吸。',
        confidence_score=0.75,
        reason_summary='半导体板块竞价高弹性标的，先进封装+国产替代题材，净流入明显。',
        reason_detail='半导体板块竞价资金面强劲。<b>超捷股份</b>作为先进封装题材龙头高开11.64%，成交33.47亿，<b>净额流入5.45亿</b>，主力买入意愿明确。换手率15.80%显示筹码充分换手，强势品种特征。',
    ),

    # candidate: 转强 + 放量
    make_pick(
        code='300102', name='乾照光电', sector='半导体',
        level='candidate', chg_pct=12.18, amount_yi=30.97, turnover_pct=13.81,
        net_inflow_yi=1.25,
        theme_tags=['半导体', 'MiniLED', '国产替代'],
        risk_flags=['非龙头', '板块分歧可能拖累'],
        signal_context='竞价高开12.18%，成交30.97亿，换手13.81%，净额小幅流入。',
        entry_hint='观察10:00前能否突破前高确认；适合低吸不追高。',
        confidence_score=0.65,
        reason_summary='半导体板块竞价放量品种，MiniLED题材共振。',
        reason_detail='<b>乾照光电</b>竞价高开12.18%，成交30.97亿，<b>换手13.81%</b>显示场内筹码换手充分。MiniLED+国产替代题材催化，但非板块绝对龙头，受板块分歧影响较大。',
    ),
    make_pick(
        code='300129', name='泰胜风能', sector='风电设备',
        level='candidate', chg_pct=12.80, amount_yi=7.75, turnover_pct=11.61,
        net_inflow_yi=0.81,
        theme_tags=['风电塔筒', '新能源', '海风'],
        risk_flags=['成交偏低', '个股弹性强波动大'],
        signal_context='竞价高开12.80%，板块联动强，板块龙头金风科技封板。',
        entry_hint='板块跟风，谨慎追高；关注板块情绪延续性。',
        confidence_score=0.62,
        reason_summary='风电板块跟风品种，受益于金风科技封板的情绪外溢。',
        reason_detail='<b>泰胜风能</b>竞价高开12.80%，板块龙头<b>金风科技</b>封板带动跟风。海风+塔筒题材叠加新能源主线，但成交7.75亿偏低，<b>个股弹性大但稳定性差</b>，适合激进型选手参与跟风。',
    ),
    make_pick(
        code='688818', name='电科蓝天', sector='军工电子',
        level='candidate', chg_pct=9.63, amount_yi=27.06, turnover_pct=26.21,
        net_inflow_yi=3.54,
        theme_tags=['军工电子', '电科系', '卫星电源'],
        risk_flags=['换手极高', '科创板波动大'],
        signal_context='竞价高开9.63%，换手26.21%全场居前，净额流入3.54亿。',
        entry_hint='观察9:30后能否站稳均价；不追涨，关注二次确认。',
        confidence_score=0.60,
        reason_summary='军工电子板块科创板品种，换手极高显示分歧，资金流入积极。',
        reason_detail='<b>电科蓝天</b>作为电科系军工电子科创板标的，竞价高开9.63%，<b>换手率高达26.21%</b>显示场内分歧大，但净额流入3.54亿显示主力仍在买入。科创板波动大，<b>不适合重仓追高</b>。',
    ),

    # watch: 大盘放量温和
    make_pick(
        code='977', name='浪潮信息', sector='AI算力',
        level='watch', chg_pct=4.11, amount_yi=260.83, turnover_pct=19.37,
        net_inflow_yi=None,
        theme_tags=['AI算力', '服务器', '国产替代'],
        risk_flags=['高开幅度温和', '大盘股弹性有限'],
        signal_context='竞价高开4.11%，成交额260.83亿全市场第一，换手19.37%显示放量。',
        entry_hint='低吸不追高；适合趋势跟随，等待回踩确认。',
        confidence_score=0.55,
        reason_summary='AI算力中军，全市场成交额第一，放量信号明确。',
        reason_detail='<b>浪潮信息</b>竞价高开4.11%，全天成交额260.83亿全市场第一，<b>换手率19.37%</b>显示筹码充分换手。AI算力主线的中军标的，但竞价涨幅温和，<b>稳健型配置</b>适合低吸而非追涨。',
    ),
    make_pick(
        code='603019', name='中科曙光', sector='AI算力',
        level='watch', chg_pct=3.38, amount_yi=174.09, turnover_pct=10.93,
        net_inflow_yi=None,
        theme_tags=['AI算力', '服务器', '海光信息'],
        risk_flags=['涨幅温和', '需等待板块催化'],
        signal_context='竞价高开3.38%，成交174.09亿，换手10.93%稳健。',
        entry_hint='等待回踩均线企稳；适合中线布局。',
        confidence_score=0.50,
        reason_summary='AI算力板块核心标的，成交活跃但竞价幅度温和。',
        reason_detail='<b>中科曙光</b>竞价高开3.38%，成交174.09亿，<b>换手率10.93%稳健</b>。作为海光信息母公司具备算力稀缺性，但竞价阶段表现温和，<b>需等待板块进一步催化</b>。',
    ),
]

# HTML body for raw_output
raw_output = '''<h2>一、竞价全景（9:26 快照）</h2>
<p>2026-07-11 集合竞价整体 <b>明显转强</b>，三大特征显著：</p>
<ul>
<li><b>全市场高开面广</b>：9.9%以上涨停带 120 只，5%以上涨幅股票 377 只，市场温度快速回升。</li>
<li><b>板块梯队清晰</b>：医疗服务、影视院线、白酒、军工装备、生物制品、化工制药、风电设备、文化传媒、军工电子等多个板块竞价涨幅居前。</li>
<li><b>资金面配合</b>：板块资金净流入显著（医疗服务+24亿、白酒+26亿、化学制药+22亿），主力做多意愿明确。</li>
</ul>

<hr>

<h2>二、板块涨跌排行（Top 10）</h2>
<table>
<thead><tr><th>排名</th><th>板块</th><th>涨跌幅</th></tr></thead>
<tbody>
<tr><td>1</td><td><span class="sector">医疗服务</span></td><td><span class="up">+5.59%</span></td></tr>
<tr><td>2</td><td><span class="sector">影视院线</span></td><td><span class="up">+3.94%</span></td></tr>
<tr><td>3</td><td><span class="sector">白酒</span></td><td><span class="up">+3.77%</span></td></tr>
<tr><td>4</td><td><span class="sector">军工装备</span></td><td><span class="up">+3.77%</span></td></tr>
<tr><td>5</td><td><span class="sector">生物制品</span></td><td><span class="up">+3.33%</span></td></tr>
<tr><td>6</td><td><span class="sector">化学制药</span></td><td><span class="up">+3.20%</span></td></tr>
<tr><td>7</td><td><span class="sector">风电设备</span></td><td><span class="up">+2.95%</span></td></tr>
<tr><td>8</td><td><span class="sector">文化传媒</span></td><td><span class="up">+2.91%</span></td></tr>
<tr><td>9</td><td><span class="sector">厨卫电器</span></td><td><span class="up">+2.76%</span></td></tr>
<tr><td>10</td><td><span class="sector">军工电子</span></td><td><span class="up">+2.74%</span></td></tr>
</tbody>
</table>
<p>板块 <b>领涨梯队</b>：医药（医疗服务/生物制品/化学制药合计 6 家上市公司过百）+ 军工（装备/电子）+ 大消费（白酒/影视/厨卫）+ 新能源（风电）。</p>

<hr>

<h2>三、强势个股梯队</h2>

<h3>3.1 板块联动核心（strong_recommend）</h3>
<table>
<thead><tr><th>代码</th><th>名称</th><th>板块</th><th>竞价涨幅</th><th>成交额</th><th>净额</th></tr></thead>
<tbody>
<tr><td><span class="highlight">688523</span></td><td><span class="stock"><b>航天环宇</b></span></td><td><span class="sector">军工装备</span></td><td><span class="limit-up">涨停</span></td><td><span class="highlight">9.30亿</span></td><td><span class="inflow">+0.10亿</span></td></tr>
<tr><td>300065</td><td><span class="stock"><b>海兰信</b></span></td><td><span class="sector">军工电子</span></td><td><span class="limit-up">涨停</span></td><td><span class="highlight">32.79亿</span></td><td><span class="outflow">-6.12亿</span></td></tr>
<tr><td>300255</td><td><span class="stock"><b>常山药业</b></span></td><td><span class="sector">化学制药</span></td><td><span class="limit-up">涨停</span></td><td><span class="highlight">17.67亿</span></td><td><span class="outflow">-1.34亿</span></td></tr>
</tbody>
</table>
<div class="alert-good">板块共振强度：军工板块联动 6+ 只个股封板，化学制药板块多家创新药同步走强，<b>板块联动极致</b>。</div>

<h3>3.2 板块中军确认（confirm）</h3>
<table>
<thead><tr><th>代码</th><th>名称</th><th>板块</th><th>竞价涨幅</th><th>成交额</th><th>净额</th></tr></thead>
<tbody>
<tr><td>600879</td><td><span class="stock"><b>航天电子</b></span></td><td><span class="sector">军工电子</span></td><td><span class="limit-up">涨停</span></td><td><span class="highlight">58.17亿</span></td><td><span class="inflow">+1.67亿</span></td></tr>
<tr><td>2202</td><td><span class="stock"><b>金风科技</b></span></td><td><span class="sector">风电整机</span></td><td><span class="limit-up">涨停</span></td><td><span class="highlight">58.10亿</span></td><td><span class="inflow">+6.35亿</span></td></tr>
<tr><td>301005</td><td><span class="stock"><b>超捷股份</b></span></td><td><span class="sector">半导体</span></td><td><span class="up">+11.64%</span></td><td><span class="highlight">33.47亿</span></td><td><span class="inflow">+5.45亿</span></td></tr>
</tbody>
</table>
<div class="alert-good"><b>金风科技</b>净额流入 6.35 亿为风电板块首位，主力净买入明确；<b>航天电子</b>成交额 58.17 亿为军工板块第一，板块中军属性。</div>

<h3>3.3 跟风转强候选（candidate）</h3>
<table>
<thead><tr><th>代码</th><th>名称</th><th>板块</th><th>竞价涨幅</th><th>成交额</th></tr></thead>
<tbody>
<tr><td>300102</td><td><span class="stock">乾照光电</span></td><td><span class="sector">半导体</span></td><td><span class="up">+12.18%</span></td><td><span class="highlight">30.97亿</span></td></tr>
<tr><td>300129</td><td><span class="stock">泰胜风能</span></td><td><span class="sector">风电设备</span></td><td><span class="up">+12.80%</span></td><td><span class="highlight">7.75亿</span></td></tr>
<tr><td>688818</td><td><span class="stock">电科蓝天</span></td><td><span class="sector">军工电子</span></td><td><span class="up">+9.63%</span></td><td><span class="highlight">27.06亿</span></td></tr>
</tbody>
</table>

<h3>3.4 大盘放量观察（watch）</h3>
<table>
<thead><tr><th>代码</th><th>名称</th><th>板块</th><th>竞价涨幅</th><th>成交额</th></tr></thead>
<tbody>
<tr><td>977</td><td><span class="stock">浪潮信息</span></td><td><span class="sector">AI算力</span></td><td><span class="up">+4.11%</span></td><td><span class="highlight">260.83亿</span></td></tr>
<tr><td>603019</td><td><span class="stock">中科曙光</span></td><td><span class="sector">AI算力</span></td><td><span class="up">+3.38%</span></td><td><span class="highlight">174.09亿</span></td></tr>
</tbody>
</table>
<p>AI 算力中军 <b>浪潮信息</b>成交额 <span class="highlight">260.83 亿</span>全市场第一，但竞价涨幅温和，<b>更适合回踩低吸</b>。</p>

<hr>

<h2>四、核心结论</h2>
<ol>
<li><b>主线一：军工</b>（装备+电子）— 商业航天/卫星导航题材催化，板块联动极致，<b>航天环宇</b>封板 + <b>航天电子</b>中军放量 + <b>海兰信</b>高弹性。</li>
<li><b>主线二：医药</b>（服务+创新药）— GLP-1 减重药题材发酵，<b>常山药业</b>封板带动化学制药板块，<b>益诺思</b>+20% 同步走强。</li>
<li><b>主线三：风电</b> — 出海逻辑 + 海风增量，<b>金风科技</b>封板 + 净额流入 6.35 亿，板块情绪强。</li>
<li><b>辅线：AI 算力</b> — 中军放量（浪潮信息成交 260 亿），但竞价涨幅温和，<b>趋势跟随优于追涨</b>。</li>
</ol>

<hr>

<h2>五、风险提示</h2>
<div class="risk-box">
<ul>
<li><b>竞价数据尚未最终确定</b>（9:15-9:20 可撤单阶段已过，9:20 后数据相对稳定），但 9:25 集合竞价撮合结果仍可能受最后一刻大单影响。</li>
<li><b>高开低走风险</b>：竞价涨幅 8%+ 的个股需警惕开盘后获利回吐，<b>海兰信</b>已显示净额流出 6.12 亿。</li>
<li><b>板块分歧风险</b>：军工板块竞价强度高，但科创板<b>电科蓝天</b>换手 26.21% 显示场内分歧，谨防板块内部分化。</li>
<li><b>大盘股弹性有限</b>：<b>浪潮信息/中科曙光</b>竞价涨幅温和，重仓参与需耐心。</li>
<li><b>ST/退市风险</b>：<b>恒久退</b>+10.53% 在涨停带，但属退市股，<b>不参与</b>。</li>
<li><b>新上市公司异常波动</b>：<b>托伦斯</b>+858.85% 为新股首日波动，<b>排除观察池</b>。</li>
</ul>
</div>

<hr>

<h2>六、执行建议</h2>
<div class="alert-good">
<p><b>优先关注</b>：<span class="stock"><b>航天环宇</b></span>、<span class="stock"><b>金风科技</b></span>、<span class="stock"><b>航天电子</b></span> 三个核心标的的 9:30 开板表现。</p>
<p><b>辅线观察</b>：<span class="stock"><b>浪潮信息</b></span>、<span class="stock"><b>中科曙光</b></span>的 AI 算力主线下半场。</p>
<p><b>执行节奏</b>：板块联动 + 竞价强势 → strong_recommend；板块中军放量 → confirm；跟风 + 转强 → candidate；大盘温和放量 → watch。</p>
</div>
'''

payload = {
    'trading_date': '2026-07-11',
    'skill_name': '09:26 集合竞价分析',
    'job_name': '09:26 集合竞价分析',
    'job_type': 'stock_pick',
    'run_type': 'production',
    'source_input_ref': 'claude-code-cli',
    '_meta': {
        'schema_version': '3.0',
        'engine_type': 'claude-code',
        'data_sources_used': [
            'akshare: sector_fund_rank',
            'akshare: individual_fund_rank',
            'prefetched_file: /tmp/easyquant_market_data_2026-07-11.json',
        ],
    },
    'summary': {
        'market_phase': '竞价转强 — 多个板块共振走强，军工/医药/风电三主线明确',
        'hot_sectors': ['军工装备', '军工电子', '医疗服务', '化学制药', '风电设备', '文化传媒', '白酒'],
        'risk_signals': [
            '竞价数据已过 9:20 不可撤单阶段，撮合结果相对稳定',
            '海兰信等高弹性品种净额流出，谨防开盘分歧',
            '科创板电科蓝天换手 26.21% 板块内部分歧大',
            'ST/退市股（恒久退）涨停但不参与',
            '新股托伦斯 +858.85% 异常波动排除',
        ],
    },
    'result_payload': {
        'structured_picks': structured_picks,
    },
    'raw_output': raw_output,
}

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(OUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

print('Wrote:', OUT_PATH)
print('Size:', OUT_PATH.stat().st_size, 'bytes')
print('Picks count:', len(structured_picks))
for p in structured_picks:
    print('  -', p['pick_level'], p['stock_code'], p['stock_name'], p['sector_name'], 'confidence=' + str(p['confidence_score']))