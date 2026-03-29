#!/usr/bin/env python3
"""
分析 coding-team-loop 定时任务的最近一次执行流程。

用法：
  python3 parse-run.py              # 分析最近一次
  python3 parse-run.py --run 2      # 分析最近第 N 次（1=最新）
  python3 parse-run.py --raw        # 输出原始工具调用，不做摘要
"""

import json
import sys
from pathlib import Path

JOB_NAME = "clawcoach-progress-10m"
JOB_ID   = "31740710-1019-46cf-95bd-0c7dfc7899d4"   # 固定 ID，无需动态查询
SESSIONS_DIR = Path.home() / ".openclaw" / "agents" / "main" / "sessions"
CRON_RUNS_DIR = Path.home() / ".openclaw" / "cron" / "runs"


def get_job_id() -> tuple[str, str]:
    return JOB_ID, JOB_NAME


def get_session_id(job_id: str, run_index: int = 1) -> tuple[str, dict]:
    """Read cron run entries directly from the on-disk JSONL file.

    The file lives at ~/.openclaw/cron/runs/{jobId}.jsonl.
    Each line is a JSON object; we sort descending by 'ts' and pick
    the run at position run_index (1-based).

    sessionId is stored directly as the 'sessionId' field.
    sessionKey format: agent:main:cron:{jobId}:run:{sessionId}
    Both are supported for backward compatibility.
    """
    runs_file = CRON_RUNS_DIR / f"{job_id}.jsonl"
    if not runs_file.exists():
        print(f"[error] cron runs 文件不存在: {runs_file}", file=sys.stderr)
        sys.exit(1)

    runs: list[dict] = []
    with open(runs_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                runs.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    # Keep only finished runs with a sessionId, sorted newest-first
    finished = [r for r in runs if r.get("sessionId")]
    finished.sort(key=lambda r: r.get("ts", 0), reverse=True)

    if not finished:
        print("[error] 没有包含 sessionId 的执行记录", file=sys.stderr)
        sys.exit(1)

    if run_index > len(finished):
        print(
            f"[error] 只有 {len(finished)} 条有效记录，无法获取第 {run_index} 条",
            file=sys.stderr,
        )
        sys.exit(1)

    entry = finished[run_index - 1]

    # Prefer explicit sessionId field; fall back to parsing sessionKey
    session_id = entry.get("sessionId", "")
    if not session_id:
        session_key = entry.get("sessionKey", "")
        if ":run:" in session_key:
            session_id = session_key.split(":run:")[-1]

    if not session_id:
        print(
            f"[error] 无法从记录中解析 sessionId: {entry}",
            file=sys.stderr,
        )
        sys.exit(1)

    return session_id, entry


def parse_session(session_id: str) -> list[dict]:
    path = SESSIONS_DIR / f"{session_id}.jsonl"
    if not path.exists():
        print(f"[error] session 文件不存在: {path}", file=sys.stderr)
        sys.exit(1)
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


def extract_steps(entries: list[dict]) -> list[dict]:
    steps = []
    for entry in entries:
        if entry.get("type") != "message":
            continue
        msg = entry.get("message", {})
        parts = msg.get("content", [])
        if not isinstance(parts, list):
            continue
        for p in parts:
            if not isinstance(p, dict):
                continue
            pt = p.get("type", "")
            if pt in ("tool_use", "toolCall"):
                args = p.get("arguments", p.get("input", {}))
                steps.append({"kind": "call", "name": p.get("name", ""), "args": args})
            elif pt == "tool_result":
                c = p.get("content", "")
                if isinstance(c, list):
                    c = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
                steps.append({"kind": "result", "content": str(c).strip()})
            elif pt == "text" and msg.get("role") == "assistant":
                txt = p.get("text", "").strip()
                if txt:
                    steps.append({"kind": "output", "text": txt})
    return steps


def fmt_args(args: dict) -> str:
    if "command" in args:
        return args["command"].replace("\n", "↵")[:120]
    if "query" in args:
        return f'query: {args["query"][:80]}'
    if "path" in args:
        return f'path: {args["path"]}'
    if "prompt" in args:
        return f'prompt: {args["prompt"][:80]}'
    return str(args)[:80]


def print_steps(steps: list[dict], raw: bool = False):
    step_n = 0
    i = 0
    while i < len(steps):
        s = steps[i]
        if s["kind"] == "call":
            step_n += 1
            print(f"STEP {step_n:02d} [{s['name']}] {fmt_args(s['args'])}")
            if i + 1 < len(steps) and steps[i + 1]["kind"] == "result":
                result_text = steps[i + 1]["content"]
                limit = 300 if raw else 150
                print(f"         => {result_text[:limit]}")
                print()
                i += 2
                continue
        elif s["kind"] == "output":
            print(f"\n{'='*60}")
            print("[最终输出]")
            print(s["text"])
            print(f"{'='*60}\n")
        i += 1


def main():
    raw = "--raw" in sys.argv
    run_index = 1
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--run" and i < len(sys.argv) - 1:
            run_index = int(sys.argv[i + 1])

    print(f"[1/3] 查询定时任务 '{JOB_NAME}'...")
    job_id, job_name = get_job_id()
    print(f"      jobId: {job_id}\n")

    print(f"[2/3] 获取第 {run_index} 次执行记录...")
    session_id, run_entry = get_session_id(job_id, run_index)
    import datetime
    ts = datetime.datetime.fromtimestamp(run_entry["ts"] / 1000).strftime("%Y-%m-%d %H:%M:%S")
    print(f"      时间:      {ts}")
    print(f"      状态:      {run_entry.get('status')}")
    print(f"      耗时:      {run_entry.get('durationMs', 0) / 1000:.1f}s")
    print(f"      delivery:  {run_entry.get('deliveryStatus')}")
    if run_entry.get("error"):
        print(f"      错误:      {run_entry['error']}")
    print(f"      sessionId: {session_id}\n")

    print(f"[3/3] 解析执行详情...\n")
    entries = parse_session(session_id)
    steps = extract_steps(entries)
    print_steps(steps, raw=raw)


if __name__ == "__main__":
    main()
