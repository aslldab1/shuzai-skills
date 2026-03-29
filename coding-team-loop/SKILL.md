---
name: coding-team-loop
description: openclaw 协调 Claude + Codex 双 worker 开发循环。以 GitHub Issues 为唯一任务数据库，Claude 负责设计/路由/review/验收，Codex 负责实现，两者独立调度，同一轮可以同时派发。
---

# Coding Team Loop

## 全局约定

### Issue Label 规范

Label 由 openclaw 维护，只有 HUMAN 关闭 Issue：

| Label | 含义 |
|-------|------|
| `pending` | 待派发 |
| `in-progress` | 已派发，执行中 |
| `needs-review` | Codex PR 已提交，等待 Claude review |
| `changes-requested` | Claude review 要求修改，等待 Codex 修复 |
| `verifying` | PR 已合并，等待 Claude 验收主干流程 |
| `verified` | 验收通过，等待 HUMAN 关闭 |
| `epic` | 大需求拆解跟踪 Issue，不直接执行 |

Owner label（与状态 label 并用）：
- `owner/claude` — 由 Claude 执行
- `owner/codex` — 由 Codex 执行
- `owner/shuzai` — 当前球在 HUMAN 手里（等待人工决策/确认/操作）

### 评论前缀规范

所有评论使用同一 git 账号，通过开头标识区分：
- `【OPENCLAW】` — 系统自动写入（派发通知、label 变更记录）
- `【CLAUDE】` — Claude 写入（方案概要、进度摘要、验收报告、完成信号）
- `【CODEX】` — Codex 写入（进度摘要、完成信号）

**完成信号**（openclaw 唯一的状态推进依据）：
- `【CLAUDE】【完成】PR #{pr_number} related to #{N}` — Claude 任务完成
- `【CODEX】【完成】PR #{pr_number} related to #{N}` — Codex 任务完成
- 无 PR 的纯文档/设计任务：`【CLAUDE】【完成】无 PR，产出已在 Issue 评论中`

### HUMAN 操作指引

| 情况 | 操作 |
|------|------|
| 看到 `verified`，确认无误 | 直接关闭 Issue |
| 看到 `verified`，发现还有问题 | 在 Issue 评论中描述问题，将 label 改回 `pending`（保留 owner label）→ 下轮自动重新派发 |
| 发现的是独立 bug，与原 Issue 无关 | 另开新 Issue，原 Issue 正常关闭 |
| 修改了已派发任务的内容，想重新执行 | 关闭/放弃当前 PR，将 label 改回 `pending` |
| 看到 `owner/shuzai` 通知，方案认可 | merge PR，关闭 Issue |
| 看到 `owner/shuzai` 通知，有修改意见 | 在 Issue 评论说明，将 label 改回 `pending`，owner 改回对应 worker |

### Codex 分支命名约定

Codex 创建分支必须使用 `issue-{N}` 格式，便于 openclaw 自愈时检测关联。
例：`issue-42`、`issue-42-fix-auth`

### Agent 身份

| Agent | GitHub 账户 | 职责 |
|-------|------------|------|
| Claude | 主账户 | 路由、设计、review、验收 |
| Codex | codex-bot 账户 | 实现、提 PR |

Codex 开始工作前必须设置 `GH_TOKEN` 为 codex-bot 的 token。验证：`gh api user --jq .login`

---

## 每轮执行（固定 3 步）

### Step 1 — 读取信号（只读）

**GitHub Issues：**
- 读取所有 open Issues 及 label
- **对每个 `in-progress` Issue，读取最近 10 条评论（含 body 和 createdAt）：**
  - 检测完成信号：最新评论含 `【CLAUDE】【完成】` 或 `【CODEX】【完成】`
    - owner/claude 完成 → 推进为 `verifying + owner/shuzai`，Feishu 通知 HUMAN，留 【OPENCLAW】 评论
    - owner/codex 完成 → 推进为 `needs-review`，留 【OPENCLAW】 评论
  - 检测 stale：无完成信号 + 最后活动时间（最新评论或分支最新 commit）距今 > 20 分钟
    - → 标记为"待确认"，Step 2/3 发送进度确认消息（参考：refs/progress-confirm.md）
- **对每个 `pending` + `owner/claude` 或 `owner/codex` 的 Issue，额外读取最近 10 条评论，供 Step 2/3 派发判断使用**

**GitHub PR：**
- 扫描所有 open PR，通过 body 中 `related to #N` / `closes #N` / `fixes #N` / `refs #N` 建立 PR ↔ Issue 关联映射
  - **仅供后续步骤查询使用，不触发状态自动推进**
- 若 PR 最新提交时间 > 最新 review 时间 → 自动将 label 从 `changes-requested` 更新为 `needs-review`（客观事实，无需 worker 信号）

**Pane 状态：**
- 抓取 Claude / Codex pane 最后 **30 行**，判断忙碌状态
- → 参考：refs/busy-detection.md

**Memory：**
- 读取 `run_lock`，若为 true 说明上一轮仍在执行，跳过本轮

### Step 2 — 处理 Claude 侧

**前置检查（必须通过才能继续）：**
```bash
bash scripts/busy_check.sh {claude_pane}
```
**只检查最底部 5 行非空行：行首符号 + 动名词**（`✢ Generating`、`• Working` 等）或行首 spinner。单独符号不算忙碌（`✻ Conversation compacted` 不匹配）。**输出 BUSY → 忙碌，跳过；输出 IDLE → 可派发**。匹配到时会同时输出匹配行，便于事后排查。→ 参考：refs/busy-detection.md

按优先级选择第一个匹配：

**P1** — 有 `needs-review` Issue
→ 派发 review 请求，Claude review 通过后直接 merge
→ 参考：refs/review-and-merge.md

**P2** — 有 `in-progress` + `owner/claude` + stale（Step 1 标记为"待确认"）
→ 发送进度确认消息，等待 Claude 回复
→ 参考：refs/progress-confirm.md

**P3** — 有 `verifying` + `owner/codex` Issue
→ 派发验收请求给 Claude，由 Claude 验收 Codex 的实现
→ 参考：refs/deliverable-verify.md

**P4** — 有 `pending` + `owner/claude` Issue
→ 取编号最小的一条
→ **读取该 Issue 完整评论历史（Step 1 已读）+ Claude pane 内容，综合判断当前状态后派发**
→ 参考：refs/task-dispatch.md

**P5** — 有 `pending` + 无 owner label 的 Issue
→ 派发路由请求，Claude 判断 owner 或拆解 epic
→ 要求：① 小任务直接打 owner/claude 或 owner/codex；② 大需求拆子 Issue 并打 epic；③ 路由结果写 【CLAUDE】 评论到 Issue

**P6** — 以上均无
→ Claude 侧本轮无动作

### Step 3 — 处理 Codex 侧

**前置检查（必须通过才能继续）：**
```bash
bash scripts/busy_check.sh {codex_pane}
```
同 Claude 侧：**输出 BUSY → 跳过，输出 IDLE → 可派发**。匹配行会一并输出。

按优先级选择第一个匹配：

**P1** — 有 `changes-requested` Issue
→ 派发修复请求，原文转发 Claude 的 review 意见
→ 参考：refs/fix-dispatch.md

**P2** — 有 `in-progress` + `owner/codex` + stale（Step 1 标记为"待确认"）
→ 发送进度确认消息，等待 Codex 回复
→ 参考：refs/progress-confirm.md

**P3** — 有 `pending` + `owner/codex` Issue
→ 取编号最小的一条
→ **读取该 Issue 完整评论历史（Step 1 已读）+ Codex pane 内容，综合判断当前状态后派发**
→ 参考：refs/task-dispatch.md

**P4** — 以上均无
→ Codex 侧本轮无动作

### owner/shuzai 处理（Step 1 完成后、Step 2 之前）

扫描所有含 `owner/shuzai` 的 open Issue，对每条执行以下判断：

**1. 检查最新评论是谁写的**

```
gh issue view {N} --json comments --jq '.comments | last'
```

| 最新评论情况 | 动作 |
|------------|------|
| 无评论 | 跳过，继续等 HUMAN |
| 最新评论以 `【OPENCLAW】` 或 `【CLAUDE】` 开头 | 跳过（系统已回复，等 HUMAN 再次操作）|
| 最新评论是 HUMAN 写的（无系统前缀） | 视为新反馈，执行下方"处理人工反馈"流程 |

**2. 处理人工反馈**

1. 从该 Issue 的评论历史中找到最近一条记录了"owner 切换为 owner/shuzai"的 【OPENCLAW】 评论，提取切换前的 owner（即上一个负责人）
2. Issue label：`verifying → pending`，owner 恢复为上一个 owner
3. 留 【OPENCLAW】 评论，记录已接收反馈并重置，引用 HUMAN 的评论
4. 下轮派发时，将 HUMAN 的评论原文作为补充上下文带入 Task Brief

**3. Feishu 通知**

- 若该 Issue 本轮状态发生变化（刚从 in-progress 转入 owner/shuzai）→ 发通知
- 若状态未变化且 hash 不变 → 不重复通知
- `owner/shuzai` 的 Issue **不进入 Step 2 / Step 3 的派发逻辑**

### 全局异常（两侧均无动作时）

- 有 `in-progress` 任务且进度确认消息已发出超过 1 小时仍无回复 → Feishu 通知人工（worker 可能彻底卡死）
- 所有 Issue 均为 `verified` 且无 pending → Feishu 通知人工"请下发新任务"（每次进入此状态只通知一次）
- 连续派发失败 3 次 → Feishu 通知人工
- Worker 会话缺失 → 参考：refs/session-recovery.md

### Step 4 — 输出进度报告（每轮必须执行）

**本轮所有操作完成后，先读取 refs/progress-report-format.md，按其中的模板逐字段填写输出。**
→ 参考：refs/progress-report-format.md

---

## Memory 结构

```yaml
workers:
  claude:
    last_dispatched_at: ""      # ISO8601
    last_issue_number: null
  codex:
    last_dispatched_at: ""
    last_issue_number: null

notifications:
  all_verified_notified_at: null   # 防止重复通知
  last_feishu_report_hash: ""      # Issue label 状态 hash，内容不变时跳过报告

run_lock: false    # 防并发：本轮执行中设为 true，完成后清除
```

