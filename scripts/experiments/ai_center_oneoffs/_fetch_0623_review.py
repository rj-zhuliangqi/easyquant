"""Fetch market data for 2026-06-23 post-close review."""
import os, sys, json
for k in ['http_proxy','https_proxy','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','all_proxy']:
    os.environ.pop(k, None)
import akshare as ak

out = {}

# 1. 大盘指数
try:
    idx = ak.stock_zh_index_spot_em(symbol="指数成份")
    print("=== INDEX ===")
    if idx is not None and len(idx)>0:
        # 主要指数
        wanted = ['000001','399001','399006','000300','000016','000688','899050','000852','000905']
        sub = idx[idx['代码'].astype(str).isin(wanted)] if '代码' in idx.columns else idx
        print(sub.to_string() if len(sub)>0 else idx.head(10).to_string())
except Exception as e:
    print("ERR_IDX", e)

try:
    idx2 = ak.stock_zh_index_spot_em(symbol="上证系列指数")
    print("=== SSE ===")
    if idx2 is not None:
        print(idx2.head(8).to_string())
except Exception as e:
    print("ERR_SSE", e)

# 2. 行业板块
try:
    df = ak.stock_board_industry_name_em()
    df = df.sort_values('涨跌幅', ascending=False)
    print("=== INDUSTRY TOP15 ===")
    print(df.head(15).to_string())
    print("=== INDUSTRY BOTTOM10 ===")
    print(df.tail(10).to_string())
except Exception as e:
    print("ERR_IND", e)

# 3. 概念板块
try:
    cdf = ak.stock_board_concept_name_em()
    cdf = cdf.sort_values('涨跌幅', ascending=False)
    print("=== CONCEPT TOP20 ===")
    print(cdf.head(20).to_string())
    print("=== CONCEPT BOTTOM10 ===")
    print(cdf.tail(10).to_string())
except Exception as e:
    print("ERR_CON", e)
