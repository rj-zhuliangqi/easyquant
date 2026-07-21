import akshare as ak

try:
    df = ak.stock_zh_a_spot_em()
    print("rows:", len(df))
    print("cols:", df.columns.tolist())

    # 涨跌家数
    up = (df['涨跌幅'] > 0).sum()
    dn = (df['涨跌幅'] < 0).sum()
    fl = (df['涨跌幅'] == 0).sum()
    print(f"\nup={up} down={dn} flat={fl}")
    print(f"limit_up={(df['涨跌幅']>=9.9).sum()} limit_dn={(df['涨跌幅']<=-9.9).sum()}")

    targets = ["002965","002080","000823","688359","300655","300567",
               "002617","002141","600667","002821","002354","002335","002008"]
    sub = df[df['代码'].isin(targets)][['代码','名称','最新价','涨跌幅','成交额','换手率','量比']]
    print("\n=== 推荐股午盘 ===")
    print(sub.to_string())

    print("\n=== 涨幅榜 top 10 ===")
    print(df.nlargest(10, '涨跌幅')[['代码','名称','最新价','涨跌幅','成交额']].to_string())

    print("\n=== 跌幅榜 top 10 ===")
    print(df.nsmallest(10, '涨跌幅')[['代码','名称','最新价','涨跌幅','成交额']].to_string())

    print("\n=== 行业板块涨幅前 15 ===")
    bd = ak.stock_board_industry_spot_em()
    print(bd.head(15)[['板块名称','最新价','涨跌幅','成交额','领涨股','换手率']].to_string())

    print("\n=== 行业板块跌幅前 15 ===")
    print(bd.nsmallest(15, '涨跌幅')[['板块名称','最新价','涨跌幅','成交额','领涨股','换手率']].to_string())

    # 主要指数
    print("\n=== 主要指数 ===")
    for code in ["000001","399001","399006","000688","000300"]:
        secid = ("1" if code.startswith("0") else "0") + "." + code
        import urllib.request
        url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f44,f45,f46,f47,f60,f170"
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode()
        print(code, data[:500])

except Exception as e:
    import traceback
    traceback.print_exc()
