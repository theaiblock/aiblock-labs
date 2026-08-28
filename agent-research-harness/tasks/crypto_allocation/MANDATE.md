# Mandate: crypto allocation research

Complete one coherent allocation experiment using only the files in this workspace. Training
prices and their snapshot manifest are in `train/`. Change `candidate.py`, state the hypothesis
before submission, and leave one candidate that implements `allocate(history) -> dict[str, float]`.

`history` maps symbols to trailing daily returns, oldest to newest. The host calls the function
every 21 days with a maximum of 252 observations per asset. The private period is evaluated as a
long-only portfolio with a 10-basis-point taker fee charged against one-way turnover.

Weights must be finite, non-negative, and sum to one. This is offline research, not investment
advice. Do not connect an exchange, request credentials, or place an order.
