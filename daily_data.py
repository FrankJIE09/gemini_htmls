import yfinance as yf
import pandas_datareader.data as web
import pandas as pd
from datetime import datetime

def download_financial_data(start_date="2018-01-01", end_date="2025-12-31"):
    """
    从 Yahoo Finance 下载纳斯达克 100 指数 (NDX) 日线数据
    从 FRED 下载联邦基金有效利率 (FEDFUNDS)，按日对齐（前向填充月度数据）
    """
    print(f"开始获取每日数据：从 {start_date} 到 {end_date}...")

    try:
        # 1. 下载纳斯达克 100 指数日线数据 (Yahoo Finance)
        print("正在从 Yahoo Finance 获取纳指日线数据...")
        nasdaq = yf.download("^NDX", start=start_date, end=end_date, interval="1d")
        nasdaq_close = nasdaq[['Close']].copy()
        nasdaq_close.columns = ['Nasdaq_Close']

        # 2. 下载联邦基金利率 (FRED 为月度)，再按日对齐
        print("正在从 FRED 获取联邦基金利率并按日对齐...")
        rates = web.DataReader("FEDFUNDS", "fred", start_date, end_date)
        rates.columns = ['Fed_Rate']
        # 将月度利率按日重采样并前向填充，与纳指交易日对齐
        rates_daily = rates.reindex(nasdaq_close.index).ffill()

        # 3. 合并
        combined_data = pd.concat([nasdaq_close, rates_daily], axis=1).dropna()

        # 4. 保存为 CSV
        filename = f"nasdaq_vs_rates_daily_{datetime.now().strftime('%Y%m%d')}.csv"
        combined_data.to_csv(filename)

        print("-" * 30)
        print(f"成功！每日数据已保存至: {filename}")
        print(combined_data.tail())

    except Exception as e:
        print(f"获取数据时发生错误: {e}")
        print("提示: 请确保已安装 yfinance, pandas_datareader 和 pandas 库。")
        print("安装命令: pip install yfinance pandas_datareader pandas")

if __name__ == "__main__":
    download_financial_data()
