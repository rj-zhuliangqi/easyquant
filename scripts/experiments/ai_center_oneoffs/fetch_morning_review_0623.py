"""Fetch morning review data for 2026-06-23."""
import akshare as ak
import json

result = {}

# 1. Industry sector ranking
try:
    df = ak.stock_board_industry_name_em()
    df = df.sort_values('涨跌幅', ascending=False)
    cols = ['板块名称', '涨跌幅', '最新价', '换手率', '上涨家数', '下跌家数']
    cols = [c for c in cols if c in df.columns]
    top = df.head(12)[cols].to_dict(orient='records')
    bot = df.tail(10).sort_values('涨跌幅')[cols].to_dict(orient='records')
    result['top_sectors'] = top
    result['bot_sectors'] = bot
except Exception as e:
    result['sector_err'] = str(e)

# 2. Concept sector ranking
try:
    df = ak.stock_board_concept_name_em()
    df = df.sort_values('涨跌幅', ascending=False)
    cols = ['板块名称', '涨跌幅', '换手率', '上涨家数', '下跌家数']
    cols = [c for c in cols if c in df.columns]
    result['top_concepts'] = df.head(15)[cols].to_dict(orient='records')
    result['bot_concepts'] = df.tail(8).sort_values('涨跌幅')[cols].to_dict(orient='records')
except Exception as e:
    result['concept_err'] = str(e)

# 3. Limit up pool
try:
    df = ak.stock_zt_pool_em(date='20260623')
    if df is not None and not df.empty:
        cols = ['代码', '名称', '涨跌幅', '最新价', '成交额', '流通市值', '所属行业', '封板资金', '连板数', '首次封板时间']
        cols = [c for c in cols if c in df.columns]
        result['limit_up'] = df[cols].to_dict(orient='records')
        result['limit_up_count'] = len(df)
except Exception as e:
    result['lu_err'] = str(e)

# 4. Limit down
try:
    df = ak.stock_zt_pool_dtgc_em(date='20260623')
    if df is not None and not df.empty:
        result['limit_down_count'] = len(df)
        cols = ['代码', '名称', '涨跌幅', '最新价', '所属行业']
        cols = [c for c in cols if c in df.columns]
        result['limit_down'] = df[cols].head(15).to_dict(orient='records')
    else:
        result['limit_down_count'] = 0
except Exception as e:
    result['ld_err'] = str(e)

# 5. Broken limit (炸板)
try:
    df = ak.stock_zt_pool_zbgc_em(date='20260623')
    if df is not None and not df.empty:
        result['zhaban_count'] = len(df)
    else:
        result['zhaban_count'] = 0
except Exception as e:
    result['zb_err'] = str(e)

# 6. Market overview - up/down stock counts
try:
    df = ak.stock_market_activity_legu()
    result['market_activity'] = df.to_dict(orient='records') if hasattr(df, 'to_dict') else str(df)
except Exception as e:
    result['ma_err'] = str(e)

# 7. Capital flow
try:
    df = ak.stock_market_fund_flow()
    if df is not None and not df.empty:
        result['fund_flow'] = df.tail(3).to_dict(orient='records')
except Exception as e:
    result['ff_err'] = str(e)

# 8. North bound
try:
    df = ak.stock_hsgt_fund_flow_summary_em()
    if df is not None and not df.empty:
        result['hsgt'] = df.to_dict(orient='records')
except Exception as e:
    result['hsgt_err'] = str(e)

print(json.dumps(result, ensure_ascii=False, default=str))
