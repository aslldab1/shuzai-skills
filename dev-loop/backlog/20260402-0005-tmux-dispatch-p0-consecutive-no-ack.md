# P0: tmux 派发连续 3 轮 no_ack — 违反派发失败处理规则

## 问题级别
P0

## 依据条款（cron-log-review SKILL.md 原文）

> 连续 ≥ 2 轮执行相同的派发动作（对同一 Issue 重复派发）→ P0 无效重复

> 派发后 worker 无任何产出（无新评论、无新 commit、无 PR）→ P0 派发失效

用户指令中的 P0 标准补充：
> 连续 dispatch 失败（no_ack/no_session/worker_start_timeout）→ P0

## 问题表现
连续 3 轮（04-01 23:22, 23:42, 04-02 00:01）tmux_dispatch.sh 均返回 `dispatch=failed reason=no_ack`。

dev-loop SKILL.md 第 76-77 行明确规定：
- "连续 2 轮 dispatch 失败 → 飞书通知中高亮标注'⚠️ Worker 不可达，请恢复 tmux worker 会话'，暂停后续派发"
- "禁止对不可达的 worker 继续写派发评论（避免评论堆积混淆）"

但实际执行未遵守此规则，第 3 轮仍写入派发评论并尝试 dispatch。

## 影响分析
- Worker 完全不可达，所有派发均为无效操作
- 派发评论堆积在 Issue 上，worker 恢复后可能混淆
- 飞书通知未高亮 worker 不可达警告，HUMAN 无法及时介入恢复
- 任务推进完全停滞

## 根因
LLM 每轮无状态执行，缺少跨轮 dispatch 失败记忆。SKILL.md 虽有规则但 LLM 无法回溯之前轮次的 dispatch 结果。

## 解决方案
在 SKILL.md "判断 + 执行" 部分增加派发前检查逻辑：读取目标 Issue 最近评论，如果发现连续 >= 2 条 OPENCLAW 评论且中间无 CLAUDE/CODEX 回复，视为 dispatch 失败，执行暂停策略。
