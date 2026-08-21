# Backtest Run Card

Generated: 2026-08-19T15:09:05.778824Z
Run directory: `./runs/20260819T150800Z-donchian-120-60`

## Backtest Summary
- codes: ['BTC-USDT']
- start_date: 2022-01-01
- end_date: 2025-12-31
- interval: 1D
- engine: daily
- initial_cash: 1000000
- source: binance

## Reproducibility
- config_hash: `7f897164c85ffc97c73b791b9835e7148be8079b2417314d13be28100bd1b120`
- strategy_hash: `8e2f5e296eabdc385df7d7834d226f65781e940961d9d1e25bd3c36f1adf3832`

## Data Sources
- binance

## Metrics
- final_value: 2326864.900272917
- total_return: 1.3268649002729171
- annual_return: 0.1568109161207143
- max_drawdown: -0.2648132450952168
- sharpe: 0.6998395258540949
- calmar: 0.5922
- sortino: 0.7216
- win_rate: 0.8
- profit_loss_ratio: 2.2992
- profit_factor: 9.1967
- max_consecutive_loss: 1
- avg_holding_days: 129.4
- trade_count: 5
- benchmark_return: 0.836617
- excess_return: 0.490248
- information_ratio: -0.0537
- avg_turnover: 0.00344
- total_turnover: 5.025768

## Validation
- monte_carlo: {'actual_sharpe': 10.8723, 'actual_max_dd': -0.1499, 'p_value_sharpe': 0.617, 'p_value_max_dd': 0.945, 'simulated_sharpe_mean': 12.9875, 'simulated_sharpe_std': 3.7466, 'simulated_sharpe_p5': 8.6753, 'simulated_sharpe_p95': 19.4699, 'n_simulations': 1000, 'n_trades': 5}
- bootstrap: {'observed_sharpe': 0.7003, 'ci_lower': -0.0908, 'ci_upper': 1.4637, 'median_sharpe': 0.7168, 'prob_positive': 0.954, 'confidence': 0.95, 'n_bootstrap': 1000}
- walk_forward: {'n_windows': 5, 'windows': [{'window': 1, 'start': '2022-01-01', 'end': '2022-10-19', 'return': 0.0, 'sharpe': 0.0, 'max_dd': 0.0, 'trades': 0, 'win_rate': 0.0}, {'window': 2, 'start': '2022-10-20', 'end': '2023-08-07', 'return': 0.102017, 'sharpe': 0.4379, 'max_dd': -0.191054, 'trades': 2, 'win_rate': 0.5}, {'window': 3, 'start': '2023-08-08', 'end': '2024-05-25', 'return': 0.573768, 'sharpe': 1.2503, 'max_dd': -0.176189, 'trades': 1, 'win_rate': 1.0}, {'window': 4, 'start': '2024-05-26', 'end': '2025-03-13', 'return': 0.318207, 'sharpe': 1.0456, 'max_dd': -0.145077, 'trades': 1, 'win_rate': 1.0}, {'window': 5, 'start': '2025-03-14', 'end': '2025-12-31', 'return': -0.00132, 'sharpe': 0.0943, 'max_dd': -0.135325, 'trades': 1, 'win_rate': 1.0}], 'profitable_windows': 3, 'consistency_rate': 0.6, 'return_mean': 0.198534, 'return_std': 0.220814, 'sharpe_mean': 0.5656, 'sharpe_std': 0.5015}

## Artifacts
- `artifacts/equity.csv` (139186 bytes, sha256 `4885f3c58295d851bde1e062cc2b8bfd97361e3095d36088dfc988edde3c9f33`)
- `artifacts/metrics.csv` (422 bytes, sha256 `7d0fc80ab80b9ea586cfec26b06a15e1ea6028316966ed9c82b645cb881fc1e9`)
- `artifacts/ohlcv_BTC-USDT.csv` (85516 bytes, sha256 `e35c0065f473ef545e1a6a4c287e7b7bc4a16024fc74cff95c064f74ac32ad8b`)
- `artifacts/positions.csv` (21934 bytes, sha256 `fea25b510dc7391b3d2f8b1eafe9e520af3b1b9d92e893a42f747d4b1b0096d1`)
- `artifacts/trades.csv` (746 bytes, sha256 `4e3de70ea42878e263ee181c6a973e80ccb80931bf2a8f7d3c9fa209901d5dda`)
- `artifacts/validation.json` (1894 bytes, sha256 `82f639b2f09ce1cf8cc528b80c5517e265c267241baf52939ae5e5c91c05663b`)
- `code/signal_engine.py` (1386 bytes, sha256 `8e2f5e296eabdc385df7d7834d226f65781e940961d9d1e25bd3c36f1adf3832`)
- `config.json` (1242 bytes, sha256 `7f897164c85ffc97c73b791b9835e7148be8079b2417314d13be28100bd1b120`)
