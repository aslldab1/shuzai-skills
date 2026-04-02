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

### Phase 3 — 记录发现

**所有发现的问题都写入 `dev-loop/backlog/`**，文件名格式：`{YYYYMMDD-HHmm}-{简述}.md`。

内容格式：

```markdown
# {级别}: {标题}

## 问题级别
{P0/P1/P2}（仅评估，不区分处理方式）

## 观测现象
{具体发生了什么}

## 证据
{具体数据：轮次编号、Issue 编号、日志摘录}

## 影响
{阻塞或劣化了什么}
```

**本阶段禁止：**
- 修改 skill 文件、脚本或任何代码
- 创建分支、提交或 PR
- 直接修复问题

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
```bash
openclaw message send --channel feishu --target "ou_c5bd4c88f78cbf338f76dbb5e8f64fed" -m "通知内容"
```

通知格式：
```
【测试循环告警 {datetime}】

问题：{问题描述}
持续：连续 {N} 轮
影响：{影响分析}
建议：{推荐操作}
详情：{backlog 文件路径}
```

#### 未触发升级时

- **不发送额外通知**，避免噪音
- dev-loop 自身的每轮飞书进度通知照常发送

#### 边界情况

- 首轮无历史 backlog：不可能升级，仅记录
- 同轮多个触发：合并为一条通知
- 同一 Issue 上轮已通知：除非情况恶化（轮次增加），不重复通知

### Phase 4 — 更新计划
更新 `docs/superpowers/plans/2026-04-01-coding-team-loop-test-optimization.md`，记录本轮结果。

## 配置参数

| 参数 | 值 | 说明 |
|------|---|------|
| schedule | every 5min | 测试间隔 |
| timeout | 300s | 单轮超时 |
| rounds | 20 | 总轮次 |
| sessionTarget | isolated | 每轮独立 session |
