import os
import yfinance as yf
import pandas as pd
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

def download_shanghai_index(start_date="2000-01-01", end_date="2025-12-31"):
    """从 Yahoo Finance 下载上证指数 (^SSEC) 日线数据。"""
    print(f"开始获取上证指数每日数据：从 {start_date} 到 {end_date}...")
    try:
        sh = yf.download("^SSEC", start=start_date, end=end_date, interval="1d")
        if sh.empty:
            print("未获取到数据。")
            return
        sh = sh[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        filename = os.path.join(DATA_DIR, f"shanghai_index_daily_{datetime.now().strftime('%Y%m%d')}.csv")
        sh.to_csv(filename)
        print(f"成功！已保存至: {filename}")
        print(sh.tail())
    except Exception as e:
        print(f"获取数据时发生错误: {e}")
        print("安装: pip install yfinance pandas")

if __name__ == "__main__":
    download_shanghai_index()
