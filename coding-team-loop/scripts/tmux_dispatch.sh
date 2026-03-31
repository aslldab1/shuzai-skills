#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-}"
PAYLOAD="${2:-}"

if [[ -z "$TARGET" || -z "$PAYLOAD" ]]; then
  echo "usage: tmux_dispatch.sh <session:win.pane> <payload>" >&2
  exit 2
fi

# NOTE: busy check is done by openclaw BEFORE calling this script (SKILL.md Step 2/3).
# This script does NOT re-check busy state — doing so caused timing-gap false rejections.

capture_tail() {
  tmux capture-pane -p -t "$TARGET" -S -40 2>/dev/null || true
}

# Ack detection: match symbol + capitalized gerund (e.g. ✢ Composing, • Working)
# or Codex-specific patterns (Thinking..., braille spinners)
# Uses Python regex for consistency with busy_check.sh
has_ack() {
  capture_tail | python3 -c "
import sys, re
patterns = [
    re.compile(r'^\s*[✢✦✳✶✻✽•·∙⏺] [A-Z][a-z]+ing'),
    re.compile(r'^\s*[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏⣾⣽⣻⢿⡿⣟⣯⣷]'),
    re.compile(r'Running…'),
    re.compile(r'Thinking\.\.\.'),
]
for line in sys.stdin:
    line = line.rstrip('\n')
    for p in patterns:
        if p.search(line):
            sys.exit(0)
sys.exit(1)
"
}

# Step1: send payload via load-buffer + paste-buffer (reliable for long messages)
TMPFILE=$(mktemp /tmp/tmux_dispatch.XXXXXX)
trap 'rm -f "$TMPFILE"' EXIT
printf '%s' "$PAYLOAD" > "$TMPFILE"
(tmux load-buffer "$TMPFILE" && tmux paste-buffer -t "$TARGET" && sleep 0.6 && tmux send-keys -t "$TARGET" C-m) || {
  echo "dispatch=failed reason=send_error target=$TARGET"
  exit 1
}

# Step2: ack check with retries
for _ in 1 2 3; do
  sleep 1
  if has_ack; then
    echo "dispatch=submitted target=$TARGET"
    exit 0
  fi
  tmux send-keys -t "$TARGET" C-m || true
done

# Step3: final ack check
sleep 1
if has_ack; then
  echo "dispatch=submitted target=$TARGET mode=retry-cm"
  exit 0
fi

echo "dispatch=failed reason=no_ack target=$TARGET"
exit 1
