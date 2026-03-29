#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-}"
PAYLOAD="${2:-}"

if [[ -z "$TARGET" || -z "$PAYLOAD" ]]; then
  echo "usage: tmux_dispatch.sh <session:win.pane> <payload>" >&2
  exit 2
fi

ack_regex='Working|Calculating|Misting|Ran '

# NOTE: busy check is done by openclaw BEFORE calling this script (SKILL.md Step 2/3).
# This script does NOT re-check busy state — doing so caused timing-gap false rejections.

capture_tail() {
  tmux capture-pane -p -t "$TARGET" -S -40 2>/dev/null || true
}

has_ack() {
  capture_tail | grep -Eq "$ack_regex"
}

# Step1 send payload
(tmux send-keys -t "$TARGET" -l -- "$PAYLOAD" && tmux send-keys -t "$TARGET" C-m && sleep 0.6 && tmux send-keys -t "$TARGET" C-m) || {
  echo "dispatch=failed reason=send_error target=$TARGET"
  exit 1
}

# Step2 ack check with retries
for _ in 1 2 3; do
  sleep 1
  if has_ack; then
    echo "dispatch=submitted target=$TARGET"
    exit 0
  fi
  tmux send-keys -t "$TARGET" C-m || true
done

# Step3 final ack check only (no hardcoded task text)
sleep 1
if has_ack; then
  echo "dispatch=submitted target=$TARGET mode=retry-cm"
  exit 0
fi

echo "dispatch=failed reason=no_ack target=$TARGET"
exit 1
