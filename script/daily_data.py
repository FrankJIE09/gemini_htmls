import argparse
import os
import yfinance as yf
import pandas_datareader.data as web
import pandas as pd
from datetime import datetime

from daily_data_nasdaq_pe import download_pe_data

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

def download_financial_data(start_date="2000-01-01", end_date="2025-12-31", with_pe=False):
    """
    从 Yahoo Finance 下载纳斯达克 100 指数 (NDX) 日线数据
    从 FRED 下载联邦基金有效利率 (FEDFUNDS)，按日对齐（前向填充月度数据）
    with_pe=True 时额外合并 Forward PE 并输出四列 CSV
    """
    if with_pe:
        download_pe_data(start_date=start_date, end_date=end_date)
        return

    print(f"开始获取每日数据：从 {start_date} 到 {end_date}...")
    try:
        print("正在从 Yahoo Finance 获取纳指日线数据...")
        nasdaq = yf.download("^NDX", start=start_date, end=end_date, interval="1d")
        nasdaq_close = nasdaq[['Close']].copy()
        nasdaq_close.columns = ['Nasdaq_Close']

        print("正在从 FRED 获取联邦基金利率并按日对齐...")
        rates = web.DataReader("FEDFUNDS", "fred", start_date, end_date)
        rates.columns = ['Fed_Rate']
        rates_daily = rates.reindex(nasdaq_close.index).ffill()

        combined_data = pd.concat([nasdaq_close, rates_daily], axis=1).dropna()
        filename = os.path.join(DATA_DIR, f"nasdaq_vs_rates_daily_{datetime.now().strftime('%Y%m%d')}.csv")
        combined_data.to_csv(filename)

        print("-" * 30)
        print(f"成功！每日数据已保存至: {filename}")
        print(combined_data.tail())
    except Exception as e:
        print(f"获取数据时发生错误: {e}")
        print("安装: pip install yfinance pandas_datareader pandas")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="下载纳指日线 + Fed 利率（可选含 PE）")
    parser.add_argument("--with-pe", action="store_true", help="同时拉取 Forward PE 并输出四列合并 CSV")
    parser.add_argument("--start", default="2000-01-01")
    parser.add_argument("--end", default="2025-12-31")
    args = parser.parse_args()
    download_financial_data(start_date=args.start, end_date=args.end, with_pe=args.with_pe)
