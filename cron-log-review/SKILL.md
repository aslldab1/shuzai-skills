---
name: cron-log-review
description: 分析 openclaw cron 定时任务的执行日志，重点检查状态推进错误和流程执行问题。
---

# Cron Log Review

## 背景

openclaw 通过定时任务（cron job）每 10 分钟执行 `coding-team-loop` skill，自动编排双 worker（Claude + Codex）协同开发：
- 读取 GitHub Issues 状态和 worker 工作进度
- 按优先级规则派发任务给 Claude（设计/review/验收）或 Codex（实现）
- 推进 Issue 状态流转（pending → in-progress → needs-review → verifying → verified）
- 与 HUMAN 交互 review 产出

每轮执行涉及多步 LLM 判断和 GitHub 操作，容易出现：
- **状态推进错误**：把 Issue 推到了错误的状态（如任务还在执行就被标为完成）
- **误派发**：把任务派给了错误的 worker，或重复派发
- **漏处理**：应该触发的动作没有执行
- **超时**：执行步骤过多导致超过时间上限

## 用途

拉取定时任务的运行日志和 session 详情，**首要目标是发现执行逻辑错误**，其次是性能优化：

1. **状态推进是否正确** — label 变更是否符合 coding-team-loop 规则，有没有跳步或错误推进
2. **派发决策是否合理** — 选择了正确的优先级分支吗，派给了正确的 worker 吗
3. **操作顺序是否正确** — 先写评论再改 label、先判断忙碌再派发等
4. **超时和错误原因** — 卡在哪一步，为什么
5. **执行效率** — 冗余步骤、数据膨胀、token 浪费

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

1. **状态推进正确性**（最重要）：
   - 提取所有 `gh issue edit --add-label / --remove-label` 调用，还原 label 变更链
   - 对照 coding-team-loop 规则验证每次 label 变更是否合法：
     - `pending → in-progress`：必须在派发动作之后
     - `in-progress → needs-review`：必须检测到 `【CODEX】【完成】` 信号
     - `in-progress → verifying`：必须检测到 `【CLAUDE】【完成】` 信号
     - `verifying → pending`：必须有 HUMAN 反馈（owner/shuzai 流程）
     - `changes-requested → needs-review`：必须 PR 有新 commit
   - 标记违规的状态推进为 P0 问题
2. **派发决策合理性**：
   - 提取 `tmux_dispatch.sh` 调用和 `gh issue comment` 中的派发消息
   - 验证：是否选了正确的优先级分支（P1 > P2 > ... ），派给了正确的 worker
   - 检查是否有重复派发（同一 Issue 在同一轮被派发两次）
3. **操作顺序**：
   - 派发前是否先做了 busy_check
   - label 变更前是否先写了 【OPENCLAW】 评论
   - dispatch 失败后是否回滚了 label
4. **busy_check 交叉验证**（P0 级别）：
   - 将 busy_check 脚本返回值与 pane 实际输出内容做对比
   - 如果 pane 中有明显活动迹象（thinking、Running、工具调用输出、生成中等）但 busy_check 返回 IDLE → P0 问题（脚本漏检导致误派发风险）
   - 如果 pane 无活动但 busy_check 返回 BUSY → P1 问题（脚本误判导致任务延迟）
   - 检查方式：对比 `tmux capture-pane` 原始输出与 busy_check.sh 返回值，不能只看脚本返回值就下结论
5. **执行阶段划分**：把 tool calls 按逻辑分为环境探测 / 信号读取 / 判断决策 / 执行动作 / 报告输出
5. **冗余检测**：同一文件被 read 多次、同一命令重复执行、环境探测类命令（ls、git remote、echo $VAR）
6. **数据膨胀点**：哪个 tool result 返回数据量最大（> 5K chars）
7. **被中断位置**：超时时执行到了哪一步

### Step 4 — 输出分析报告

按以下结构输出：

```
## 运行概览
最近 {N} 次执行统计表格

## 状态推进审计
列出本轮所有 label 变更，逐条标注：
- ✅ 合规 — 符合 coding-team-loop 规则
- ❌ 违规 — 不符合规则，说明预期行为和实际行为的差异
- ⚠️ 可疑 — 规则允许但上下文不合理（如 worker 还在忙就改了状态）

## 派发决策审计
列出本轮派发动作，验证优先级选择和 worker 分配是否正确

## 发现的问题
按严重程度排序：
- P0: 状态推进错误、误派发（影响任务正确性）
- P1: 超时/执行失败（影响任务完成）
- P2: 效率问题（冗余步骤、数据膨胀）

## 优化建议
每个问题对应具体的修改建议，标明：
- 改什么文件（SKILL.md / refs/*.md / scripts/）
- 预期效果

## 趋势观察
耗时和 token 用量是否在恶化？是否有周期性模式？
```
