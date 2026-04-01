# Dev-Loop 测试问题追踪

轮询发现和人工反馈的问题汇总。每轮复盘后更新。

## 状态说明
- `OPEN` — 待修复
- `FIXED` — 已修复（标注 PR 编号）
- `WONTFIX` — 不修复（标注原因）

## 问题列表

| # | 级别 | 来源 | 问题 | 状态 | 备注 |
|---|------|------|------|------|------|
| 1 | P0 | R2 轮询 | Issue #69 连续 3 轮重复派发且 worker 无产出 | FIXED | PR #16 |
| 2 | P0 | R2 轮询 | tmux dispatch 连续 3 轮 no_ack | FIXED | tmux_dispatch.sh 增加 Claude 进程检测+自动启动 |
| 3 | P0 | R2 轮询 | Issue #65 连续 2 轮卡在 verifying 无推进 | OPEN | 需 validator 介入或人工检查 |
| 4 | P0 | R1 轮询 | SKILL.md 飞书通知只有格式没有发送命令 | FIXED | SKILL.md 增加 openclaw message send 命令 |
| 5 | P1 | R3 轮询 | tmux worker 持续不可达 | FIXED | tmux_dispatch.sh 自动检测+启动 Claude Code |
| 6 | P2 | R1 轮询 | 派发后多余 busy_check 调用 | OPEN | |
| 7 | P2 | R1/R3 轮询 | cron delivery channel 未配置（feishu/dingtalk 多通道） | OPEN | 需用户修改 cron job 配置 |
| 8 | P2 | R2 轮询 | Issue #69 连续派发产生无效评论堆积 | WONTFIX | 用户要求每轮重试派发，不加门禁 |
| 9 | P0 | 人工反馈 | 飞书通知目标地址错误（应为 ou_92ebef681150322a26c3af3d1d79072e） | FIXED | SKILL.md + CLAUDE.md 已更新 |
| 10 | P0 | 人工反馈 | tmux 启动 Claude 缺少 --dangerously-skip-permissions 参数 | FIXED | tmux_dispatch.sh 已更新 |
| 11 | P0 | 人工反馈 | cron-test-loop Phase 2 未强制按 P0 标准判定 | FIXED | cron-test-loop.md 增加强制标准 |
| 12 | P0 | 人工反馈 | tmux auto-create 只创建空 session 不启动 Claude | FIXED | tmux_dispatch.sh 增加进程检测+启动逻辑 |
| 13 | P0 | 人工反馈 | 跨轮门禁阻止派发重试 | FIXED | SKILL.md 移除门禁，每轮必须重试 |
| 14 | P0 | R4 轮询 | 飞书目标 ou_92eb... 返回 open_id cross app，应为 ou_c5bd... | FIXED | PR #17，SKILL.md 已恢复正确目标 |
| 15 | P0 | R4 轮询 | Issue #69 连续 5 轮派发无 worker 产出 | OPEN | 根因已修复；R5/R6 轮 worker=BUSY（正在执行），R7 轮 IDLE 后重新派发成功，待完成信号确认后关闭 |
| 16 | P2 | R7 轮询 | 派发前重复 busy_check 调用（Step 4 + Step 6） | OPEN | 模型行为，同 #6 |
| 17 | P0 | R8 轮询 | Epic #69 子任务完成信号误判为 epic 完成，被错误推进 verifying | FIXED | SKILL.md 明确 epic 不受评论完成信号影响；已回退 label |
