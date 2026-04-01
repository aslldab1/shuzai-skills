#!/usr/bin/env python3
"""
openclaw cron 执行日志分析工具

用法：
  python3 analyze_runs.py --list-jobs
  python3 analyze_runs.py --job clawcoach-progress-10m --last 10
  python3 analyze_runs.py --job clawcoach-progress-10m --last 5 --steps
  python3 analyze_runs.py --session {id} --steps                    # 步骤概览
  python3 analyze_runs.py --session {id} --verbose                  # 全部步骤完整入参+返回
  python3 analyze_runs.py --session {id} --step 28                  # 只看第 28 步的完整详情
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


def print_steps(steps: list[dict], verbose: bool = False, focus_step: int = 0):
    """Print step-by-step execution trace.

    Args:
        verbose: Show full arguments and result content for every step.
        focus_step: If > 0, only show this step number with full detail.
    """
    step_n = 0
    seen_calls = {}
    duplicates = []
    large_results = []
    label_changes = []

    i = 0
    while i < len(steps):
        s = steps[i]
        if s["kind"] == "call":
            step_n += 1
            name = s["name"]
            args = s["args"]

            # Full argument string (used for verbose / focus)
            if name in ("exec",):
                arg_full = args.get("command", "")
            elif name in ("read",):
                arg_full = args.get("file_path", args.get("path", str(args)))
            else:
                arg_full = json.dumps(args, ensure_ascii=False, indent=2)
            arg_short = arg_full[:200]

            # Detect label changes for audit
            if name == "exec" and "gh issue edit" in arg_full:
                label_changes.append((step_n, arg_full))

            # Check duplicates
            call_key = f"{name}:{arg_short[:80]}"
            is_dup = call_key in seen_calls
            if is_dup:
                duplicates.append((step_n, name, arg_short[:80]))
            seen_calls[call_key] = step_n

            # Get result if next
            result = None
            if i + 1 < len(steps) and steps[i + 1]["kind"] == "result":
                result = steps[i + 1]

            # Skip if focusing on a different step
            if focus_step and step_n != focus_step:
                if result:
                    i += 2
                else:
                    i += 1
                continue

            # Print step header
            dup_tag = f" {YELLOW}[DUP of step {seen_calls.get(call_key, '?')}]{RESET}" if is_dup and seen_calls[call_key] != step_n else ""
            print(f"{BOLD}Step {step_n:2d}{RESET} [{name}]{dup_tag}")

            # Print arguments
            if verbose or focus_step:
                print(f"       {DIM}{arg_full}{RESET}")
            else:
                print(f"       {DIM}{arg_short}{RESET}")

            # Print result
            if result:
                chars = result["chars"]
                size_tag = ""
                if chars > 10000:
                    size_tag = f" {RED}⚠ LARGE{RESET}"
                    large_results.append((step_n, name, chars))
                elif chars > 5000:
                    size_tag = f" {YELLOW}⚠{RESET}"
                    large_results.append((step_n, name, chars))

                if verbose or focus_step:
                    # Show full content
                    print(f"       → {chars:,} chars{size_tag}")
                    content = result["content"]
                    # Indent content for readability
                    for line in content.split("\n"):
                        print(f"       │ {line}")
                else:
                    print(f"       → {chars:,} chars{size_tag}")

                i += 2
                continue

        elif s["kind"] == "output":
            if not focus_step:
                print(f"\n{'─' * 60}")
                print(f"{BOLD}[Output]{RESET} ({len(s['text'])} chars)")
                if verbose:
                    print(s["text"])
                else:
                    print(s["text"][:500])
                    if len(s["text"]) > 500:
                        print("...")
                print(f"{'─' * 60}\n")

        elif s["kind"] == "error":
            if not focus_step:
                print(f"\n{RED}{'─' * 60}")
                print(f"[ABORTED] {s['error']}")
                print(f"{'─' * 60}{RESET}\n")

        i += 1

    if focus_step:
        return

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
    if label_changes:
        print(f"\n{BOLD}Label 变更审计{RESET}")
        for sn, cmd in label_changes:
            print(f"  Step {sn}: {cmd}")


def extract_issue_states_from_session(session_id: str) -> dict[int, dict]:
    """Parse gh issue list results from a session to get Issue states."""
    import re
    steps = parse_session_steps(session_id)
    issue_states: dict[int, dict] = {}

    for i, s in enumerate(steps):
        if s["kind"] != "result":
            continue
        content = s.get("content", "")
        # Try to parse JSON array from gh issue list results
        if not content.strip().startswith("["):
            continue
        try:
            issues = json.loads(content)
            if not isinstance(issues, list):
                continue
            for issue in issues:
                if not isinstance(issue, dict) or "number" not in issue:
                    continue
                num = issue["number"]
                labels = [l.get("name", "") if isinstance(l, dict) else str(l)
                          for l in issue.get("labels", [])]
                issue_states[num] = {
                    "title": issue.get("title", ""),
                    "labels": labels,
                    "label_str": "+".join(sorted(labels)),
                }
        except (json.JSONDecodeError, TypeError):
            continue

    # Also detect dispatches
    dispatched_issues: set[int] = set()
    for s in steps:
        if s["kind"] == "call" and s["name"] == "exec":
            cmd = s["args"].get("command", "")
            if "tmux_dispatch" in cmd or "send-keys" in cmd:
                for m in re.finditer(r'#(\d+)', cmd):
                    dispatched_issues.add(int(m.group(1)))

    for num in dispatched_issues:
        if num in issue_states:
            issue_states[num]["dispatched"] = True

    return issue_states


def print_progress(runs: list[dict]) -> None:
    """Cross-round progress analysis: detect stuck issues and repeated dispatches."""
    if len(runs) < 2:
        print(f"\n{YELLOW}需要至少 2 轮数据才能做跨轮推进分析{RESET}")
        return

    print(f"\n{BOLD}任务推进有效性（跨轮分析，最近 {len(runs)} 轮）{RESET}\n")

    # Collect Issue states per round from session data
    round_states: list[dict[int, dict]] = []  # [{issue_num: {labels, dispatched, ...}}]
    round_meta: list[dict] = []  # [{ts, session}]

    for run in runs:
        sid = run.get("sessionId")
        ts = fmt_ts(run.get("ts", 0))
        if not sid:
            round_states.append({})
            round_meta.append({"ts": ts, "session": "?"})
            continue
        states = extract_issue_states_from_session(sid)
        round_states.append(states)
        round_meta.append({"ts": ts, "session": sid[:8]})

    # Aggregate all Issues seen across rounds
    all_issues: set[int] = set()
    for states in round_states:
        all_issues.update(states.keys())

    if not all_issues:
        print(f"  {YELLOW}未从 session 中解析到 Issue 数据（可能 gh issue list 返回为空）{RESET}\n")
        return

    has_problems = False

    for num in sorted(all_issues):
        appearances = []
        for idx, states in enumerate(round_states):
            if num in states:
                appearances.append({
                    "round": idx + 1,
                    "ts": round_meta[idx]["ts"],
                    "labels": states[num].get("label_str", ""),
                    "dispatched": states[num].get("dispatched", False),
                    "title": states[num].get("title", ""),
                })

        if len(appearances) < 2:
            continue

        # Check if labels are the same across consecutive rounds (stuck)
        recent = appearances[-3:] if len(appearances) >= 3 else appearances
        label_sets = [a["labels"] for a in recent]
        all_same = len(set(label_sets)) == 1 and label_sets[0]

        # Check if dispatched multiple times
        dispatch_count = sum(1 for a in appearances if a["dispatched"])

        title = appearances[0].get("title", "")[:50]

        # Skip owner/shuzai issues (ball is in HUMAN's court)
        is_human_owned = "owner/shuzai" in label_sets[0] if label_sets else False

        if all_same and len(recent) >= 2 and not is_human_owned:
            has_problems = True
            print(f"  {RED}❌ Issue #{num}: {title}{RESET}")
            print(f"     状态: {label_sets[0]}")
            print(f"     连续 {len(recent)} 轮无变化 → P0 任务卡死")
            for a in recent:
                disp = " [已派发]" if a["dispatched"] else ""
                print(f"     {a['ts']}: {a['labels']}{disp}")
            if dispatch_count >= 2:
                print(f"     {RED}重复派发 {dispatch_count} 次 → P0 无效重复{RESET}")
            print()

        elif all_same and len(recent) >= 2 and is_human_owned:
            # Not a problem, just informational
            print(f"  {DIM}ℹ Issue #{num}: {title} — owner/shuzai 等待 HUMAN 操作（{len(recent)} 轮）{RESET}")

        elif dispatch_count >= 2:
            has_problems = True
            print(f"  {RED}❌ Issue #{num}: {title}{RESET}")
            print(f"     在 {dispatch_count} 轮中被重复派发 → P0 派发失效（worker 未产出）")
            for a in appearances:
                if a["dispatched"]:
                    print(f"     {a['ts']}: {a['labels']} [派发]")
            print()

    if not has_problems:
        print(f"  {GREEN}✅ 所有 Issue 状态正常推进{RESET}\n")


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
    parser.add_argument("--step", type=int, default=0, help="查看指定步骤的完整入参和返回内容")
    parser.add_argument("--verbose", action="store_true", help="显示所有步骤的完整入参和返回内容")
    parser.add_argument("--progress", action="store_true", help="跨轮任务推进有效性分析")
    parser.add_argument("--list-jobs", action="store_true", help="列出所有 cron jobs")
    args = parser.parse_args()

    if args.list_jobs:
        list_jobs()
        return

    if args.session:
        print(f"\n{BOLD}Session 步骤分析: {args.session}{RESET}\n")
        steps = parse_session_steps(args.session)
        if steps:
            print_steps(steps, verbose=args.verbose, focus_step=args.step)
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

    if args.progress and runs:
        print_progress(runs)

    if (args.steps or args.step or args.verbose) and runs:
        # Find latest run with session
        for run in reversed(runs):
            sid = run.get("sessionId")
            if sid:
                print(f"\n\n{BOLD}最近一次执行步骤 ({fmt_ts(run.get('ts', 0))}){RESET}\n")
                steps = parse_session_steps(sid)
                if steps:
                    print_steps(steps, verbose=args.verbose, focus_step=args.step)
                break


if __name__ == "__main__":
    main()
