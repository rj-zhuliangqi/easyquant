"""Build candidate pool for the 20:00 super-short post-market stock pick job."""
import json

P = '/tmp/easyquant_market_data_2026-06-30.json'
with open(P) as f:
    d = json.load(f)

ind = d['individual_rankings']['individual']
sec = d['sector_rankings']['industry']


def pct(s):
    try:
        return float(str(s).rstrip('%'))
    except Exception:
        return 0.0


def yi(s):
    s = str(s)
    if '亿' in s:
        try:
            return float(s.replace('亿', ''))
        except Exception:
            return 0.0
    if '万' in s:
        try:
            return float(s.replace('万', '')) / 10000.0
        except Exception:
            return 0.0
    return 0.0


# 候选池: 涨幅10%-19%(已涨停过但非涨停) + 排除ST + 净额>0
cands = [x for x in ind if 10.0 <= pct(x.get('涨跌幅')) < 19.0]
cands = [x for x in cands if 'ST' not in x.get('股票简称', '') and '*' not in x.get('股票简称', '')]
cands = [x for x in cands if yi(x.get('净额', '0')) > 0]
cands = sorted(cands, key=lambda x: yi(x.get('净额', '0')), reverse=True)

print('强候选池(>=10%且<19% 且非ST 且净额>0):', len(cands))
print()
print('按净额 Top 30:')
for c in cands[:30]:
    print(f"  {c.get('股票简称')}({c.get('股票代码')}): {c.get('涨跌幅')} 换手={c.get('换手率')} 净额={c.get('净额')} 成交={c.get('成交额')}")

# 候选池: 涨停但仍有空间(创业板/科创板涨停20cm, 有连板预期)
zt = [x for x in ind if pct(x.get('涨跌幅')) >= 19.9]
zt = [x for x in zt if 'ST' not in x.get('股票简称', '') and '*' not in x.get('股票简称', '')]
zt = sorted(zt, key=lambda x: yi(x.get('净额', '0')), reverse=True)
print()
print('涨停候选(>=19.9% 非ST)数量:', len(zt))
print('涨停按净额 Top 15:')
for c in zt[:15]:
    print(f"  {c.get('股票简称')}({c.get('股票代码')}): {c.get('涨跌幅')} 换手={c.get('换手率')} 净额={c.get('净额')} 成交={c.get('成交额')}")

# 跌幅榜
losers = [x for x in ind if pct(x.get('涨跌幅')) <= -7.0]
losers = sorted(losers, key=lambda x: pct(x.get('涨跌幅')))
print()
print('跌幅>=7%数量:', len(losers))
print('跌幅Top 10:')
for c in losers[:10]:
    print(f"  {c.get('股票简称')}({c.get('股票代码')}): {c.get('涨跌幅')} 换手={c.get('换手率')} 净额={c.get('净额')}")