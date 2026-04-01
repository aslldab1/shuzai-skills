#!/usr/bin/env python3
"""
Claude Code 使用数据收集器

从 ~/.claude/ 读取历史数据，输出结构化 JSON 摘要。
支持指定时间范围（默认过去 7 天）。

用法：
  python3 collect_usage_data.py                    # 过去 7 天
  python3 collect_usage_data.py --days 30          # 过去 30 天
  python3 collect_usage_data.py --since 2026-03-01 # 指定起始日期
  python3 collect_usage_data.py --output report.json
"""

import argparse
import glob
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional, List, Dict


CLAUDE_DIR = Path.home() / ".claude"


def parse_timestamp(ts: Any) -> Optional[datetime]:
    """Parse timestamp from various formats."""
    if isinstance(ts, (int, float)):
        # Unix milliseconds
        if ts > 1e12:
            ts = ts / 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(ts, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f%z"):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                continue
    return None


def load_jsonl(path: Path, since: datetime) -> List[dict]:
    """Load JSONL file, filtering by timestamp."""
    if not path.exists():
        return []
    results = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = parse_timestamp(entry.get("timestamp"))
            if ts and ts >= since:
                entry["_parsed_ts"] = ts.isoformat()
                results.append(entry)
    return results


def collect_history(since: datetime) -> dict:
    """Collect command history stats."""
    entries = load_jsonl(CLAUDE_DIR / "history.jsonl", since)

    sessions: Dict[str, list] = defaultdict(list)
    projects: Counter = Counter()
    commands: List[str] = []
    daily_activity: Counter = Counter()

    for e in entries:
        sid = e.get("sessionId", "unknown")
        sessions[sid].append(e)
        proj = e.get("project", "unknown")
        projects[os.path.basename(proj)] += 1
        commands.append(e.get("display", ""))
        ts = parse_timestamp(e.get("timestamp"))
        if ts:
            daily_activity[ts.strftime("%Y-%m-%d")] += 1

    # Classify commands
    slash_commands: Counter = Counter()
    for cmd in commands:
        if cmd.startswith("/"):
            slash_commands[cmd.split()[0]] += 1

    # Session duration estimation
    session_durations: List[float] = []
    for sid, events in sessions.items():
        timestamps = []
        for ev in events:
            ts = parse_timestamp(ev.get("timestamp"))
            if ts:
                timestamps.append(ts)
        if len(timestamps) >= 2:
            duration = (max(timestamps) - min(timestamps)).total_seconds() / 60
            session_durations.append(duration)

    return {
        "total_inputs": len(entries),
        "unique_sessions": len(sessions),
        "unique_projects": len(set(projects.keys())),
        "top_projects": projects.most_common(10),
        "daily_activity": sorted(daily_activity.items()),
        "slash_commands": slash_commands.most_common(20),
        "avg_session_duration_min": round(sum(session_durations) / max(len(session_durations), 1), 1),
        "max_session_duration_min": round(max(session_durations, default=0), 1),
        "avg_inputs_per_session": round(len(entries) / max(len(sessions), 1), 1),
    }


def collect_tool_usage(since: datetime) -> dict:
    """Collect tool usage from homunculus observations."""
    pattern = str(CLAUDE_DIR / "homunculus" / "projects" / "*" / "observations.jsonl")
    tool_counts: Counter = Counter()
    tool_by_project: Dict[str, Counter] = defaultdict(Counter)
    tool_by_day: Dict[str, Counter] = defaultdict(Counter)
    total = 0

    for f in glob.glob(pattern):
        entries = load_jsonl(Path(f), since)
        for e in entries:
            if e.get("event") != "tool_complete":
                continue
            tool = e.get("tool", "unknown")
            project = e.get("project_name", "unknown")
            tool_counts[tool] += 1
            tool_by_project[project][tool] += 1
            total += 1
            ts = parse_timestamp(e.get("timestamp"))
            if ts:
                tool_by_day[ts.strftime("%Y-%m-%d")][tool] += 1

    # Calculate ratios
    bash_count = tool_counts.get("Bash", 0)
    dedicated_tools = sum(tool_counts.get(t, 0) for t in ["Read", "Write", "Edit", "Glob", "Grep"])
    agent_count = tool_counts.get("Agent", 0)

    return {
        "total_tool_calls": total,
        "tool_distribution": tool_counts.most_common(20),
        "tool_by_project": {
            proj: counter.most_common(5)
            for proj, counter in sorted(tool_by_project.items(), key=lambda x: -sum(x[1].values()))[:5]
        },
        "tool_by_day": {day: dict(counter.most_common(5)) for day, counter in sorted(tool_by_day.items())},
        "bash_ratio": round(bash_count / max(total, 1) * 100, 1),
        "dedicated_tool_ratio": round(dedicated_tools / max(total, 1) * 100, 1),
        "agent_ratio": round(agent_count / max(total, 1) * 100, 1),
    }


def collect_costs(since: datetime) -> dict:
    """Collect API cost data."""
    entries = load_jsonl(CLAUDE_DIR / "metrics" / "costs.jsonl", since)
    total_input = 0
    total_output = 0
    total_cost = 0.0
    model_usage: Counter = Counter()
    daily_cost: Dict[str, float] = defaultdict(float)

    for e in entries:
        inp = e.get("input_tokens", 0)
        out = e.get("output_tokens", 0)
        cost = e.get("estimated_cost_usd", 0)
        model = e.get("model", "unknown")
        total_input += inp
        total_output += out
        total_cost += cost
        if inp > 0 or out > 0:
            model_usage[model] += 1
        ts = parse_timestamp(e.get("timestamp"))
        if ts:
            daily_cost[ts.strftime("%Y-%m-%d")] += cost

    return {
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cost_usd": round(total_cost, 4),
        "model_usage": model_usage.most_common(),
        "daily_cost": sorted(daily_cost.items()),
    }


def collect_compactions(since: datetime) -> dict:
    """Collect context compaction events."""
    log_path = CLAUDE_DIR / "sessions" / "compaction-log.txt"
    if not log_path.exists():
        return {"total_compactions": 0, "daily_compactions": []}

    count = 0
    daily: Counter = Counter()
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            # Format: [2026-03-19 18:21:53] Context compaction triggered
            if "compaction" not in line.lower():
                continue
            try:
                ts_str = line.split("]")[0].strip("[")
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                if ts >= since:
                    count += 1
                    daily[ts.strftime("%Y-%m-%d")] += 1
            except (ValueError, IndexError):
                continue

    return {
        "total_compactions": count,
        "daily_compactions": sorted(daily.items()),
    }


def collect_projects() -> List[dict]:
    """Collect project metadata."""
    proj_file = CLAUDE_DIR / "homunculus" / "projects.json"
    if not proj_file.exists():
        return []

    with open(proj_file, encoding="utf-8") as f:
        data = json.load(f)

    projects = []
    if isinstance(data, dict):
        for pid, info in data.items():
            if isinstance(info, dict):
                projects.append({
                    "name": info.get("name", "unknown"),
                    "root": info.get("root", ""),
                    "created_at": info.get("created_at", ""),
                    "last_seen": info.get("last_seen", ""),
                })
    elif isinstance(data, list):
        for info in data:
            if isinstance(info, dict):
                projects.append({
                    "name": info.get("name", "unknown"),
                    "root": info.get("root", ""),
                    "created_at": info.get("created_at", ""),
                    "last_seen": info.get("last_seen", ""),
                })

    return sorted(projects, key=lambda p: p.get("last_seen", ""), reverse=True)


def collect_session_files(since: datetime) -> dict:
    """Collect session metadata from .tmp files."""
    session_dir = CLAUDE_DIR / "sessions"
    tmp_files = list(session_dir.glob("*.tmp"))
    active_sessions = list(session_dir.glob("*.json"))

    return {
        "recent_session_summaries": len(tmp_files),
        "active_session_files": len(active_sessions),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Claude Code 使用数据收集器")
    parser.add_argument("--days", type=int, default=7, help="分析过去 N 天的数据（默认 7）")
    parser.add_argument("--since", type=str, help="起始日期（YYYY-MM-DD），覆盖 --days")
    parser.add_argument("--output", type=str, help="输出 JSON 文件路径")
    args = parser.parse_args()

    if args.since:
        since = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        since = datetime.now(timezone.utc) - timedelta(days=args.days)

    until = datetime.now(timezone.utc)

    report = {
        "meta": {
            "generated_at": until.isoformat(),
            "period_start": since.isoformat(),
            "period_end": until.isoformat(),
            "days": args.days if not args.since else (until - since).days,
        },
        "history": collect_history(since),
        "tools": collect_tool_usage(since),
        "costs": collect_costs(since),
        "compactions": collect_compactions(since),
        "projects": collect_projects(),
        "sessions": collect_session_files(since),
    }

    output = json.dumps(report, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"数据已保存到 {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
