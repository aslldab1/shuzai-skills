#!/usr/bin/env python3
"""
coding-team-loop SKILL.md 验证器

通过 openclaw agent CLI 发送场景 prompt，解析 JSON 回复，判断 PASS/FAIL。
对话历史存储在 OpenClaw session，可在控制台查看。

用法：
  python3 scripts/validate_skill.py                    # 跑全部场景（默认 4 并行）
  python3 scripts/validate_skill.py --suite core       # 只跑主干用例
  python3 scripts/validate_skill.py --suite task-dispatch  # 只跑 task-dispatch 模块
  python3 scripts/validate_skill.py --scenario CS01
  python3 scripts/validate_skill.py --verbose          # 显示 OpenClaw 原始回复
  python3 scripts/validate_skill.py --concurrency 8    # 自定义并行度
"""

import sys
import json
import time
import argparse
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

# ── 配置 ───────────────────────────────────────────────────────────────────────
OPENCLAW_BIN  = "/Users/lin/workspace/AI/git/openclaw/dist/index.js"
SESSION_ID    = f"skill-validator-{int(time.time())}"
AGENT_TIMEOUT = 120  # 秒

SKILL_DIR     = Path(__file__).parent.parent
SKILL_MD      = SKILL_DIR / "SKILL.md"
SCENARIOS_DIR = SKILL_DIR / "tests"


def load_all_scenarios():
    """自动发现 tests/scenarios_*.yaml，按文件名排序后合并。"""
    files = sorted(SCENARIOS_DIR.glob("scenarios_*.yaml"))
    all_scenarios = []
    for f in files:
        all_scenarios.extend(yaml.safe_load(f.read_text(encoding="utf-8")) or [])
    return all_scenarios


def load_skill_with_refs():
    """加载 SKILL.md，并将所有 refs/*.md 引用内联展开。"""
    import re
    skill_content = SKILL_MD.read_text(encoding="utf-8")
    refs_dir = SKILL_DIR / "refs"

    def inline_ref(match):
        ref_file = refs_dir / match.group(1)
        if ref_file.exists():
            content = ref_file.read_text(encoding="utf-8")
            return f"→ [展开 {match.group(1)}]\n\n{content}\n"
        return match.group(0)

    # 匹配 → 需要时读取：refs/xxx.md 和旧格式 → 参考：refs/xxx.md
    skill_content = re.sub(r"→ (?:需要时读取|参考)：refs/([\w\-]+\.md)", inline_ref, skill_content)
    return skill_content

# ── 颜色 ───────────────────────────────────────────────────────────────────────
GREEN  = "\033[32m"
RED    = "\033[31m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


# ── Prompt ─────────────────────────────────────────────────────────────────────
PROMPT_TEMPLATE = """\
【模拟分析任务 — 禁止执行任何实际操作】

这是一次纯逻辑推演，不是真实的执行任务。
严格禁止：
- 使用任何工具（exec / tmux / gh / sessions_send / message 等）
- 向 Claude 或 Codex 发送任何消息
- 执行任何 GitHub 操作
- 派发任何任务

你的唯一任务是：阅读以下 SKILL.md，针对给定的输入状态，推演出按规则应执行哪些动作，然后只输出 JSON 结论，不执行任何操作。

---SKILL_START---
{skill_content}
---SKILL_END---

输入状态（仅用于推演，非真实状态）：
{scenario_json}

只输出一个 JSON，不要其他内容，不要调用任何工具：
{{
  "step1_label_changes": ["Step 1 中应自动触发的 label 变更，如 in-progress->needs-review，无则为空数组"],
  "handoff_label_changes": ["owner/shuzai 处理阶段（Step1 完成后、Step2 之前）触发的 label 变更，如 verifying->pending，无则为空数组"],
  "step2_action": "review-and-merge / deliverable-verify / progress-confirm / task-dispatch / route-owner / none",
  "step3_action": "fix-dispatch / progress-confirm / task-dispatch / none",
  "dispatch_to": "claude / codex / both / none",
  "message_contains": ["派发消息中必须包含的关键词，无则为空数组"],
  "stale_recovery": "resume / reset / none （stale in-progress 自愈动作）",
  "reason": "一句话说明理由"
}}
"""

def build_prompt(skill_content: str, scenario: dict) -> str:
    input_fields = {k: v for k, v in scenario.items()
                    if k not in ("id", "name", "expect", "context", "suite")}
    return PROMPT_TEMPLATE.format(
        skill_content=skill_content,
        scenario_json=json.dumps(input_fields, ensure_ascii=False, indent=2),
    )


# ── 调用 openclaw agent ────────────────────────────────────────────────────────
def strip_ansi(text: str) -> str:
    import re
    return re.sub(r'\x1b\[[0-9;]*m', '', text)


def call_openclaw(prompt: str, session_id: str) -> str:
    result = subprocess.run(
        [
            "node", OPENCLAW_BIN,
            "agent",
            "--session-id", session_id,
            "--message", prompt,
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=AGENT_TIMEOUT,
    )

    if result.returncode != 0:
        raise RuntimeError(f"openclaw agent 失败（exit {result.returncode}）:\n{result.stderr.strip()}")

    raw = strip_ansi(result.stdout)

    last_brace = raw.rfind('\n{')
    if last_brace == -1:
        last_brace = raw.find('{')
    if last_brace == -1:
        raise RuntimeError(f"输出中未找到 JSON：{raw[:300]}")

    json_str = raw[last_brace:].strip()
    data = json.loads(json_str)

    payloads = data.get("payloads") or data.get("result", {}).get("payloads", [])
    if payloads and payloads[0].get("text"):
        return payloads[0]["text"]

    raise RuntimeError(f"payloads 为空，完整输出：{json_str[:300]}")


# ── JSON 提取 ──────────────────────────────────────────────────────────────────
def extract_json(text: str) -> dict:
    if "```" in text:
        parts = text.split("```")
        for part in parts[1::2]:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except json.JSONDecodeError:
                continue

    start = text.find("{")
    end   = text.rfind("}") + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])

    raise ValueError(f"回复中未找到 JSON：{text[:200]}")



# ── 线程安全输出 ──────────────────────────────────────────────────────────────
_print_lock = threading.Lock()

def _print_sync(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)


# ── 单场景评估 ─────────────────────────────────────────────────────────────────
def evaluate_scenario(skill_content: str, scenario: dict,
                      session_id: str, verbose: bool) -> bool:
    sid    = scenario.get("id", "?")
    name   = scenario.get("name", "")
    expect = scenario.get("expect", {})

    # 每个场景使用独立 session，避免并行时上下文污染
    scenario_session = f"{session_id}-{sid}"

    lines: list[str] = []
    lines.append(f"\n{BOLD}[{sid}]{RESET} {name}")

    prompt = build_prompt(skill_content, scenario)

    try:
        reply = call_openclaw(prompt, scenario_session)
    except subprocess.TimeoutExpired:
        lines.append(f"{RED}  ✗ 超时（>{AGENT_TIMEOUT}s）{RESET}")
        _print_sync("\n".join(lines))
        return False
    except RuntimeError as e:
        lines.append(f"{RED}  ✗ {e}{RESET}")
        _print_sync("\n".join(lines))
        return False

    if verbose:
        preview = reply[:400] + ("..." if len(reply) > 400 else "")
        lines.append(f"       OpenClaw 回复：{preview}")

    try:
        result = extract_json(reply)
    except (ValueError, json.JSONDecodeError) as e:
        lines.append(f"{RED}  ✗ 回复不是合法 JSON：{e}{RESET}")
        _print_sync("\n".join(lines))
        return False

    passed = True
    for field_name in ["step2_action", "step3_action", "dispatch_to",
                       "message_contains", "step1_label_changes",
                       "handoff_label_changes", "stale_recovery"]:
        actual_val = result.get(field_name)
        expect_val = expect.get(field_name)
        if expect_val is None:
            continue

        if isinstance(actual_val, list):
            actual_str = " ".join(str(x) for x in actual_val)
        elif actual_val is None:
            actual_str = "null"
        else:
            actual_str = str(actual_val)

        keywords = expect_val if isinstance(expect_val, list) else [expect_val]
        missing = [kw for kw in keywords if kw not in actual_str]

        if missing:
            lines.append(f"{RED}  ✗ {field_name}: 缺少关键词 {missing}（实际：{actual_val}）{RESET}")
            passed = False
        elif verbose:
            lines.append(f"{GREEN}  ✓ {field_name}: {actual_val}{RESET}")

    if passed:
        lines.append(f"{GREEN}  ✓ PASS{RESET}")

    _print_sync("\n".join(lines))
    return passed


# ── 主流程 ─────────────────────────────────────────────────────────────────────
DEFAULT_CONCURRENCY = 4


def main():
    parser = argparse.ArgumentParser(description="验证 coding-team-loop SKILL.md")
    parser.add_argument("--scenario", help="只运行指定场景 ID（如 CS01）")
    parser.add_argument("--suite",    help="只运行指定套件（core / module:xxx，如 task-dispatch）")
    parser.add_argument("--file",     help="只运行指定场景文件（如 scenarios_routing.yaml）")
    parser.add_argument("--verbose",  action="store_true", help="显示 OpenClaw 原始回复")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                        help=f"并行执行的场景数（默认 {DEFAULT_CONCURRENCY}）")
    args = parser.parse_args()

    skill_content = load_skill_with_refs()

    if args.file:
        target = SCENARIOS_DIR / args.file
        if not target.exists():
            print(f"{RED}找不到文件 {args.file}{RESET}")
            sys.exit(1)
        scenarios = yaml.safe_load(target.read_text(encoding="utf-8")) or []
    else:
        scenarios = load_all_scenarios()

    if args.scenario:
        scenarios = [s for s in scenarios if s.get("id") == args.scenario]
        if not scenarios:
            print(f"{RED}找不到场景 {args.scenario}{RESET}")
            sys.exit(1)

    if args.suite:
        suite_filter = args.suite
        # 支持 --suite core 或 --suite task-dispatch（自动补 module: 前缀）
        if suite_filter != "core" and not suite_filter.startswith("module:"):
            suite_filter = f"module:{suite_filter}"
        scenarios = [s for s in scenarios if s.get("suite") == suite_filter]
        if not scenarios:
            print(f"{RED}找不到套件 {args.suite} 的场景{RESET}")
            sys.exit(1)

    runnable = [s for s in scenarios if "expect" in s]
    concurrency = min(args.concurrency, len(runnable)) if runnable else 1

    suite_label = args.suite or "all"
    print(f"\n{BOLD}coding-team-loop SKILL.md 验证器{RESET}")
    print(f"Session  : {SESSION_ID}")
    print(f"Suite    : {suite_label}")
    print(f"场景总数 : {len(runnable)}")
    print(f"并行度   : {concurrency}")
    print(f"（对话记录可在 OpenClaw 控制台 session '{SESSION_ID}-{{ID}}' 中查看）")

    passed_count = 0
    failed_ids: list[str] = []

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        future_to_sid = {
            pool.submit(evaluate_scenario, skill_content, s, SESSION_ID, args.verbose): s.get("id", "?")
            for s in runnable
        }
        for future in as_completed(future_to_sid):
            sid = future_to_sid[future]
            try:
                if future.result():
                    passed_count += 1
                else:
                    failed_ids.append(sid)
            except Exception as e:
                _print_sync(f"{RED}  ✗ [{sid}] 未捕获异常：{e}{RESET}")
                failed_ids.append(sid)

    total = len(runnable)
    print(f"\n{'─' * 50}")
    print(f"{BOLD}结果：{passed_count}/{total} 通过{RESET}")

    if failed_ids:
        print(f"{RED}失败场景：{', '.join(failed_ids)}{RESET}")
        print(f"建议：python3 scripts/validate_skill.py --scenario {failed_ids[0]} --verbose")
        sys.exit(1)
    else:
        print(f"{GREEN}全部通过 ✓{RESET}")


if __name__ == "__main__":
    main()
