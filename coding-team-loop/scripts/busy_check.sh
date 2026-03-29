#!/usr/bin/env bash
# busy_check.sh <session:win.pane>
# Outputs: matched line + BUSY, or IDLE
# Uses Python regex for portability (grep -E behaves inconsistently across exec environments)
set -euo pipefail

TARGET="${1:-}"
if [[ -z "$TARGET" ]]; then
  echo "usage: busy_check.sh <session:win.pane>" >&2
  exit 2
fi

tmux capture-pane -p -t "$TARGET" -S -40 2>/dev/null \
  | grep -v '^$' | tail -5 \
  | python3 -c "
import sys, re
p = re.compile(r'^\s*[✢✦✳✶✻✽•] [A-Z][a-z]+ing|^\s*[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]')
for line in sys.stdin:
    line = line.rstrip('\n')
    if p.search(line):
        print(line)
        print('BUSY')
        sys.exit(0)
print('IDLE')
"
