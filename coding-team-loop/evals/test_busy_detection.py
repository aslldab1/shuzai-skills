#!/usr/bin/env python3
"""
Tests for busy detection regex used in tmux_dispatch.sh.

Validates that the regex correctly distinguishes busy vs idle pane content.
Run: python3 test_busy_detection.py
"""
import re
import subprocess
import sys

# Must match tmux_dispatch.sh busy_regex exactly
BUSY_REGEX = r'^\s*[✢✦✳✶✻✽•] [A-Z][a-z]+ing|^\s*[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]'

# --- Test cases ---

BUSY_LINES = [
    # Claude Code busy states (dingbat + gerund)
    ("✢ Generating… (49s · ↓ 87 tokens)", "Claude generating"),
    ("✻ Thinking…", "Claude thinking"),
    ("✦ Reading…", "Claude reading"),
    ("✳ Writing…", "Claude writing"),
    ("✶ Searching…", "Claude searching"),
    ("✽ Installing…", "Claude installing"),
    ("  ✢ Compiling… (12s)", "Claude compiling with leading space"),
    # Codex busy states (bullet + gerund)
    ("• Working (5s • esc to interrupt)", "Codex working"),
    ("• Thinking (2s • esc to interrupt)", "Codex thinking"),
    ("• Running tests…", "Codex running"),
    # Braille spinner (standalone)
    ("⠋", "spinner frame 1"),
    ("⠙", "spinner frame 2"),
    ("⠹", "spinner frame 3"),
    ("⠸", "spinner frame 4"),
    ("⠼", "spinner frame 5"),
    ("⠴", "spinner frame 6"),
    ("⠦", "spinner frame 7"),
    ("⠧", "spinner frame 8"),
    ("⠇", "spinner frame 9"),
    ("⠏", "spinner frame 10"),
    ("  ⠋", "spinner with leading space"),
]

IDLE_LINES = [
    # Claude Code idle / history output with dingbat but no gerund
    ("✻ Conversation compacted (ctrl+o for history)", "compacted notification"),
    ("✢ Task completed successfully", "completed notification"),
    ("✦ Connected to server", "connected notification"),
    # Codex idle / history output with bullet but no gerund
    ("• Context compacted", "codex compacted"),
    ("• Ran git status --short", "codex ran command"),
    ("• Waited for background terminal", "codex waited"),
    ("• PR 已经开出来了", "codex Chinese output"),
    # Normal output that contains 'ing' words (must NOT match)
    ("  ⎿  Read docs/tasks/issue-50-stitch-redesign-plan.md (191 lines)", "read tool output"),
    ("  Reading file…", "indented reading without symbol"),
    ("  Writing to disk…", "indented writing without symbol"),
    ("  Searching for pattern…", "indented searching without symbol"),
    ("Running tests in CI…", "running without symbol"),
    # Prompt lines
    ("❯ ", "Claude Code idle prompt"),
    ("❯ /compact", "Claude Code command"),
    ("› Improve documentation in @filename", "Codex idle prompt"),
    # Status bar lines
    ("  [Sonnet 4.6] │ Claw-Coach git:(main)", "Claude status bar"),
    ("  Context █████░░░░░ 52% │ Usage █░░░░░░░░░ 10%", "Claude context bar"),
    ("  ⏵⏵ bypass permissions on · 1 shell", "Claude permissions bar"),
    ("  gpt-5.4 default · 100% left · ~/workspace/AI/git/Claw-Coach_codex", "Codex status bar"),
    # Separator lines
    ("────────────────────", "separator"),
    # Empty / whitespace
    ("", "empty line"),
    ("   ", "whitespace only"),
    # Edge cases: gerund in middle of line (not at symbol position)
    ("  ⎿  Referenced file docs/tasks/issue-51-harness-engineering-rollout.md", "referenced file"),
    ("     PreCompact [node ...] completed successfully", "precompact hook"),
]


def test_regex():
    pattern = re.compile(BUSY_REGEX)
    failures = []

    for line, desc in BUSY_LINES:
        if not pattern.search(line):
            failures.append(f"  FAIL: expected BUSY  but got IDLE  | {desc}: {line!r}")

    for line, desc in IDLE_LINES:
        if pattern.search(line):
            failures.append(f"  FAIL: expected IDLE  but got BUSY  | {desc}: {line!r}")

    total = len(BUSY_LINES) + len(IDLE_LINES)
    passed = total - len(failures)

    print(f"Busy detection regex test: {passed}/{total} passed")
    if failures:
        print()
        for f in failures:
            print(f)
        print()
        return False
    return True


def test_grep_consistency():
    """Verify Python regex matches grep -E behavior for key cases."""
    busy_regex_shell = r'^\s*[✢✦✳✶✻✽•] [A-Z][a-z]+ing|^\s*[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]'

    spot_checks = [
        ("✢ Generating… (49s · ↓ 87 tokens)", True),
        ("✻ Conversation compacted", False),
        ("• Working (5s • esc to interrupt)", True),
        ("• Context compacted", False),
        ("  Reading file…", False),
        ("⠋", True),
    ]

    failures = []
    for line, expect_busy in spot_checks:
        result = subprocess.run(
            ["grep", "-Eq", busy_regex_shell],
            input=line, capture_output=True, text=True,
        )
        got_busy = result.returncode == 0
        if got_busy != expect_busy:
            expected = "BUSY" if expect_busy else "IDLE"
            got = "BUSY" if got_busy else "IDLE"
            failures.append(f"  FAIL (grep): expected {expected} but got {got} | {line!r}")

    total = len(spot_checks)
    passed = total - len(failures)
    print(f"grep -E consistency check: {passed}/{total} passed")
    if failures:
        print()
        for f in failures:
            print(f)
        print()
        return False
    return True


def test_pane_pipeline():
    """End-to-end test: simulate full pane capture → grep -v → tail -5 → grep -Eq pipeline."""
    busy_regex_shell = r'^\s*[✢✦✳✶✻✽•] [A-Z][a-z]+ing|^\s*[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]'

    cases = [
        # (pane content as multiline string, expected_busy, description)
        (
            # Claude idle: prompt + status bar (real capture from 10:04 run)
            "❯ /model opusplan\n"
            "────────────────────\n"
            "❯\xa0Press up to edit queued messages\n"
            "────────────────────\n"
            "  [Opus 4.6] │ Claw-Coach git:(claude\n",
            False,
            "Claude idle with prompt and status bar",
        ),
        (
            # Codex idle: prompt + status bar (real capture)
            "› Improve documentation in @filename\n"
            "\n"
            "  gpt-5.4 default · 100% left · ~/workspace/AI/git/Claw-Coach_codex\n",
            False,
            "Codex idle with prompt and status bar",
        ),
        (
            # Claude busy: generating at bottom
            "  ⎿  Read docs/plan.md (191 lines)\n"
            "\n"
            "  Some output here\n"
            "✢ Generating… (49s · ↓ 87 tokens)\n",
            True,
            "Claude busy generating at bottom",
        ),
        (
            # Codex busy: working at bottom
            "› Previous task done\n"
            "\n"
            "• Working (5s • esc to interrupt)\n",
            True,
            "Codex busy working at bottom",
        ),
        (
            # Historical 'ing' in scrollback but idle at bottom
            "  ✢ Generating… (old output from last task)\n"
            "  ⎿  Read file.md (50 lines)\n"
            "  Task completed successfully\n"
            "\n"
            "❯ \n"
            "────────────────────\n"
            "  [Sonnet 4.6] │ Claw-Coach git:(main)\n"
            "  Context ██░░░░░░░░ 22%\n"
            "  ⏵⏵ bypass permissions on · 1 shell\n",
            False,
            "Historical busy output in scrollback but idle at bottom",
        ),
        (
            # Spinner busy
            "some output\n"
            "\n"
            "⠋\n",
            True,
            "Spinner at bottom",
        ),
        (
            # All empty lines (edge case)
            "\n\n\n\n\n",
            False,
            "All empty lines",
        ),
        (
            # Claude idle with bypass permissions line containing 'ing' word
            "❯ \n"
            "────────────────────\n"
            "  [Sonnet 4.6] │ Claw-Coach git:(main)\n"
            "  Context █████░░░░░ 52% │ Usage █░░░░░░░░░ 10%\n"
            "  ⏵⏵ bypass permissions on · 1 shell\n",
            False,
            "Claude idle - bypass permissions has no busy symbol",
        ),
        (
            # Codex idle: multiple compacted lines (real capture from 13:12 run)
            "• Context compacted\n"
            "• Context compacted\n"
            "• Context compacted\n"
            "› Improve documentation in @filename\n"
            "  gpt-5.4 default · 100% left · ~/workspace/AI/git/Claw-Coach_codex\n",
            False,
            "Codex idle - compacted lines with bullet but no gerund",
        ),
        (
            # Claude idle: prompt + branch status (real capture from 13:12 run)
            "❯ \n"
            "────────────────────────────────────────────────────────────────\n"
            "  [Sonnet 4.6] │ Claw-Coach git:(claude/issue-51-harness-plan-v2*)\n"
            "  Context ███░░░░░░░ 34% │ Usage ████░░░░░░ 35% (resets in 52m)\n"
            "  ⏵⏵ bypass permissions on · 1 shell\n",
            False,
            "Claude idle - real capture with branch and usage stats",
        ),
    ]

    failures = []
    for pane_content, expect_busy, desc in cases:
        # Simulate: echo pane | grep -v '^$' | tail -5 | grep -Eq 'regex'
        result = subprocess.run(
            f"echo {repr(pane_content)} | grep -v '^$' | tail -5 | grep -Eq '{busy_regex_shell}'",
            shell=True, capture_output=True, text=True,
        )
        got_busy = result.returncode == 0
        if got_busy != expect_busy:
            expected = "BUSY" if expect_busy else "IDLE"
            got = "BUSY" if got_busy else "IDLE"
            failures.append(f"  FAIL (pipeline): expected {expected} but got {got} | {desc}")

    total = len(cases)
    passed = total - len(failures)
    print(f"Pane pipeline end-to-end test: {passed}/{total} passed")
    if failures:
        print()
        for f in failures:
            print(f)
        print()
        return False
    return True


def test_python_pipeline():
    """Test the Python-based busy check (same logic as busy_check.sh) against pane scenarios."""
    import os

    cases = [
        # Reuse same cases as test_pane_pipeline but test via Python regex (the actual detection path)
        (
            "❯ /model opusplan\n"
            "────────────────────\n"
            "❯\xa0Press up to edit queued messages\n"
            "────────────────────\n"
            "  [Opus 4.6] │ Claw-Coach git:(claude\n",
            False,
            "Claude idle with prompt and status bar",
        ),
        (
            "› Improve documentation in @filename\n"
            "\n"
            "  gpt-5.4 default · 100% left · ~/workspace/AI/git/Claw-Coach_codex\n",
            False,
            "Codex idle with prompt and status bar",
        ),
        (
            "  ⎿  Read docs/plan.md (191 lines)\n"
            "\n"
            "  Some output here\n"
            "✢ Generating… (49s · ↓ 87 tokens)\n",
            True,
            "Claude busy generating at bottom",
        ),
        (
            "› Previous task done\n"
            "\n"
            "• Working (5s • esc to interrupt)\n",
            True,
            "Codex busy working at bottom",
        ),
        (
            "• Context compacted\n"
            "• Context compacted\n"
            "• Context compacted\n"
            "› Improve documentation in @filename\n"
            "  gpt-5.4 default · 100% left · ~/workspace/AI/git/Claw-Coach_codex\n",
            False,
            "Codex idle - compacted lines (13:12 false positive case)",
        ),
        (
            "❯ \n"
            "────────────────────────────────────────────────────────────────\n"
            "  [Sonnet 4.6] │ Claw-Coach git:(claude/issue-51-harness-plan-v2*)\n"
            "  Context ███░░░░░░░ 34% │ Usage ████░░░░░░ 35% (resets in 52m)\n"
            "  ⏵⏵ bypass permissions on · 1 shell\n",
            False,
            "Claude idle - real capture (13:12 false positive case)",
        ),
        ("⠋\n", True, "Spinner"),
        ("\n\n\n", False, "Empty"),
    ]

    pattern = re.compile(BUSY_REGEX)
    failures = []

    for pane_content, expect_busy, desc in cases:
        # Simulate: filter empty lines, take last 5, check regex
        lines = [l for l in pane_content.split('\n') if l.strip()]
        tail5 = lines[-5:] if len(lines) > 5 else lines
        got_busy = any(pattern.search(l) for l in tail5)
        if got_busy != expect_busy:
            expected = "BUSY" if expect_busy else "IDLE"
            got = "BUSY" if got_busy else "IDLE"
            failures.append(f"  FAIL (python): expected {expected} but got {got} | {desc}")

    total = len(cases)
    passed = total - len(failures)
    print(f"Python pipeline test: {passed}/{total} passed")
    if failures:
        print()
        for f in failures:
            print(f)
        print()
        return False
    return True


if __name__ == "__main__":
    ok1 = test_regex()
    ok2 = test_grep_consistency()
    ok3 = test_pane_pipeline()
    ok4 = test_python_pipeline()
    sys.exit(0 if ok1 and ok2 and ok3 and ok4 else 1)
