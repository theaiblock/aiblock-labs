#!/usr/bin/env bash

set -euo pipefail

runner="codex"
iterations=1
task="crypto_allocation"

for arg in "$@"; do
    case "$arg" in
        --claude) runner="claude" ;;
        --codex) runner="codex" ;;
        --opencode) runner="opencode" ;;
        --task=*) task="${arg#--task=}" ;;
        [0-9]*) iterations="$arg" ;;
        *) echo "Unknown argument: $arg" >&2; exit 2 ;;
    esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$script_dir"
mkdir -p logs

run_agent() {
    local workspace="$1"
    local prompt
    prompt="$(<"$workspace/PROMPT.md")"
    case "$runner" in
        claude)
            (cd "$workspace" && claude -p --permission-mode acceptEdits \
                --allowedTools "Read,Write,Edit,Glob,Grep" "$prompt")
            ;;
        codex)
            codex exec -C "$workspace" --sandbox workspace-write "$prompt"
            ;;
        opencode)
            (cd "$workspace" && opencode run "$prompt")
            ;;
    esac
}

for ((iteration = 1; iteration <= iterations; iteration++)); do
    workspace="$(python -m harness.cli stage "$task")"
    timestamp="$(date -u +%Y%m%d_%H%M%S)"
    log="logs/iteration_${timestamp}.log"
    printf 'iteration=%s workspace=%s runner=%s\n' "$iteration" "$workspace" "$runner" | tee "$log"
    run_agent "$workspace" 2>&1 | tee -a "$log"
    python -m harness.cli submit "$workspace" | tee -a "$log"
done
