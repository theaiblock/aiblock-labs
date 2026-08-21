#!/usr/bin/env bash

set -uo pipefail

RUNNER="opencode"
MAX_ITERATIONS=1

for arg in "$@"; do
    case "$arg" in
        --claude) RUNNER="claude" ;;
        --codex) RUNNER="codex" ;;
        --opencode) RUNNER="opencode" ;;
        [0-9]*) MAX_ITERATIONS="$arg" ;;
        *) echo "Unknown argument: $arg" >&2; exit 2 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
mkdir -p logs runs

if [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
    export PATH="$SCRIPT_DIR/.venv/bin:$PATH"
fi

# Public model defaults, so a fresh clone runs without extra configuration.
# Override one runner with CLAUDE_MODEL / OPENCODE_MODEL / CODEX_MODEL, or all
# of them with MODEL_OVERRIDE — useful to point at a private gateway or a
# provider-specific deployment name without editing this file.
CLAUDE_MODEL="${CLAUDE_MODEL:-claude-opus-5}"
OPENCODE_MODEL="${OPENCODE_MODEL:-anthropic/claude-opus-5}"
CODEX_MODEL="${CODEX_MODEL:-}"

run_agent() {
    local prompt="$1"
    if [[ "$RUNNER" == "claude" ]]; then
        local model="${MODEL_OVERRIDE:-$CLAUDE_MODEL}"
        claude -p --model "$model" --permission-mode acceptEdits \
            --allowedTools "Read,Write,Edit,Bash,Glob,Grep" "$prompt"
    elif [[ "$RUNNER" == "codex" ]]; then
        local model="${MODEL_OVERRIDE:-$CODEX_MODEL}"
        local model_args=()
        if [[ -n "$model" ]]; then
            model_args=(-m "$model")
        fi
        codex exec -C "$SCRIPT_DIR" --approve-for-me \
            "${model_args[@]}" "$prompt"
    else
        local model="${MODEL_OVERRIDE:-$OPENCODE_MODEL}"
        opencode run --model "$model" "$prompt"
    fi
}

for ((iteration = 1; iteration <= MAX_ITERATIONS; iteration++)); do
    timestamp="$(date -u +%Y%m%d_%H%M%S)"
    log_file="logs/iteration_${timestamp}.log"
    prompt="$(<PROMPT.md)"
    run_agent "$prompt" 2>&1 | stdbuf -oL tee "$log_file"
    exit_code=${PIPESTATUS[0]}
    if [[ $exit_code -ne 0 ]]; then
        echo "WARNING: $RUNNER exited with code $exit_code" | tee -a "$log_file"
    fi
done
