"""Fetch ST stock list via mootdx + per-stock quote via tencent."""
import json
import re
import time
import urllib.request

from mootdx.quotes import Quotes
import pandas as pd

client = Quotes.factory(market='std')
df0 = client.stocks(market=0)
df1 = client.stocks(market=1)
all_df = pd.concat([df0, df1], ignore_index=True)
print('TOTAL_STOCKS', len(all_df))

# stock_zh_a_st covers ST/*ST (excludes already delisted)
st_df = all_df[all_df['name'].str.contains('ST', na=False)].copy()
st_df = st_df[~st_df['name'].str.contains('退', na=False)]
print('ST_COUNT', len(st_df))

def to_tencent_code(code: str) -> str | None:
    code = str(code).zfill(6)
    if code.startswith('60') or code.startswith('68') or code.startswith('9'):
        return f'sh{code}'
    if code.startswith(('00', '30', '20')):
        return f'sz{code}'
    if code.startswith(('43', '83', '87', '92')):
        return f'bj{code}'
    return None

codes = []
for _, row in st_df.iterrows():
    tc = to_tencent_code(row['code'])
    if tc:
        codes.append((tc, row['name'], row['code']))

print('VALID_CODES', len(codes))

req = urllib.request.Request
opener = urllib.request.build_opener()
opener.addheaders = [
    ('User-Agent', 'Mozilla/5.0'),
    ('Referer', 'https://finance.qq.com'),
]

rows = []
batch = 30
for i in range(0, len(codes), batch):
    chunk = codes[i:i+batch]
    qstr = ','.join(c[0] for c in chunk)
    url = f'http://qt.gtimg.cn/q={qstr}'
    try:
        resp = opener.open(url, timeout=10)
        raw = resp.read().decode('gbk', errors='ignore')
    except Exception as exc:
        print('ERR', i, exc)
        continue
    for line in raw.splitlines():
        m = re.match(r'v_([a-z]{2}\d+)="([^"]*)"', line)
        if not m:
            continue
        tc, payload = m.group(1), m.group(2)
        parts = payload.split('~')
        if len(parts) < 50:
            continue
        try:
            name = parts[1]
            code = parts[2]
            cur = float(parts[3] or 0)
            prev = float(parts[4] or 0)
            open_p = float(parts[5] or 0)
            volume_lots = float(parts[6] or 0)  # 总手
            high = float(parts[33] or 0)
            low = float(parts[34] or 0)
            chg = float(parts[31] or 0)
            chg_pct = float(parts[32] or 0)
            amount_yuan = float(parts[37] or 0) * 10000  # 成交额(万元)
            turnover = float(parts[38] or 0)
            mktcap = float(parts[44] or 0)  # 总市值(亿)
            float_mc = float(parts[45] or 0)  # 流通市值(亿)
            pe = float(parts[39] or 0)
            pb = float(parts[46] or 0)
            limit_up = float(parts[47] or 0)
            limit_down = float(parts[48] or 0)
        except (ValueError, IndexError):
            continue
        rows.append({
            'tencent_code': tc,
            'code': code,
            'name': name,
            'cur': cur,
            'prev': prev,
            'open': open_p,
            'high': high,
            'low': low,
            'chg_pct': chg_pct,
            'amount_yuan': amount_yuan,
            'turnover_pct': turnover,
            'mktcap_yi': mktcap,
            'float_mc_yi': float_mc,
            'pe': pe,
            'pb': pb,
            'limit_up': limit_up,
            'limit_down': limit_down,
        })
    time.sleep(0.2)

print('FETCHED', len(rows))
df = pd.DataFrame(rows)
df = df[df['cur'] > 0]
df = df.sort_values('chg_pct', ascending=False).reset_index(drop=True)
print('NONZERO', len(df))
df.to_json('/Users/jwkj/easyquant/scripts/_st_2030_data.json', orient='records', force_ascii=False)
print('SAVED')

# Print summary
total_amt = df['amount_yuan'].sum() / 1e8
limit_up_cnt = ((df['chg_pct'] >= 4.9) & (df['cur'] >= df['limit_up'] - 0.01)).sum()
gain_cnt = (df['chg_pct'] > 0).sum()
loss_cnt = (df['chg_pct'] < 0).sum()
flat_cnt = (df['chg_pct'] == 0).sum()
avg_chg = df['chg_pct'].mean()
print(f'TOTAL_AMT_YI {total_amt:.2f}')
print(f'LIMIT_UP {limit_up_cnt}')
print(f'GAIN/LOSS/FLAT {gain_cnt}/{loss_cnt}/{flat_cnt}')
print(f'AVG_CHG {avg_chg:.2f}%')
print('TOP10:')
print(df.head(10)[['code','name','cur','chg_pct','amount_yuan','turnover_pct','float_mc_yi','limit_up']].to_string())
print('BOTTOM10:')
print(df.tail(10)[['code','name','cur','chg_pct','amount_yuan','turnover_pct','float_mc_yi','limit_down']].to_string())
