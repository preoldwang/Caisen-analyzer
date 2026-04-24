#!/usr/bin/env python3
"""
蔡森技术分析 - 图表可视化模块
生成带颈线、型态标注的K线图
"""

import sys
import numpy as np
import pandas as pd
import mplfinance as mpf
import yfinance as yf
from datetime import datetime, timedelta


def create_chart(symbol: str, period: str = "6mo", output_file: str = None):
    """
    生成蔡森技术分析K线图
    标注: 颈线、支撑/压力、成交量
    """
    # 获取数据
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, auto_adjust=False)

    if df.empty:
        print(f"❌ 无法获取 {symbol} 数据")
        return

    # 计算颈线 (简单移动平均作为参考)
    df['SMA20'] = df['Close'].rolling(20).mean()
    df['SMA60'] = df['Close'].rolling(60).mean()

    # 识别局部高低点
    window = 10
    highs = []
    lows = []
    for i in range(window, len(df) - window):
        if df['High'].iloc[i] == df['High'].iloc[i-window:i+window+1].max():
            highs.append((df.index[i], df['High'].iloc[i]))
        if df['Low'].iloc[i] == df['Low'].iloc[i-window:i+window+1].min():
            lows.append((df.index[i], df['Low'].iloc[i]))

    # 添加技术指标
    # 成交量均线
    df['Vol_SMA20'] = df['Volume'].rolling(20).mean()

    # 构建 mplfinance 图表
    mc = mpf.make_marketcolors(
        up='red', down='green',  # 中国/台湾习惯: 红涨绿跌
        edge='inherit',
        wick='inherit',
        volume='in',
    )

    s = mpf.make_mpf_style(
        marketcolors=mc,
        gridstyle='-',
        gridcolor='#e0e0e0',
    )

    # 添加均线到图表
    ap = [
        mpf.make_addplot(df['SMA20'], color='blue', width=1, label='MA20'),
        mpf.make_addplot(df['SMA60'], color='orange', width=1, label='MA60'),
    ]

    # 颈线标注
    # 找到最近的显著支撑和压力
    current_price = df['Close'].iloc[-1]

    # 支撑 = 最近60天的最低价区域
    recent_lows = df['Low'].tail(60)
    support_level = recent_lows.quantile(0.05)

    # 压力 = 最近60天的最高价区域
    recent_highs = df['High'].tail(60)
    resistance_level = recent_highs.quantile(0.95)

    # 绘制图表
    title = f"\n{symbol} | 蔡森技术分析 | {datetime.now().strftime('%Y-%m-%d')}"

    if output_file is None:
        output_file = f"/root/.openclaw/workspace/stock-analyzer/{symbol.replace('.', '_')}_chart.png"

    mpf.plot(
        df,
        type='candle',
        style=s,
        addplot=ap,
        volume=True,
        title=title,
        ylabel='价格',
        ylabel_lower='成交量',
        figsize=(16, 10),
        savefig=dict(fname=output_file, dpi=150, bbox_inches='tight'),
    )

    print(f"✅ 图表已保存: {output_file}")
    return output_file


def create_analysis_dashboard(symbol: str, period: str = "1y", output_file: str = None):
    """
    创建完整分析仪表盘
    包含: K线图 + 量价分析 + 型态识别 + 操作建议
    """
    from cai_sen_analyzer import CaiSenAnalyzer

    analyzer = CaiSenAnalyzer()
    analyzer.fetch_data(symbol, period=period)
    result = analyzer.analyze()

    # 生成图表
    chart_file = create_chart(symbol, period, output_file)

    # 输出文字分析
    print("\n" + "=" * 60)
    print(result.summary)
    print("=" * 60)

    return result, chart_file


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python chart.py <股票代码> [周期]")
        print("示例: python chart.py 2330.TW 6mo")
        sys.exit(0)

    symbol = sys.argv[1]
    period = sys.argv[2] if len(sys.argv) > 2 else "6mo"

    create_analysis_dashboard(symbol, period)
