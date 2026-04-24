# Cai Sen Analyzer — Strategy Naming Convention
# ================================================

## Strategy Names

| Code | Full Name | Engine | Selection Rule |
|------|-----------|--------|----------------|
| **FULL** | 全信号 Top 3 策略 | cai_sen_analyzer.py v3.0 | Top 3 by composite score, all signal types |
| **PDFAN** | 破底翻精简版 | cai_sen_analyzer.py v3.0 (filtered) | Only 破底翻 signals, ranked by confidence. Cash when none. |
| **SMART2** | Smart Top 2 策略 | cai_sen_analyzer.py v3.0 + smart filter | Top 2 only. Trade if: has 颈线突破/量价背离 OR both scores ≥ 12. Skip otherwise. |

## Additional Tools

| Code | Full Name | Engine | Purpose |
|------|-----------|--------|---------|
| **PODIFAN-V2** | 破底翻信号验证器 | podifan_v2.py (imports cai_sen_analyzer) | 12-month rolling signal verification, 1M/3M outcome tracking |
| **PODIFAN-A4** | 破底翻独立扫描器 | podifan_analyzer.py v4.0 | Standalone 破底翻 scanner, real-time focused |
| **SIMPLE** | 简化量化版 | monthly_backtest.py (separate engine) | Multi-factor scoring (momentum/volume/trend/RR/reversal), NO Cai Sen patterns |

## Usage

When you say:
- **PDFAN** → use 破底翻-only filtering strategy
- **SMART2** → use Top 2 + smart filter strategy
- **FULL** → use all-signal Top 3 baseline
- **PODIFAN-V2** → run signal verification backtest
- **PODIFAN-A4** → run real-time 破底翻 scanner
- **SIMPLE** → use simplified quant scoring (non-Cai-Sen)

## 20-Month Backtest Results (Aug 2024 – Mar 2026)

| Strategy | Compound | Trades | Win Rate | PF | Sharpe | Return/Trade |
|----------|----------|--------|----------|-----|--------|-------------|
| 🥇 SMART2 | +166.46% | 36 | 61.1% | 5.08 | 0.55 | +4.62% |
| 🥈 PDFAN | +159.81% | 28 | 57.1% | 4.74 | 0.50 | +5.71% |
| 🥉 FULL | +102.80% | 60 | 56.7% | 2.83 | 0.47 | +1.71% |

All use cai_sen_analyzer.py v3.0 with 5-year data lookback, multi-timeframe (monthly+weekly+daily).
