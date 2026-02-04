import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time

# 统一输出为人民币（CNY），需汇率：USD/CNY、HKD/CNY
def get_fx_rates(start_date, end_date):
    """拉取区间内每日 USD/CNY、HKD/CNY，返回 date -> (usd_cny, hkd_cny)。"""
    rates = {}
    try:
        # USDCNY=X：1 美元 = ? 人民币
        usdcny = yf.Ticker("USDCNY=X").history(start=start_date, end=end_date)
        # USDHKD=X：1 美元 = ? 港币 → 1 港币 = usdcny/usdhkd 人民币
        usdhkd = yf.Ticker("USDHKD=X").history(start=start_date, end=end_date)
        if usdcny is not None and not usdcny.empty and usdhkd is not None and not usdhkd.empty:
            for d in usdcny.index:
                ds = d.strftime("%Y-%m-%d")
                cny_per_usd = float(usdcny.loc[d, "Close"])
                hkd_per_usd = float(usdhkd.loc[d, "Close"]) if d in usdhkd.index else None
                if hkd_per_usd and hkd_per_usd > 0:
                    cny_per_hkd = cny_per_usd / hkd_per_usd
                else:
                    cny_per_hkd = cny_per_usd / 7.8  # 兜底
                rates[ds] = (cny_per_usd, cny_per_hkd)
        # 若无历史，用最近一日汇率填充
        if not rates and usdcny is not None and not usdcny.empty:
            last = usdcny.index[-1]
            ds = last.strftime("%Y-%m-%d")
            cny_per_usd = float(usdcny.loc[last, "Close"])
            rates[ds] = (cny_per_usd, cny_per_usd / 7.8)
    except Exception as e:
        print(f"汇率获取失败，将使用兜底汇率: {e}")
    return rates

def to_cny(value, currency, date_str, fx_rates):
    """将金额按当日汇率换算为人民币。"""
    if currency in ("CNY", "RMB", "RMB ") or not value:
        return round(value, 2) if value else 0
    usd_cny, hkd_cny = 7.2, 0.92  # 兜底
    if fx_rates:
        usd_cny, hkd_cny = fx_rates.get(date_str) or next(iter(fx_rates.values()), (7.2, 0.92))
    if currency in ("USD",):
        return round(value * usd_cny, 2)
    if currency in ("HKD", "HK$"):
        return round(value * hkd_cny, 2)
    return round(value, 2)

# 定义要查询的两地上市目标企业
# 格式：企业名称: [A股/美股代码, 港股代码]
stocks_pairs = {
    # 金融类 (A+H)
    "工商银行": ["601398.SS", "1398.HK"],
    "建设银行": ["601939.SS", "0939.HK"],
    "中国银行": ["601988.SS", "3988.HK"],
    "农业银行": ["601288.SS", "1288.HK"],
    "招商银行": ["600036.SS", "3968.HK"],
    "中国平安": ["601318.SS", "2318.HK"],
    "中国人寿": ["601628.SS", "2628.HK"],
    "中信证券": ["600030.SS", "6030.HK"],
    
    # 科技与互联网 (美+港 / A+H)
    "阿里巴巴": ["BABA", "9988.HK"],
    "京东集团": ["JD", "9618.HK"],
    "网易": ["NTES", "9999.HK"],
    "百度": ["BIDU", "9888.HK"],
    "中兴通讯": ["000063.SZ", "0763.HK"],
    "比亚迪": ["002594.SZ", "1211.HK"],
    
    # 工业与资源 (A+H)
    "中国石油": ["601857.SS", "0857.HK"],
    "中国石化": ["600028.SS", "0386.HK"],
    "中国神华": ["601088.SS", "1088.HK"],
    "中远海控": ["601919.SS", "1919.HK"],
    "紫金矿业": ["601899.SS", "2899.HK"],
    "潍柴动力": ["000338.SZ", "2338.HK"],
    "海螺水泥": ["600585.SS", "0914.HK"],
    
    # 医药与消费 (A+H)
    "药明康德": ["603259.SS", "2359.HK"],
    "复星医药": ["600196.SS", "2196.HK"],
    "青岛啤酒": ["600600.SS", "0168.HK"],
}

def fetch_dual_listed_data():
    all_data = []
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1*365)
    
    print(f"开始抓取两地数据，范围: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
    print("正在获取汇率（USD/CNY、HKD/CNY）...")
    fx_rates = get_fx_rates(start_date, end_date)
    if fx_rates:
        sample = next(iter(fx_rates.items()))
        print(f"汇率已加载，共 {len(fx_rates)} 个交易日，示例: {sample[0]} -> USD= {sample[1][0]:.4f} CNY, HKD= {sample[1][1]:.4f} CNY")
    else:
        print("未获取到汇率，非 CNY 数据将按兜底汇率换算。")

    for name, tickers in stocks_pairs.items():
        for ticker_symbol in tickers:
            # 识别市场类型
            market_type = "HK" if ".HK" in ticker_symbol else ("A" if (".SS" in ticker_symbol or ".SZ" in ticker_symbol) else "US")
            
            print(f"正在获取: {name} | 市场: {market_type} | 代码: {ticker_symbol}...")
            try:
                ticker = yf.Ticker(ticker_symbol)
                hist = ticker.history(start=start_date, end=end_date)
                
                info = ticker.info
                # 总值 = 总股本 * 价格（A/HK/US 均用总股本算总市值，不用流通股 floatShares）
                total_shares = (
                    info.get("totalSharesOutstanding")
                    or info.get("impliedSharesOutstanding")
                    or info.get("sharesOutstanding")
                    or info.get("outstandingShares")
                    or 0
                )
                currency = info.get("currency", "Unknown")

                if len(hist) == 0:
                    print(f"未找到 {ticker_symbol} 的历史数据")
                    continue

                for date, row in hist.iterrows():
                    date_str = date.strftime('%Y-%m-%d')
                    # 总市值 = 总股本 * 收盘价（单位：亿元/亿港元/亿美元）
                    market_cap_local = (row['Close'] * total_shares) / 100000000 if total_shares > 0 else 0
                    price_local = row['Close']
                    # 统一换算为人民币（亿元、元）
                    market_cap_cny = to_cny(market_cap_local, currency, date_str, fx_rates)
                    price_cny = to_cny(price_local, currency, date_str, fx_rates)
                    all_data.append({
                        "Date": date_str,
                        "Name": name,
                        "Market": market_type,
                        "Ticker": ticker_symbol,
                        "MarketCap": market_cap_cny,
                        "Price": round(price_cny, 2),
                        "Currency": "CNY"
                    })
                
                # 减缓请求频率
                time.sleep(0.5)
                
            except Exception as e:
                print(f"获取 {ticker_symbol} 失败: {e}")

    if all_data:
        df = pd.DataFrame(all_data)
        df.to_csv("market_cap_history.csv", index=False, encoding='utf-8-sig')
        print(f"\n抓取完成！已保存 {len(all_data)} 条记录至 market_cap_history.csv")
    else:
        print("未获取到数据。")

if __name__ == "__main__":
    fetch_dual_listed_data()