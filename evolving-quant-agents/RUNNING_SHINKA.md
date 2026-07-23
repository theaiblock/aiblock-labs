# Running ShinkaEvolve on a Claude subscription (no API key)

Operational notes from actually running it for this lab. Verified against
**`shinka-evolve==0.0.7`** (2026-07-20). Upstream: <https://github.com/SakanaAI/ShinkaEvolve>
· paper [arXiv:2509.19349](https://arxiv.org/abs/2509.19349) · Apache-2.0.

ShinkaEvolve is an LLM + evolutionary-search loop for evolving **code**: keep a population of
programs, an LLM proposes edits, an evaluator you supply scores each candidate, scores feed
back, repeat. It is domain-agnostic — it ships **zero** finance code. You bring the seed
program and the evaluator; it brings the search. (That's the whole thesis of this lab.)

## Install

It needs its own virtualenv — don't mix it with this project's:

```bash
uv venv shinka-venv --python 3.12
uv pip install --python shinka-venv/bin/python shinka-evolve pyarrow
```

`pyarrow` is for reading our parquet inside the evaluator subprocess.

## The subscription backend

Model strings are `provider/...`. Alongside the usual API-key providers, ShinkaEvolve has a
**`headless`** provider that shells out to `npx -y @roberttlange/headless <agent> -p …` — i.e.
it drives the local **`claude` CLI in print mode**, which runs on your **Claude subscription,
no API key**. The provider strips `ANTHROPIC_API_KEY` / `CLAUDE_CODE_OAUTH_TOKEN` so Claude
Code uses its own oauth login; it never reads or transmits the token.

```bash
npx -y @roberttlange/headless --check     # shows agents + auth state
```

Examples: `headless/claude` (Opus), `headless/claude@sonnet`, `headless/codex@gpt-5.5?effort=high`.

**What hitting the subscription limit looks like:** failed attempts come back with
`failure_class: llm_output_invalid` and `error: "LLM response content was None."` — the CLI
returns empty. That's your quota, not a bug. Stop and resume later (see below).

## The four LLM roles

`EvolutionConfig` separates them, and using different models per role is the main cost lever:

| Role | Config | Frequency | What it does |
|---|---|---|---|
| **Mutation** | `llm_models`, `llm_kwargs` | ~1 call/generation | Diagnoses the current program and writes the improved code. A cheap model is plenty — we used `headless/claude@sonnet` at low effort. |
| **Orchestrator (meta)** | `meta_llm_models`, `meta_rec_interval` | every N gens | Reads the whole population and history, writes strategic recommendations injected into later mutation prompts. Worth a strong model — we used Opus every 5 generations. |
| **Novelty** | `novelty_llm_models` | per proposal (optional) | Checks a proposal is novel vs the archive. |
| **Prompt evolution** | `prompt_llm_models` | optional, off by default | Evolves the meta-prompt itself. |

`reasoning_efforts: ["high"]` on a big model is the token hog — `low`/`medium` is plenty for
mutating a small strategy function. Set `embedding_model=None` to avoid needing an embedding
API key.

## Loop mechanics worth knowing

- **EVOLVE-BLOCK markers.** Only code between `# EVOLVE-BLOCK-START` and `# EVOLVE-BLOCK-END`
  mutates; everything else in the seed file is preserved verbatim in every evolved copy. Put
  fixed helpers and imports *outside* the block so each program stays self-contained.
- **Keep the editable block small.** `patch_types=["diff","full"]`: `diff` is SEARCH/REPLACE and
  needs an exact text match, so a docstring-heavy function breaks patching. We kept the block
  minimal and allowed `full` as a fallback.
- **Retries multiply cost.** `max_patch_attempts × max_patch_resamples` calls per generation on
  failure — once the subscription was limited we burned 6 doomed calls in one generation. Keep
  them low (we used 2 × 1).
- **Evaluator contract.** Invoked as
  `[sys.executable, eval_program_path, --program_path <evolved.py> --results_dir <dir>]`, so
  `sys.executable` is the Shinka venv — your numpy/pandas/pyarrow must be installed *there*.
  It must write `metrics.json = {combined_score, public:{…}, private:{…}}` and
  `correct.json = {correct, error}`. **`combined_score` is what the search maximizes; `public`
  is shown to the mutation LLM as feedback; `private` is not.**

## Resume

Point `results_dir` at an existing run directory and ShinkaEvolve detects the previous run,
restores the population and history, and continues from the last completed generation. So
re-running the same command with the same `results_dir` loses nothing.

`resume.py` in this folder wraps that: it drives resume per mode, reports progress out of
`programs.sqlite`, and detects the limit (a batch that adds zero programs) so it stops cleanly
instead of burning retries.

## Where the run output lands

```
runs/<mode>/
  programs.sqlite            the state DB — resume and progress read from here
  headless_prompts/          every prompt sent to the CLI
  meta/meta_N.txt            the orchestrator's output: per-program diagnosis, a global
                             insights scratchpad, and recommendations for the next generations
  gen_N/
    main.py                  the evolved program (full file)
    original.py              the parent it mutated from
    edit.diff / rewrite.txt  the applied change
    results/metrics.json     evaluator output
    results/correct.json     {correct, error}
    failure.json             only if the patch failed
    attempts/…/llm_response.txt   the mutation model's full response — its reasoning + the diff
  best/                      the best program overall
```

If you want to see the agent reason about its own overfitting, `meta/meta_N.txt` is the file.
