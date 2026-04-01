# 开发任务派发

适用于 Step 2-P6（Claude 直接执行）和 Step 2-P7（Claude 通过 Codex 插件执行）。

## 脚本

```bash
~/.openclaw/workspace/skills/coding-team-loop/scripts/tmux_dispatch.sh {claude_pane} "{payload}"
```

返回值：
- `dispatch=submitted` → 正常
- `dispatch=failed reason=no_ack` → 派发失败，计入连续失败计数

## Claude 开发任务消息格式

**派发前综合判断（不靠单一规则，LLM 根据完整信息推断）：**

Step 1 已读取该 Issue 最近 10 条评论（含 body 和 createdAt）和 Claude pane 最近 30 行。在派发前，综合以下两个信息源做出判断：

**判断维度：**

1. **任务是否已处理？**
   - pane 内容显示 Claude 说"已完成/已处理/无需重复执行"，且评论中有对应的 【CLAUDE】 回复
   - → 工作已做，**不重新派发**；只需补做未完成的状态更新（补写派发评论、修正 label）

2. **是否有未响应的 HUMAN 反馈？**
   - 在评论历史中，找最近一条 `【OPENCLAW】已将此任务派发给` 评论之后，是否有**无系统前缀**的评论
   - → 有：使用**带人工反馈格式**，引用该 HUMAN 评论原文（用 `jq -r` 解码，确保为原始 UTF-8，不含 `\uXXXX`）
   - → 没有：使用**标准格式**

3. **是否涉及产品原型设计？**
   - Issue 需求描述中涉及 UI 原型、页面原型、交互设计、产品原型、wireframe、mockup 等
   - → 是：在派发消息中追加原型设计指令（见下方 ⓪ 步骤），要求 worker 使用 `/stitch-prototype` skill 执行原型设计
   - → 如果 worker 执行时发现 skill 不可用（执行报错或无响应），**不要尝试替代方案**，立即在 Issue 评论反馈环境问题，停止执行

4. **产出物是否为方案/文档类？**
   - Issue 需求描述中涉及方案设计、调研报告、落地方案、技术文档等（产出物是给 HUMAN 阅读的文档）
   - → 是：在派发消息中追加产出格式要求（见下方「方案文档产出规范」）
   - → 否（纯代码开发任务）：不追加

> **【CLAUDE】前缀规范：** Claude 发布到 Issue 的所有评论必须以 `【CLAUDE】` 开头。这是系统区分 HUMAN 评论与 Claude 回复的唯一依据，缺少前缀会导致下一轮误判。

**标准格式（无 HUMAN 反馈）：**
```
【OPENCLAW】【开发任务】
Issue #{N}：{Issue标题}
链接：{Issue URL}

需求描述：
{Issue 正文中的需求描述}

验收标准：
{Issue 正文中的验收条件}

请按以下步骤执行：
{如判断维度 3 命中，插入 ⓪}
① 在 `issue-{N}` 分支上工作（从 main 创建，若已存在则直接使用）
② 在 Issue 评论中回复方案概要（2~3 句，不需要展开细节）
   **必须以 【CLAUDE】 开头，例如：`【CLAUDE】方案概要：…`**
③ 将详细技术方案输出到仓库文档（docs/tasks/issue-{N}-{slug}.md）
   Issue 评论中贴带分支的直链，格式：
   https://github.com/{owner}/{repo}/blob/{branch}/docs/tasks/issue-{N}-{slug}.md
④ 完成后，push 分支并开 PR，PR body 中包含 `related to #{N}`
⑤ 在 Issue 写完成信号（这是 openclaw 推进状态的唯一依据）：
   有 PR：`【CLAUDE】【完成】PR #{pr_number} related to #{N}`
   无 PR（纯文档/设计）：`【CLAUDE】【完成】无 PR，产出已在 Issue 评论中`

⚠️ 禁止执行 gh issue edit / gh issue close / gh pr merge —— 所有状态推进由 openclaw 自动处理。
```

**带人工反馈格式（有 HUMAN 评论时必须使用）：**
```
【OPENCLAW】【开发任务】
Issue #{N}：{Issue标题}
链接：{Issue URL}

需求描述：
{Issue 正文中的需求描述}

验收标准：
{Issue 正文中的验收条件}

人工反馈（请针对上次结果优化，不要从头开始）：
{HUMAN 最新评论原文，完整引用}

请按以下步骤执行：
{如判断维度 3 命中，插入 ⓪}
① 在 `issue-{N}` 分支上工作（从 main 创建，若已存在则直接使用）
② 在 Issue 评论中回复针对反馈的修改方案（2~3 句）
   **必须以 【CLAUDE】 开头，例如：`【CLAUDE】方案修订：…`**
③ 更新方案文档（若已存在 docs/tasks/issue-{N}-{slug}.md 则在原文件修订）
④ 完成后，push 分支并开 PR，PR body 中包含 `related to #{N}`
⑤ 在 Issue 写完成信号：`【CLAUDE】【完成】PR #{pr_number} related to #{N}`

⚠️ 禁止执行 gh issue edit / gh issue close / gh pr merge —— 所有状态推进由 openclaw 自动处理。
```

## Codex 开发任务消息格式（通过 Claude 调度）

当 Issue 的 owner 是 `owner/codex` 时，消息发给 Claude，指示 Claude 通过 Codex 插件执行：

```
【OPENCLAW】【Codex 开发任务（通过 Codex 插件调度）】
Issue #{N}：{Issue标题}
链接：{Issue URL}

任务：{一句话目标}
分支：issue-{N}（从 main 创建，必须使用此命名格式）
验收条件：
- {条件1}
- {条件2}
范围边界：{明确不包含的内容}

{如判断维度 3 命中，插入 ⓪}

请通过 Codex 插件执行此任务：
① 使用 /rescue 或 codex:codex-rescue agent 将以下任务派发给 Codex：
   - 任务描述：{Issue 正文中的需求描述}
   - 分支：issue-{N}
   - 验收条件：{条件列表}
② 跟踪执行进度（foreground 模式等待完成，或 --background + status 轮询）
③ Codex 完成后，验证结果：
   - 检查分支是否存在且有 commit
   - 检查 PR 是否已创建且 body 含 "related to #{N}"
   - 如有问题，重新派发修复
④ 在 Issue 写完成信号：`【CODEX】【完成】PR #{pr_number} related to #{N}`
   （这是 openclaw 推进状态的唯一依据）

⚠️ 禁止执行 gh issue edit / gh issue close / gh pr merge —— 所有状态推进由 openclaw 自动处理。
```

## 原型设计步骤 ⓪（判断维度 3 命中时插入）

当 Issue 涉及产品原型设计时，在派发消息的步骤列表中插入以下步骤：

```
⓪ 本任务涉及产品原型设计，请使用 /stitch-prototype skill 完成原型。
   如果 skill 不可用（执行报错、skill 未安装、无响应），立即在 Issue 评论：
   「【{WORKER前缀}】stitch-prototype skill 不可用，请 HUMAN 检查环境配置」
   然后停止执行，不要用其他方式替代原型设计。
```

其中 `{WORKER前缀}` 按任务类型替换：owner/claude → `【CLAUDE】`，owner/codex → `【CODEX】`。

## 方案文档产出规范（判断维度 4 命中时追加）

当 Issue 产出物为方案/文档类时，在派发消息的步骤列表**末尾**追加以下要求：

```
📄 产出格式要求：
- 方案必须做成 HTML 页面文件（不是 Markdown），确保内容具备强表达力
- 尽量通过图文方式表达思路和方案，避免纯文字堆砌
- 简单图表/流程图使用 Canvas 绘制（内嵌 <canvas> + JS）
- 复杂的插图/示意图使用 /nano-banana skill 生成
  如果 skill 不可用，在 Issue 评论说明并改用 Canvas 替代
```

## 派发动作（必须严格按序）

> 顺序不可颠倒。评论写在最前，是唯一持久化的派发锚点；即使后续步骤失败，下一轮也能通过它判断"曾经派发过"。

**第 1 步：写 【OPENCLAW】 派发评论（最先执行）**
```bash
gh issue comment {N} --body "【OPENCLAW】已将此任务派发给 @{worker}，开始执行。
label: in-progress · 派发时间：{datetime}"
```

**第 2 步：更新 label**
```bash
gh issue edit {N} --add-label in-progress --remove-label pending
```

**第 3 步：tmux 派发（始终发给 Claude pane）**
```bash
bash scripts/tmux_dispatch.sh {claude_pane} "{payload}"
```
- 返回 `dispatch=submitted` → 正常，继续
- 返回 `dispatch=failed`（任何原因）→ **本轮立即停止**，不得用任何其他 tmux 命令重试，等下一轮
  - 禁止：`tmux paste-buffer`、`tmux load-buffer`、`tmux send-keys` 等 bypass 方式
  - 计入连续失败计数，3 次 → Feishu 通知人工

**第 4 步：更新 memory**
```
last_dispatched_at、last_issue_number
```

**中断容错：** 任意步骤中断后，下一轮 LLM 读取 Issue 评论历史 + pane，可判断执行到了哪步并恢复：
- 有派发评论 + label 仍为 pending → 补做第 2、3 步
- 有派发评论 + label 为 in-progress + pane idle + 无 PR → stale 自愈逻辑接管

## Claude 拆分 Codex 子任务规则

当 Claude 需要将实现工作交给 Codex 时，**必须创建 GitHub Issue**，不得只更新 QUEUE.md：

**第 1 步：创建 Codex Issue**
```bash
gh issue create -R {repo} \
  --title "[子任务] {简短描述，如 C33-ui-rebuild：前端页面重建}" \
  --body "## 任务来源\n由 Issue #{父N} 拆解，Claude 已完成规划。\n\n## 开发清单\n{详细步骤}\n\n## 验收标准\n{条件}\n\nrelated to #{父N}" \
  --label "pending" --label "owner/codex"
```

**第 2 步：在父 Issue 写 【CLAUDE】 评论说明已创建子 Issue（包含编号）**

**第 3 步：父 Issue 保持 `in-progress`，禁止写 `【CLAUDE】【完成】`**

> ⚠️ **父 Issue 完成信号约束（严格执行）：**
> 如果你拆分了子 Issue，**禁止手动写父 Issue 的 `【CLAUDE】【完成】` 信号**。
>
> 以下情况都不算完成，**不得写完成信号**：
> - Codex 子任务已准备就绪 ≠ 完成
> - 子 Issue PR 已提交 ≠ 完成
> - 子 Issue review 通过 ≠ 完成
> - 所有子 Issue 已关闭 ≠ 完成（仍需 openclaw 触发最终验收）
>
> 父 Issue 的完成由 openclaw 自动处理：所有子 Issue 关闭后，openclaw 通过 Step 1.6 自动触发最终验收（Step 2-P2），
> Claude 只需在收到最终验收请求时回复【验收通过】即可。**不要主动写 `【CLAUDE】【完成】`。**

> ⚠️ **Claude 在拆分子任务时，禁止对父 Issue 执行 `gh issue edit` / `gh issue close`。** 只允许 `gh issue comment` 和 `gh issue create`。

> ⚠️ QUEUE.md 是 Codex 的内部工作文件，**不是 openclaw 的派发依据**。
> openclaw 只通过 GitHub Issue label（`pending + owner/codex`）发现并派发 Codex 任务。
> 只写 QUEUE.md 会导致 Codex 任务永远不会被自动派发。

## 中断恢复派发

Step 1 检测到 stale in-progress 且有对应分支时，改用恢复消息：

```
【OPENCLAW】【恢复执行】
Issue #{N}：{Issue标题}
之前因中断暂停，已有进度在分支 {branch_name}。
请检查分支当前状态后继续执行，不要从头开始。

⚠️ 禁止执行 gh issue edit / gh issue close / gh pr merge —— 所有状态推进由 openclaw 自动处理。
```
