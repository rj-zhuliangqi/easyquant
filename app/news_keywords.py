"""资讯重要性识别词典 — 行为关键词 + 行业关键词。

命中策略：标题 + 摘要拼成一段文本，对每个 (tag → keywords) 做子串包含判断，
命中即把 tag 加入返回数组。双命中（行为 ∩ 行业非空）由调用方设为 importance_level=2 +
is_pinned=True；单命中 level=1；都没命中 level=0。

后续如果词条频繁调整，再迁到 YAML + mtime hot-reload；v1 用 Python dict 享受 IDE 跳转
+ 单元测试 import + 类型检查。
"""

from __future__ import annotations


# 行为关键词 — 强信号动作（涨价 / 减产 / 重大合同 / 政策面 / 业绩 等）
ACTION_KEYWORDS: dict[str, list[str]] = {
    "涨价": ["涨价", "提价", "调价", "上调价格", "价格上涨", "挺价", "惜售", "再创新高"],
    "减产限产": ["减产", "限产", "停产", "检修", "供给收缩", "去产能"],
    "重大合同": ["重大合同", "中标", "签约", "百亿订单", "战略合作", "框架协议", "重大订单"],
    "利好": ["利好", "重大利好", "重组", "并购", "资产注入", "借壳", "重大资产重组"],
    "业绩": ["业绩预增", "业绩翻倍", "净利润大增", "扭亏", "业绩超预期", "营收增长"],
    "解禁": ["解禁", "限售股解禁", "股东减持"],
    "异动": ["暴涨", "涨停", "跌停", "异动", "封板", "炸板"],
    "政策": [
        "国务院",
        "发改委",
        "工信部",
        "央行",
        "证监会",
        "财政部",
        "科技部",
        "政策支持",
        "补贴",
        "减税",
        "降息",
        "降准",
    ],
}

# 行业关键词 — 题材归因（化工 / 锂电 / 稀土 / 光伏 / 半导体 等）
INDUSTRY_KEYWORDS: dict[str, list[str]] = {
    "化工": ["化工", "纯碱", "MDI", "TDI", "草甘膦", "聚氨酯", "环氧丙烷", "尿素"],
    "磷化工": ["磷化工", "黄磷", "磷酸铁", "磷矿", "工业磷酸"],
    "锂电": ["锂电", "碳酸锂", "六氟磷酸锂", "电解液", "电池级", "锂矿"],
    "稀土": ["稀土", "钕铁硼", "氧化镨钕", "永磁"],
    "光伏": ["光伏", "硅料", "电池片", "组件", "TOPCon", "HJT", "钙钛矿"],
    "半导体": ["半导体", "芯片", "晶圆", "存储", "EDA", "光刻", "封测", "MCU"],
    "医药": ["创新药", "CXO", "中药", "疫苗", "GLP-1", "减肥药", "创新医疗器械"],
    "AI": ["人工智能", "AI算力", "大模型", "GPU", "智算中心", "算力中心", "数据中心"],
    "军工": ["军工", "国防", "导弹", "航空发动机", "舰船", "无人机"],
    "新能源车": ["新能源车", "智能驾驶", "L3", "Robotaxi", "智能汽车", "整车"],
    "煤炭": ["煤炭", "焦煤", "动力煤", "炼焦"],
    "有色": ["有色金属", "黄金", "白银", "铜价", "铝价", "锡价"],
}


def match_keywords(text: str) -> tuple[list[str], list[str]]:
    """返回 ``(action_hits, industry_hits)``。

    简单子串包含匹配；v1 不做分词 / 正则 / 否定语境检测。命中顺序保持词典声明顺序。
    """

    if not text:
        return [], []
    action_hits: list[str] = []
    for tag, keywords in ACTION_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                action_hits.append(tag)
                break  # 同一 tag 只算一次
    industry_hits: list[str] = []
    for tag, keywords in INDUSTRY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                industry_hits.append(tag)
                break
    return action_hits, industry_hits
