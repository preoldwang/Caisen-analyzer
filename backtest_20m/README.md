# HK Blue Chip Monthly Rotation Backtest

## Objective
For each month (Aug 2024 – Mar 2026), select the **best 3 HK blue chip stocks** to buy on the **first trading day** and sell on the **last trading day**. Use actual historical data from Yahoo Finance. Show transaction dates, prices, and reasoning.

## Methodology
Each sub-agent fetches real OHLCV data for 83 HK blue chips for its assigned months. On the first trading day of each month, it scores all stocks using:

1. **Momentum** (prior 1-month return) — 30%
2. **Volume trend** (20-day avg volume vs prior 20 days) — 20%
3. **Trend strength** (price vs 5/10/20/60-day MAs) — 25%
4. **Risk-reward** (distance from support/resistance) — 15%
5. **Reversal signals** (W-bottom, 破底翻, volume divergence) — 10%

Top 3 by composite score → buy at open on day 1, sell at close on last day.

## Agent Split
| Agent | Months | Count |
|-------|--------|-------|
| 1 | 2024-08 to 2024-11 | 4 |
| 2 | 2024-12 to 2025-03 | 4 |
| 3 | 2025-04 to 2025-07 | 4 |
| 4 | 2025-08 to 2025-11 | 4 |
| 5 | 2025-12 to 2026-03 | 4 |
