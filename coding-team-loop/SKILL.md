---
name: coding-team-loop
description: openclaw 协调 Claude + Codex 双 worker 开发循环。以 GitHub Issues 为唯一任务数据库，Claude 负责设计/路由/review/验收，Codex 负责实现，两者独立调度，同一轮可以同时派发。
---

# Coding Team Loop

## 执行纪律

- **refs/ 文件禁止预读**：遇到 `→ 需要时读取：refs/xxx.md` 标记时，只在执行到该分支且确认需要执行时才 read，未命中的分支不读。每轮通常只会命中 1-2 个 ref，全部预读是浪费。
- 已在 SKILL.md 正文中写明的规则不需要再读 ref 确认。ref 文件只包含正文未覆盖的执行细节（消息模板、脚本参数等）。
- **禁止环境探测**：不要 `ls`、`git remote -v`、`echo $GH_REPO` 等命令。所有固定信息已在 cron payload 或本文件中给出。

## 全局约定

### Issue Label 规范

Label 由 openclaw 维护：

| Label | 含义 |
|-------|------|
| `pending` | 待派发 |
| `in-progress` | 已派发，执行中 |
| `needs-review` | Codex PR 已提交，等待 Claude review |
| `changes-requested` | Claude review 要求修改，等待 Codex 修复 |
| `verifying` | PR 已合并，等待验收（Claude 验收子 Issue，HUMAN 验收自己创建的 Issue） |
| `verified` | 验收通过，等待 HUMAN 关闭 |
| `blocked` | 验收发现问题，等待修复 Issue 关闭后重验（与 `verifying` 并用） |
| `epic` | 大需求拆解跟踪 Issue，不直接执行 |

### 子 Issue 与 HUMAN Issue 区分

Issue 分两类，**验收和关闭方式不同**：

| 类型 | 识别方式 | 验收者 | 关闭者 |
|------|---------|--------|--------|
| **HUMAN Issue** | body **不含** `related to #N` | HUMAN 验收 | HUMAN 关闭 |
| **子 Issue** | body **含** `related to #N`（由 Claude/openclaw 拆解创建） | Claude 验收 | openclaw 自动关闭 |

子 Issue 验收通过后 openclaw 直接关闭，不交给 HUMAN。HUMAN 只需关注自己创建的 Issue。

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

> ⚠️ **完成信号识别严格规则（禁止宽松匹配）：**
> - 必须精确包含 `【完成】` 两字（全角方括号）
> - 以下评论**绝对不算完成信号**，不得触发任何状态推进：
>   - `【CLAUDE】方案概要`、`【CLAUDE】执行分流方案`
>   - `【CLAUDE】Codex C{N} 任务已准备就绪`、`【CLAUDE】QUEUE.md 已更新`
>   - 任何不含 `【完成】` 的 `【CLAUDE】` 或 `【CODEX】` 评论
> - LLM **不得**通过语义推断（"这条评论说任务准备好了，所以算完成"）扩展识别范围

### HUMAN 操作指引

HUMAN 只需关注自己创建的 Issue。子 Issue（由 Claude/openclaw 创建）的验收和关闭由 Claude 自动处理。

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

### Memory 持久化

Memory 存储在本地 JSON 文件，路径：`~/.openclaw/coding-team-loop/memory.json`
- 每轮 Step 1 最先读取，Step 5 最后写回
- 文件不存在（首次运行）→ 使用默认值
- → 需要时读取：refs/memory-persistence.md

### Worker 权限边界（严格执行）

Worker（Claude / Codex）在执行任务时，**只允许以下 GitHub 写操作**：
- `gh issue comment` — 写评论（进度、方案、完成信号）
- `gh pr create` — 创建 PR
- `gh pr review` — 提交 review（仅 Claude）
- `gh pr comment` — 写 PR 评论
- `gh issue create` — 创建子 Issue（仅 Claude 拆解任务时）

**以下操作严格禁止，只能由 openclaw 执行：**
- `gh issue edit`（修改 label、title、body、assignee 等）
- `gh issue close` / `gh issue reopen`
- `gh pr merge`
- 任何直接修改 Issue/PR 状态的命令

所有状态推进由 openclaw 根据完成信号自动处理。派发消息中的 ⚠️ 禁令是对此规则的重申。

---

## 每轮执行（固定 3 步）

### Step 1 — 读取信号（只读）

**GitHub Issues：**
- 读取所有 open Issues 及 label
- **对每个 `in-progress` Issue，读取最近 10 条评论（只取 author/body/createdAt，控制数据量）：**
  ```bash
  gh issue view {N} --repo {REPO} --json comments --jq '.comments[-10:] | map({author:.author.login,body:.body,createdAt:.createdAt})'
  ```
  - 检测完成信号：最新评论**精确包含** `【CLAUDE】【完成】` 或 `【CODEX】【完成】` 字样（不含`【完成】`的评论一律忽略）
    - owner/claude 完成：
      - **先检查是否为有子 Issue 的父 Issue**：查询是否存在 body 含 `related to #{此Issue编号}` 的 Issue（open 或 closed）
        - 如果存在子 Issue → **时序检查**：获取父 Issue 最新 `【OPENCLAW】已将此任务派发给` 评论时间（dispatch_time），与每个子 Issue 的 createdAt 比较
          - 至少一个子 Issue 的 createdAt > dispatch_time → **忽略完成信号，不做状态推进**（当前周期有活跃子 Issue，由 Step 1.6 驱动）
          - 所有子 Issue 的 createdAt < dispatch_time → **视为旧周期遗留，正常处理完成信号**（按下方规则继续）
          - 无 dispatch 评论 → 忽略完成信号（异常状态，不触发）
      - **子 Issue**（body 含 `related to #N`）→ 推进为 `verifying + owner/claude`（Claude 自行验收），留 【OPENCLAW】 评论
      - **HUMAN Issue**（body 不含 `related to #N`，且无当前周期子 Issue）→ 推进为 `verifying + owner/shuzai`，Feishu 通知 HUMAN，留 【OPENCLAW】 评论
    - owner/codex 完成 → 推进为 `needs-review`，留 【OPENCLAW】 评论
- **对每个 `verifying + blocked` Issue：** 查询所有 body 含 `fix for #{此Issue编号}` 的 Issue（open + closed）
  - 如果存在修复 Issue 且全部为 `state=CLOSED` → 移除 `blocked` label，留 【OPENCLAW】 评论「修复 Issue 已关闭，重新触发验收」，下轮 Step 2-P2/P4 正常命中
  - 如果不存在修复 Issue 或仍有 open 的 → 跳过，继续等待

  - 检测 stale：无完成信号 + 最后活动时间（最新评论或分支最新 commit）距今 > 20 分钟
    - → 标记为"待确认"，Step 2/3 发送进度确认消息（→ 需要时读取：refs/progress-confirm.md）
- **对每个 `pending` + `owner/claude` 或 `owner/codex` 的 Issue，额外读取最近 10 条评论，供 Step 2/3 派发判断使用：**
  ```bash
  gh issue view {N} --repo {REPO} --json comments --jq '.comments[-10:] | map({author:.author.login,body:.body,createdAt:.createdAt})'
  ```

**GitHub PR：**
- 扫描所有 open PR，通过 body 中 `related to #N` / `closes #N` / `fixes #N` / `refs #N` 建立 PR ↔ Issue 关联映射
  - **仅供后续步骤查询使用，不触发状态自动推进**
- 若 PR 最新提交时间 > 最新 review 时间 → 自动将 label 从 `changes-requested` 更新为 `needs-review`（客观事实，无需 worker 信号）

**Pane 状态：**
- 抓取 Claude / Codex pane 最后 **30 行**，判断忙碌状态
- → 需要时读取：refs/busy-detection.md

**Memory（本轮最先执行）：**
- 读取 memory 文件：`cat ~/.openclaw/coding-team-loop/memory.json 2>/dev/null || echo '{}'`
- 文件不存在或 JSON 解析失败 → 使用默认值（全部为空/false/null）
- 检查 `run_lock`：
  - `true` 且文件修改时间距今 < 10 分钟 → 上轮仍在执行，**跳过本轮**
  - `true` 且文件修改时间距今 ≥ 10 分钟 → 上轮崩溃，强制清除 lock 继续
  - `false` → 正常继续
- 立即设置 `run_lock = true` 并写回文件（缩小并发窗口）

### Step 2 — 处理 Claude 侧

**前置检查（必须通过才能继续）：**
```bash
bash scripts/busy_check.sh {claude_pane}
```
**只检查最底部 5 行非空行：行首符号 + 动名词**（`✢ Generating`、`• Working` 等）或行首 spinner。单独符号不算忙碌（`✻ Conversation compacted` 不匹配）。**输出 BUSY → 忙碌，跳过；输出 IDLE → 可派发**。匹配到时会同时输出匹配行，便于事后排查。→ 需要时读取：refs/busy-detection.md

按优先级选择第一个匹配：

**P1** — 有 `needs-review` Issue
→ 派发 review 请求，Claude review 通过后直接 merge
→ 需要时读取：refs/review-and-merge.md

**P2** — 有 `verifying` + `owner/claude` 且**无 `blocked`** 的 Issue（子 Issue 验收 或 父 Issue 最终验收）
→ 派发验收请求给 Claude
→ 需要时读取：refs/deliverable-verify.md
→ 验收通过后的处理方式取决于 Issue 类型（详见 refs/deliverable-verify.md）

**P3** — 有 `in-progress` + `owner/claude` + stale（Step 1 标记为"待确认"）
→ 发送进度确认消息，等待 Claude 回复
→ 需要时读取：refs/progress-confirm.md

**P4** — 有 `verifying` + `owner/codex` 且**无 `blocked`** 的 Issue
→ 派发验收请求给 Claude，由 Claude 验收 Codex 的实现
→ 需要时读取：refs/deliverable-verify.md

**P5** — 有 `pending` + `owner/claude` Issue
→ 取编号最小的一条
→ **读取该 Issue 完整评论历史（Step 1 已读）+ Claude pane 内容，综合判断当前状态后派发**
→ 需要时读取：refs/task-dispatch.md

**P6** — 有 `pending` + 无 owner label 的 Issue
→ 派发路由请求，Claude 判断 owner 或拆解 epic
→ 要求：① 小任务直接打 owner/claude 或 owner/codex；② 大需求拆子 Issue 并打 epic；③ 路由结果写 【CLAUDE】 评论到 Issue

**P7** — 以上均无
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
→ 需要时读取：refs/fix-dispatch.md

**P2** — 有 `in-progress` + `owner/codex` + stale（Step 1 标记为"待确认"）
→ 发送进度确认消息，等待 Codex 回复
→ 需要时读取：refs/progress-confirm.md

**P3** — 有 `pending` + `owner/codex` Issue
→ 取编号最小的一条
→ **读取该 Issue 完整评论历史（Step 1 已读）+ Codex pane 内容，综合判断当前状态后派发**
→ 需要时读取：refs/task-dispatch.md

**P4** — 以上均无
→ Codex 侧本轮无动作

### Step 1.5 — Codex 子任务孤儿检测（Codex Orphan Recovery）

**触发条件：** Step 1 完成后，**对每个** `in-progress + owner/claude` 的 Issue **独立**检测其最近 10 条评论，判断 Claude 是否已规划但尚未建 Issue 的 Codex 子任务。

**孤儿特征（满足其一即触发）：**
- 评论含 `tasks/codex/` 路径（如 `tasks/codex/C33-ui-rebuild/TASK.md`）
- 评论含 `QUEUE.md 已更新` 且附有 Codex 开发清单

**且** GitHub 上**不存在** body 含 `related to #{父Issue编号}` 的 `pending + owner/codex` open Issue（即该父 Issue 的 Codex 子任务均已派发或不存在）。

**openclaw 执行以下操作（不改变父 Issue 状态）：**

第 1 步：从 Claude 评论中提取子任务标题和开发清单，创建 GitHub Issue：
```bash
gh issue create -R {repo} \
  --title "[子任务] {子任务标题，如 C33-ui-rebuild：前端页面重建}" \
  --body "## 任务来源
由 Issue #{父Issue编号} 拆解，Claude 已完成规划。

## 开发清单
{从 Claude 评论中提取的完整开发清单}

## 验收标准
{从 Claude 评论中提取的验收标准，若无则写"由 Claude code review + Playwright E2E 验收"}

related to #{父Issue编号}" \
  --label "pending" --label "owner/codex"
```

第 2 步：在父 Issue 写 【OPENCLAW】 评论说明：
```
【OPENCLAW】已检测到 Codex 子任务未建 Issue，已补建 Issue #{新Issue编号}，下轮自动派发给 Codex。
```

第 3 步：在 memory 中记录已处理的父 Issue 编号，防止下轮重复创建：
```
codex_orphan_recovered: [#{父Issue编号}]
```

> **父 Issue 保持 `in-progress`，不改状态。** 下一轮 Step 3-P3 会正常找到新 Issue 并派发给 Codex。

### Step 1.6 — 子任务完成联动（Sub-Task Completion Linkage）

**触发条件：** 存在 `in-progress + owner/claude` 的父 Issue（已经是 `verifying` 的跳过），且其所有子 Issue 均已关闭。

> Step 1.6 在 Step 1 之后、Step 2 之前执行，因此只能检测到**之前轮次**关闭的子 Issue。
> 这意味着子 Issue 被关闭后，父 Issue 最终验收会在**下一轮**触发，延迟一轮是正常行为。

**检测方式：**
1. 对每个 `in-progress + owner/claude` 的 Issue，查询所有 body 含 `related to #{父Issue编号}` 的 Issue（含 open 和 closed）
2. 如果存在子 Issue 且**全部**为 `state=CLOSED` → **进入时序检查（第 3 步）**
3. **时序检查（防止旧子 Issue 误触发）：** 比较父 Issue 最新的 `【OPENCLAW】已将此任务派发给` 评论时间（dispatch_time）与所有子 Issue 中最晚的关闭时间（last_child_close_time）：
   - `dispatch_time > last_child_close_time` → **跳过**（父 Issue 已被重新派发，旧子 Issue 不再相关，如 HUMAN 打回重做的场景）
   - `dispatch_time < last_child_close_time` → 触发父 Issue 最终验收（子 Issue 是在当前周期内关闭的）
   - 无派发评论 → 跳过（异常状态，不触发）
4. 如果没有子 Issue 或仍有未关闭的子 Issue → 跳过

**openclaw 执行以下操作：**

第 1 步：在父 Issue 写 【OPENCLAW】 评论：
```
【OPENCLAW】所有子任务已完成并验收通过，进入最终验收阶段。请运行 Playwright E2E 完整验收后给出结论。
```

第 2 步：将父 Issue 推进为 `verifying + owner/claude`：
```bash
gh issue edit {父N} --add-label verifying --remove-label in-progress
```
（owner 保持 `owner/claude`，由 Claude 做最终验收）

> **注意：** 父 Issue 的 `verifying + owner/claude` 状态会在下一轮被 Step 2-P2 命中，触发 Claude 最终验收（含 Playwright E2E）。
> 验收通过后，父 Issue 才会被推进为 `verified + owner/shuzai` 交给 HUMAN。

### owner/shuzai 处理（Step 1.6 完成后、Step 2 之前）

→ 需要时读取：refs/human-handoff.md

### 全局异常（两侧均无动作时）

- 有 `in-progress` 任务且进度确认消息已发出超过 1 小时仍无回复 → Feishu 通知人工（worker 可能彻底卡死）
- 所有 Issue 均为 `verified` 且无 pending → Feishu 通知人工"请下发新任务"（每次进入此状态只通知一次）
- 连续派发失败 3 次 → Feishu 通知人工
- Worker 会话缺失 → 需要时读取：refs/session-recovery.md

### Step 4 — 输出进度报告（每轮必须执行）

**本轮所有操作完成后，先读取 refs/progress-report-format.md，按其中的模板逐字段填写输出。**
→ 需要时读取：refs/progress-report-format.md

### Step 5 — 写回 Memory（每轮最后执行）

将本轮 memory 写回 `~/.openclaw/coding-team-loop/memory.json`：
- `run_lock` → `false`
- 如本轮有派发 → 更新 `workers.{worker}.last_dispatched_at`（ISO8601）和 `last_issue_number`
- 如本轮 Step 1.5 补建了子 Issue → 追加父 Issue 编号到 `codex_orphan_recovered`
- 如本轮发送了"全部已验收"通知 → 记录 `notifications.all_verified_notified_at`
- 如本轮发送了进度报告 → 更新 `notifications.last_feishu_report_hash`

→ 需要时读取：refs/memory-persistence.md

---

## Memory 结构（持久化至 ~/.openclaw/coding-team-loop/memory.json）

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

codex_orphan_recovered: []  # 已补建 Issue 的父 Issue 编号，防止重复创建；父 Issue 关闭后可清除

run_lock: false    # 防并发：本轮执行中设为 true，完成后清除
```

