import os
import yfinance as yf
import pandas as pd
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

def download_btc_data(start_date="2014-01-01", end_date="2026-3-2"):
    """从 Yahoo Finance 下载比特币 (BTC-USD) 日线数据。"""
    print(f"开始获取 BTC 每日数据：从 {start_date} 到 {end_date}...")
    try:
        btc = yf.download("BTC-USD", start=start_date, end=end_date, interval="1d")
        if btc.empty:
            print("未获取到数据。")
            return
        btc = btc[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        filename = os.path.join(DATA_DIR, f"btc_daily_{datetime.now().strftime('%Y%m%d')}.csv")
        btc.to_csv(filename)
        print("-" * 30)
        print(f"成功！已保存至: {filename}")
        print(btc.tail())
    except Exception as e:
        print(f"获取数据时发生错误: {e}")
        print("安装: pip install yfinance pandas")

if __name__ == "__main__":
    download_btc_data()
