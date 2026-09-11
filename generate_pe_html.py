#!/usr/bin/env python3
"""
Generate a beautiful self-contained HTML page showing S&P 500 PE percentile analysis.
Reads CSV data, computes statistics, and produces a standalone HTML with Chart.js.
"""

import csv
import json
import io
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

CSV_PATH = os.path.join(os.path.dirname(__file__), "data", "sp500_pe_monthly_20260629.csv")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "sp500_pe_percentile.html")


def load_data(path: str) -> pd.DataFrame:
    """Load CSV and parse dates."""
    df = pd.read_csv(path, parse_dates=["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    return df


def compute_percentile(series, value):
    """Compute percentile rank of `value` within `series` (0-100)."""
    count_less = (series < value).sum()
    count_equal = (series == value).sum()
    n = len(series)
    return round((count_less + 0.5 * count_equal) / n * 100, 1)


def compute_stats(df: pd.DataFrame):
    """Compute all statistics for each period."""
    current_pe = df["PE"].iloc[-1]
    current_date = df["Date"].iloc[-1]
    today = current_date

    periods = {
        "all": (f"全部历史 (1871-{today.year})", df),
        "20y": ("最近20年", df[df["Date"] >= today - pd.DateOffset(years=20)]),
        "10y": ("最近10年", df[df["Date"] >= today - pd.DateOffset(years=10)]),
        "5y":  ("最近5年",  df[df["Date"] >= today - pd.DateOffset(years=5)]),
    }

    stats = {}
    for key, (label, sub_df) in periods.items():
        pe = sub_df["PE"]
        stats[key] = {
            "label": label,
            "count": len(sub_df),
            "min": round(pe.min(), 2),
            "max": round(pe.max(), 2),
            "mean": round(pe.mean(), 2),
            "median": round(pe.median(), 2),
            "current": round(current_pe, 2),
            "percentile": compute_percentile(pe, current_pe),
        }

    return stats, current_pe, current_date


def build_html_table(stats, current_pe):
    """Build the HTML for the stats table."""
    rows = ""
    for key in ["all", "20y", "10y", "5y"]:
        s = stats[key]
        bar_width = min(s["percentile"], 100)
        bar_color = "#ef4444" if s["percentile"] >= 90 else "#f97316" if s["percentile"] >= 70 else "#22c55e"

        rows += f"""
        <tr class="border-b border-gray-200 hover:bg-gray-50 transition-colors">
            <td class="py-3 px-4 font-medium text-gray-800">{s['label']}</td>
            <td class="py-3 px-4 text-gray-600">{s['count']}</td>
            <td class="py-3 px-4 text-gray-600">{s['min']}</td>
            <td class="py-3 px-4 text-gray-600">{s['max']}</td>
            <td class="py-3 px-4 text-gray-600">{s['mean']}</td>
            <td class="py-3 px-4 text-gray-600">{s['median']}</td>
            <td class="py-3 px-4 text-gray-600">{s['current']}</td>
            <td class="py-3 px-4">
                <div class="flex items-center gap-2">
                    <div class="flex-1 bg-gray-200 rounded-full h-2.5 overflow-hidden">
                        <div class="h-full rounded-full transition-all duration-1000 ease-out"
                             style="width: {bar_width}%; background-color: {bar_color};"></div>
                    </div>
                    <span class="text-sm font-semibold whitespace-nowrap" style="color: {bar_color}">{s['percentile']}%</span>
                </div>
            </td>
        </tr>"""
    return rows


def build_html(data_json: str, stats: dict, current_pe: float, current_date_str: str) -> str:
    """Generate the complete self-contained HTML page."""
    table_rows = build_html_table(stats, current_pe)

    df_all = pd.read_json(io.StringIO(data_json))
    dates = df_all["Date"].tolist()
    pes = df_all["PE"].tolist()

    cutoff_5y = (pd.Timestamp(current_date_str) - pd.DateOffset(years=5)).strftime("%Y-%m-%d")
    cutoff_10y = (pd.Timestamp(current_date_str) - pd.DateOffset(years=10)).strftime("%Y-%m-%d")

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>S&P 500 市盈率百分位分析</title>
    <script src="https://cdn.tailwindcss.com">
    </script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js">
    </script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.1.0/dist/chartjs-plugin-annotation.min.js">
    </script>
    <script src="https://cdn.jsdelivr.net/npm/luxon@3.4.4/build/global/luxon.min.js">
    </script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-luxon@1.3.1/dist/chartjs-adapter-luxon.min.js">
    </script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        * {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }}
        body {{ background: linear-gradient(135deg, #f0f4f8 0%, #d9e2ec 100%); min-height: 100vh; }}
        .fade-in {{ animation: fadeIn 0.8s ease-out both; }}
        .slide-up {{ animation: slideUp 0.6s ease-out both; }}
        @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
        @keyframes slideUp {{ from {{ opacity: 0; transform: translateY(30px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        .card {{ background: rgba(255,255,255,0.9); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.3); border-radius: 1.25rem; box-shadow: 0 8px 32px rgba(0,0,0,0.08); transition: transform 0.2s, box-shadow 0.2s; }}
        .card:hover {{ transform: translateY(-2px); box-shadow: 0 12px 40px rgba(0,0,0,0.12); }}
        .gradient-text {{ background: linear-gradient(135deg, #1e3a5f, #2d6a9f); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }}
        .pill {{ display: inline-flex; align-items: center; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.025em; }}
        .pct-high {{ background: #fef2f2; color: #dc2626; }}
        .pct-mid {{ background: #fff7ed; color: #ea580c; }}
        .pct-low {{ background: #f0fdf4; color: #16a34a; }}
    </style>
</head>
<body>
    <div class="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">

        <!-- Header -->
        <header class="text-center mb-10 fade-in">
            <div class="inline-flex items-center gap-2 px-4 py-1.5 bg-white/70 backdrop-blur rounded-full shadow-sm mb-4 text-sm text-gray-500">
                <span class="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
                数据更新于 {current_date_str}
            </div>
            <h1 class="text-4xl sm:text-5xl font-extrabold gradient-text mb-3">
                S&P 500 市盈率百分位分析
            </h1>
            <p class="text-lg text-gray-500 max-w-2xl mx-auto">
                基于 {stats['all']['count']} 个月度数据点的全面市盈率分析
            </p>
        </header>

        <!-- Current PE Hero -->
        <div class="card p-8 mb-8 text-center slide-up" style="animation-delay: 0.1s;">
            <p class="text-sm font-medium text-gray-400 uppercase tracking-widest mb-1">当前市盈率 (PE)</p>
            <div class="flex items-baseline justify-center gap-4">
                <span class="text-7xl font-extrabold gradient-text">{current_pe}</span>
                <div class="text-left">
                    <span class="pill pct-high text-base px-3 py-0.5">{stats['all']['percentile']}%</span>
                    <p class="text-xs text-gray-400 mt-0.5">全部历史百分位</p>
                </div>
            </div>
            <div class="mt-4 flex flex-wrap justify-center gap-3">
                <div class="bg-white/60 rounded-xl px-4 py-2 text-sm">
                    <span class="text-gray-400">最小值</span>
                    <span class="ml-2 font-semibold text-gray-700">{stats['all']['min']}</span>
                </div>
                <div class="bg-white/60 rounded-xl px-4 py-2 text-sm">
                    <span class="text-gray-400">最大值</span>
                    <span class="ml-2 font-semibold text-gray-700">{stats['all']['max']}</span>
                </div>
                <div class="bg-white/60 rounded-xl px-4 py-2 text-sm">
                    <span class="text-gray-400">平均值</span>
                    <span class="ml-2 font-semibold text-gray-700">{stats['all']['mean']}</span>
                </div>
                <div class="bg-white/60 rounded-xl px-4 py-2 text-sm">
                    <span class="text-gray-400">中位数</span>
                    <span class="ml-2 font-semibold text-gray-700">{stats['all']['median']}</span>
                </div>
            </div>
        </div>

        <!-- Percentile Cards -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
            {''.join(_build_percentile_card(key, stats, current_pe) for key in ['all', '20y', '10y', '5y'])}
        </div>

        <!-- Chart -->
        <div class="card p-6 mb-8 slide-up" style="animation-delay: 0.3s;">
            <h2 class="text-xl font-bold text-gray-800 mb-1">市盈率历史走势</h2>
            <p class="text-sm text-gray-400 mb-4">1871 年至今 · 月度数据</p>
            <div class="relative" style="height: 480px;">
                <canvas id="peChart"></canvas>
            </div>
        </div>

        <!-- Stats Table -->
        <div class="card p-6 mb-8 slide-up" style="animation-delay: 0.4s;">
            <h2 class="text-xl font-bold text-gray-800 mb-1">各周期统计对比</h2>
            <p class="text-sm text-gray-400 mb-4">详细统计指标与百分位排名</p>
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead>
                        <tr class="border-b-2 border-gray-200 bg-gray-50/50">
                            <th class="py-3 px-4 text-left font-semibold text-gray-600">周期</th>
                            <th class="py-3 px-4 text-left font-semibold text-gray-600">数据点</th>
                            <th class="py-3 px-4 text-left font-semibold text-gray-600">最小值</th>
                            <th class="py-3 px-4 text-left font-semibold text-gray-600">最大值</th>
                            <th class="py-3 px-4 text-left font-semibold text-gray-600">平均值</th>
                            <th class="py-3 px-4 text-left font-semibold text-gray-600">中位数</th>
                            <th class="py-3 px-4 text-left font-semibold text-gray-600">当前值</th>
                            <th class="py-3 px-4 text-left font-semibold text-gray-600">百分位</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Footer -->
        <footer class="text-center text-gray-400 text-xs py-6 fade-in">
            <p>数据来源: S&P 500 月度市盈率数据 · 自动生成分析报告</p>
        </footer>
    </div>

    <script>
        // Register annotation plugin
        Chart.register(ChartAnnotation);

        const data = {data_json};
        const dates = data.map(d => d.Date);
        const peValues = data.map(d => d.PE);

        const currentPE = {current_pe};
        const cutoff5y = '{cutoff_5y}';
        const cutoff10y = '{cutoff_10y}';

        // Find index of cutoff dates
        const idx5y = dates.findIndex(d => d >= cutoff5y);
        const idx10y = dates.findIndex(d => d >= cutoff10y);

        // Wait for DOM and all scripts to load
        window.addEventListener('load', function() {{
            const ctx = document.getElementById('peChart').getContext('2d');
            new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: dates,
                    datasets: [{{
                        label: '市盈率 (PE)',
                        data: peValues,
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.06)',
                        borderWidth: 1.5,
                        pointRadius: 0,
                        pointHitRadius: 5,
                        fill: true,
                        tension: 0.1,
                        order: 3,
                    }},
                    {{
                        label: '最近5年范围',
                        data: peValues.map((v, i) => (i >= idx5y && i < idx10y) ? v : null),
                        borderColor: 'rgba(34, 197, 94, 0.5)',
                        backgroundColor: 'rgba(34, 197, 94, 0.07)',
                        borderWidth: 0,
                        pointRadius: 0,
                        fill: true,
                        order: 5,
                    }},
                    {{
                        label: '最近10年范围',
                        data: peValues.map((v, i) => (i >= idx10y) ? v : null),
                        borderColor: 'rgba(59, 130, 246, 0.4)',
                        backgroundColor: 'rgba(59, 130, 246, 0.07)',
                        borderWidth: 0,
                        pointRadius: 0,
                        fill: true,
                        order: 4,
                    }}],
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {{
                        mode: 'index',
                        intersect: false,
                    }},
                    plugins: {{
                        legend: {{
                            display: true,
                            position: 'top',
                            labels: {{
                                usePointStyle: true,
                                padding: 20,
                                font: {{ size: 12, family: 'Inter' }},
                                color: '#4b5563',
                            }},
                        }},
                        tooltip: {{
                            backgroundColor: 'rgba(255,255,255,0.95)',
                            titleColor: '#1f2937',
                            bodyColor: '#4b5563',
                            borderColor: 'rgba(0,0,0,0.08)',
                            borderWidth: 1,
                            padding: 12,
                            cornerRadius: 8,
                            boxPadding: 6,
                            callbacks: {{
                                title: function(items) {{
                                    return items[0].label;
                                }},
                                label: function(context) {{
                                    if (context.dataset.label === '市盈率 (PE)') {{
                                        return '市盈率: ' + context.parsed.y;
                                    }}
                                    return context.dataset.label + ': ' + context.parsed.y;
                                }},
                            }},
                        }},
                        annotation: {{
                            annotations: {{
                                currentPELine: {{
                                    type: 'line',
                                    yMin: currentPE,
                                    yMax: currentPE,
                                    borderColor: '#ef4444',
                                    borderWidth: 2,
                                    borderDash: [8, 4],
                                    label: {{
                                        display: true,
                                        content: '当前 PE: ' + currentPE,
                                        position: 'start',
                                        backgroundColor: 'rgba(239, 68, 68, 0.9)',
                                        color: '#fff',
                                        font: {{ size: 11, weight: 'bold' }},
                                        padding: 6,
                                        borderRadius: 4,
                                    }},
                                }},
                            }},
                        }},
                    }},
                    scales: {{
                        x: {{
                            type: 'time',
                            time: {{
                                unit: 'year',
                                displayFormats: {{ year: 'YYYY' }},
                            }},
                            ticks: {{
                                maxTicksLimit: 20,
                                color: '#9ca3af',
                                font: {{ size: 11, family: 'Inter' }},
                            }},
                            grid: {{
                                color: 'rgba(0,0,0,0.04)',
                            }},
                        }},
                        y: {{
                            title: {{
                                display: true,
                                text: '市盈率 (PE)',
                                color: '#6b7280',
                                font: {{ size: 12, family: 'Inter' }},
                            }},
                            ticks: {{
                                color: '#9ca3af',
                                font: {{ size: 11, family: 'Inter' }},
                            }},
                            grid: {{
                                color: 'rgba(0,0,0,0.04)',
                            }},
                        }},
                    }},
                }},
            }});
        }});
    </script>
</body>
</html>"""
    return html


def _build_percentile_card(key: str, stats: dict, current_pe: float) -> str:
    """Build a single percentile card."""
    s = stats[key]
    pct = s["percentile"]

    delays = {"all": "0.15s", "20y": "0.2s", "10y": "0.25s", "5y": "0.3s"}

    return f"""
        <div class="card p-5 slide-up" style="animation-delay: {delays[key]};">
            <div class="flex items-center justify-between mb-3">
                <span class="text-sm font-medium text-gray-400">{s['label']}</span>
                <span class="pill {'pct-high' if pct >= 90 else 'pct-mid' if pct >= 70 else 'pct-low'}">{pct}%</span>
            </div>
            <div class="text-3xl font-extrabold text-gray-800 mb-1">{s['current']}</div>
            <div class="text-xs text-gray-400 mb-3">当前 PE</div>
            <div class="w-full bg-gray-100 rounded-full h-2.5 mb-2 overflow-hidden">
                <div class="h-full rounded-full transition-all duration-1000 ease-out"
                     style="width: {min(pct, 100)}%; background: linear-gradient(90deg, #3b82f6, #2563eb);"></div>
            </div>
            <div class="flex justify-between text-xs text-gray-400">
                <span>最小值: {s['min']}</span>
                <span>最大值: {s['max']}</span>
            </div>
            <div class="flex justify-between text-xs text-gray-400 mt-0.5">
                <span>平均: {s['mean']}</span>
                <span>中位: {s['median']}</span>
            </div>
        </div>"""


def main():
    print("=" * 60)
    print("  S&P 500 PE Percentile HTML Generator")
    print("=" * 60)

    # Load data
    df = load_data(CSV_PATH)
    print(f"\n[1/3] 已加载 {len(df)} 条月度数据")
    print(f"      日期范围: {df['Date'].iloc[0].strftime('%Y-%m-%d')} 至 {df['Date'].iloc[-1].strftime('%Y-%m-%d')}")

    # Compute stats
    stats, current_pe, current_date = compute_stats(df)
    current_date_str = current_date.strftime("%Y-%m-%d")
    current_pe_val = round(current_pe, 2)

    print(f"\n[2/3] 统计计算完成")
    print(f"      当前 PE: {current_pe_val} ({current_date_str})")
    for key in ["all", "20y", "10y", "5y"]:
        s = stats[key]
        print(f"      {s['label']:15s}: {s['count']:5d} 个点, "
              f"范围 [{s['min']:.2f}, {s['max']:.2f}], "
              f"均值={s['mean']:.2f}, 中位={s['median']:.2f}, "
              f"百分位={s['percentile']}%")

    # Convert data to JSON and generate HTML
    data_json = df.to_json(orient="records", date_format="iso")
    html = build_html(data_json, stats, current_pe_val, current_date_str)

    # Write output
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    file_size = os.path.getsize(OUTPUT_PATH) / 1024
    print(f"\n[3/3] HTML 文件已生成: {OUTPUT_PATH} ({file_size:.1f} KB)")
    print("=" * 60)


if __name__ == "__main__":
    main()
