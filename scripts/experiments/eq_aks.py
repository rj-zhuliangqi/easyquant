import akshare as ak
import json
try:
    df = ak.stock_zh_a_spot_em()
    print('total:', len(df))
    print(df.columns.tolist())
    df['_pct'] = df['涨跌幅'].astype(float)
    out = df[df['_pct'] > 2][['代码', '名称', '最新价', '涨跌幅', '成交额', '换手率']].head(40).to_string()
    print(out)
except Exception as e:
    print('ERR:', repr(e))