#!/usr/bin/env python3
"""
validator skill 执行日志分析工具

用法：
  python3 analyze_runs.py --last 10                                   # 最近 10 次概览
  python3 analyze_runs.py --last 5 --steps                            # 概览 + 最近一次步骤
  python3 analyze_runs.py --session {id} --steps                      # 步骤概览
  python3 analyze_runs.py --session {id} --verbose                    # 全部步骤完整入参+返回
  python3 analyze_runs.py --session {id} --step 28                    # 只看第 28 步完整详情
  python3 analyze_runs.py --session {id} --quality                    # 验收质量分析
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

CRON_DIR = Path.home() / ".openclaw" / "cron"
JOBS_FILE = CRON_DIR / "jobs.json"
RUNS_DIR = CRON_DIR / "runs"
SESSIONS_DIR = Path.home() / ".openclaw" / "agents" / "main" / "sessions"

VALIDATOR_JOB_ID = "905d36b2-7b50-423f-84d8-571a030bd5e5"

TZ_CST = timezone(timedelta(hours=8))

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# ── Validator-specific keywords ───────────────────────────────────────────────
VISUAL_KEYWORDS = [
    "布局", "间距", "对齐", "溢出", "截断", "空白", "比例", "变形",
    "色彩", "字号", "字体", "padding", "margin", "overflow", "alignment",
    "spacing", "layout", "truncat", "overlap", "deform", "proportion",
    "visual", "视觉", "首印象", "水平滚动",
]

JOURNEY_KEYWORDS = [
    "旅程", "journey", "用户旅程", "入口", "终态", "操作流程",
    "Phase B", "phase b", "阶段B", "阶段 B",
]

SCREENSHOT_ANALYSIS_KEYWORDS = [
    "看到", "显示", "布局", "间距", "对齐", "区块", "页面呈现", "截图分析",
    "截图显示", "观察到", "注意到", "发现", "可以看到", "图中", "截图中",
    "视觉", "外观", "样式", "排列", "位置", "大小", "颜色", "空白",
    "可见", "可读", "可访问", "不可点击", "不可用", "证据", "截图",
    "横向滚动", "溢出", "截断", "变形", "首印象",
]

PLAYWRIGHT_TOOLS = {
    "navigate": "mcp__plugin_playwright_playwright__browser_navigate",
    "screenshot": "mcp__plugin_playwright_playwright__browser_take_screenshot",
    "snapshot": "mcp__plugin_playwright_playwright__browser_snapshot",
    "click": "mcp__plugin_playwright_playwright__browser_click",
    "fill": "mcp__plugin_playwright_playwright__browser_fill_form",
    "select": "mcp__plugin_playwright_playwright__browser_select_option",
    "console": "mcp__plugin_playwright_playwright__browser_console_messages",
    "resize": "mcp__plugin_playwright_playwright__browser_resize",
    "hover": "mcp__plugin_playwright_playwright__browser_hover",
    "wait": "mcp__plugin_playwright_playwright__browser_wait_for",
}

# Reverse lookup: full name -> short name
PLAYWRIGHT_REVERSE = {v: k for k, v in PLAYWRIGHT_TOOLS.items()}


def load_jobs() -> list[dict]:
    if not JOBS_FILE.exists():
        print(f"{RED}jobs.json not found: {JOBS_FILE}{RESET}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(JOBS_FILE.read_text())
    return data.get("jobs", [])


def find_validator_job() -> dict:
    for job in load_jobs():
        if job.get("id") == VALIDATOR_JOB_ID:
            return job
    print(f"{RED}Validator job not found (ID: {VALIDATOR_JOB_ID}){RESET}", file=sys.stderr)
    print("Available jobs:")
    for job in load_jobs():
        print(f"  - {job.get('name')} ({job.get('id', '?')[:8]})")
    sys.exit(1)


def load_runs(last_n: int = 20) -> list[dict]:
    runs_file = RUNS_DIR / f"{VALIDATOR_JOB_ID}.jsonl"
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


def print_overview(runs: list[dict], timeout_sec: int) -> None:
    if not runs:
        print("No runs found.")
        return

    print(f"\n{BOLD}{'Time':>11} {'Status':>7} {'Duration':>9} {'In Tokens':>10} {'Out Tokens':>11} {'Error'}{RESET}")
    print("\u2500" * 75)

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

    print("\u2500" * 75)
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
            print(f"\n  {YELLOW}\u26a0 趋势恶化: 后半段平均 {avg_second:.0f}s vs 前半段 {avg_first:.0f}s (+{(avg_second/avg_first-1)*100:.0f}%){RESET}")

    # Token anomalies
    if input_tokens_list and len(input_tokens_list) >= 3:
        median_tok = sorted(input_tokens_list)[len(input_tokens_list) // 2]
        anomalies = [(i, t) for i, t in enumerate(input_tokens_list) if t > median_tok * 2]
        if anomalies:
            print(f"\n  {YELLOW}\u26a0 Token 异常 (>2x 中位数 {median_tok:,}):{RESET}")
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


def print_steps(steps: list[dict], verbose: bool = False, focus_step: int = 0) -> None:
    step_n = 0
    seen_calls: dict[str, int] = {}
    duplicates = []
    large_results = []

    i = 0
    while i < len(steps):
        s = steps[i]
        if s["kind"] == "call":
            step_n += 1
            name = s["name"]
            args = s["args"]

            # Short name for Playwright tools
            short_name = PLAYWRIGHT_REVERSE.get(name, "")
            display_name = f"{name} ({short_name})" if short_name else name

            # Full argument string
            if name in ("exec", "Bash"):
                arg_full = args.get("command", "")
            elif name in ("read", "Read"):
                arg_full = args.get("file_path", args.get("path", str(args)))
            else:
                arg_full = json.dumps(args, ensure_ascii=False, indent=2)
            arg_short = arg_full[:200]

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
            dup_tag = f" {YELLOW}[DUP]{RESET}" if is_dup and seen_calls.get(call_key) != step_n else ""

            # Tag Playwright tools
            pw_tag = ""
            if short_name:
                pw_tag = f" {CYAN}[PW:{short_name}]{RESET}"

            print(f"{BOLD}Step {step_n:3d}{RESET} [{display_name}]{pw_tag}{dup_tag}")

            if verbose or focus_step:
                print(f"        {DIM}{arg_full}{RESET}")
            else:
                print(f"        {DIM}{arg_short}{RESET}")

            if result:
                chars = result["chars"]
                size_tag = ""
                if chars > 10000:
                    size_tag = f" {RED}\u26a0 LARGE{RESET}"
                    large_results.append((step_n, name, chars))
                elif chars > 5000:
                    size_tag = f" {YELLOW}\u26a0{RESET}"
                    large_results.append((step_n, name, chars))

                if verbose or focus_step:
                    print(f"        \u2192 {chars:,} chars{size_tag}")
                    content = result["content"]
                    for line in content.split("\n"):
                        print(f"        \u2502 {line}")
                else:
                    print(f"        \u2192 {chars:,} chars{size_tag}")

                i += 2
                continue

        elif s["kind"] == "output":
            if not focus_step:
                sep = "\u2500" * 60
                print(f"\n{sep}")
                print(f"{BOLD}[Output]{RESET} ({len(s['text'])} chars)")
                if verbose:
                    print(s["text"])
                else:
                    print(s["text"][:500])
                    if len(s["text"]) > 500:
                        print("...")
                print(f"{sep}\n")

        elif s["kind"] == "error":
            if not focus_step:
                sep = "\u2500" * 60
                print(f"\n{RED}{sep}")
                print(f"[ABORTED] {s['error']}")
                print(f"{sep}{RESET}\n")

        i += 1

    if focus_step:
        return

    # Summary
    print(f"\n{BOLD}步骤统计{RESET}")
    print(f"  总步骤: {step_n}")
    if duplicates:
        print(f"  {YELLOW}重复调用 ({len(duplicates)}):{RESET}")
        for sn, name, arg in duplicates:
            short = PLAYWRIGHT_REVERSE.get(name, "")
            tag = f" [PW:{short}]" if short else ""
            print(f"    Step {sn}: [{name}{tag}] {arg}")
    if large_results:
        print(f"  {YELLOW}大数据返回 ({len(large_results)}):{RESET}")
        for sn, name, chars in large_results:
            print(f"    Step {sn}: [{name}] {chars:,} chars")


def analyze_quality(steps: list[dict]) -> None:
    """Analyze validator execution quality from session steps."""
    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}验收质量分析{RESET}")
    print(f"{'=' * 60}\n")

    # Collect Playwright calls and assistant outputs
    pw_calls: list[dict] = []          # {step, tool, args}
    screenshots: list[int] = []         # step numbers of screenshots
    assistant_texts: list[dict] = []    # {step, text} - after-step outputs
    all_texts: list[str] = []           # all assistant text for keyword search
    issue_comments: list[dict] = []     # gh issue comment calls

    step_n = 0
    i = 0
    last_screenshot_step = -1

    while i < len(steps):
        s = steps[i]
        if s["kind"] == "call":
            step_n += 1
            name = s["name"]
            args = s["args"]

            # Detect browser tool calls (two formats):
            # 1. Playwright MCP: name="mcp__plugin_playwright_*"
            # 2. openclaw browser: name="browser", action in args
            short = PLAYWRIGHT_REVERSE.get(name, "")
            if not short and name == "browser":
                action = args.get("action", "")
                kind = args.get("kind", "")
                # Map openclaw browser actions to short names
                action_map = {
                    "open": "navigate", "navigate": "navigate",
                    "screenshot": "screenshot", "snapshot": "snapshot",
                    "click": "click", "type": "fill", "select": "select",
                    "console": "console", "resize": "resize",
                    "hover": "hover",
                }
                if action == "act" and kind:
                    # act with kind: use kind as the action
                    kind_map = {
                        "resize": "resize", "click": "click",
                        "type": "fill", "select": "select",
                        "hover": "hover",
                    }
                    short = kind_map.get(kind, kind)
                else:
                    short = action_map.get(action, action)

            if short:
                pw_calls.append({"step": step_n, "tool": short, "args": args})
                if short == "screenshot":
                    screenshots.append(step_n)
                    last_screenshot_step = step_n

            # Detect gh issue comment
            if name in ("exec", "Bash"):
                cmd = args.get("command", "")
                if "gh issue comment" in cmd:
                    issue_comments.append({"step": step_n, "cmd": cmd})

        elif s["kind"] == "output":
            assistant_texts.append({"step": step_n, "text": s["text"]})
            all_texts.append(s["text"])

        elif s["kind"] == "result":
            # Also search tool results for content (e.g. gh issue comment body)
            content = s.get("content", "")
            if len(content) > 100:
                all_texts.append(content)

        i += 1

    full_text = "\n".join(all_texts)

    # ── 1. Three-phase audit ──────────────────────────────────────────────
    print(f"{BOLD}1. 三阶段执行审计{RESET}\n")

    has_navigate = any(c["tool"] == "navigate" for c in pw_calls)
    has_screenshot = len(screenshots) > 0
    has_click = any(c["tool"] == "click" for c in pw_calls)
    has_resize = any(c["tool"] == "resize" for c in pw_calls)
    has_console = any(c["tool"] == "console" for c in pw_calls)
    has_snapshot = any(c["tool"] == "snapshot" for c in pw_calls)

    # Detect phases by looking at call sequences
    # Phase A: navigate + screenshot without clicks between them
    # Phase B: screenshot + click + screenshot patterns
    # Phase C: targeted clicks on specific elements

    phase_a_detected = False
    phase_b_detected = False
    phase_c_detected = False

    # Search in text for explicit phase mentions
    for text in all_texts:
        text_lower = text.lower()
        if "phase a" in text_lower or "阶段a" in text_lower or "阶段 a" in text_lower or "视觉扫描" in text:
            phase_a_detected = True
        if "phase b" in text_lower or "阶段b" in text_lower or "阶段 b" in text_lower or "用户旅程" in text:
            phase_b_detected = True
        if "phase c" in text_lower or "阶段c" in text_lower or "阶段 c" in text_lower or "系统性" in text:
            phase_c_detected = True

    phase_status = []
    if phase_a_detected:
        phase_status.append(f"  {GREEN}\u2713{RESET} Phase A (视觉扫描)")
    else:
        phase_status.append(f"  {RED}\u2717{RESET} Phase A (视觉扫描) — {RED}未检测到{RESET}")

    if phase_b_detected:
        phase_status.append(f"  {GREEN}\u2713{RESET} Phase B (用户旅程)")
    else:
        phase_status.append(f"  {RED}\u2717{RESET} Phase B (用户旅程) — {RED}未检测到{RESET}")

    if phase_c_detected:
        phase_status.append(f"  {GREEN}\u2713{RESET} Phase C (系统性测试)")
    else:
        phase_status.append(f"  {RED}\u2717{RESET} Phase C (系统性测试) — {RED}未检测到{RESET}")

    for line in phase_status:
        print(line)

    phases_complete = sum([phase_a_detected, phase_b_detected, phase_c_detected])
    if phases_complete < 3:
        print(f"\n  {RED}P0: 缺失 {3 - phases_complete} 个阶段{RESET}")
    print()

    # ── 2. Screenshot analysis quality ────────────────────────────────────
    print(f"{BOLD}2. 截图分析质量{RESET}\n")

    total_screenshots = len(screenshots)
    analyzed_screenshots = 0

    # Also extract analysis text from gh issue comment bodies (in exec args)
    issue_comment_body = ""
    for s in steps:
        if s["kind"] == "call" and s["name"] in ("exec", "Bash"):
            cmd = s["args"].get("command", "")
            if "gh issue comment" in cmd:
                all_texts.append(cmd)
                issue_comment_body += cmd + "\n"

    # Combine all analysis sources for screenshot analysis detection
    # In openclaw mode, agent often emits all tool calls first, then one text block
    all_analysis_texts = list(assistant_texts)
    if issue_comment_body:
        all_analysis_texts.append({"step": 999999, "text": issue_comment_body})

    # For each screenshot, check if there's analysis text in subsequent outputs
    per_screenshot_matched = 0
    for idx, ss_step in enumerate(screenshots):
        next_ss_step = screenshots[idx + 1] if idx + 1 < len(screenshots) else 999999
        has_analysis = False
        for at in all_analysis_texts:
            if at["step"] >= ss_step and at["step"] < next_ss_step:
                text_lower = at["text"].lower()
                if any(kw in text_lower for kw in SCREENSHOT_ANALYSIS_KEYWORDS):
                    has_analysis = True
                    break
        if has_analysis:
            per_screenshot_matched += 1

    # In openclaw mode, analysis is often consolidated in a single block at the end
    # (issue comment or final output). If per-screenshot matching is low but there's
    # substantial consolidated analysis, credit screenshots proportionally.
    consolidated_kw_hits = 0
    if issue_comment_body:
        body_lower = issue_comment_body.lower()
        consolidated_kw_hits = sum(1 for kw in SCREENSHOT_ANALYSIS_KEYWORDS if kw in body_lower)
    for at in assistant_texts:
        text_lower = at["text"].lower()
        consolidated_kw_hits += sum(1 for kw in SCREENSHOT_ANALYSIS_KEYWORDS if kw in text_lower)

    if per_screenshot_matched < total_screenshots and consolidated_kw_hits >= 3:
        # Consolidated analysis exists — estimate coverage from keyword diversity
        # and analysis depth (comment length indicates thoroughness)
        kw_credit = consolidated_kw_hits  # each keyword hit ≈ 1 screenshot covered
        # Detailed comments (>500 chars) with structure indicate thorough analysis
        length_credit = len(issue_comment_body) // 400 if len(issue_comment_body) > 500 else 0
        consolidated_credit = min(total_screenshots, max(kw_credit, length_credit))
        analyzed_screenshots = max(per_screenshot_matched, consolidated_credit)
    else:
        analyzed_screenshots = per_screenshot_matched

    analysis_rate = (analyzed_screenshots / total_screenshots * 100) if total_screenshots > 0 else 0

    print(f"  总截图数:     {total_screenshots}")
    print(f"  有效分析数:   {analyzed_screenshots}")

    if total_screenshots > 0:
        rate_color = GREEN if analysis_rate >= 80 else (YELLOW if analysis_rate >= 50 else RED)
        print(f"  截图分析率:   {rate_color}{analysis_rate:.0f}%{RESET}")
    else:
        print(f"  {RED}截图分析率:   N/A (无截图！){RESET}")

    if total_screenshots < 5:
        print(f"\n  {RED}P0: 截图数过少 ({total_screenshots})，可能跳过了视觉验收{RESET}")
    if analysis_rate < 80 and total_screenshots > 0:
        print(f"\n  {RED}P0: 截图分析率 < 80%，存在形式主义验收{RESET}")
    print()

    # ── 3. User journey coverage ──────────────────────────────────────────
    print(f"{BOLD}3. 用户旅程覆盖{RESET}\n")

    journey_defined = any(
        any(kw in text for kw in ["用户旅程", "旅程 1", "旅程1", "Journey", "journey"])
        for text in all_texts
    )
    journey_executed = any(
        any(kw in text for kw in ["旅程 1", "旅程1", "走通", "旅程步骤", "journey step"])
        for text in all_texts
    )

    if journey_defined:
        print(f"  {GREEN}\u2713{RESET} 用户旅程已定义")
    else:
        print(f"  {RED}\u2717{RESET} 用户旅程未定义 — {RED}P0{RESET}")

    if journey_executed:
        print(f"  {GREEN}\u2713{RESET} 用户旅程已执行")
    elif journey_defined:
        print(f"  {RED}\u2717{RESET} 用户旅程已定义但未执行 — {RED}P0{RESET}")
    else:
        print(f"  {RED}\u2717{RESET} 用户旅程未执行 — {RED}P0{RESET}")
    print()

    # ── 4. Visual detection capability ────────────────────────────────────
    print(f"{BOLD}4. 视觉检测能力{RESET}\n")

    visual_mentions = 0
    visual_found_keywords: set[str] = set()
    for text in all_texts:
        for kw in VISUAL_KEYWORDS:
            if kw in text.lower():
                visual_mentions += 1
                visual_found_keywords.add(kw)

    print(f"  视觉关键词命中数: {visual_mentions}")
    print(f"  涉及维度: {', '.join(sorted(visual_found_keywords)) if visual_found_keywords else '无'}")

    # Check if visual issues were actually reported (FAIL/WARN related to visual)
    visual_issues = 0
    for text in all_texts:
        if ("FAIL" in text or "WARN" in text) and any(kw in text for kw in VISUAL_KEYWORDS):
            visual_issues += 1

    print(f"  视觉相关问题报告数: {visual_issues}")

    if visual_mentions == 0:
        print(f"\n  {YELLOW}P1: 0 个视觉相关分析，可能存在视觉盲区{RESET}")
    print()

    # ── 5. Strictness assessment ──────────────────────────────────────────
    print(f"{BOLD}5. 严格性评估{RESET}\n")

    pass_count = full_text.count("PASS")
    fail_count = full_text.count("FAIL")
    warn_count = full_text.count("WARN")

    verdict_pass = "验收通过" in full_text
    verdict_fail = "验收不通过" in full_text

    print(f"  PASS: {pass_count}  FAIL: {fail_count}  WARN: {warn_count}")
    if verdict_pass:
        print(f"  最终结论: {GREEN}验收通过{RESET}")
    elif verdict_fail:
        print(f"  最终结论: {RED}验收不通过{RESET}")
    else:
        print(f"  最终结论: {YELLOW}未检测到明确结论{RESET}")

    if fail_count == 0 and warn_count == 0 and pass_count > 0:
        print(f"\n  {YELLOW}\u26a0 全部 PASS 0 问题 — 可能验收走过场，建议人工抽检{RESET}")
    print()

    # ── 6. Playwright operation compliance ────────────────────────────────
    print(f"{BOLD}6. Playwright 操作规范{RESET}\n")

    checks = [
        ("设置视口 1280\u00d7800", has_resize),
        ("检查 console errors", has_console),
        ("使用截图 (screenshot)", has_screenshot),
        ("使用页面导航 (navigate)", has_navigate),
    ]

    for label, passed in checks:
        icon = f"{GREEN}\u2713{RESET}" if passed else f"{RED}\u2717{RESET}"
        print(f"  {icon} {label}")

    # Check snapshot-without-screenshot anti-pattern
    snapshot_only = has_snapshot and not has_screenshot
    if snapshot_only:
        print(f"\n  {RED}P1: 使用了 snapshot 但没有 screenshot — 只看 DOM 不看视觉{RESET}")

    # Check click-without-screenshot (before/after)
    click_steps = [c["step"] for c in pw_calls if c["tool"] == "click"]
    clicks_without_before = 0
    clicks_without_after = 0
    for cs in click_steps:
        has_before = any(ss < cs and cs - ss <= 3 for ss in screenshots)
        has_after = any(ss > cs and ss - cs <= 3 for ss in screenshots)
        if not has_before:
            clicks_without_before += 1
        if not has_after:
            clicks_without_after += 1

    if click_steps:
        print(f"\n  点击操作: {len(click_steps)} 次")
        if clicks_without_before > 0:
            print(f"  {YELLOW}\u26a0 {clicks_without_before} 次点击前无截图{RESET}")
        if clicks_without_after > 0:
            print(f"  {YELLOW}\u26a0 {clicks_without_after} 次点击后无截图{RESET}")
    print()

    # ── 7. Playwright tool usage summary ──────────────────────────────────
    print(f"{BOLD}7. Playwright 工具使用统计{RESET}\n")

    pw_counts: dict[str, int] = {}
    for c in pw_calls:
        pw_counts[c["tool"]] = pw_counts.get(c["tool"], 0) + 1

    for tool, count in sorted(pw_counts.items(), key=lambda x: -x[1]):
        print(f"  {tool:>12}: {count}")

    total_pw = sum(pw_counts.values())
    print(f"  {'TOTAL':>12}: {total_pw}")
    print()

    # ── 8. Issue feedback quality ─────────────────────────────────────────
    print(f"{BOLD}8. Issue 反馈质量{RESET}\n")

    if issue_comments:
        print(f"  评论次数: {len(issue_comments)}")
        for ic in issue_comments:
            cmd = ic["cmd"]
            # Extract body length estimate
            body_match = re.search(r"--body\s+['\"](.+?)['\"]", cmd, re.DOTALL)
            if body_match:
                body_len = len(body_match.group(1))
                print(f"  Step {ic['step']}: ~{body_len} chars")
            else:
                print(f"  Step {ic['step']}: (body length unknown)")
    else:
        print(f"  {YELLOW}\u26a0 未检测到 Issue 评论 — 验收结果可能未反馈{RESET}")
    print()

    # ── Overall grade ─────────────────────────────────────────────────────
    print(f"{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}综合评级{RESET}\n")

    score = 100
    deductions = []

    if phases_complete < 3:
        d = (3 - phases_complete) * 20
        score -= d
        deductions.append(f"-{d}: 缺失 {3 - phases_complete} 个阶段")

    if total_screenshots < 5:
        score -= 20
        deductions.append(f"-20: 截图数不足 ({total_screenshots})")

    if analysis_rate < 80 and total_screenshots > 0:
        d = int((80 - analysis_rate) * 0.3)
        score -= d
        deductions.append(f"-{d}: 截图分析率 {analysis_rate:.0f}%")

    if not journey_defined:
        score -= 15
        deductions.append("-15: 未定义用户旅程")
    elif not journey_executed:
        score -= 15
        deductions.append("-15: 定义了旅程但未执行")

    if visual_mentions == 0:
        score -= 10
        deductions.append("-10: 无视觉分析")

    if not has_resize:
        score -= 5
        deductions.append("-5: 未设置视口")

    if not has_console:
        score -= 5
        deductions.append("-5: 未检查 console errors")

    if snapshot_only:
        score -= 10
        deductions.append("-10: 只用 snapshot 不用 screenshot")

    score = max(0, score)

    if score >= 90:
        grade = f"{GREEN}A{RESET}"
    elif score >= 75:
        grade = f"{GREEN}B{RESET}"
    elif score >= 60:
        grade = f"{YELLOW}C{RESET}"
    elif score >= 40:
        grade = f"{YELLOW}D{RESET}"
    else:
        grade = f"{RED}F{RESET}"

    print(f"  评级: {grade} ({score}/100)")
    if deductions:
        print(f"  扣分项:")
        for d in deductions:
            print(f"    {d}")

    print(f"\n{BOLD}{'=' * 60}{RESET}")


def main() -> None:
    parser = argparse.ArgumentParser(description="validator skill 执行日志分析")
    parser.add_argument("--last", type=int, default=10, help="分析最近 N 次执行 (default: 10)")
    parser.add_argument("--session", help="分析指定 session 的执行步骤")
    parser.add_argument("--steps", action="store_true", help="输出执行步骤详情")
    parser.add_argument("--step", type=int, default=0, help="查看指定步骤的完整入参和返回内容")
    parser.add_argument("--verbose", action="store_true", help="显示所有步骤的完整入参和返回内容")
    parser.add_argument("--quality", action="store_true", help="验收质量分析")
    args = parser.parse_args()

    if args.session:
        print(f"\n{BOLD}Session 步骤分析: {args.session}{RESET}\n")
        steps = parse_session_steps(args.session)
        if steps:
            if args.quality:
                analyze_quality(steps)
            else:
                print_steps(steps, verbose=args.verbose, focus_step=args.step)
        return

    job = find_validator_job()
    timeout = job.get("payload", {}).get("timeoutSeconds", 900)

    print(f"\n{BOLD}Validator Job{RESET}")
    print(f"  Name:    {job.get('name', '?')}")
    print(f"  ID:      {VALIDATOR_JOB_ID[:8]}...")
    print(f"  Enabled: {job.get('enabled')}")
    print(f"  Timeout: {timeout}s")

    runs = load_runs(args.last)
    print_overview(runs, timeout)

    if args.quality and runs:
        # Run quality analysis on latest session
        for run in reversed(runs):
            sid = run.get("sessionId")
            if sid:
                print(f"\n\n{BOLD}最近一次执行质量分析 ({fmt_ts(run.get('ts', 0))}){RESET}")
                steps = parse_session_steps(sid)
                if steps:
                    analyze_quality(steps)
                break
    elif (args.steps or args.step or args.verbose) and runs:
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
