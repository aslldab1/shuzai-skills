# Evals 使用指南

## 全量验证（改动后必跑）

```bash
cd ~/.openclaw/workspace/skills/coding-team-loop/evals
python3 run_all_tests.py          # 全量测试
python3 run_all_tests.py -v       # 详细输出
```

| 文件 | 用途 |
|------|------|
| `run_all_tests.py` | 统一入口，运行所有测试模块 |
| `test_busy_detection.py` | 忙碌检测正则的正确性验证 |
| `parse-run.py` | 分析 cron 执行日志（诊断工具，非测试） |

**新增测试文件时**：在 `run_all_tests.py` 的 `TEST_MODULES` 列表中注册。

---

# 执行日志分析流程

## 概述

每次定时任务触发后，openclaw 会生成两层日志：

| 层级 | 路径 | 内容 |
|------|------|------|
| 轮次摘要 | `~/.openclaw/cron/runs/<jobId>.jsonl` | 每轮完成后的结果（status、summary、耗时、token） |
| 执行详情 | `~/.openclaw/agents/main/sessions/<sessionId>.jsonl` | 完整的工具调用链（tool_use + tool_result） |

两层日志通过 `sessionId` 关联。

---

## 快速分析（推荐）

```bash
cd ~/.openclaw/workspace/skills/coding-team-loop/evals
python3 parse-run.py              # 分析最近一次
python3 parse-run.py --run 2      # 分析倒数第 2 次
python3 parse-run.py --raw        # 输出完整工具调用内容
```

---

## 手动分析步骤

### Step 1：找到 jobId

```bash
cat ~/.openclaw/cron/jobs.json | python3 -c "
import sys, json
data = json.load(sys.stdin)
jobs = data.get('jobs', data) if isinstance(data, dict) else data
if isinstance(jobs, dict):
    jobs = list(jobs.values())
for job in jobs:
    if isinstance(job, dict):
        print(job.get('id'), job.get('name'))
"
```

### Step 2：查看最近几轮概览

```bash
tail -10 ~/.openclaw/cron/runs/<jobId>.jsonl | python3 -c "
import sys, json, datetime
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    e = json.loads(line)
    dt = datetime.datetime.fromtimestamp(e['ts']/1000).strftime('%H:%M:%S')
    dur = e.get('durationMs',0)/1000
    status = e.get('status','?')
    delivery = e.get('deliveryStatus','-')
    err = e.get('error','')
    summary_first = (e.get('summary','') or '').split('\n')[0][:40]
    print(f'{dt} | {status:8} | {dur:6.1f}s | {delivery:15} | {err or summary_first}')
"
```

### Step 3：查看最近一轮详情

```bash
tail -1 ~/.openclaw/cron/runs/<jobId>.jsonl | python3 -c "
import sys, json, datetime
obj = json.loads(sys.stdin.read())
ts = datetime.datetime.fromtimestamp(obj['ts']/1000).strftime('%Y-%m-%d %H:%M:%S')
print(f'时间:      {ts}')
print(f'状态:      {obj.get(\"status\")}')
print(f'耗时:      {obj.get(\"durationMs\",0)/1000:.1f}s')
print(f'sessionId: {obj.get(\"sessionId\")}')
print(f'错误:      {obj.get(\"error\",\"无\")}')
print()
print(obj.get('summary','（无摘要）'))
"
```

---

## 执行流程分析要点

拿到工具调用链后，逐步核对：

### 1. Step 1 信号读取是否完整

- 是否查询了所有 open Issues 及其 label
- 是否扫描了 open PR body 中的 closes/fixes 关键字
- 是否检测了 stale in-progress Issue
- 是否抓取了 Claude/Codex pane 状态

### 2. PR 关联是否正确推进

- 若 Codex 提了 PR（body 含 closes #N），Issue label 是否自动从 in-progress → needs-review
- 若 PR 最新提交时间 > review 时间，是否自动从 changes-requested → needs-review

### 3. Worker 忙碌判断是否准确

- 忙碌判断结果与实际 pane 内容是否吻合
- 是否有误判导致跳过了本应执行的派发

### 4. 派发是否成功

重点看 `tmux_dispatch.sh` 的返回值：
- `dispatch=submitted` → 正常
- `dispatch=failed reason=no_ack` → 发送失败，检查连续失败计数

### 5. Issue label 转换是否正确

对照流程中的每次 label 变更，确认转换时机和方向正确。

### 6. 自愈是否触发

- stale in-progress 检测是否准确
- 有分支的情况是否正确标记为待恢复而非直接重置

---

## 常见问题模式

| 问题 | 表现 | 对应规则 |
|------|------|---------|
| PR 提了但 Issue 还是 in-progress | Step 1 未扫描 PR body，或关键字格式不对 | 检查 PR body 是否有 closes #N |
| 派发失败但摘要报成功 | dispatch=failed 后仍写"投递成功" | 检查 no_ack 后的处理逻辑 |
| stale 检测误触发 | worker 实际忙碌但被判断为空闲 | 检查 pane 抓取的行数和 …ing 匹配规则 |
| 同一 Issue 重复派发 | 连续多轮都向同一 worker 派发 | 检查 in-progress label 是否正确设置 |
| 路由 Issue 后次轮又路由 | P4 路由后 label 未更新 | 确认路由后 owner label 已写入 GitHub |
