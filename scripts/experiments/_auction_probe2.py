"""盘前竞价数据补充 - 避免 /tmp/inspect.py 干扰，使用工作区路径"""
import sys
import os
# 切到 /tmp 之前先把标准库路径放最前
import importlib.util
# 强制使用标准 inspect
spec = importlib.util.find_spec('inspect')
print("using inspect from:", spec.origin if spec else "n/a")

import akshare as ak
import json

# 1. 大盘指数
print("=== 关键指数 ===")
try:
    idx = ak.stock_zh_index_spot_em()
    key_idx = idx[idx['名称'].isin(['上证指数','深证成指','创业板指','科创50','北证50'])]
    print(key_idx[['名称','最新价','涨跌幅','涨跌额']].to_string())
except Exception as e:
    print("idx err:", e)

# 2. 涨停股池
print()
print("=== 涨停股池 ===")
try:
    zt = ak.stock_zt_pool_em(date='20260703')
    print("rows:", len(zt))
    print(zt.columns.tolist())
    print(zt.head(15).to_string())
except Exception as e:
    print("zt err:", e)

# 3. 炸板股池
print()
print("=== 炸板股池 ===")
try:
    zb = ak.stock_zt_pool_zbgc_em(date='20260703')
    print("rows:", len(zb))
    print(zb.head(10).to_string() if len(zb) else "empty")
except Exception as e:
    print("zb err:", e)

# 4. 强势股池
print()
print("=== 强势股池 ===")
try:
    qs = ak.stock_zt_pool_strong_em(date='20260703')
    print("rows:", len(qs))
    print(qs.head(10).to_string() if len(qs) else "empty")
except Exception as e:
    print("qs err:", e)
