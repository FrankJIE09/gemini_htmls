import yfinance as yf
import pandas_datareader.data as web
import pandas as pd
from datetime import datetime

def download_financial_data(start_date="2018-01-01", end_date="2025-12-31"):
    """
    从 Yahoo Finance 下载纳斯达克 100 指数 (NDX) 日频数据
    从 FRED 下载联邦基金有效利率 (FEDFUNDS)，按日向前填充以与日频对齐
    """
    print(f"开始获取数据（日频）：从 {start_date} 到 {end_date}...")

    try:
        # 1. 下载纳斯达克 100 指数日频数据 (Yahoo Finance)
        print("正在从 Yahoo Finance 获取纳指日频数据...")
        nasdaq = yf.download("^NDX", start=start_date, end=end_date, interval="1d")
        # 只取收盘价
        nasdaq_close = nasdaq[['Close']].copy()
        nasdaq_close.columns = ['Nasdaq_Close']
        nasdaq_close.index = pd.to_datetime(nasdaq_close.index).tz_localize(None)

        # 2. 下载联邦基金利率 (FRED，月度)，按日向前填充
        print("正在从 FRED 数据库获取联邦基金利率（月度→按日向前填充）...")
        rates = web.DataReader("FEDFUNDS", "fred", start_date, end_date)
        rates.columns = ['Fed_Rate']
        rates.index = pd.to_datetime(rates.index)

        # 3. 日频对齐：以纳指日期为索引，利率按日向前填充
        rates_daily = rates.reindex(nasdaq_close.index).ffill()

        # 合并
        combined_data = pd.concat([nasdaq_close, rates_daily], axis=1).dropna()

        # 4. 保存为 CSV
        filename = f"nasdaq_vs_rates_{datetime.now().strftime('%Y%m%d')}.csv"
        combined_data.to_csv(filename)
        
        print("-" * 30)
        print(f"成功！数据已保存至: {filename}")
        print(combined_data.tail()) # 显示最后几行预览
        
    except Exception as e:
        print(f"获取数据时发生错误: {e}")
        print("提示: 请确保已安装 yfinance, pandas_datareader 和 pandas 库。")
        print("安装命令: pip install yfinance pandas_datareader pandas")

if __name__ == "__main__":
    download_financial_data()