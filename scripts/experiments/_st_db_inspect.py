import sqlite3, json
conn = sqlite3.connect("file:data/sector_fund_monitor.db?mode=ro", uri=True)
cur = conn.cursor()

print('=== 个股快照 ST (去重) ===')
rows = cur.execute(
    "SELECT DISTINCT stock_code, stock_name FROM individual_stock_snapshots "
    "WHERE (stock_name LIKE '%ST%' OR stock_name LIKE '%退%') "
    "  AND trading_date = '2026-06-30'"
).fetchall()
for r in rows:
    print(r)

print()
print('=== ST 个股今日快照 ===')
rows = cur.execute(
    "SELECT stock_code, stock_name, latest_price, change_percent, net_amount "
    "FROM individual_stock_snapshots "
    "WHERE (stock_name LIKE '%ST%' OR stock_name LIKE '%退%') "
    "  AND trading_date = '2026-06-30' "
    "  AND captured_at = (SELECT MAX(captured_at) FROM individual_stock_snapshots WHERE trading_date='2026-06-30')"
).fetchall()
for r in rows:
    print(r)

print()
print('=== ST 板块快照 ===')
rows = cur.execute(
    "SELECT captured_at, sector_name, sector_index, change_percent, net_amount, leading_stock "
    "FROM fund_flow_snapshots "
    "WHERE sector_name LIKE '%ST%' OR sector_name LIKE '%风险%' OR sector_name LIKE '%退市%' "
    "ORDER BY captured_at DESC LIMIT 20"
).fetchall()
for r in rows:
    print(r)

print()
print('=== ai_runs 今天 ===')
rows = cur.execute(
    "SELECT job_id, run_type, status, source_input_ref, duration_ms FROM ai_runs WHERE trading_date = '2026-06-30'"
).fetchall()
for r in rows:
    print(r)

print()
print('=== ai_jobs 列表 ===')
rows = cur.execute("SELECT id, name, schedule_label, job_type, enabled FROM ai_jobs").fetchall()
for r in rows:
    print(r)

print()
print('=== news ST 相关近一周 ===')
rows = cur.execute(
    "SELECT title, matched_industry, importance_level, affected_stocks, substr(published_at, 1, 16) "
    "FROM news_items "
    "WHERE (title LIKE '%ST%' OR title LIKE '%摘帽%' OR title LIKE '%退市%') "
    "  AND published_at >= '2026-06-23' "
    "ORDER BY published_at DESC LIMIT 40"
).fetchall()
for r in rows:
    print(r)