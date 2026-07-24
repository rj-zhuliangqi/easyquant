import json, re

with open('/tmp/easyquant_market_data_2026-07-11.json', 'r') as f:
    data = json.load(f)

def to_pct(s):
    if s is None: return None
    m = re.search(r'-?\d+\.?\d*', str(s))
    return float(m.group()) if m else None

def to_num(s):
    if s is None: return None
    if isinstance(s, (int, float)): return float(s)
    text = str(s).strip().replace('亿', '').replace('万', '')
    m = re.search(r'-?\d+\.?\d*', text)
    return float(m.group()) if m else None

indv = data['individual_rankings']['individual']

# Build sector lookup — assign each top stock to its leading sector based on common knowledge
# Since we don't have a stock-to-sector table here, we manually map for the chosen candidates
sector_map = {
    # 军工装备 / 军工电子 (military equipment / electronics)
    '688523': '军工装备', '600879': '军工电子', '600118': '军工电子',
    '300065': '军工电子', '300102': '军工电子', '2414': '军工装备',
    '547': '军工电子', '300342': '军工电子', '300184': '军工电子',
    '2465': '军工通信', '688387': '军工通信', '688375': '军工电子',
    '688818': '军工电子', '300053': '军工电子', '300762': '军工通信',
    '300900': '军工装备', '600745': '半导体', '300444': '军工电子',
    '600360': '半导体', '300657': '军工电子', '600118': '军工电子',
    # 医疗服务 / 生物制品 / 化学制药 (medical)
    '688710': '医疗服务', '300255': '化学制药', '688238': '生物制品',
    '301367': '医疗器械', '300244': '医疗服务', '688202': '医疗服务',
    '688293': '医疗服务', '300319': '生物制品', '301230': '医疗服务',
    '688328': '半导体', '300487': '化学制药', '688584': '半导体',
    '301592': '化学制药', '688617': '医疗服务',
    # 影视院线 / 文化传媒 / 游戏 (media)
    '300071': '文化传媒', '300058': '文化传媒', '2739': '影视院线',
    '300105': '文化传媒', '300364': '游戏', '300052': '游戏',
    # 风电设备 / 风电整机 (wind power)
    '300129': '风电设备', '2202': '风电整机', '601615': '风电整机',
    '600416': '风电整机', '002531': '风电整机',
    # 半导体 (semiconductors)
    '2185': '半导体', '301005': '半导体', '688102': '半导体',
    '600460': '半导体', '603893': '半导体', '002129': '半导体',
    # AI 算力 / 服务器 (computing)
    '977': 'AI算力', '603019': 'AI算力', '300170': 'AI算力',
    '300846': 'AI算力', '600588': 'AI算力',
}

# Filter and select auction candidates
# Phase 1: 板块联动竞价 — top sector leaders with auction strong stocks
# Sector leaders: 医疗服务, 影视院线, 白酒, 军工装备, 生物制品, 化学制药, 风电设备, 文化传媒, 军工电子

def get(name, code, sector, chg_pct, amt, turnover, inflow):
    return {'code': code, 'name': name, 'sector': sector, 'chg': chg_pct,
            'amount': amt, 'turnover': turnover, 'inflow': inflow}

# Selected candidates from the parsed analysis above
# Format: (code, name, sector_estimate, chg_pct, amount_yi, turnover_pct, net_inflow_yi)
picks_pool = [
    # Tier 1: strong_recommend - 板块联动 + 竞价强势 (sector leader auction)
    get('688523', '航天环宇', '军工装备', 20.01, 9.30, 3.99, 0.10),
    get('300065', '海兰信', '军工电子', 20.01, 32.79, 18.80, -6.12),
    get('688710', '益诺思', '医疗服务', 20.00, 5.03, 7.56, -0.18),
    get('300255', '常山药业', '化学制药', 20.00, 17.67, 7.66, -1.34),
    # Tier 2: confirm - 板块领涨 + 龙头 (sector leaders, big cap, big amount)
    get('300102', '乾照光电', '军工电子', 12.18, 30.97, 13.81, 1.25),
    get('2202', '金风科技', '风电整机', 9.99, 58.10, 7.96, 6.35),
    get('600879', '航天电子', '军工电子', 10.01, 58.17, 7.95, 1.67),
    get('301005', '超捷股份', '半导体', 11.64, 33.47, 15.80, 5.45),
    # Tier 3: candidate - 转强 + 放量
    get('300058', '蓝色光标', '文化传媒', 6.81, 76.76, 15.84, None),
    get('2185', '华天科技', '半导体', 6.66, 127.64, 14.89, None),
    get('600360', '华微电子', '半导体', 5.00, 47.91, 29.05, None),
    get('300129', '泰胜风能', '风电设备', 12.80, 7.75, 11.61, 0.81),
    get('688102', '斯瑞新材', '军工电子', 11.36, 24.70, 6.93, 3.67),
    get('300342', '天银机电', '军工电子', 8.43, 27.94, 14.16, 2.40),
    get('688818', '电科蓝天', '军工电子', 9.63, 27.06, 26.21, 3.54),
    # Tier 4: watch - 大盘放量但涨幅温和
    get('977', '浪潮信息', 'AI算力', 4.11, 260.83, 19.37, None),
    get('603019', '中科曙光', 'AI算力', 3.38, 174.09, 10.93, None),
    get('2354', '天娱数科', '文化传媒', 5.69, 46.55, 33.09, None),
    get('300244', '迪安诊断', '医疗服务', 11.56, 14.55, 14.35, 2.78),
    get('300762', '上海瀚讯', '军工通信', 6.34, 43.01, 15.09, None),
]

# Sort by amount desc
picks_pool_sorted = sorted(picks_pool, key=lambda x: -x['amount'])
for p in picks_pool_sorted:
    print(p['code'], p['name'], p['sector'], '+' + str(p['chg']) + '%', str(p['amount']) + '亿', '换手' + str(p['turnover']) + '%')