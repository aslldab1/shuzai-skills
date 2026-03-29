# Human Handoff（人工介入流转）

## 触发条件

Step 1 完成后、Step 2 之前：扫描所有含 `owner/shuzai` 的 open Issue。

## 执行逻辑

### 1. 检查最新评论是谁写的

```bash
gh issue view {N} --json comments --jq '.comments | last'
```

| 最新评论情况 | 动作 |
|------------|------|
| 无评论 | 跳过，继续等 HUMAN |
| 以 `【OPENCLAW】` 或 `【CLAUDE】` 或 `【CODEX】` 开头 | 跳过（系统已回复，等 HUMAN 再次操作）|
| 无系统前缀（HUMAN 写的） | 视为新反馈，执行下方流程 |

### 2. 处理人工反馈

1. 从评论历史中找最近一条含"owner 切换为 owner/shuzai"的 `【OPENCLAW】` 评论，提取切换前的 owner
2. Issue label：当前状态 → `pending`，owner 恢复为上一个 owner
3. 留 `【OPENCLAW】` 评论，记录已接收反馈并重置，引用 HUMAN 的评论原文
4. 下轮派发时，HUMAN 评论原文作为补充上下文带入 Task Brief（带人工反馈格式）

### 3. Feishu 通知

- 本轮该 Issue 状态发生变化（刚转入 `owner/shuzai`）→ 发通知
- 状态未变化且 hash 不变 → 不重复通知

## 约束

- `owner/shuzai` 的 Issue **不进入 Step 2 / Step 3 的派发逻辑**
- 本步骤处理完后才进入 Step 2
