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
  | grep -v '^$' | tail -15 \
  | python3 -c "
import sys, re

patterns = [
    # === Claude Code ===
    # Symbol + gerund: ✢ Generating, • Working, · Choreographing, etc.
    re.compile(r'^\s*[✢✦✳✶✻✽•·∙] [A-Z][a-z]+ing'),
    # Braille spinner characters
    re.compile(r'^\s*[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]'),
    # Tool execution in progress
    re.compile(r'Running…'),

    # === Codex CLI ===
    # Codex shows 'Thinking...' or similar during generation
    re.compile(r'Thinking\.\.\.'),
    # Codex active execution — NOT 'background terminal running' (that persists in idle state)
    # Codex spinner/progress (⣾⣽⣻⢿⡿⣟⣯⣷ or similar)
    re.compile(r'^\s*[⣾⣽⣻⢿⡿⣟⣯⣷]'),
]

for line in sys.stdin:
    line = line.rstrip('\n')
    for p in patterns:
        if p.search(line):
            print(line)
            print('BUSY')
            sys.exit(0)
print('IDLE')
"
