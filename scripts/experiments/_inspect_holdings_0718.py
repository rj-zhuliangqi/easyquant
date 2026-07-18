import json

with open('/tmp/easyquant_market_data_2026-07-18.json') as f:
    d = json.load(f)

holdings = {
    '300157': '新锦动力',
    '601988': '中国银行',
    '601857': '中国石油',
    '600519': '贵州茅台',
    '300760': '迈瑞医疗',
}
ir = d['individual_rankings']['individual']

print('=== 持仓个股行情(来自 individual_rankings) ===')
found = {}
for r in ir:
    code = str(r.get('股票代码', '')).zfill(6)
    if code in holdings:
        found[code] = r
        print(
            '%s %s: 价%s 涨跌%s 换手%s 净额%s 成交%s'
            % (code, r['股票简称'], r['最新价'], r['涨跌幅'], r['换手率'], r['净额'], r['成交额'])
        )

print('\n未在 individual_rankings 中找到的持仓:', [c for c in holdings if c not in found])

# 涨跌停与广度
def pct(r):
    s = str(r.get('涨跌幅', '0%')).replace('%', '').replace('+', '')
    try:
        return float(s)
    except Exception:
        return 0.0

changes = [pct(r) for r in ir]
up_cnt = sum(1 for c in changes if c > 0)
down_cnt = sum(1 for c in changes if c < 0)
flat_cnt = sum(1 for c in changes if c == 0)
limit_up = sum(1 for c in changes if c >= 9.9)
limit_down = sum(1 for c in changes if c <= -9.9)
import statistics
med = statistics.median(changes) if changes else 0
print('\n=== 全市场广度(样本 %d) ===' % len(ir))
print('上涨:%d 下跌:%d 平:%d' % (up_cnt, down_cnt, flat_cnt))
print('涨停(>=9.9%%):%d 跌停(<=-9.9%%):%d 中位数:%.2f%%' % (limit_up, limit_down, med))
