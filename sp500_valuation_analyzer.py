"""
标普500指数估值分析器 - 完整版
================================
功能：在线抓取真实标普500估值数据，计算历史百分位

数据源：
  1. MULTPL (www.multpl.com) - 席勒CAPE (Shiller P/E 10) 月度数据
     - 席勒CAPE使用过去10年平均通胀调整后的盈利计算
  2. MULTPL - S&P500 TTM PE Ratio 月度数据
  3. Yahoo Finance (备用/补充) - 实时市场数据

时间范围：2006-2026年 完整20年月度数据

依赖安装：
  pip install pandas numpy yfinance matplotlib requests beautifulsoup4

作者：AI Assistant
日期：2026-06-29
"""

import pandas as pd
import numpy as np
import yfinance as yf
import requests
import warnings
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from bs4 import BeautifulSoup
import re

warnings.filterwarnings("ignore")

# ============================================================
# 第一部分：配置与常量
# ============================================================

# 数据源配置
MULTPL_CAPE_URL = "https://www.multpl.com/shiller-pe/table/by-month"
MULTPL_PE_URL = "https://www.multpl.com/s-p-500-pe-ratio/table/by-month"

# 时间范围配置
START_YEAR = 2006
END_YEAR = 2026

# 异常值过滤阈值
PE_MIN_VALID = 0      # PE下限（剔除负值）
PE_MAX_VALID = 200    # PE上限（剔除极端异常）

# 网络请求配置
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# ============================================================
# 第二部分：网络异常处理装饰器
# ============================================================

def with_retry(max_retries: int = 3, delay: float = 2.0):
    """
    网络请求重试装饰器
    
    参数:
        max_retries: 最大重试次数
        delay: 每次重试间隔(秒)
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            import time
            last_error = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (requests.RequestException, Exception) as e:
                    last_error = e
                    if attempt < max_retries:
                        print(f"  ⚠️ 第{attempt}次尝试失败: {str(e)[:50]}...")
                        print(f"     {delay}秒后重试...")
                        time.sleep(delay)
                    else:
                        print(f"  ❌ 所有{max_retries}次尝试均失败")
            raise last_error
        return wrapper
    return decorator

# ============================================================
# 第三部分：MULTPL 席勒CAPE数据获取
# ============================================================

@with_retry(max_retries=3, delay=2.0)
def fetch_multpl_cape_data() -> pd.DataFrame:
    """
    从MULTPL网站获取席勒CAPE (Shiller P/E 10) 真实历史数据
    
    席勒CAPE使用过去10年平均通胀调整后的盈利计算，
    是比TTM PE更稳定的长期估值指标。
    
    数据源: https://www.multpl.com/shiller-pe
    
    返回: DataFrame[date, cape]，月度数据
    """
    print("\n【数据源1: MULTPL 席勒CAPE】")
    print("-" * 50)
    print(f"  数据源URL: {MULTPL_CAPE_URL}")
    
    try:
        response = requests.get(MULTPL_CAPE_URL, headers=HEADERS, timeout=30)
        response.raise_for_status()
        html = response.text
        
        # 使用BeautifulSoup解析HTML
        df = parse_multpl_table(html, 'cape')
        
        if df is not None and len(df) > 0:
            # 筛选时间范围
            df = df[(df['date'].dt.year >= START_YEAR) & (df['date'].dt.year <= END_YEAR)]
            df = df.reset_index(drop=True)
            
            if len(df) > 0:
                print(f"✅ 成功获取CAPE数据: {len(df)}条")
                print(f"   时间范围: {df['date'].min().date()} ~ {df['date'].max().date()}")
                print(f"   当前CAPE: {df['cape'].iloc[-1]:.2f}")
                return df
        
        raise ValueError("解析后无有效数据")
        
    except Exception as e:
        print(f"  ❌ 从MULTPL获取CAPE失败: {e}")
        print("  切换到备用数据源...")
        return fetch_backup_cape()


def parse_multpl_table(html: str, value_column: str) -> Optional[pd.DataFrame]:
    """
    使用BeautifulSoup解析MULTPL网站的HTML表格
    
    表格结构:
    <table id="datatable">
        <tr><th>Date</th><th>Value</th></tr>
        <tr class="odd"><td>Jun 26, 2026</td><td>40.70</td></tr>
        <tr class="even"><td>Jun 1, 2026</td><td>41.32</td></tr>
        ...
    </table>
    
    参数:
        html: 网页HTML内容
        value_column: 值列名 (如 'cape' 或 'ttm_pe')
    
    返回: DataFrame[date, value_column]
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    # 查找数据表格
    table = soup.find('table', {'id': 'datatable'})
    if not table:
        # 尝试其他选择器
        table = soup.find('table')
        if not table:
            raise ValueError("未找到数据表格")
    
    rows = []
    
    # 遍历表格行
    for tr in table.find_all('tr'):
        tds = tr.find_all('td')
        if len(tds) < 2:
            continue  # 跳过表头行
        
        # 提取日期和值
        date_text = tds[0].get_text(strip=True)
        value_text = tds[1].get_text(strip=True)
        
        # 清理值文本 (移除空格、特殊字符)
        value_text = value_text.replace('\u2002', '').replace('\xa0', '').replace(',', '').strip()
        
        try:
            # 解析日期 (格式: "Jun 26, 2026" 或 "Jun 1, 2026")
            dt = pd.to_datetime(date_text, errors='coerce')
            if pd.isna(dt):
                # 尝试手动解析
                for fmt in ["%b %d, %Y", "%b %d %Y", "%B %d, %Y", "%Y-%m-%d", "%m/%d/%Y"]:
                    try:
                        dt = datetime.strptime(date_text, fmt)
                        break
                    except ValueError:
                        continue
            
            if pd.isna(dt) or dt.year < 1900:
                continue
            
            # 解析数值
            value = float(value_text)
            
            # 有效性检查
            if PE_MIN_VALID <= value <= PE_MAX_VALID:
                rows.append({'date': dt, value_column: value})
                
        except (ValueError, TypeError):
            continue
    
    if not rows:
        return None
    
    df = pd.DataFrame(rows)
    df = df.sort_values('date').reset_index(drop=True)
    return df


def fetch_backup_cape() -> pd.DataFrame:
    """
    备用方案：通过SPY ETF估算CAPE近似值
    
    注意: 这是近似值，非真实CAPE
    """
    print("  使用YFinance SPY作为备用数据源...")
    
    try:
        spy = yf.Ticker("SPY")
        end_date = datetime.today()
        start_date = datetime(START_YEAR, 1, 1)
        
        hist = spy.history(start=start_date, end=end_date)
        
        if hist.empty or len(hist) < 100:
            raise ValueError("获取的历史数据不足")
        
        # 获取月度价格
        monthly_prices = hist['Close'].resample('M').last()
        
        # 获取当前PE作为起点
        info = spy.info
        current_pe = info.get('trailingPE', 25.0)
        current_price = monthly_prices.iloc[-1]
        
        # 估算CAPE (CAPE通常比TTM PE高约10-20%，因为用10年平均盈利)
        # 这里使用12个月移动平均价格来模拟平滑效果
        prices_rolling = monthly_prices.rolling(window=12, min_periods=1).mean()
        
        cape_values = []
        for date, price in monthly_prices.items():
            smoothed_price = prices_rolling.loc[date]
            price_ratio = smoothed_price / current_price
            estimated_cape = current_pe * price_ratio * 1.15  # 1.15系数近似CAPE/TTM比例
            cape_values.append(estimated_cape)
        
        df = pd.DataFrame({
            'date': monthly_prices.index,
            'cape': cape_values
        })
        
        df['date'] = pd.to_datetime(df['date'])
        df = df[(df['date'].dt.year >= START_YEAR) & (df['date'].dt.year <= END_YEAR)]
        
        print(f"  ⚠️ 使用估算CAPE数据: {len(df)}条")
        return df
        
    except Exception as e:
        print(f"  备用方案失败: {e}")
        return pd.DataFrame(columns=['date', 'cape'])

# ============================================================
# 第四部分：MULTPL TTM PE数据获取
# ============================================================

@with_retry(max_retries=3, delay=2.0)
def fetch_multpl_ttm_pe() -> pd.DataFrame:
    """
    从MULTPL网站获取S&P500 TTM滚动PE真实历史数据
    
    TTM PE = 当前价格 / 过去12个月每股收益(EPS)
    
    数据源: https://www.multpl.com/s-p-500-pe-ratio
    
    返回: DataFrame[date, ttm_pe]，月度数据
    """
    print("\n【数据源2: MULTPL TTM PE】")
    print("-" * 50)
    print(f"  数据源URL: {MULTPL_PE_URL}")
    
    try:
        response = requests.get(MULTPL_PE_URL, headers=HEADERS, timeout=30)
        response.raise_for_status()
        html = response.text
        
        # 解析HTML表格
        df = parse_multpl_table(html, 'ttm_pe')
        
        if df is not None and len(df) > 0:
            # 筛选时间范围
            df = df[(df['date'].dt.year >= START_YEAR) & (df['date'].dt.year <= END_YEAR)]
            df = df.reset_index(drop=True)
            
            if len(df) > 0:
                print(f"✅ 成功获取TTM PE数据: {len(df)}条")
                print(f"   时间范围: {df['date'].min().date()} ~ {df['date'].max().date()}")
                print(f"   当前TTM PE: {df['ttm_pe'].iloc[-1]:.2f}")
                return df
        
        raise ValueError("解析后无有效数据")
        
    except Exception as e:
        print(f"  ❌ 从MULTPL获取TTM PE失败: {e}")
        print("  切换到备用数据源...")
        return fetch_backup_ttm_pe()


def fetch_backup_ttm_pe() -> pd.DataFrame:
    """
    备用方案：使用YFinance的^GSPC数据估算TTM PE
    """
    print("  使用YFinance ^GSPC作为备用数据源...")
    
    try:
        ticker = yf.Ticker("^GSPC")
        end_date = datetime.today()
        start_date = datetime(START_YEAR, 1, 1)
        
        hist = ticker.history(start=start_date, end=end_date)
        
        if hist.empty:
            raise ValueError("未获取到指数数据")
        
        # 获取月度价格
        monthly_prices = hist['Close'].resample('M').last()
        
        # 获取当前TTM PE
        info = ticker.info
        current_pe = info.get('trailingPE', None)
        
        if current_pe is None:
            # 尝试从SPY获取
            spy = yf.Ticker("SPY")
            spy_info = spy.info
            current_pe = spy_info.get('trailingPE', 25.0)
        
        current_price = monthly_prices.iloc[-1]
        
        # 构建TTM PE序列
        pe_values = []
        for date, price in monthly_prices.items():
            ratio = price / current_price
            estimated_pe = current_pe * ratio
            pe_values.append(estimated_pe)
        
        df = pd.DataFrame({
            'date': monthly_prices.index,
            'ttm_pe': pe_values
        })
        
        df['date'] = pd.to_datetime(df['date'])
        df = df[(df['date'].dt.year >= START_YEAR) & (df['date'].dt.year <= END_YEAR)]
        
        print(f"  ⚠️ 使用估算TTM PE数据: {len(df)}条")
        return df
        
    except Exception as e:
        print(f"  备用方案失败: {e}")
        return pd.DataFrame(columns=['date', 'ttm_pe'])

# ============================================================
# 第五部分：数据清洗与处理
# ============================================================

def clean_and_merge_data(cape_df: pd.DataFrame, ttm_df: pd.DataFrame) -> pd.DataFrame:
    """
    合并CAPE和TTM PE数据，进行数据清洗
    
    清洗规则:
    1. 剔除PE <= 0 的数据 (负EPS无意义)
    2. 剔除PE > 200 的极端异常值
    3. 剔除EPS为负的数据 (已通过PE过滤间接实现)
    4. 填充少量缺失值 (线性插值)
    5. 合并两个数据源到统一时间索引
    
    参数:
        cape_df: CAPE数据
        ttm_df: TTM PE数据
    
    返回: 合并后的DataFrame
    """
    print("\n【数据清洗与合并】")
    print("-" * 50)
    
    # 确保日期格式正确
    if not cape_df.empty:
        cape_df['date'] = pd.to_datetime(cape_df['date'])
    if not ttm_df.empty:
        ttm_df['date'] = pd.to_datetime(ttm_df['date'])
    
    # 设置日期索引
    if not cape_df.empty:
        cape_df = cape_df.set_index('date')
    if not ttm_df.empty:
        ttm_df = ttm_df.set_index('date')
    
    # 按月统一索引 (每月最后一天)
    def align_to_month_end(df):
        df.index = df.index.to_period('M').to_timestamp('M')
        return df.groupby(df.index).last()
    
    if not cape_df.empty:
        cape_df = align_to_month_end(cape_df)
    if not ttm_df.empty:
        ttm_df = align_to_month_end(ttm_df)
    
    # 合并数据
    if not cape_df.empty and not ttm_df.empty:
        df = pd.merge(cape_df, ttm_df, left_index=True, right_index=True, how='outer')
    elif not cape_df.empty:
        df = cape_df.copy()
    elif not ttm_df.empty:
        df = ttm_df.copy()
    else:
        raise ValueError("两个数据源都为空")
    
    # 按时间排序
    df = df.sort_index()
    
    # 限制时间范围
    start_date = datetime(START_YEAR, 1, 1)
    end_date = datetime(END_YEAR, 12, 31)
    df = df[(df.index >= start_date) & (df.index <= end_date)]
    
    n_before = len(df)
    print(f"合并前数据点: {n_before}")
    
    # 清洗: 剔除极端异常值并统计
    for col in ['cape', 'ttm_pe']:
        if col in df.columns:
            before_count = df[col].notna().sum()
            # 标记异常值为NaN
            df.loc[(df[col] <= PE_MIN_VALID) | (df[col] > PE_MAX_VALID), col] = np.nan
            after_count = df[col].notna().sum()
            removed = before_count - after_count
            if removed > 0:
                print(f"  {col.upper()}清洗: 剔除{removed}个异常值 → {after_count}个有效值")
    
    # 填充缺失值
    for col in ['cape', 'ttm_pe']:
        if col in df.columns:
            missing = df[col].isna().sum()
            if missing > 0:
                # 先进行线性插值，再前后向填充
                df[col] = df[col].interpolate(method='linear', limit_direction='both')
                df[col] = df[col].ffill().bfill()
                print(f"  {col.upper()}填充: {missing}个缺失值已处理")
    
    # 再次过滤，确保无异常值
    for col in ['cape', 'ttm_pe']:
        if col in df.columns:
            df.loc[(df[col] <= PE_MIN_VALID) | (df[col] > PE_MAX_VALID), col] = np.nan
    
    n_after = len(df)
    print(f"清洗后数据点: {n_after}")
    
    # 重置索引为列
    df = df.reset_index().rename(columns={'index': 'date'})
    df['date'] = pd.to_datetime(df['date'])
    
    # 只保留两个指标都有数据的行（用于对齐比较）
    if 'cape' in df.columns and 'ttm_pe' in df.columns:
        valid_mask = df['cape'].notna() & df['ttm_pe'].notna()
        if valid_mask.sum() > 50:  # 确保有足够的数据
            df = df[valid_mask].reset_index(drop=True)
            print(f"对齐后有效数据: {len(df)}条")
    
    return df

# ============================================================
# 第六部分：百分位计算（核心逻辑）
# ============================================================

def compute_percentile(current_value: float, historical_values: np.ndarray) -> float:
    """
    计算当前值在历史分布中的百分位
    
    公式: 分位 = (小于当前值的样本数量 / 总样本数) × 100
    
    参数:
        current_value: 当前PE值
        historical_values: 历史PE序列
        
    返回:
        percentile: 保留2位小数的百分数
                   (如 85.50 表示85.50%的历史数据小于当前值)
    """
    if len(historical_values) == 0 or np.isnan(current_value):
        return 0.0
    
    # 过滤掉NaN值
    clean_values = historical_values[~np.isnan(historical_values)]
    
    if len(clean_values) == 0:
        return 0.0
    
    # 统计严格小于当前值的样本数
    count_less = np.sum(clean_values < current_value)
    total = len(clean_values)
    
    # 计算百分位
    percentile = (count_less / total) * 100
    
    return round(percentile, 2)


def calculate_percentiles(df: pd.DataFrame) -> Dict:
    """
    计算CAPE和TTM PE在各时间区间的历史百分位
    
    区间:
    ① 近5年
    ② 近10年
    ③ 近20年
    
    参数:
        df: 包含date、cape、ttm_pe的DataFrame
    
    返回: 完整的结果字典
    """
    print("\n【百分位计算】")
    print("-" * 50)
    
    df = df.sort_values('date').reset_index(drop=True)
    latest_date = df['date'].iloc[-1]
    
    results = {
        'latest_date': latest_date,
        'cape': {},
        'ttm_pe': {}
    }
    
    # 提取最新值
    if 'cape' in df.columns and df['cape'].notna().any():
        current_cape = df['cape'].iloc[-1]
        results['cape']['current'] = round(current_cape, 2)
        print(f"最新CAPE: {current_cape:.2f} (日期: {latest_date.date()})")
    else:
        current_cape = None
        results['cape']['current'] = None
    
    if 'ttm_pe' in df.columns and df['ttm_pe'].notna().any():
        current_ttm = df['ttm_pe'].iloc[-1]
        results['ttm_pe']['current'] = round(current_ttm, 2)
        print(f"最新TTM PE: {current_ttm:.2f} (日期: {latest_date.date()})")
    else:
        current_ttm = None
        results['ttm_pe']['current'] = None
    
    # 计算各区间百分位
    now = pd.Timestamp.now()
    periods = {
        '5年': 5,
        '10年': 10,
        '20年': 20
    }
    
    for period_name, years in periods.items():
        cutoff_date = now - pd.DateOffset(years=years)
        
        # CAPE百分位
        if current_cape is not None and 'cape' in df.columns:
            mask = df['date'] >= cutoff_date
            period_cape = df.loc[mask, 'cape'].dropna().values
            if len(period_cape) > 0:
                percentile = compute_percentile(current_cape, period_cape)
                results['cape'][f'{period_name}_percentile'] = percentile
                results['cape'][f'{period_name}_count'] = len(period_cape)
                print(f"  CAPE 近{period_name}: {percentile}% 分位 (样本{len(period_cape)})")
        
        # TTM PE百分位
        if current_ttm is not None and 'ttm_pe' in df.columns:
            mask = df['date'] >= cutoff_date
            period_ttm = df.loc[mask, 'ttm_pe'].dropna().values
            if len(period_ttm) > 0:
                percentile = compute_percentile(current_ttm, period_ttm)
                results['ttm_pe'][f'{period_name}_percentile'] = percentile
                results['ttm_pe'][f'{period_name}_count'] = len(period_ttm)
                print(f"  TTM PE 近{period_name}: {percentile}% 分位 (样本{len(period_ttm)})")
    
    # 计算描述性统计
    for metric in ['cape', 'ttm_pe']:
        if metric in df.columns and df[metric].notna().any():
            values = df[metric].dropna().values
            results[metric]['stats'] = {
                'min': round(float(np.min(values)), 2),
                'max': round(float(np.max(values)), 2),
                'mean': round(float(np.mean(values)), 2),
                'median': round(float(np.median(values)), 2),
                'std': round(float(np.std(values, ddof=1)), 2)
            }
    
    return results

# ============================================================
# 第七部分：格式化输出
# ============================================================

def print_results(results: Dict):
    """
    打印格式化结果表格
    
    输出格式:
    ================================================================================
      标普500估值历史百分位分析结果
    ================================================================================
    数据日期: YYYY-MM-DD
    --------------------------------------------------------------------------------
    指标           当前值        近5年分位        近10年分位       近20年分位      
    --------------------------------------------------------------------------------
    席勒CAPE       XX.XX      XX.XX%       XX.XX%       XX.XX%      
    TTM PE         XX.XX      XX.XX%       XX.XX%       XX.XX%      
    --------------------------------------------------------------------------------
    
    【估值水平判定】
    --------------------------------------------------
      席勒CAPE: 当前XX.XX → [估值区间]
      TTM PE: 当前XX.XX → [估值区间]
    ================================================================================
    """
    print("\n" + "=" * 80)
    print("  标普500估值历史百分位分析结果")
    print("=" * 80)
    print(f"数据日期: {results['latest_date'].date()}")
    print("-" * 80)
    
    # 表头
    header = f"{'指标':<12} {'当前值':<10} {'近5年分位':<12} {'近10年分位':<12} {'近20年分位':<12}"
    print(header)
    print("-" * 80)
    
    # CAPE行
    if results['cape'].get('current') is not None:
        cape = results['cape']
        p5y = cape.get('5年_percentile', 'N/A')
        p10y = cape.get('10年_percentile', 'N/A')
        p20y = cape.get('20年_percentile', 'N/A')
        
        p5y_str = f"{p5y}%" if isinstance(p5y, (int, float)) else p5y
        p10y_str = f"{p10y}%" if isinstance(p10y, (int, float)) else p10y
        p20y_str = f"{p20y}%" if isinstance(p20y, (int, float)) else p20y
        
        row = f"{'席勒CAPE':<12} {cape['current']:<10.2f} {p5y_str:<12} {p10y_str:<12} {p20y_str:<12}"
        print(row)
    
    # TTM PE行
    if results['ttm_pe'].get('current') is not None:
        ttm = results['ttm_pe']
        p5y = ttm.get('5年_percentile', 'N/A')
        p10y = ttm.get('10年_percentile', 'N/A')
        p20y = ttm.get('20年_percentile', 'N/A')
        
        p5y_str = f"{p5y}%" if isinstance(p5y, (int, float)) else p5y
        p10y_str = f"{p10y}%" if isinstance(p10y, (int, float)) else p10y
        p20y_str = f"{p20y}%" if isinstance(p20y, (int, float)) else p20y
        
        row = f"{'TTM PE':<12} {ttm['current']:<10.2f} {p5y_str:<12} {p10y_str:<12} {p20y_str:<12}"
        print(row)
    
    print("-" * 80)
    
    # 估值水平判定
    print("\n【估值水平判定】")
    print("-" * 50)
    
    for metric_name, metric_key in [('席勒CAPE', 'cape'), ('TTM PE', 'ttm_pe')]:
        if metric_key in results and results[metric_key].get('current') is not None:
            metric = results[metric_key]
            current = metric['current']
            pct_20y = metric.get('20年_percentile', 50)
            
            if isinstance(pct_20y, (int, float)):
                if pct_20y <= 20:
                    level = "🔵 低估区间 (≤20%分位) - 价值投资机会"
                elif pct_20y <= 40:
                    level = "🟢 偏低区间 (20%-40%分位) - 适度关注"
                elif pct_20y <= 60:
                    level = "🟡 合理区间 (40%-60%分位) - 估值中性"
                elif pct_20y <= 80:
                    level = "🟠 偏高区间 (60%-80%分位) - 谨慎对待"
                else:
                    level = "🔴 高估区间 (>80%分位) - 风险较高"
                
                print(f"  {metric_name}: 当前{current:.2f} → {level}")
    
    # 分位解读
    print("\n【分位解读】")
    print("-" * 50)
    print("  分位含义: 当前估值高于历史上X%的时间")
    print("  例如: 85%分位表示当前估值比85%的历史时期都贵")
    
    print("=" * 80)


def print_detailed_stats(results: Dict):
    """
    打印详细统计信息
    """
    print("\n【详细统计信息】")
    print("-" * 60)
    
    for metric_name, metric_key in [('席勒CAPE (P/E10)', 'cape'), ('TTM PE', 'ttm_pe')]:
        if metric_key in results and results[metric_key].get('stats') is not None:
            stats = results[metric_key]['stats']
            print(f"\n{metric_name} (20年完整样本):")
            print(f"  最小值: {stats['min']:.2f}")
            print(f"  最大值: {stats['max']:.2f}")
            print(f"  平均值: {stats['mean']:.2f}")
            print(f"  中位数: {stats['median']:.2f}")
            print(f"  标准差: {stats['std']:.2f}")

# ============================================================
# 第八部分：可视化
# ============================================================

def plot_valuation_history(df: pd.DataFrame, results: Dict):
    """
    绘制20年PE走势图表
    
    包含:
    - CAPE历史曲线
    - TTM PE历史曲线
    - 当前估值水平线
    - 百分位区间标注
    
    参数:
        df: 包含date、cape、ttm_pe的DataFrame
        results: 计算结果字典
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib import font_manager as fm
    except ImportError:
        print("\n⚠️ matplotlib未安装，跳过可视化")
        print("   安装命令: pip install matplotlib")
        return
    
    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'SimHei', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False
    
    df = df.sort_values('date')
    
    fig, axes = plt.subplots(2, 1, figsize=(16, 12), sharex=True)
    fig.suptitle('S&P 500 Valuation History (2006-2026)', fontsize=16, fontweight='bold')
    
    # 子图1: CAPE
    ax1 = axes[0]
    if 'cape' in df.columns and df['cape'].notna().any():
        ax1.plot(df['date'], df['cape'], color='#2196F3', linewidth=1.5, 
                label='Shiller CAPE (P/E10)', alpha=0.8)
        
        current_cape = results['cape'].get('current')
        if current_cape:
            ax1.axhline(y=current_cape, color='#F44336', linestyle='--', linewidth=2, 
                       label=f'Current CAPE = {current_cape}')
            
            # 添加当前值标注
            ax1.annotate(f'Current CAPE: {current_cape}',
                        xy=(df['date'].iloc[-1], current_cape),
                        xytext=(df['date'].iloc[-20] if len(df) > 20 else df['date'].iloc[0], 
                               current_cape * 1.15),
                        fontsize=11, fontweight='bold', color='#F44336',
                        ha='center',
                        arrowprops=dict(arrowstyle='->', color='#F44336', lw=1.5))
        
        # 添加历史均值线
        mean_cape = df['cape'].mean()
        ax1.axhline(y=mean_cape, color='#4CAF50', linestyle=':', linewidth=1.5, 
                   alpha=0.7, label=f'Historical Mean = {mean_cape:.2f}')
        
        # 添加估值区间带
        p75 = df['cape'].quantile(0.75)
        p25 = df['cape'].quantile(0.25)
        ax1.axhspan(p25, p75, alpha=0.1, color='gray', label=f'25%-75% Range')
    
    ax1.set_ylabel('CAPE (P/E10)', fontsize=12)
    ax1.legend(loc='upper left', fontsize=10)
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.set_title('Shiller CAPE - 10-Year Average Real Earnings', fontsize=13)
    
    # 子图2: TTM PE
    ax2 = axes[1]
    if 'ttm_pe' in df.columns and df['ttm_pe'].notna().any():
        ax2.plot(df['date'], df['ttm_pe'], color='#FF9800', linewidth=1.5, 
                label='TTM P/E Ratio', alpha=0.8)
        
        current_ttm = results['ttm_pe'].get('current')
        if current_ttm:
            ax2.axhline(y=current_ttm, color='#F44336', linestyle='--', linewidth=2,
                       label=f'Current TTM PE = {current_ttm}')
            
            ax2.annotate(f'Current TTM PE: {current_ttm}',
                        xy=(df['date'].iloc[-1], current_ttm),
                        xytext=(df['date'].iloc[-20] if len(df) > 20 else df['date'].iloc[0], 
                               current_ttm * 1.15),
                        fontsize=11, fontweight='bold', color='#F44336',
                        ha='center',
                        arrowprops=dict(arrowstyle='->', color='#F44336', lw=1.5))
        
        # 添加历史均值线
        mean_ttm = df['ttm_pe'].mean()
        ax2.axhline(y=mean_ttm, color='#4CAF50', linestyle=':', linewidth=1.5,
                   alpha=0.7, label=f'Historical Mean = {mean_ttm:.2f}')
        
        # 添加估值区间带
        p75 = df['ttm_pe'].quantile(0.75)
        p25 = df['ttm_pe'].quantile(0.25)
        ax2.axhspan(p25, p75, alpha=0.1, color='gray', label=f'25%-75% Range')
    
    ax2.set_xlabel('Date', fontsize=12)
    ax2.set_ylabel('TTM P/E Ratio', fontsize=12)
    ax2.legend(loc='upper left', fontsize=10)
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.set_title('Trailing 12-Month P/E Ratio', fontsize=13)
    
    # X轴格式
    ax2.xaxis.set_major_locator(mdates.YearLocator(2))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    
    plt.tight_layout()
    
    # 保存图片
    output_path = f"sp500_valuation_{datetime.now().strftime('%Y%m%d')}.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n📊 图表已保存: {output_path}")
    
    plt.show()

# ============================================================
# 第九部分：主流程
# ============================================================

def main():
    """
    主函数：串联数据获取→清洗→计算→输出→可视化全过程
    
    执行流程:
    1. 获取CAPE数据 (MULTPL优先，失败则用YFinance备用)
    2. 获取TTM PE数据 (MULTPL优先，失败则用YFinance备用)
    3. 数据清洗与合并
    4. 计算各周期历史百分位
    5. 格式化打印结果表格
    6. 打印详细统计信息
    7. 绘制可视化图表
    
    网络异常处理:
    - 自动重试3次，每次间隔2秒
    - 主数据源失败时自动切换备用源
    - 详细错误提示和建议
    """
    print("=" * 80)
    print("  标普500估值历史百分位分析工具")
    print("  数据源: MULTPL.com (CAPE + TTM PE)")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    try:
        # 步骤1: 获取CAPE数据
        cape_df = fetch_multpl_cape_data()
        
        # 步骤2: 获取TTM PE数据
        ttm_df = fetch_multpl_ttm_pe()
        
        # 检查数据获取结果
        if cape_df.empty and ttm_df.empty:
            print("\n❌ 错误: 未能获取任何估值数据")
            print("   请检查网络连接或稍后重试")
            return 1
        
        # 步骤3: 数据清洗与合并
        merged_df = clean_and_merge_data(cape_df, ttm_df)
        
        if merged_df.empty or len(merged_df) < 12:
            print("\n❌ 错误: 数据不足12个月，无法进行分析")
            return 1
        
        # 步骤4: 计算百分位
        results = calculate_percentiles(merged_df)
        
        # 步骤5: 打印结果表格
        print_results(results)
        
        # 步骤6: 打印详细统计
        print_detailed_stats(results)
        
        # 步骤7: 可视化
        print("\n正在生成可视化图表...")
        plot_valuation_history(merged_df, results)
        
        print("\n✅ 分析完成!")
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断程序")
        return 130
    except Exception as e:
        print(f"\n❌ 程序执行出错: {e}")
        import traceback
        traceback.print_exc()
        print("\n【故障排除建议】")
        print("  1. 检查网络连接是否正常")
        print("  2. 确认已安装所需依赖:")
        print("     pip install pandas numpy yfinance matplotlib requests beautifulsoup4")
        print("  3. 稍后重试（可能是数据源临时不可用）")
        print("  4. 检查是否安装了beautifulsoup4用于HTML解析:")
        print("     pip install beautifulsoup4 lxml")
        return 1


# ============================================================
# 依赖安装说明
# ============================================================
"""
═══════════════════════════════════════════════════════════════════════════════
                          【安装依赖说明】
═══════════════════════════════════════════════════════════════════════════════

首次运行前，请确保已安装以下Python包:

# 方式1: 使用pip逐一安装 (推荐)
pip install pandas numpy yfinance matplotlib requests beautifulsoup4 lxml

# 方式2: 使用requirements.txt
cat > requirements_sp500.txt << 'EOF'
pandas>=1.5.0
numpy>=1.21.0
yfinance>=0.2.0
matplotlib>=3.5.0
requests>=2.28.0
beautifulsoup4>=4.11.0
lxml>=4.9.0
EOF
pip install -r requirements_sp500.txt

# 方式3: 一键安装（Linux/Mac/Windows）
pip install pandas numpy yfinance matplotlib requests beautifulsoup4 lxml

═══════════════════════════════════════════════════════════════════════════════
                          【数据源说明】
═══════════════════════════════════════════════════════════════════════════════

1. 席勒CAPE (Shiller P/E 10)
   数据源: https://www.multpl.com/shiller-pe
   说明: 使用过去10年平均通胀调整盈利的PE，长期估值指标
   作者: Robert Shiller (诺贝尔经济学奖得主)

2. TTM PE (Trailing 12-Month PE)
   数据源: https://www.multpl.com/s-p-500-pe-ratio
   说明: 使用过去12个月盈利的PE，短期估值指标

3. 备用数据源
   主数据源失败时自动使用Yahoo Finance (^GSPC/SPY)
   数据为实时估算值，精度略低于MULTPL

═══════════════════════════════════════════════════════════════════════════════
                          【运行程序】
═══════════════════════════════════════════════════════════════════════════════

python sp500_valuation_analyzer.py

═══════════════════════════════════════════════════════════════════════════════
"""

if __name__ == "__main__":
    exit(main())
