# Backtest Run Card

Generated: 2026-08-19T15:01:39.907134Z
Run directory: `./runs/20260819T150036Z-sma-50-200`

## Backtest Summary
- codes: ['BTC-USDT']
- start_date: 2022-01-01
- end_date: 2025-12-31
- interval: 1D
- engine: daily
- initial_cash: 1000000
- source: binance

## Reproducibility
- config_hash: `b0911e6a5b1d37946ea2dc54d209c0df9e212aa5bc5cb2c990bcaf5901a8fe48`
- strategy_hash: `1889742cbb9285ac7cfd70cbe5ea82e9ebc688bb9bbd88eb20bf1a42e2af1962`

## Data Sources
- binance

## Metrics
- final_value: 1703339.3908697686
- total_return: 0.7033393908697685
- annual_return: 0.09621538543373087
- max_drawdown: -0.3942364051380817
- sharpe: 0.45253988448913673
- calmar: 0.2441
- sortino: 0.5353
- win_rate: 0.75
- profit_loss_ratio: 1.2173
- profit_factor: 3.6519
- max_consecutive_loss: 1
- avg_holding_days: 210.2
- trade_count: 4
- benchmark_return: 0.836617
- excess_return: -0.133277
- information_ratio: -0.1923
- avg_turnover: 0.002773
- total_turnover: 4.052055

## Validation
- monte_carlo: {'actual_sharpe': 10.2223, 'actual_max_dd': -0.1484, 'p_value_sharpe': 0.337, 'p_value_max_dd': 0.529, 'simulated_sharpe_mean': 9.7653, 'simulated_sharpe_std': 6.799, 'simulated_sharpe_p5': 1.6865, 'simulated_sharpe_p95': 23.9403, 'n_simulations': 1000, 'n_trades': 4}
- bootstrap: {'observed_sharpe': 0.4528, 'ci_lower': -0.3858, 'ci_upper': 1.2579, 'median_sharpe': 0.4645, 'prob_positive': 0.857, 'confidence': 0.95, 'n_bootstrap': 1000}
- walk_forward: {'n_windows': 5, 'windows': [{'window': 1, 'start': '2022-01-01', 'end': '2022-10-19', 'return': 0.0, 'sharpe': 0.0, 'max_dd': 0.0, 'trades': 0, 'win_rate': 0.0}, {'window': 2, 'start': '2022-10-20', 'end': '2023-08-07', 'return': 0.234256, 'sharpe': 0.7463, 'max_dd': -0.190734, 'trades': 1, 'win_rate': 1.0}, {'window': 3, 'start': '2023-08-08', 'end': '2024-05-25', 'return': 0.703343, 'sharpe': 1.342, 'max_dd': -0.207463, 'trades': 1, 'win_rate': 1.0}, {'window': 4, 'start': '2024-05-26', 'end': '2025-03-13', 'return': 0.002862, 'sharpe': 0.1939, 'max_dd': -0.268124, 'trades': 1, 'win_rate': 1.0}, {'window': 5, 'start': '2025-03-14', 'end': '2025-12-31', 'return': -0.225899, 'sharpe': -0.7577, 'max_dd': -0.256729, 'trades': 1, 'win_rate': 0.0}], 'profitable_windows': 3, 'consistency_rate': 0.6, 'return_mean': 0.142912, 'return_std': 0.315749, 'sharpe_mean': 0.3049, 'sharpe_std': 0.7078}

## Artifacts
- `artifacts/equity.csv` (142719 bytes, sha256 `c7781abbd9326462c4ce4f99afbe5e635e98cfa91d3a0b4a11933276ee86d183`)
- `artifacts/metrics.csv` (428 bytes, sha256 `fd7c18fcaa1dfb024f7b76cf5aa446af3d13921168a9052f3021995d1cbc8c88`)
- `artifacts/ohlcv_BTC-USDT.csv` (85516 bytes, sha256 `e35c0065f473ef545e1a6a4c287e7b7bc4a16024fc74cff95c064f74ac32ad8b`)
- `artifacts/positions.csv` (21934 bytes, sha256 `658e7ae39a95b20a8ffdf0a61fd5dbd89c23fb2a2b58ec93ab0353ec56faf38e`)
- `artifacts/trades.csv` (610 bytes, sha256 `92aa4866c151f4097269f9e3d918c96a22ca017f0d5089e3fa8053b1054a9430`)
- `artifacts/validation.json` (1893 bytes, sha256 `aca7b894814e752e892903e80a4ee284f6efba0a447b5d865201547e96ebd803`)
- `code/signal_engine.py` (850 bytes, sha256 `1889742cbb9285ac7cfd70cbe5ea82e9ebc688bb9bbd88eb20bf1a42e2af1962`)
- `config.json` (1202 bytes, sha256 `b0911e6a5b1d37946ea2dc54d209c0df9e212aa5bc5cb2c990bcaf5901a8fe48`)
