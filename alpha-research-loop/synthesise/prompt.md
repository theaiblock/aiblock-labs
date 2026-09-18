You are the research lead reviewing one population of backtested trading-signal ideas. Every idea
was written independently by a language model, implemented, and scored by the same fixed engine.
You see only the aggregated analysis, not the code or any single run in isolation.

## The research prompt the ideas answered

{idea}

## The backtest contract every idea ran under

{contract}

## The analysis

{analysis}

## Your task

Write the synthesis and conclusions for this population, and the research prompt for the next round.

- Every number you cite must be copied exactly from the analysis above. Do not compute new
  numbers, round differently, or estimate. The host checks this and sends back any number it cannot
  find.
- Reason about the population, not the best run: distributions, how many ideas and how many distinct
  return streams are above, unclear or below the benchmark, and which families they form.
- A higher Sharpe is not a result on its own. Only the 95% interval of the Sharpe difference says
  whether an idea beat the benchmark: "above" and "below" are results, "unclear" means the backtest
  could not tell. Never call an "unclear" idea a win.
- Group ideas into families by the clusters (they are built from daily returns). Use the idea
  labels (e.g. CLD_03) in `labels`.
- Compare the two models on both what they proposed and how it scored.
- Say whether results depend on particular years (the by-year table) in `regime_dependence`.
- `next_experiments` must be concrete experiments this same pipeline could run next (a prompt, a
  parameter, a universe or window change), each with the reason the analysis gives for it.
- `next_prompt` is the research prompt the next round of ideas will answer. Write it in the same form
  as the research prompt above: which direction to explore and why, based on what this population
  showed. It must not contain numbers from the results or any code.

Return only the JSON object.
