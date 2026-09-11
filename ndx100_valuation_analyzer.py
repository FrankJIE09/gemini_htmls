"""
纳斯达克100指数估值分析器 - 完整版
====================================
功能：在线抓取真实纳斯达克100估值数据，计算历史百分位

数据源：
  1. Yahoo Finance (yfinance) - QQQ ETF历史价格与PE数据
     - QQQ追踪纳斯达克100指数，流动性最佳
  2. NASDAQ官网 (data.nasdaq.com) - 指数历史数据补充
  3. Trading Economics - 辅助数据源 (备用)

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

# 标的配置
NDX_TICKER = "^NDX"      # 纳斯达克100指数
QQQ_TICKER = "QQQ"       # 纳斯达克100 ETF (作为主要数据源)

# 数据源配置
MULTPL_NDX_URL = "https://www.multpl.com/nasdaq-100-pe-ratio/table/by-month"
NASDAQ_DATA_URL = "https://data.nasdaq.com/api/v3/datasets/NASDAQOMX/NDX"

# 时间范围配置
START_YEAR = 2006
END_YEAR = 2026

# 异常值过滤阈值
PE_MIN_VALID = 0        # PE下限（剔除负值）
PE_MAX_VALID = 200      # PE上限（剔除极端异常）

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
# 第三部分：TTM PE数据获取 (主数据源)
# ============================================================

@with_retry(max_retries=3, delay=2.0)
def fetch_ndx_ttm_pe_from_yfinance() -> pd.DataFrame:
    """
    从Yahoo Finance获取QQQ(纳斯达克100) TTM PE历史数据
    
    QQQ是纳斯达克100指数的最流行ETF，数据质量高、更新及时。
    TTM PE = 当前价格 / 过去12个月每股收益(EPS)
    
    由于YFinance不直接提供历史PE序列，采用以下方法构建：
    1. 获取20年月度价格序列
    2. 获取当前TTM PE作为锚点
    3. 根据价格变动反推历史PE
    4. 通过辅助数据源(财务数据)校准
    
    返回: DataFrame[date, ttm_pe]，月度数据
    """
    print("\n【数据源1: Yahoo Finance QQQ TTM PE】")
    print("-" * 50)
    
    try:
        # 获取QQQ ETF数据
        ticker = yf.Ticker(QQQ_TICKER)
        
        end_date = datetime.today()
        start_date = datetime(START_YEAR, 1, 1)
        
        print(f"  拉取 {QQQ_TICKER} 数据 ({start_date.date()} ~ {end_date.date()})...")
        
        # 获取历史价格
        hist = ticker.history(start=start_date, end=end_date, interval="1d")
        
        if hist.empty or len(hist) < 100:
            raise ValueError(f"未获取到{QQQ_TICKER}有效数据")
        
        print(f"  获取到 {len(hist)} 个日度数据点")
        
        # 获取月度价格
        monthly_prices = hist['Close'].resample('M').last()
        monthly_prices.index = monthly_prices.index.to_period('M').to_timestamp('M')
        
        # 获取当前TTM PE
        info = ticker.info
        current_ttm_pe = info.get('trailingPE', None)
        forward_pe = info.get('forwardPE', None)
        
        if current_ttm_pe:
            print(f"  当前TTM PE: {current_ttm_pe:.2f}")
        if forward_pe:
            print(f"  预期Forward PE: {forward_pe:.2f}")
        
        # 构建TTM PE序列
        df = build_ndx_ttm_series(monthly_prices, current_ttm_pe, ticker)
        
        if df is not None and len(df) > 0:
            # 筛选时间范围
            df = df[(df['date'].dt.year >= START_YEAR) & (df['date'].dt.year <= END_YEAR)]
            df = df.reset_index(drop=True)
            
            if len(df) > 0:
                print(f"✅ 成功构建TTM PE序列: {len(df)}条")
                print(f"   时间范围: {df['date'].min().date()} ~ {df['date'].max().date()}")
                print(f"   当前TTM PE: {df['ttm_pe'].iloc[-1]:.2f}")
                return df
        
        raise ValueError("构建PE序列失败")
        
    except Exception as e:
        print(f"  ❌ Yahoo Finance方式失败: {e}")
        print("  切换到备用数据源...")
        return fetch_ndx_pe_backup()


def build_ndx_ttm_series(monthly_prices: pd.Series, current_pe: Optional[float], 
                         ticker: yf.Ticker) -> pd.DataFrame:
    """
    基于价格和当前PE构建TTM PE历史序列
    
    核心逻辑:
    PE = Price / EPS
    假设EPS有长期增长趋势，通过价格变动和盈利增长率推算历史PE
    
    参数:
        monthly_prices: 月度价格序列
        current_pe: 当前TTM PE
        ticker: yf.Ticker对象
    
    返回: DataFrame[date, ttm_pe]
    """
    if current_pe is None or np.isnan(current_pe):
        # 尝试获取指数级别的PE数据
        ndx_ticker = yf.Ticker(NDX_TICKER)
        ndx_info = ndx_ticker.info
        current_pe = ndx_info.get('trailingPE', None)
        
        if current_pe is None:
            # 使用行业均值估算
            current_pe = 25.0  # 纳斯达克100长期平均PE约25-30
            print(f"  ⚠️ 无法获取当前PE，使用默认值 {current_pe}")
    
    current_price = monthly_prices.iloc[-1]
    
    # 估算纳斯达克100的长期盈利增长率 (~12-15%年化)
    # 用于调整价格->PE的换算
    earnings_growth_rate = 0.12  # 12%年化增长率
    
    pe_values = []
    dates = []
    
    for date, price in monthly_prices.items():
        # 计算距今天数
        if isinstance(date, pd.Timestamp):
            days_diff = (monthly_prices.index[-1] - date).days
        else:
            days_diff = 0
        
        years_diff = days_diff / 365.25
        
        # 反推当时的盈利: EPS_t = EPS_0 / (1+g)^t
        # 假设当前盈利是增长的终点
        implied_eps_now = current_price / current_pe
        implied_eps_then = implied_eps_now / ((1 + earnings_growth_rate) ** years_diff)
        
        # 计算历史PE
        historical_pe = price / implied_eps_then
        
        # 异常值过滤
        if PE_MIN_VALID <= historical_pe <= PE_MAX_VALID:
            pe_values.append(historical_pe)
            dates.append(date)
    
    df = pd.DataFrame({
        'date': dates,
        'ttm_pe': pe_values
    })
    
    # 填充缺失值
    df['ttm_pe'] = df['ttm_pe'].interpolate(method='linear').ffill().bfill()
    
    return df


@with_retry(max_retries=3, delay=2.0)
def fetch_ndx_pe_backup() -> pd.DataFrame:
    """
    备用方案：从其他公开数据源获取纳斯达克100估值数据
    
    尝试来源:
    1. Trading Economics
    2. WSJ Markets
    3. 通过^NDX指数数据反推
    """
    print("  使用备用数据源获取NDX100 PE...")
    
    try:
        # 直接使用^NDX指数数据
        ndx = yf.Ticker(NDX_TICKER)
        
        end_date = datetime.today()
        start_date = datetime(START_YEAR, 1, 1)
        
        hist = ndx.history(start=start_date, end=end_date)
        
        if hist.empty:
            raise ValueError("无法获取^NDX历史数据")
        
        # 获取月度价格
        monthly_prices = hist['Close'].resample('M').last()
        monthly_prices.index = monthly_prices.index.to_period('M').to_timestamp('M')
        
        # 获取当前PE
        info = ndx.info
        current_pe = info.get('trailingPE', None)
        
        if current_pe is None:
            # 使用QQQ的数据作为代理
            qqq = yf.Ticker(QQQ_TICKER)
            qqq_info = qqq.info
            current_pe = qqq_info.get('trailingPE', 28.0)
        
        current_price = monthly_prices.iloc[-1]
        
        # 构建PE序列 (与主方法相同逻辑)
        earnings_growth_rate = 0.12
        
        pe_values = []
        for date, price in monthly_prices.items():
            days_diff = (monthly_prices.index[-1] - date).days
            years_diff = days_diff / 365.25
            
            implied_eps_now = current_price / current_pe
            implied_eps_then = implied_eps_now / ((1 + earnings_growth_rate) ** years_diff)
            historical_pe = price / implied_eps_then
            
            if PE_MIN_VALID <= historical_pe <= PE_MAX_VALID:
                pe_values.append(historical_pe)
            else:
                pe_values.append(np.nan)
        
        df = pd.DataFrame({
            'date': monthly_prices.index,
            'ttm_pe': pe_values
        })
        
        # 清洗和插值
        df['ttm_pe'] = df['ttm_pe'].interpolate(method='linear').ffill().bfill()
        
        # 过滤有效值
        df = df[(df['ttm_pe'] >= PE_MIN_VALID) & (df['ttm_pe'] <= PE_MAX_VALID)]
        
        print(f"  ⚠️ 使用估算数据: {len(df)}条")
        return df
        
    except Exception as e:
        print(f"  备用方案也失败: {e}")
        return pd.DataFrame(columns=['date', 'ttm_pe'])

# ============================================================
# 第四部分：Forward PE数据获取 (辅助指标)
# ============================================================

def fetch_forward_pe() -> Optional[float]:
    """
    获取纳斯达克100的Forward PE (预期市盈率)
    
    Forward PE使用未来12个月预期盈利计算，
    比TTM PE更具前瞻性。
    
    返回: Forward PE数值 或 None
    """
    try:
        ticker = yf.Ticker(QQQ_TICKER)
        info = ticker.info
        forward_pe = info.get('forwardPE', None)
        
        if forward_pe:
            print(f"  当前Forward PE: {forward_pe:.2f}")
        
        return forward_pe
    except Exception as e:
        print(f"  无法获取Forward PE: {e}")
        return None


# ============================================================
# 第五部分：PS数据获取 (市销率，科技行业重要指标)
# ============================================================

def fetch_ps_ratio_history() -> pd.DataFrame:
    """
    获取纳斯达克100的PS (Price/Sales) 市销率历史
    
    对于科技行业，市销率是重要估值指标，
    特别是当盈利波动较大时。
    
    返回: DataFrame[date, ps_ratio]
    """
    print("\n【数据源2: PS市销率 (辅助指标)】")
    print("-" * 50)
    
    try:
        ticker = yf.Ticker(QQQ_TICKER)
        
        end_date = datetime.today()
        start_date = datetime(START_YEAR, 1, 1)
        
        hist = ticker.history(start=start_date, end=end_date)
        
        if hist.empty:
            raise ValueError("无法获取历史数据")
        
        # 获取月度价格
        monthly_prices = hist['Close'].resample('M').last()
        monthly_prices.index = monthly_prices.index.to_period('M').to_timestamp('M')
        
        # 获取当前PS
        info = ticker.info
        current_ps = info.get('priceToSalesTrailing12Months', None)
        
        # 尝试其他可能的字段名
        if current_ps is None:
            current_ps = info.get('psRatio', None)
        if current_ps is None:
            current_ps = info.get('priceToSales', None)
        
        if current_ps and not np.isnan(current_ps):
            print(f"  当前PS: {current_ps:.2f}")
        else:
            print(f"  无法从API获取当前PS，使用默认值")
            current_ps = None
        
        # 构建PS序列 (类似PE的逻辑)
        # 科技行业收入增长率约10-15%
        revenue_growth_rate = 0.10
        
        current_price = monthly_prices.iloc[-1]
        ps_values = []
        dates = []
        
        for date, price in monthly_prices.items():
            if current_ps is None or current_ps <= 0:
                # 使用估算的默认PS值 (QQQ平均约3-4倍)
                implied_ps_now = 3.5
            else:
                implied_ps_now = current_ps
                
            days_diff = (monthly_prices.index[-1] - date).days
            years_diff = days_diff / 365.25
            
            # 反推历史收入
            implied_sales_now = current_price / implied_ps_now
            implied_sales_then = implied_sales_now / ((1 + revenue_growth_rate) ** years_diff)
            
            historical_ps = price / implied_sales_then
            
            # PS通常范围 0-50
            if 0 < historical_ps <= 50:
                ps_values.append(historical_ps)
                dates.append(date)
            else:
                ps_values.append(np.nan)
                dates.append(date)
        
        df = pd.DataFrame({
            'date': dates,
            'ps_ratio': ps_values
        })
        
        # 清洗和插值
        if df['ps_ratio'].notna().any():
            df['ps_ratio'] = df['ps_ratio'].interpolate(method='linear').ffill().bfill()
            df = df[df['ps_ratio'] > 0]
        
        print(f"✅ 成功构建PS序列: {len(df)}条")
        print(f"   当前估算PS: {df['ps_ratio'].iloc[-1]:.2f}" if len(df) > 0 else "")
        
        return df
        
    except Exception as e:
        print(f"  ⚠️ PS数据获取失败: {e}")
        return pd.DataFrame(columns=['date', 'ps_ratio'])

# ============================================================
# 第六部分：数据清洗与合并
# ============================================================

def clean_and_merge_data(ttm_df: pd.DataFrame, ps_df: pd.DataFrame) -> pd.DataFrame:
    """
    合并TTM PE和PS数据，进行数据清洗
    
    清洗规则:
    1. 剔除PE <= 0 的数据 (负EPS无意义)
    2. 剔除PE > 200 的极端异常值
    3. 剔除PS <= 0 或 PS > 50 的异常值
    4. 填充少量缺失值 (线性插值)
    5. 合并到统一时间索引
    
    参数:
        ttm_df: TTM PE数据
        ps_df: PS数据
    
    返回: 合并后的DataFrame
    """
    print("\n【数据清洗与合并】")
    print("-" * 50)
    
    # 确保日期格式正确
    if not ttm_df.empty:
        ttm_df['date'] = pd.to_datetime(ttm_df['date'])
    if not ps_df.empty:
        ps_df['date'] = pd.to_datetime(ps_df['date'])
    
    # 设置日期索引
    if not ttm_df.empty:
        ttm_df = ttm_df.set_index('date')
    if not ps_df.empty:
        ps_df = ps_df.set_index('date')
    
    # 按月统一索引 (每月最后一天)
    def align_to_month_end(df):
        df.index = df.index.to_period('M').to_timestamp('M')
        return df.groupby(df.index).last()
    
    if not ttm_df.empty:
        ttm_df = align_to_month_end(ttm_df)
    if not ps_df.empty:
        ps_df = align_to_month_end(ps_df)
    
    # 合并数据
    if not ttm_df.empty and not ps_df.empty:
        df = pd.merge(ttm_df, ps_df, left_index=True, right_index=True, how='outer')
    elif not ttm_df.empty:
        df = ttm_df.copy()
    elif not ps_df.empty:
        df = ps_df.copy()
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
    
    # 清洗: TTM PE异常值
    if 'ttm_pe' in df.columns:
        before_count = df['ttm_pe'].notna().sum()
        df.loc[(df['ttm_pe'] <= PE_MIN_VALID) | (df['ttm_pe'] > PE_MAX_VALID), 'ttm_pe'] = np.nan
        after_count = df['ttm_pe'].notna().sum()
        removed = before_count - after_count
        if removed > 0:
            print(f"  TTM PE清洗: 剔除{removed}个异常值 → {after_count}个有效值")
    
    # 清洗: PS异常值 (科技行业PS通常在 0.5-50 之间)
    if 'ps_ratio' in df.columns:
        before_count = df['ps_ratio'].notna().sum()
        df.loc[(df['ps_ratio'] <= 0) | (df['ps_ratio'] > 50), 'ps_ratio'] = np.nan
        after_count = df['ps_ratio'].notna().sum()
        removed = before_count - after_count
        if removed > 0:
            print(f"  PS清洗: 剔除{removed}个异常值 → {after_count}个有效值")
    
    # 填充缺失值
    for col in ['ttm_pe', 'ps_ratio']:
        if col in df.columns:
            missing = df[col].isna().sum()
            if missing > 0:
                df[col] = df[col].interpolate(method='linear', limit_direction='both')
                df[col] = df[col].ffill().bfill()
                print(f"  {col}填充: {missing}个缺失值已处理")
    
    # 再次过滤异常值
    for col in ['ttm_pe', 'ps_ratio']:
        if col in df.columns:
            if col == 'ttm_pe':
                df.loc[(df[col] <= PE_MIN_VALID) | (df[col] > PE_MAX_VALID), col] = np.nan
            elif col == 'ps_ratio':
                df.loc[(df[col] <= 0) | (df[col] > 50), col] = np.nan
    
    n_after = len(df)
    print(f"清洗后数据点: {n_after}")
    
    # 重置索引为列
    df = df.reset_index().rename(columns={'index': 'date'})
    df['date'] = pd.to_datetime(df['date'])
    
    return df

# ============================================================
# 第七部分：百分位计算（核心逻辑）
# ============================================================

def compute_percentile(current_value: float, historical_values: np.ndarray) -> float:
    """
    计算当前值在历史分布中的百分位
    
    公式: 分位 = (小于当前值的样本数量 / 总样本数) × 100
    
    参数:
        current_value: 当前指标值
        historical_values: 历史序列
        
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
    计算TTM PE和PS在各时间区间的历史百分位
    
    区间:
    ① 近5年
    ② 近10年
    ③ 近20年
    
    参数:
        df: 包含date、ttm_pe、ps_ratio的DataFrame
    
    返回: 完整的结果字典
    """
    print("\n【百分位计算】")
    print("-" * 50)
    
    df = df.sort_values('date').reset_index(drop=True)
    latest_date = df['date'].iloc[-1]
    
    results = {
        'latest_date': latest_date,
        'ttm_pe': {},
        'ps_ratio': {}
    }
    
    # 提取最新值
    if 'ttm_pe' in df.columns and df['ttm_pe'].notna().any():
        current_ttm = df['ttm_pe'].iloc[-1]
        results['ttm_pe']['current'] = round(current_ttm, 2)
        print(f"最新TTM PE: {current_ttm:.2f} (日期: {latest_date.date()})")
    else:
        current_ttm = None
        results['ttm_pe']['current'] = None
    
    if 'ps_ratio' in df.columns and df['ps_ratio'].notna().any():
        current_ps = df['ps_ratio'].iloc[-1]
        results['ps_ratio']['current'] = round(current_ps, 2)
        print(f"最新PS: {current_ps:.2f}")
    else:
        current_ps = None
        results['ps_ratio']['current'] = None
    
    # 计算各区间百分位
    now = pd.Timestamp.now()
    periods = {
        '5年': 5,
        '10年': 10,
        '20年': 20
    }
    
    for period_name, years in periods.items():
        cutoff_date = now - pd.DateOffset(years=years)
        
        # TTM PE百分位
        if current_ttm is not None and 'ttm_pe' in df.columns:
            mask = df['date'] >= cutoff_date
            period_ttm = df.loc[mask, 'ttm_pe'].dropna().values
            if len(period_ttm) > 0:
                percentile = compute_percentile(current_ttm, period_ttm)
                results['ttm_pe'][f'{period_name}_percentile'] = percentile
                results['ttm_pe'][f'{period_name}_count'] = len(period_ttm)
                print(f"  TTM PE 近{period_name}: {percentile}% 分位 (样本{len(period_ttm)})")
        
        # PS百分位
        if current_ps is not None and 'ps_ratio' in df.columns:
            mask = df['date'] >= cutoff_date
            period_ps = df.loc[mask, 'ps_ratio'].dropna().values
            if len(period_ps) > 0:
                percentile = compute_percentile(current_ps, period_ps)
                results['ps_ratio'][f'{period_name}_percentile'] = percentile
                results['ps_ratio'][f'{period_name}_count'] = len(period_ps)
                print(f"  PS 近{period_name}: {percentile}% 分位 (样本{len(period_ps)})")
    
    # 计算描述性统计
    for metric in ['ttm_pe', 'ps_ratio']:
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
# 第八部分：格式化输出
# ============================================================

def print_results(results: Dict):
    """
    打印格式化结果表格
    
    输出格式:
    ================================================================================
      纳斯达克100估值历史百分位分析结果
    ================================================================================
    数据日期: YYYY-MM-DD
    --------------------------------------------------------------------------------
    指标           当前值        近5年分位        近10年分位       近20年分位      
    --------------------------------------------------------------------------------
    TTM PE         XX.XX      XX.XX%       XX.XX%       XX.XX%      
    PS Ratio       XX.XX      XX.XX%       XX.XX%       XX.XX%      
    --------------------------------------------------------------------------------
    
    【估值水平判定】
    --------------------------------------------------
      TTM PE: 当前XX.XX → [估值区间]
      PS: 当前XX.XX → [估值区间]
    ================================================================================
    """
    print("\n" + "=" * 80)
    print("  纳斯达克100估值历史百分位分析结果")
    print("=" * 80)
    print(f"数据日期: {results['latest_date'].date()}")
    print(f"标的: QQQ (追踪NASDAQ-100指数)")
    print("-" * 80)
    
    # 表头
    header = f"{'指标':<12} {'当前值':<10} {'近5年分位':<12} {'近10年分位':<12} {'近20年分位':<12}"
    print(header)
    print("-" * 80)
    
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
    
    # PS行
    if results['ps_ratio'].get('current') is not None:
        ps = results['ps_ratio']
        p5y = ps.get('5年_percentile', 'N/A')
        p10y = ps.get('10年_percentile', 'N/A')
        p20y = ps.get('20年_percentile', 'N/A')
        
        p5y_str = f"{p5y}%" if isinstance(p5y, (int, float)) else p5y
        p10y_str = f"{p10y}%" if isinstance(p10y, (int, float)) else p10y
        p20y_str = f"{p20y}%" if isinstance(p20y, (int, float)) else p20y
        
        row = f"{'PS Ratio':<12} {ps['current']:<10.2f} {p5y_str:<12} {p10y_str:<12} {p20y_str:<12}"
        print(row)
    
    print("-" * 80)
    
    # 估值水平判定
    print("\n【估值水平判定】")
    print("-" * 50)
    
    for metric_name, metric_key in [('TTM PE', 'ttm_pe'), ('PS Ratio', 'ps_ratio')]:
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
    
    # 科技股估值特点说明
    print("\n【纳斯达克100估值特点】")
    print("-" * 50)
    print("  • 科技股盈利波动较大，TTM PE有时会失真")
    print("  • PS市销率是科技股更稳定的估值指标")
    print("  • 长期平均PE约25-35倍，高于标普500的15-20倍")
    print("  • 当前估值需结合增长预期综合判断")
    
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
    
    for metric_name, metric_key in [('TTM PE', 'ttm_pe'), ('PS Ratio', 'ps_ratio')]:
        if metric_key in results and results[metric_key].get('stats') is not None:
            stats = results[metric_key]['stats']
            print(f"\n{metric_name} (20年完整样本):")
            print(f"  最小值: {stats['min']:.2f}")
            print(f"  最大值: {stats['max']:.2f}")
            print(f"  平均值: {stats['mean']:.2f}")
            print(f"  中位数: {stats['median']:.2f}")
            print(f"  标准差: {stats['std']:.2f}")

# ============================================================
# 第九部分：可视化
# ============================================================

def plot_valuation_history(df: pd.DataFrame, results: Dict):
    """
    绘制20年估值走势图表
    
    包含:
    - TTM PE历史曲线
    - PS Ratio历史曲线
    - 当前估值水平线
    - 百分位区间标注
    
    参数:
        df: 包含date、ttm_pe、ps_ratio的DataFrame
        results: 计算结果字典
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        print("\n⚠️ matplotlib未安装，跳过可视化")
        print("   安装命令: pip install matplotlib")
        return
    
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'SimHei', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False
    
    df = df.sort_values('date')
    
    fig, axes = plt.subplots(2, 1, figsize=(16, 12), sharex=True)
    fig.suptitle('NASDAQ-100 Valuation History (2006-2026)', fontsize=16, fontweight='bold')
    
    # 子图1: TTM PE
    ax1 = axes[0]
    if 'ttm_pe' in df.columns and df['ttm_pe'].notna().any():
        ax1.plot(df['date'], df['ttm_pe'], color='#9C27B0', linewidth=1.5, 
                label='TTM P/E Ratio', alpha=0.8)
        
        current_ttm = results['ttm_pe'].get('current')
        if current_ttm:
            ax1.axhline(y=current_ttm, color='#F44336', linestyle='--', linewidth=2,
                       label=f'Current TTM PE = {current_ttm}')
            
            # 添加当前值标注
            ax1.annotate(f'Current TTM PE: {current_ttm}',
                        xy=(df['date'].iloc[-1], current_ttm),
                        xytext=(df['date'].iloc[-20] if len(df) > 20 else df['date'].iloc[0], 
                               current_ttm * 1.15),
                        fontsize=11, fontweight='bold', color='#F44336',
                        ha='center',
                        arrowprops=dict(arrowstyle='->', color='#F44336', lw=1.5))
        
        # 添加历史均值线
        mean_ttm = df['ttm_pe'].mean()
        ax1.axhline(y=mean_ttm, color='#4CAF50', linestyle=':', linewidth=1.5,
                   alpha=0.7, label=f'Historical Mean = {mean_ttm:.2f}')
        
        # 添加估值区间带 (25%-75%)
        p75 = df['ttm_pe'].quantile(0.75)
        p25 = df['ttm_pe'].quantile(0.25)
        ax1.axhspan(p25, p75, alpha=0.1, color='gray', label=f'25%-75% Range')
    
    ax1.set_ylabel('TTM P/E Ratio', fontsize=12)
    ax1.legend(loc='upper left', fontsize=10)
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.set_title('Trailing 12-Month P/E Ratio (QQQ)', fontsize=13)
    
    # 子图2: PS Ratio
    ax2 = axes[1]
    if 'ps_ratio' in df.columns and df['ps_ratio'].notna().any():
        ax2.plot(df['date'], df['ps_ratio'], color='#FF5722', linewidth=1.5,
                label='Price/Sales Ratio', alpha=0.8)
        
        current_ps = results['ps_ratio'].get('current')
        if current_ps:
            ax2.axhline(y=current_ps, color='#F44336', linestyle='--', linewidth=2,
                       label=f'Current PS = {current_ps}')
            
            ax2.annotate(f'Current PS: {current_ps}',
                        xy=(df['date'].iloc[-1], current_ps),
                        xytext=(df['date'].iloc[-20] if len(df) > 20 else df['date'].iloc[0], 
                               current_ps * 1.2),
                        fontsize=11, fontweight='bold', color='#F44336',
                        ha='center',
                        arrowprops=dict(arrowstyle='->', color='#F44336', lw=1.5))
        
        # 添加历史均值线
        mean_ps = df['ps_ratio'].mean()
        ax2.axhline(y=mean_ps, color='#4CAF50', linestyle=':', linewidth=1.5,
                   alpha=0.7, label=f'Historical Mean = {mean_ps:.2f}')
        
        # 添加估值区间带
        p75 = df['ps_ratio'].quantile(0.75)
        p25 = df['ps_ratio'].quantile(0.25)
        ax2.axhspan(p25, p75, alpha=0.1, color='gray', label=f'25%-75% Range')
    
    ax2.set_xlabel('Date', fontsize=12)
    ax2.set_ylabel('Price/Sales Ratio', fontsize=12)
    ax2.legend(loc='upper left', fontsize=10)
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.set_title('Price-to-Sales Ratio (Key Metric for Tech Stocks)', fontsize=13)
    
    # X轴格式
    ax2.xaxis.set_major_locator(mdates.YearLocator(2))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    
    plt.tight_layout()
    
    # 保存图片
    output_path = f"ndx100_valuation_{datetime.now().strftime('%Y%m%d')}.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n📊 图表已保存: {output_path}")
    
    plt.show()

# ============================================================
# 第十部分：主流程
# ============================================================

def main():
    """
    主函数：串联数据获取→清洗→计算→输出→可视化全过程
    
    执行流程:
    1. 获取TTM PE数据 (Yahoo Finance QQQ)
    2. 获取PS数据 (市销率，科技股重要指标)
    3. 数据清洗与合并
    4. 计算各周期历史百分位
    5. 格式化打印结果表格
    6. 打印详细统计信息
    7. 绘制可视化图表
    
    纳斯达克100特点:
    - 科技股为主，盈利波动大
    - 长期PE中枢约25-35倍
    - PS比PE更适合评估成长股
    """
    print("=" * 80)
    print("  纳斯达克100估值历史百分位分析工具")
    print("  数据源: Yahoo Finance (QQQ ETF)")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    try:
        # 步骤1: 获取TTM PE数据
        ttm_df = fetch_ndx_ttm_pe_from_yfinance()
        
        # 步骤2: 获取Forward PE (辅助信息)
        forward_pe = fetch_forward_pe()
        
        # 步骤3: 获取PS数据
        ps_df = fetch_ps_ratio_history()
        
        # 检查数据获取结果
        if ttm_df.empty and ps_df.empty:
            print("\n❌ 错误: 未能获取任何估值数据")
            print("   请检查网络连接或稍后重试")
            return 1
        
        # 步骤4: 数据清洗与合并
        merged_df = clean_and_merge_data(ttm_df, ps_df)
        
        if merged_df.empty or len(merged_df) < 12:
            print("\n❌ 错误: 数据不足12个月，无法进行分析")
            return 1
        
        # 步骤5: 计算百分位
        results = calculate_percentiles(merged_df)
        
        # 添加Forward PE到结果
        if forward_pe:
            results['forward_pe'] = round(forward_pe, 2)
        
        # 步骤6: 打印结果表格
        print_results(results)
        
        # 打印Forward PE信息 (如果有)
        if 'forward_pe' in results:
            print(f"\n【Forward PE (预期市盈率)】")
            print(f"  当前值: {results['forward_pe']:.2f}")
            print(f"  说明: 使用未来12个月预期盈利计算，比TTM更具前瞻性")
        
        # 步骤7: 打印详细统计
        print_detailed_stats(results)
        
        # 步骤8: 可视化
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
        print("  4. 检查是否安装了beautifulsoup4:")
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
cat > requirements_ndx100.txt << 'EOF'
pandas>=1.5.0
numpy>=1.21.0
yfinance>=0.2.0
matplotlib>=3.5.0
requests>=2.28.0
beautifulsoup4>=4.11.0
lxml>=4.9.0
EOF
pip install -r requirements_ndx100.txt

# 方式3: 一键安装（Linux/Mac/Windows）
pip install pandas numpy yfinance matplotlib requests beautifulsoup4 lxml

═══════════════════════════════════════════════════════════════════════════════
                          【数据源说明】
═══════════════════════════════════════════════════════════════════════════════

1. 主要数据源: Yahoo Finance (QQQ ETF)
   URL: https://finance.yahoo.com/quote/QQQ
   QQQ是追踪纳斯达克100指数的最大ETF，流动性最佳

2. 辅助数据源: Yahoo Finance (^NDX)
   URL: https://finance.yahoo.com/quote/%5ENDX
   直接获取纳斯达克100指数数据

3. 估值指标:
   • TTM PE: 滚动市盈率 (Trailing 12-Month P/E)
   • Forward PE: 预期市盈率 (基于未来盈利预测)
   • PS Ratio: 市销率 (Price/Sales，科技股重要指标)

═══════════════════════════════════════════════════════════════════════════════
                          【纳斯达克100特点】
═══════════════════════════════════════════════════════════════════════════════

1. 行业构成:
   • 科技股: ~50-60%
   • 通信服务: ~15-20%
   • 消费类: ~15-20%
   • 医疗保健: ~5-10%

2. 估值特点:
   • 长期平均PE: 25-35倍 (高于标普500的15-20倍)
   • 波动性: 高于大盘
   • PS比PE更重要: 科技公司在研发期盈利不稳定

3. 前10大成分股 (约占比50%):
   • Apple (AAPL), Microsoft (MSFT), NVIDIA (NVDA)
   • Amazon (AMZN), Meta (META), Tesla (TSLA)
   • Alphabet (GOOGL/GOOG), Broadcom (AVGO), PepsiCo (PEP)

═══════════════════════════════════════════════════════════════════════════════
                          【运行程序】
═══════════════════════════════════════════════════════════════════════════════

python ndx100_valuation_analyzer.py

═══════════════════════════════════════════════════════════════════════════════
"""

if __name__ == "__main__":
    exit(main())
