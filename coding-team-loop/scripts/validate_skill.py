#!/usr/bin/env python3
"""
coding-team-loop SKILL.md 验证器

通过 openclaw agent CLI 发送场景 prompt，解析 JSON 回复，判断 PASS/FAIL。
对话历史存储在 OpenClaw session，可在控制台查看。

用法：
  python3 scripts/validate_skill.py              # 跑全部场景
  python3 scripts/validate_skill.py --scenario S01
  python3 scripts/validate_skill.py --verbose    # 显示 OpenClaw 原始回复
"""

import sys
import json
import time
import argparse
import subprocess
from pathlib import Path

import yaml

# ── 配置 ───────────────────────────────────────────────────────────────────────
OPENCLAW_BIN  = "/Users/lin/workspace/AI/git/openclaw/dist/index.js"
SESSION_ID    = f"skill-validator-{int(time.time())}"
AGENT_TIMEOUT = 120  # 秒

SKILL_DIR = Path(__file__).parent.parent
SKILL_MD  = SKILL_DIR / "SKILL.md"
SCENARIOS = SKILL_DIR / "tests" / "scenarios.yaml"

# ── 颜色 ───────────────────────────────────────────────────────────────────────
GREEN  = "\033[32m"
RED    = "\033[31m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):   print(f"{GREEN}  ✓ {msg}{RESET}")
def fail(msg): print(f"{RED}  ✗ {msg}{RESET}")

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
  "step2_action": "review-and-merge / deliverable-verify / task-dispatch / route-owner / none",
  "step3_action": "fix-dispatch / task-dispatch / none",
  "dispatch_to": "claude / codex / both / none",
  "message_contains": ["派发消息中必须包含的关键词，无则为空数组"],
  "stale_recovery": "resume / reset / none （stale in-progress 自愈动作）",
  "reason": "一句话说明理由"
}}
"""

def build_prompt(skill_content: str, scenario: dict) -> str:
    input_fields = {k: v for k, v in scenario.items()
                    if k not in ("id", "name", "expect", "context")}
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


# ── 字段对比 ───────────────────────────────────────────────────────────────────
def check_field(label: str, actual, expected, verbose: bool) -> bool:
    if expected is None:
        return True

    if isinstance(actual, list):
        actual_str = " ".join(str(x) for x in actual)
    elif actual is None:
        actual_str = "null"
    else:
        actual_str = str(actual)

    keywords = expected if isinstance(expected, list) else [expected]
    missing = [kw for kw in keywords if kw not in actual_str]

    if missing:
        fail(f"{label}: 缺少关键词 {missing}（实际：{actual}）")
        return False

    if verbose:
        ok(f"{label}: {actual}")
    return True


# ── 单场景评估 ─────────────────────────────────────────────────────────────────
def evaluate_scenario(skill_content: str, scenario: dict,
                      session_id: str, verbose: bool) -> bool:
    sid    = scenario.get("id", "?")
    name   = scenario.get("name", "")
    expect = scenario.get("expect", {})

    print(f"\n{BOLD}[{sid}]{RESET} {name}")

    prompt = build_prompt(skill_content, scenario)

    try:
        reply = call_openclaw(prompt, session_id)
    except subprocess.TimeoutExpired:
        fail(f"超时（>{AGENT_TIMEOUT}s）")
        return False
    except RuntimeError as e:
        fail(str(e))
        return False

    if verbose:
        preview = reply[:400] + ("..." if len(reply) > 400 else "")
        print(f"       OpenClaw 回复：{preview}")

    try:
        result = extract_json(reply)
    except (ValueError, json.JSONDecodeError) as e:
        fail(f"回复不是合法 JSON：{e}")
        return False

    passed = True
    passed &= check_field("step2_action",      result.get("step2_action"),      expect.get("step2_action"),      verbose)
    passed &= check_field("step3_action",      result.get("step3_action"),      expect.get("step3_action"),      verbose)
    passed &= check_field("dispatch_to",       result.get("dispatch_to"),       expect.get("dispatch_to"),       verbose)
    passed &= check_field("message_contains",  result.get("message_contains"),  expect.get("message_contains"),  verbose)
    passed &= check_field("step1_label_changes", result.get("step1_label_changes"), expect.get("step1_label_changes"), verbose)
    passed &= check_field("stale_recovery",    result.get("stale_recovery"),    expect.get("stale_recovery"),    verbose)

    if passed:
        ok("PASS")
    return passed


# ── 主流程 ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="验证 coding-team-loop SKILL.md")
    parser.add_argument("--scenario", help="只运行指定场景 ID（如 S01）")
    parser.add_argument("--verbose",  action="store_true", help="显示 OpenClaw 原始回复")
    args = parser.parse_args()

    skill_content = SKILL_MD.read_text(encoding="utf-8")
    scenarios     = yaml.safe_load(SCENARIOS.read_text(encoding="utf-8"))

    if args.scenario:
        scenarios = [s for s in scenarios if s.get("id") == args.scenario]
        if not scenarios:
            print(f"{RED}找不到场景 {args.scenario}{RESET}")
            sys.exit(1)

    runnable = [s for s in scenarios if "expect" in s]

    print(f"\n{BOLD}coding-team-loop SKILL.md 验证器{RESET}")
    print(f"Session  : {SESSION_ID}")
    print(f"场景总数 : {len(runnable)}")
    print(f"（对话记录可在 OpenClaw 控制台 session '{SESSION_ID}' 中查看）")

    passed_count = 0
    failed_ids   = []

    for scenario in runnable:
        result = evaluate_scenario(skill_content, scenario, SESSION_ID, args.verbose)
        if result:
            passed_count += 1
        else:
            failed_ids.append(scenario.get("id", "?"))

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
