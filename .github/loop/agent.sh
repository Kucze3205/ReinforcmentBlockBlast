#!/usr/bin/env bash
# Sesja agenta (#16). Uruchamiana z checkoutu gałęzi domyślnej; agent pracuje w $WORK.
# Wejście: .session/issue.md (przefiltrowane, #22). Wyjście: .session/report.md (publikuje workflow).
# Agent nie ma `gh` ani internetu z profilu: raport i wejście idą plikami.
set -u
LOOP="$GITHUB_WORKSPACE/loop/.github/loop/loop.py"
OUT="${RUNNER_TEMP:-/tmp}"
cd "$WORK" || exit 1
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git checkout -q -B "task/$ISSUE"
mkdir -p .session
GH_TOKEN="$LOOP_GH_TOKEN" python3 "$LOOP" export "$ISSUE" .session/issue.md

# checkpoint: raport i gałąź jadą na zewnątrz, zanim runner zginie
( while sleep 120; do
    GH_TOKEN="$LOOP_GH_TOKEN" python3 "$LOOP" publish "$ISSUE" .session/report.md
    git push -q -f origin "HEAD:refs/heads/task/$ISSUE"
  done ) >/dev/null 2>&1 &
SYNC=$!

# GH_TOKEN dostaje wyłącznie orchestrator (jedyna rola z `gh` w profilu)
[ "$ROLE" = orchestrator ] && export GH_TOKEN="$LOOP_GH_TOKEN"

PROMPT="Jesteś rolą \`$ROLE\` w pętli. Wywołaj skill \`$ROLE\` narzędziem Skill i wykonaj zadanie z issue #$ISSUE. Wejście: .session/issue.md. Raport zapisz w .session/report.md (format i statusy: .claude/skills/PROTOKOL-SESJI.md). Pracujesz na gałęzi task/$ISSUE; commituj często."
timeout "${AGENT_TIMEOUT}m" claude -p "$PROMPT" \
  --model "$MODEL" --effort "$EFFORT" \
  --permission-mode acceptEdits --allowedTools "$TOOLS" \
  --max-turns "$MAX_TURNS" --output-format stream-json --verbose \
  2> "$OUT/claude-stderr.txt" \
  | python3 "$GITHUB_WORKSPACE/loop/.github/loop/stream_filter.py" "$OUT"
echo "${PIPESTATUS[0]}" > "$OUT/agent-exit"
kill "$SYNC" 2>/dev/null
exit 0
