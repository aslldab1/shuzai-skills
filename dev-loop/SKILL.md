---
name: dev-loop
description: openclaw 开发循环（极简版）。读取 GitHub Issues，判断最高优先级动作，派发给 Claude worker 执行，跟踪进度并推进。
---

# Dev Loop

## 目标

每轮巡检做一件事：**找到最该推进的 Issue，推进它。**

读取所有 open Issue 的状态和评论，判断当前最重要的动作（review、验收、派发新任务、跟进卡住的任务），执行后输出进度报告。

## 环境

| 变量 | 值 |
|------|------|
| 目标仓库 | `aslldab1/Claw-Coach` |
| Claude pane | `clawcoach-claude-2116:0.0` |
| 脚本目录 | 本 skill 目录下的 `scripts/` |

## 硬约束（不可违反）

1. **`-R` 参数**：所有 `gh` 命令必须带 `-R aslldab1/Claw-Coach`（cron 工作目录不在目标仓库）
2. **派发用脚本**：`bash scripts/tmux_dispatch.sh clawcoach-claude-2116:0.0 "{message}"`，禁止裸 `tmux send-keys`
3. **忙碌检测**：派发前必须 `bash scripts/busy_check.sh clawcoach-claude-2116:0.0`，输出 BUSY 则不派发
4. **禁止环境探测**：不要 `ls`、`grep` 脚本内容、`tmux ls` 等。所有固定信息已在本文件中列出
4. **完成信号**：openclaw 唯一的状态推进依据是评论中的 `【CLAUDE】【完成】` 或 `【CODEX】【完成】`
5. **Worker 不碰状态**：Worker 只能 `gh issue comment` / `gh pr create` / `gh pr review`。Label 变更、Issue 关闭、PR merge 全部由 openclaw 执行
6. **一轮一个派发**：每轮最多派发一个新任务，避免并发冲突
7. **依赖门禁**：如果 Issue B 的 body 含 `related to #A`（父子/依赖关系），则 A 必须处于 `verified` 状态后才能派发 B。未满足依赖的 Issue 即使是 `pending` 也不可派发
8. **禁止 dispatch 验收**：`verifying` 状态的 Issue 必须由本 skill 执行方在本轮 session 内直接读取并执行 validator skill，**禁止**通过 `tmux_dispatch` 将验收任务派发给 tmux worker

## 每轮流程

### 1. 读取状态

```bash
# 所有 open Issue
gh issue list -R aslldab1/Claw-Coach --state open --limit 100 --json number,title,labels,body,updatedAt,url

# 所有 open PR
gh pr list -R aslldab1/Claw-Coach --state open --limit 100 --json number,title,body,updatedAt,author,headRefName,url,reviewDecision
```

对需要判断进度的 Issue（`in-progress` 等），读取最近 10 条评论：
```bash
gh issue view {N} -R aslldab1/Claw-Coach --json comments --jq '.comments[-10:] | map({author:.author.login,body:.body,createdAt:.createdAt})'
```

检查 Claude worker 是否空闲：
```bash
bash scripts/busy_check.sh {claude_pane}
```

### 2. 判断 + 执行

**用你的判断力决定最该做什么。** 以下是优先级指引（不是硬规则）：

- **有 PR 待 review** → 派发 review 请求，review 通过后 merge
- **有任务待验收** → 派发验收请求
- **有 PR 被要求修改** → 派发修复请求
- **有任务卡住**（in-progress 但长时间无进展）→ 派发进度确认
- **有待派发任务** → 选最重要的一个派发
- **有新 Issue 需要分流** → 判断 owner 或拆解子 Issue
- **全部完成** → 通知 HUMAN

**派发动作顺序：**
```
① busy_check       ← 确认 worker 可达
② gh issue comment  ← 写 【OPENCLAW】 派发评论（持久化锚点）
③ tmux 派发         ← bash scripts/tmux_dispatch.sh（脚本自动恢复 worker）
④ gh issue edit     ← 仅在 ③ 成功时更新 label（dispatch=failed 则不变更）
```

**派发失败处理：**
- tmux_dispatch.sh 返回 `dispatch=failed` → 本轮不做 label 变更（保持原状态），飞书通知中标注 dispatch 失败原因
- 每轮都必须重试派发，不得因历史失败而跳过

**完成信号处理：**
- 检测到 `【CODEX】【完成】` → label 改 `needs-review`（等 Claude review PR）
- 检测到 `【CLAUDE】【完成】` → label 改 `verifying`（**由本 skill 执行方在 session 内直接执行 validator skill 完成验收**）
- 子 Issue 全部关闭 → 父 Issue label 改 `verifying`（最终验收）
- validator 验收通过 → label 改 `verified`，通知 HUMAN 确认关闭
- validator 验收不通过 → label 改回 `pending`，附验收反馈，下轮重新派发

### 验收流程（verifying 状态专用）

当发现 Issue 处于 `verifying` 状态时，**本 skill 执行方在本轮 session 内直接执行验收**，不通过 `tmux_dispatch` 派发。

**执行步骤：**

1. 读取 validator skill（使用 Skill 工具或直接读取 `validator/SKILL.md`）

2. 在当前 session 内按 validator skill 完成三阶段验收（读取 Issue 内容与交付物、执行各阶段验证、给出结论）

3. 将完整报告写回 Issue，使用 `【VALIDATOR】` 前缀：
```bash
gh issue comment {N} -R aslldab1/Claw-Coach --body-file - <<'EOF'
【VALIDATOR】{验收报告内容}
EOF
```

4. 根据结论更新 label（comment 写入成功后才执行）：
   - **通过** → `gh issue edit {N} -R aslldab1/Claw-Coach --remove-label verifying --add-label verified`；飞书通知 HUMAN 确认关闭
   - **不通过** → `gh issue edit {N} -R aslldab1/Claw-Coach --remove-label verifying --add-label pending`；附验收问题清单，下轮重新派发

5. **工具不足时**（无法访问 browser、Playwright、Stitch MCP 等）：
   - 在 Issue 写入评论：`【VALIDATOR】工具不足，无法完成验收，缺失工具：{工具名}，请人工介入`
   - 同时发送飞书告警：`openclaw message send --channel feishu --account stage2 --target "ou_92ebef681150322a26c3af3d1d79072e" -m "【验收告警】{Issue} 验收工具不足：{工具名}"`

**派发消息必须包含：**
- Issue 编号和链接
- 需求描述和验收标准
- 明确的执行步骤
- `⚠️ 禁止执行 gh issue edit / gh issue close / gh pr merge`
- 如涉及原型设计 → 要求使用 `/stitch-prototype` skill

### 3. 输出进度报告并发送飞书通知

**必须执行以下命令发送飞书通知**（不可省略，这是每轮的必要输出）：

```bash
openclaw message send --channel feishu --account stage2 --target "ou_92ebef681150322a26c3af3d1d79072e" -m "通知内容"
```

通知内容使用以下格式：
```
【开发进度 {datetime}】

正在处理：
• {Issue 标题} — {当前状态和进展}

需要你操作：
• {等待 HUMAN 的 Issue}

排队中：
• {pending 的 Issue}

本轮变化：{做了什么}
```

## Label 约定

| Label | 含义 |
|-------|------|
| `pending` | 待派发 |
| `in-progress` | 执行中 |
| `needs-review` | PR 待 review |
| `changes-requested` | Review 要求修改 |
| `verifying` | 待验收 |
| `verified` | 验收通过，等 HUMAN 关闭 |
| `epic` | 大需求，由子 Issue 驱动（不直接派发） |
| `owner/claude` | Claude 执行 |
| `owner/codex` | Claude 通过 Codex 插件执行 |
| `owner/shuzai` | 等待 HUMAN |

## 评论前缀

- `【OPENCLAW】` — 系统评论（派发通知、label 变更）
- `【CLAUDE】` — Claude worker 评论
- `【CODEX】` — Codex worker 评论（由 Claude 代写）

## 脚本

| 脚本 | 用途 | 位置 |
|------|------|------|
| `busy_check.sh` | 检查 worker 是否忙碌 | `scripts/busy_check.sh {pane}` |
| `tmux_dispatch.sh` | 向 worker 发送消息 | `scripts/tmux_dispatch.sh {pane} "{message}"` |

## 示例场景

**场景 1：正常派发**
Issue #65 是 `pending + owner/claude`，Claude 空闲。
→ 写 OPENCLAW 评论 → label 改 in-progress → tmux 派发任务消息

**场景 2：Codex 完成 → review**
Issue #65 评论出现 `【CODEX】【完成】PR #20 related to #65`。
→ label 改 needs-review → 下轮派发 Claude review

**场景 2b：Claude 完成 → 待验收**
Issue #65 评论出现 `【CLAUDE】【完成】PR #18 related to #65`。
→ label 改 verifying → 下轮 skill 执行方在 session 内直接读取 validator skill 执行验收（见验收流程节）

**场景 3：Epic 拆解**
Issue #64 是大需求，无 owner label。
→ 派发给 Claude 做分流：决定 owner 或拆子 Issue
→ 子 Issue 必须带 `pending` + `owner/xxx` label + body 含 `related to #64`

**场景 4：任务卡住**
Issue #65 已 in-progress 30 分钟，无新评论/commit。
→ 检查 pane 状态，发进度确认消息
→ 如果 worker 已断开 → 用恢复格式重新派发

**场景 5：子 Issue 全完成**
Issue #64 的所有子 Issue 已关闭。
→ 父 Issue 推进为 verifying → 下轮派发最终验收
