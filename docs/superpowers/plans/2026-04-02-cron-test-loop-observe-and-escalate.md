# cron-test-loop Observe-and-Escalate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change `dev-loop/cron-test-loop.md` from find-and-fix to observe-and-escalate mode.

**Architecture:** Single markdown file edit. Phase 3 becomes observe-only (write backlog, no fixes). New Phase 3.5 adds pattern-based escalation with feishu notifications.

**Tech Stack:** Markdown (no code changes)

---

## Task 1: Rewrite Phase 3 — Record findings only

**Files:**
- Modify: `dev-loop/cron-test-loop.md:36-46`

- [ ] **Step 1: Replace Phase 3 content**

Replace the current Phase 3 ("问题处理") with observe-only behavior:

```markdown
### Phase 3 — 记录发现

**所有发现的问题都写入 `dev-loop/backlog/`**，文件名格式：`{YYYYMMDD-HHmm}-{简述}.md`。

内容格式：

\`\`\`markdown
# {级别}: {标题}

## 问题级别
{P0/P1/P2}（仅评估，不区分处理方式）

## 观测现象
{具体发生了什么}

## 证据
{具体数据：轮次编号、Issue 编号、日志摘录}

## 影响
{阻塞或劣化了什么}
\`\`\`

**本阶段禁止：**
- 修改 skill 文件、脚本或任何代码
- 创建分支、提交或 PR
- 直接修复问题
```

- [ ] **Step 2: Verify removed content**

Confirm the following are no longer present in Phase 3:
- "P0 问题额外执行"
- "直接修改" / "创建分支" / "提交" / "创建 PR 并合并到 main"
- "P1/P2 问题：仅写入 backlog，等待用户确认是否修复"

## Task 2: Add Phase 3.5 — Backlog summary + escalation

**Files:**
- Modify: `dev-loop/cron-test-loop.md` (insert after Phase 3, before Phase 4)

- [ ] **Step 1: Insert Phase 3.5**

Add the following section between Phase 3 and Phase 4:

```markdown
### Phase 3.5 — Backlog 汇总 + 升级通知

写完当轮 backlog 后，扫描 `dev-loop/backlog/` 下所有文件，检查是否触发升级条件。

#### 升级触发条件

**计数型**（捕捉未知失败模式）：

| 模式 | 阈值 | 说明 |
|------|------|------|
| 同一 Issue 在连续 N 轮 backlog 中出现 | ≥ 3 轮 | 任务卡死 |
| 同一 Issue 相同 label 且无新 comment/PR/commit | ≥ 3 轮 | 状态冻结 |

**模式型**（捕捉已知失败模式，更快触发）：

| 模式 | 阈值 | 说明 |
|------|------|------|
| `dispatch=failed` 连续出现 | ≥ 2 轮 | 派发通道故障 |
| Worker 不可达（dispatch 后无响应） | ≥ 2 轮 | Worker 环境异常 |
| Dispatch 成功但无 worker 产出 | ≥ 3 轮 | Worker 静默失败 |

#### 触发升级时

发送飞书告警通知：
\`\`\`bash
openclaw message send --channel feishu --target "ou_c5bd4c88f78cbf338f76dbb5e8f64fed" -m "通知内容"
\`\`\`

通知格式：
\`\`\`
【测试循环告警 {datetime}】

问题：{问题描述}
持续：连续 {N} 轮
影响：{影响分析}
建议：{推荐操作}
详情：{backlog 文件路径}
\`\`\`

#### 未触发升级时

- **不发送额外通知**，避免噪音
- dev-loop 自身的每轮飞书进度通知照常发送

#### 边界情况

- 首轮无历史 backlog：不可能升级，仅记录
- 同轮多个触发：合并为一条通知
- 同一 Issue 上轮已通知：除非情况恶化（轮次增加），不重复通知
```

- [ ] **Step 2: Verify Phase ordering**

Confirm the final document has phases in order: Phase 1 → Phase 2 → Phase 3 → Phase 3.5 → Phase 4

## Task 3: Diff review and commit

- [ ] **Step 1: Review full diff**

Run `git diff dev-loop/cron-test-loop.md` and verify:
- Phase 3 has no fix/commit/PR language
- Phase 3.5 is correctly positioned
- Phase 4 reference is unchanged
- No unintended changes to Phase 1 or Phase 2

- [ ] **Step 2: Commit**

```bash
git add dev-loop/cron-test-loop.md
git commit -m "refactor: change cron-test-loop to observe-and-escalate mode

Phase 3 now only records findings to backlog files.
New Phase 3.5 adds pattern-based escalation with feishu notifications
when high-priority issues persist across multiple rounds."
```
