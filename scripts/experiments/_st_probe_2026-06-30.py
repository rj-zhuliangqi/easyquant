import akshare as ak
import pandas as pd
import json

pd.set_option('display.max_rows', 100)
pd.set_option('display.width', 220)


def safe(fn, label):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        print(f"[{label}] ERR: {e}")
        return None


print("=== 1) ST 列表 ===")
df_st = safe(ak.stock_zh_a_st_em, "st_list")
if df_st is not None:
    print("rows:", len(df_st), "cols:", list(df_st.columns))
    print(df_st.head(80).to_string())

print("\n=== 2) 概念板块 (查找ST/摘帽) ===")
df_concept = safe(ak.stock_board_concept_name_em, "concept")
if df_concept is not None:
    mask = df_concept["板块名称"].astype(str).str.contains("ST|摘帽|退市", na=False)
    print(df_concept[mask].to_string())

print("\n=== 3) ST 板块实时行情 ===")
df_st_bd = safe(lambda: ak.stock_board_concept_hist_em(
    symbol="ST板块", period="日k", adjust="qfq"), "st_board_hist")
if df_st_bd is not None:
    print(df_st_bd.tail(10).to_string())

print("\n=== 4) 涨停板 (今天) ===")
df_zt = safe(ak.stock_zt_pool_em, "zt_pool")
if df_zt is not None:
    print("rows:", len(df_zt), "cols:", list(df_zt.columns))
    print(df_zt.head(20).to_string())

print("\n=== 5) 板块实时涨跌幅 ===")
df_bd_now = safe(ak.stock_board_concept_spot_em, "concept_spot")
if df_bd_now is not None:
    print("rows:", len(df_bd_now), "cols:", list(df_bd_now.columns))
    print(df_bd_now.head(20).to_string())
    st_row = df_bd_now[df_bd_now["板块名称"].astype(str).str.contains("ST|摘帽", na=False)]
    print("\n--- ST 相关板块实时 ---")
    print(st_row.to_string())

print("\n=== 6) 风险警示板个股实时 ===")
df_stk = safe(ak.stock_zh_a_spot_em, "spot_em")
if df_stk is not None:
    cols = df_stk.columns.tolist()
    print("rows:", len(df_stk), "cols:", cols)
    # find code/name columns
    code_col = next((c for c in cols if "代码" in c), None)
    name_col = next((c for c in cols if "名称" in c), None)
    if code_col and name_col:
        st_mask = df_stk[name_col].astype(str).str.contains("ST|\*ST", na=False)
        print(df_stk[st_mask].head(30).to_string())