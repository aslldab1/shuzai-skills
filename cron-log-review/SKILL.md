---
name: cron-log-review
description: 分析 openclaw cron 定时任务的执行日志，识别超时、错误、执行流程问题和优化项。
---

# Cron Log Review

## 用途

拉取 openclaw 定时任务的运行日志和 session 详情，分析执行流程，找到：
- 超时和错误原因
- 执行步骤冗余（重复读取、无效探测）
- Token 消耗异常
- 耗时趋势和瓶颈
- 可优化的执行路径

## 数据源

### 1. 任务配置

```bash
cat ~/.openclaw/cron/jobs.json
```

字段说明：
- `id` — job UUID
- `name` — 任务名（如 `clawcoach-progress-10m`）
- `payload.timeoutSeconds` — 超时上限
- `state.lastRunStatus` — 最近一次状态（ok/error）
- `state.lastDurationMs` — 最近一次耗时
- `state.consecutiveErrors` — 连续错误次数

### 2. 运行历史

```bash
# 每个 job 一个 JSONL 文件，每行是一次执行记录
~/.openclaw/cron/runs/{job-id}.jsonl
```

每行字段：
| 字段 | 说明 |
|------|------|
| `ts` | 完成时间戳（ms） |
| `status` | `ok` 或 `error` |
| `error` | 错误原因（超时时为 `cron: job execution timed out`） |
| `durationMs` | 执行耗时 |
| `usage.input_tokens` | 输入 token 数 |
| `usage.output_tokens` | 输出 token 数 |
| `sessionId` | 对应 session 文件名 |
| `summary` | 执行摘要（推送到飞书的内容） |

### 3. Session 详情

```bash
# 每次执行的完整 tool call 记录
~/.openclaw/agents/main/sessions/{session-id}.jsonl
```

JSONL 格式，`type=message` 的行包含实际交互：
- `message.role=assistant` + `content[].type=toolCall` → 工具调用（name + arguments）
- `message.role=toolResult` → 工具返回结果
- `message.role=assistant` + `content[].type=text` → LLM 输出文本
- `type=custom` + `customType=openclaw:prompt-error` → 执行被中断（超时/abort）

## 分析流程

### Step 1 — 选择分析目标

用户可能指定：
- 任务名（如 `clawcoach-progress-10m`）
- 最近 N 次执行
- 特定时间段
- 只看失败的

如果用户未指定，默认分析**所有启用的 cron job 的最近 5 次执行**。

从 `jobs.json` 读取 job 配置，找到对应的 runs 文件。

### Step 2 — 运行历史概览

使用分析脚本生成概览：

```bash
python3 ~/.openclaw/workspace/skills/cron-log-review/scripts/analyze_runs.py --job {job-name} --last {N}
```

脚本输出：
- 最近 N 次执行的状态、耗时、token 用量表格
- 超时/错误次数统计
- 耗时趋势（是否在恶化）
- Token 用量异常（哪次特别高）

**关注指标：**
- 耗时 > 超时上限 80% → 超时风险
- input_tokens 波动 > 2x → prompt 膨胀
- 连续 error → 系统性问题

### Step 3 — 深入分析问题执行

对 Step 2 标记的异常执行，拉取 session 详情：

```bash
python3 ~/.openclaw/workspace/skills/cron-log-review/scripts/analyze_runs.py --job {job-name} --session {session-id} --steps
```

脚本输出每个 tool call 的：
- 序号、工具名、参数摘要
- 返回数据大小（chars）
- 是否为重复调用

**分析维度：**

1. **执行阶段划分**：把 tool calls 按逻辑分为环境探测 / 信号读取 / 判断决策 / 执行动作 / 报告输出
2. **冗余检测**：同一文件被 read 多次、同一命令重复执行、环境探测类命令（ls、git remote、echo $VAR）
3. **数据膨胀点**：哪个 tool result 返回数据量最大（> 5K chars）
4. **失败后重试**：dispatch 失败后的行为是否合理
5. **被中断位置**：超时时执行到了哪一步

### Step 4 — 输出分析报告

按以下结构输出：

```
## 运行概览
最近 {N} 次执行统计表格

## 发现的问题
按严重程度排序：
- P0: 导致超时/错误的问题
- P1: 显著影响效率的问题
- P2: 可优化但不紧急的问题

## 优化建议
每个问题对应具体的修改建议，标明：
- 改什么文件
- 预期效果（节省多少步骤/token/时间）

## 趋势观察
耗时和 token 用量是否在恶化？是否有周期性模式？
```
