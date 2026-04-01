# P0: Issue #69 连续 3 轮重复派发且 worker 无产出

## 问题级别
P0

## 依据条款（cron-log-review SKILL.md 原文）

> 连续 ≥ 2 轮执行相同的派发动作（对同一 Issue 重复派发）→ P0 无效重复

> 派发后 worker 无任何产出（无新评论、无新 commit、无 PR）→ P0 派发失效

## 问题表现
Session `3ad070cc-b06b-461e-bd8e-75395fd56167`（04-02 00:01）中，Issue #69 第 3 轮被派发：
- 04-01 23:22: `epic+pending` → 首次派发（label 变更为 `in-progress+owner/claude`）
- 04-01 23:42: `epic+in-progress+owner/claude` → 再次派发进度巡检
- 04-02 00:01: `epic+in-progress+owner/claude` → 第三次派发进度巡检

三轮之间 worker 均未产出任何评论、commit 或 PR。根因是 tmux 通道连续 no_ack，但 dev-loop 持续写入 OPENCLAW 评论并尝试派发，违反了 SKILL.md 中的派发失败处理规则。

## SKILL.md 违规
SKILL.md 明确规定：
- "连续 2 轮 dispatch 失败 → 飞书通知中高亮标注 Worker 不可达，暂停后续派发"
- "禁止对不可达的 worker 继续写派发评论（避免评论堆积混淆）"

但实际执行中第 3 轮仍然写入了派发评论并尝试 tmux dispatch。说明 LLM 未能跨轮检测连续 dispatch 失败并执行暂停策略。

## 影响分析
- Issue #69 上累积了 3 条无效的 OPENCLAW 派发评论
- Worker 恢复后可能被多条指令混淆
- 任务实际停滞 3 轮（约 30 分钟）无推进
- 飞书通知中未高亮 worker 不可达警告

## 根因
dev-loop 缺少跨轮状态持久化机制，无法记住上一轮 dispatch 是否失败。每轮都是无状态执行，无法实现"连续 N 轮失败后暂停"的逻辑。

## 解决方案
需要在 SKILL.md 中强化派发失败检测逻辑：在派发前检查最近评论中是否存在连续的 OPENCLAW 派发评论且无 worker 回复，以此作为跨轮 dispatch 失败的代理信号。
