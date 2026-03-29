#!/usr/bin/env python3
"""
openclaw cron 执行日志分析工具

用法：
  python3 analyze_runs.py --job clawcoach-progress-10m --last 10
  python3 analyze_runs.py --job clawcoach-progress-10m --session {id} --steps
  python3 analyze_runs.py --list-jobs
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

CRON_DIR = Path.home() / ".openclaw" / "cron"
JOBS_FILE = CRON_DIR / "jobs.json"
RUNS_DIR = CRON_DIR / "runs"
SESSIONS_DIR = Path.home() / ".openclaw" / "agents" / "main" / "sessions"

TZ_CST = timezone(timedelta(hours=8))

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def load_jobs() -> list[dict]:
    if not JOBS_FILE.exists():
        print(f"{RED}jobs.json not found: {JOBS_FILE}{RESET}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(JOBS_FILE.read_text())
    return data.get("jobs", [])


def find_job(name: str) -> dict:
    for job in load_jobs():
        if job.get("name") == name:
            return job
    print(f"{RED}Job not found: {name}{RESET}", file=sys.stderr)
    print("Available jobs:")
    for job in load_jobs():
        print(f"  - {job.get('name')} ({job.get('id', '?')[:8]})")
    sys.exit(1)


def load_runs(job_id: str, last_n: int = 20) -> list[dict]:
    runs_file = RUNS_DIR / f"{job_id}.jsonl"
    if not runs_file.exists():
        print(f"{RED}Runs file not found: {runs_file}{RESET}", file=sys.stderr)
        return []
    entries = []
    with open(runs_file) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entry = json.loads(line)
                    if entry.get("action") == "finished":
                        entries.append(entry)
                except json.JSONDecodeError:
                    pass
    return entries[-last_n:]


def fmt_ts(ts_ms: int) -> str:
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=TZ_CST)
    return dt.strftime("%m-%d %H:%M")


def print_overview(runs: list[dict], timeout_sec: int):
    if not runs:
        print("No runs found.")
        return

    print(f"\n{BOLD}{'Time':>11} {'Status':>7} {'Duration':>9} {'In Tokens':>10} {'Out Tokens':>11} {'Error'}{RESET}")
    print("─" * 75)

    durations = []
    input_tokens_list = []
    errors = 0
    timeouts = 0

    for run in runs:
        ts = fmt_ts(run.get("ts", 0))
        status = run.get("status", "?")
        dur_ms = run.get("durationMs", 0)
        dur_s = dur_ms / 1000
        usage = run.get("usage", {})
        in_tok = usage.get("input_tokens", 0)
        out_tok = usage.get("output_tokens", 0)
        error = run.get("error", "")

        durations.append(dur_s)
        if in_tok:
            input_tokens_list.append(in_tok)

        # Color coding
        if status == "error":
            errors += 1
            if "timeout" in error:
                timeouts += 1
            status_str = f"{RED}{status:>7}{RESET}"
        elif dur_s > timeout_sec * 0.8:
            status_str = f"{YELLOW}{status:>7}{RESET}"
        else:
            status_str = f"{GREEN}{status:>7}{RESET}"

        dur_str = f"{dur_s:>7.1f}s"
        if dur_s > timeout_sec * 0.8:
            dur_str = f"{YELLOW}{dur_str}{RESET}"

        in_str = f"{in_tok:>10,}" if in_tok else f"{'?':>10}"
        out_str = f"{out_tok:>11,}" if out_tok else f"{'?':>11}"

        print(f"{ts:>11} {status_str} {dur_str} {in_str} {out_str} {error}")

    # Summary
    print("─" * 75)
    avg_dur = sum(durations) / len(durations) if durations else 0
    max_dur = max(durations) if durations else 0
    avg_tok = sum(input_tokens_list) / len(input_tokens_list) if input_tokens_list else 0
    max_tok = max(input_tokens_list) if input_tokens_list else 0

    print(f"\n{BOLD}统计{RESET}")
    print(f"  总执行次数:    {len(runs)}")
    print(f"  错误次数:      {errors} (其中超时 {timeouts})")
    print(f"  平均耗时:      {avg_dur:.1f}s / 超时上限 {timeout_sec}s ({avg_dur/timeout_sec*100:.0f}%)")
    print(f"  最大耗时:      {max_dur:.1f}s ({max_dur/timeout_sec*100:.0f}%)")
    print(f"  平均 input:    {avg_tok:,.0f} tokens")
    print(f"  最大 input:    {max_tok:,.0f} tokens")

    # Trend detection
    if len(durations) >= 5:
        first_half = durations[: len(durations) // 2]
        second_half = durations[len(durations) // 2 :]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        if avg_second > avg_first * 1.3:
            print(f"\n  {YELLOW}⚠ 趋势恶化: 后半段平均 {avg_second:.0f}s vs 前半段 {avg_first:.0f}s (+{(avg_second/avg_first-1)*100:.0f}%){RESET}")

    # Token anomalies
    if input_tokens_list and len(input_tokens_list) >= 3:
        median_tok = sorted(input_tokens_list)[len(input_tokens_list) // 2]
        anomalies = [(i, t) for i, t in enumerate(input_tokens_list) if t > median_tok * 2]
        if anomalies:
            print(f"\n  {YELLOW}⚠ Token 异常 (>2x 中位数 {median_tok:,}):{RESET}")
            for idx, tok in anomalies:
                run = runs[idx]
                ts = fmt_ts(run.get("ts", 0))
                print(f"    {ts}: {tok:,} tokens")


def parse_session_steps(session_id: str) -> list[dict]:
    path = SESSIONS_DIR / f"{session_id}.jsonl"
    if not path.exists():
        print(f"{RED}Session file not found: {path}{RESET}", file=sys.stderr)
        return []

    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    steps = []
    for entry in entries:
        if entry.get("type") != "message":
            if entry.get("type") == "custom":
                ct = entry.get("customType", "")
                if ct == "openclaw:prompt-error":
                    steps.append({
                        "kind": "error",
                        "error": entry.get("data", {}).get("error", "unknown"),
                    })
            continue

        msg = entry.get("message", {})
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "assistant" and isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                bt = block.get("type", "")
                if bt in ("tool_use", "toolCall"):
                    args = block.get("arguments", block.get("input", {}))
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            pass
                    steps.append({
                        "kind": "call",
                        "name": block.get("name", "?"),
                        "args": args if isinstance(args, dict) else {},
                    })
                elif bt == "text":
                    text = block.get("text", "").strip()
                    if text:
                        steps.append({"kind": "output", "text": text})

        elif role in ("user", "toolResult"):
            if isinstance(content, list):
                if role == "toolResult":
                    # Single tool result: content=[{type:text, text:...}]
                    combined = " ".join(
                        b.get("text", "") for b in content
                        if isinstance(b, dict) and b.get("type") == "text"
                    )
                    if combined:
                        steps.append({
                            "kind": "result",
                            "content": combined,
                            "chars": len(combined),
                        })
                else:
                    # User message with embedded tool_result blocks
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        bt = block.get("type", "")
                        if bt in ("tool_result", "toolResult"):
                            c = block.get("content", "")
                            if isinstance(c, list):
                                c = " ".join(
                                    x.get("text", "") for x in c
                                    if isinstance(x, dict)
                                )
                            steps.append({
                                "kind": "result",
                                "content": str(c),
                                "chars": len(str(c)),
                            })
            elif isinstance(content, str) and role == "toolResult":
                steps.append({
                    "kind": "result",
                    "content": content,
                    "chars": len(content),
                })

    return steps


def print_steps(steps: list[dict]):
    step_n = 0
    seen_calls = {}
    duplicates = []
    large_results = []

    i = 0
    while i < len(steps):
        s = steps[i]
        if s["kind"] == "call":
            step_n += 1
            name = s["name"]
            args = s["args"]

            # Format arguments
            if name in ("exec",):
                arg_str = args.get("command", "")[:200]
            elif name in ("read",):
                arg_str = args.get("file_path", args.get("path", str(args)))[:150]
            else:
                arg_str = json.dumps(args, ensure_ascii=False)[:150]

            # Check duplicates
            call_key = f"{name}:{arg_str[:80]}"
            is_dup = call_key in seen_calls
            if is_dup:
                duplicates.append((step_n, name, arg_str[:80]))
            seen_calls[call_key] = step_n

            dup_tag = f" {YELLOW}[DUP of step {seen_calls.get(call_key, '?')}]{RESET}" if is_dup and seen_calls[call_key] != step_n else ""
            print(f"{BOLD}Step {step_n:2d}{RESET} [{name}]{dup_tag}")
            print(f"       {DIM}{arg_str}{RESET}")

            # Show result size
            if i + 1 < len(steps) and steps[i + 1]["kind"] == "result":
                result = steps[i + 1]
                chars = result["chars"]
                size_tag = ""
                if chars > 10000:
                    size_tag = f" {RED}⚠ LARGE{RESET}"
                    large_results.append((step_n, name, chars))
                elif chars > 5000:
                    size_tag = f" {YELLOW}⚠{RESET}"
                    large_results.append((step_n, name, chars))
                print(f"       → {chars:,} chars{size_tag}")
                i += 2
                continue

        elif s["kind"] == "output":
            print(f"\n{'─' * 60}")
            print(f"{BOLD}[Output]{RESET} ({len(s['text'])} chars)")
            print(s["text"][:500])
            if len(s["text"]) > 500:
                print("...")
            print(f"{'─' * 60}\n")

        elif s["kind"] == "error":
            print(f"\n{RED}{'─' * 60}")
            print(f"[ABORTED] {s['error']}")
            print(f"{'─' * 60}{RESET}\n")

        i += 1

    # Summary
    print(f"\n{BOLD}步骤统计{RESET}")
    print(f"  总步骤: {step_n}")
    if duplicates:
        print(f"  {YELLOW}重复调用 ({len(duplicates)}):{RESET}")
        for sn, name, arg in duplicates:
            print(f"    Step {sn}: [{name}] {arg}")
    if large_results:
        print(f"  {YELLOW}大数据返回 ({len(large_results)}):{RESET}")
        for sn, name, chars in large_results:
            print(f"    Step {sn}: [{name}] {chars:,} chars")


def list_jobs():
    jobs = load_jobs()
    print(f"\n{BOLD}Cron Jobs{RESET}\n")
    for job in jobs:
        name = job.get("name", "?")
        enabled = job.get("enabled", False)
        state = job.get("state", {})
        status_icon = f"{GREEN}●{RESET}" if enabled else f"{DIM}○{RESET}"
        last_status = state.get("lastRunStatus", "?")
        last_dur = state.get("lastDurationMs", 0) / 1000
        timeout = job.get("payload", {}).get("timeoutSeconds", "?")

        print(f"  {status_icon} {name}")
        print(f"    ID: {job.get('id', '?')[:8]}...")
        print(f"    Last: {last_status} ({last_dur:.0f}s / {timeout}s timeout)")
        print(f"    Errors: {state.get('consecutiveErrors', 0)} consecutive")
        print()


def main():
    parser = argparse.ArgumentParser(description="openclaw cron 执行日志分析")
    parser.add_argument("--job", help="Job name (e.g. clawcoach-progress-10m)")
    parser.add_argument("--last", type=int, default=10, help="分析最近 N 次执行 (default: 10)")
    parser.add_argument("--session", help="分析指定 session 的执行步骤")
    parser.add_argument("--steps", action="store_true", help="输出执行步骤详情")
    parser.add_argument("--list-jobs", action="store_true", help="列出所有 cron jobs")
    args = parser.parse_args()

    if args.list_jobs:
        list_jobs()
        return

    if args.session:
        print(f"\n{BOLD}Session 步骤分析: {args.session}{RESET}\n")
        steps = parse_session_steps(args.session)
        if steps:
            print_steps(steps)
        return

    if not args.job:
        print(f"{RED}请指定 --job 或 --list-jobs{RESET}")
        sys.exit(1)

    job = find_job(args.job)
    job_id = job["id"]
    timeout = job.get("payload", {}).get("timeoutSeconds", 300)

    print(f"\n{BOLD}Job: {args.job}{RESET}")
    print(f"  ID:      {job_id[:8]}...")
    print(f"  Enabled: {job.get('enabled')}")
    print(f"  Timeout: {timeout}s")

    runs = load_runs(job_id, args.last)
    print_overview(runs, timeout)

    if args.steps and runs:
        # Find latest run with session
        for run in reversed(runs):
            sid = run.get("sessionId")
            if sid:
                print(f"\n\n{BOLD}最近一次执行步骤 ({fmt_ts(run.get('ts', 0))}){RESET}\n")
                steps = parse_session_steps(sid)
                if steps:
                    print_steps(steps)
                break


if __name__ == "__main__":
    main()
