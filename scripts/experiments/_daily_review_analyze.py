import json
import os

data_path = '/private/tmp/easyquant_market_data_2026-06-26.json'
print('FILE EXISTS:', os.path.exists(data_path), 'SIZE:', os.path.getsize(data_path))

with open(data_path, 'r', encoding='utf-8') as f:
    data = json.load(f)


def f(x, default=0.0):
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(str(x).replace('%', '').replace('亿', '').replace('+', ''))
    except Exception:
        return default


# 打印一个样例查清类型
s = data['sector_rankings']['industry'][0]
for k, v in s.items():
    print(f"  {k} -> {type(v).__name__}: {v!r}")
print()

print('=== 行业涨跌幅排行 (前 30) ===')
sectors = data['sector_rankings']['industry']
for s in sectors[:30]:
    chg = f(s['行业-涨跌幅'])
    sign = '+' if chg > 0 else ''
    jing = f(s['净额'])
    jing_s = f"+{jing}" if jing > 0 else f"{jing}"
    lead = f(s['领涨股-涨跌幅'])
    print(f"  {s['序号']:>3} {s['行业']:<12} {sign}{chg:.2f}%  净额:{jing_s:>7.2f}亿  领涨:{s['领涨股']}({sign}{lead:.2f}%)")

print()
print('=== 行业涨跌幅排行 (末 10) ===')
for s in sectors[-10:]:
    chg = f(s['行业-涨跌幅'])
    jing = f(s['净额'])
    jing_s = f"+{jing}" if jing > 0 else f"{jing}"
    print(f"  {s['序号']:>3} {s['行业']:<12} {chg:.2f}%  净额:{jing_s:>7.2f}亿")

print()
print('=== 个股涨幅前 30 ===')
items = data['individual_rankings']['individual']


def parse_pct(s):
    try:
        return float(str(s).replace('%', ''))
    except Exception:
        return 0.0


sorted_items = sorted(items, key=lambda x: parse_pct(x.get('涨跌幅', '0%')), reverse=True)
for s in sorted_items[:30]:
    chg = s.get('涨跌幅', '-')
    print(f"  {s['股票简称']:<10} {str(s['股票代码']):<8} {str(chg):<10}  换手:{s.get('换手率','-')}  净额:{s.get('净额','-')}")

print()
print('=== 个股跌幅前 20 ===')
for s in sorted_items[-20:]:
    chg = s.get('涨跌幅', '-')
    print(f"  {s['股票简称']:<10} {str(s['股票代码']):<8} {str(chg):<10}  换手:{s.get('换手率','-')}  净额:{s.get('净额','-')}")

print()
print('=== 涨跌幅统计 ===')
arr = [parse_pct(x.get('涨跌幅', '0%')) for x in items]
pos = [x for x in arr if x > 0]
neg = [x for x in arr if x < 0]
lim_up = [x for x in arr if x >= 19.9]
lim_down = [x for x in arr if x <= -19.9]
print(f"总样本: {len(arr)}")
print(f"上涨: {len(pos)} ({len(pos)*100/len(arr):.1f}%)")
print(f"下跌: {len(neg)} ({len(neg)*100/len(arr):.1f}%)")
print(f"涨幅>=20% 接近涨停: {len(lim_up)}")
print(f"跌幅<=-20% 接近跌停: {len(lim_down)}")

# 资金净流入前列
print()
print('=== 个股资金净流入前 20 ===')


def parse_yi(s):
    try:
        return float(str(s).replace('亿', '').replace('+', ''))
    except Exception:
        return 0.0


sorted_jing = sorted(items, key=lambda x: parse_yi(x.get('净额', '0')), reverse=True)
for s in sorted_jing[:20]:
    print(f"  {s['股票简称']:<10} {str(s['股票代码']):<8} 净额:{s.get('净额','-'):<10}  涨跌幅:{s.get('涨跌幅','-')}")

print()
print('=== 个股资金净流出前 20 ===')
for s in sorted_jing[-20:]:
    print(f"  {s['股票简称']:<10} {str(s['股票代码']):<8} 净额:{s.get('净额','-'):<10}  涨跌幅:{s.get('涨跌幅','-')}")
