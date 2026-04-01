---
name: dev-loop 测试优化循环
cron_job: dev-loop-10m (4acb70ac-9714-477c-98f0-3e33bad623a7)
---

# Cron Prompt

本文件定义了 dev-loop skill 的测试循环流程。由 Claude（本会话）手动按此流程执行，**不是 cron job 的 payload**。

## 执行流程

### Phase 1 — 触发 skill 执行
```bash
openclaw cron run 4acb70ac-9714-477c-98f0-3e33bad623a7
```
等待执行完成，记录 sessionId。

### Phase 2 — 执行复盘
使用 cron-log-review 的分析脚本对执行情况进行分析：
```bash
# 步骤详情
python3 /Users/lin/workspace/AI/git/shuzai-skills/cron-log-review/scripts/analyze_runs.py --job dev-loop-10m --session {sessionId} --steps

# 跨轮进度
python3 /Users/lin/workspace/AI/git/shuzai-skills/cron-log-review/scripts/analyze_runs.py --job dev-loop-10m --last 5 --progress
```

重点关注：
- 任务推进有效性（跨轮是否卡死）
- 状态推进是否合理（label 变更有对应触发事件）
- 派发决策是否合理（选了最该推进的 Issue）
- 操作顺序（comment → label → dispatch）
- 硬约束遵守（-R 参数、tmux_dispatch.sh、busy_check）

### Phase 3 — 问题处理

**所有发现的问题都写入 `dev-loop/backlog/`**，文件名格式：`{YYYYMMDD-HHmm}-{简述}.md`。
内容包括：问题级别、问题表现、影响分析。

**P0 问题额外执行：**
1. 直接修改 `/Users/lin/workspace/AI/git/shuzai-skills/dev-loop/` 下的相关文件
2. 创建分支、提交、创建 PR 并合并到 main
3. 回填 backlog 文件，补充解决方案和 PR 编号

**P1/P2 问题**：仅写入 backlog，等待用户确认是否修复。

### Phase 4 — 更新计划
更新 `docs/superpowers/plans/2026-04-01-coding-team-loop-test-optimization.md`，记录本轮结果。

## 配置参数

| 参数 | 值 | 说明 |
|------|---|------|
| schedule | every 5min | 测试间隔 |
| timeout | 300s | 单轮超时 |
| rounds | 20 | 总轮次 |
| sessionTarget | isolated | 每轮独立 session |
