import akshare as ak
import json
import sys

result = {}

try:
    idx = ak.stock_zh_index_spot_em(symbol='沪深重要指数')
    if idx is not None and not idx.empty:
        major = idx[idx['名称'].isin(['上证指数','深证成指','创业板指','沪深300','上证50','科创50','中证500','中证1000','北证50'])]
        result['indices'] = major[['名称','最新价','涨跌幅','涨跌额','成交量','成交额']].to_dict('records')
except Exception as e:
    result['indices_err'] = str(e)

try:
    sec = ak.stock_board_industry_name_em()
    if sec is not None and not sec.empty:
        sec_sorted = sec.sort_values('涨跌幅', ascending=False)
        result['top_sectors'] = sec_sorted.head(10)[['板块名称','最新价','涨跌幅','总市值','换手率','上涨家数','下跌家数','领涨股票','领涨股票-涨跌幅']].to_dict('records')
        result['bot_sectors'] = sec_sorted.tail(10)[['板块名称','最新价','涨跌幅','总市值','换手率','上涨家数','下跌家数','领涨股票','领涨股票-涨跌幅']].to_dict('records')
except Exception as e:
    result['sec_err'] = str(e)

print(json.dumps(result, ensure_ascii=False, default=str))
