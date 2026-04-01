# 进度确认

## 触发条件

Step 1 检测到 `in-progress` Issue 满足以下条件，标记为"待确认"：
- 无完成信号（无 `【CLAUDE】【完成】` 或 `【CODEX】【完成】` 评论）
- 最后活动时间（Issue 最新评论 或 分支最新 commit，取较新者）距今 > 20 分钟

Step 2-P5 检测到"待确认"时，执行本流程（不区分 owner/claude 或 owner/codex）。

**前置检查**：Claude pane 必须 IDLE 才发确认消息。若 Claude 仍 BUSY，跳过本轮（说明 Claude 在工作，活动时间戳可能未刷新到 Issue）。

## 派发消息格式

**owner/claude 的 stale 任务：**
```
【OPENCLAW】【进度确认】
Issue #{N}：{Issue标题}

距上次活动已超过 20 分钟，未检测到完成信号。
请描述当前进度，并在 Issue 中回复。

如已完成，请补写完成信号：
【CLAUDE】【完成】PR #{pr_number} related to #{N}
（纯文档/设计任务无 PR 时：【CLAUDE】【完成】无 PR，产出已在 Issue 评论中）

⚠️ 只需在 Issue 评论中回复进度或补写完成信号。禁止执行 gh issue edit / gh issue close —— 状态推进由 openclaw 自动处理。
```

**owner/codex 的 stale 任务（Claude 通过插件检查）：**
```
【OPENCLAW】【进度确认】
Issue #{N}：{Issue标题}（Codex 实现任务）

距上次活动已超过 20 分钟，未检测到完成信号。
请通过 Codex 插件检查任务状态（/codex:status 或 codex:codex-rescue agent），确认 Codex 是否仍在执行。

- 如 Codex 仍在执行：在 Issue 评论回复当前进度
- 如 Codex 已完成：验证结果并补写完成信号 `【CODEX】【完成】PR #{pr_number} related to #{N}`
- 如 Codex 失败或卡住：重新通过插件派发任务

⚠️ 禁止执行 gh issue edit / gh issue close —— 状态推进由 openclaw 自动处理。
```

## 派发丢失检测（进度确认前置检查）

在发送进度确认消息**之前**，先检查 Claude pane 中是否有该 Issue 的执行痕迹：

```
tmux capture-pane -p -t {claude_pane} -S -200 2>/dev/null | grep -c "Issue #{N}\|issue-{N}\|#{N}"
```

| 检测结果 | 含义 | 动作 |
|---------|------|------|
| 匹配数 > 0 | Claude 收到过任务，可能卡住了 | 正常发送进度确认消息 |
| 匹配数 = 0 | **派发可能未送达**（tmux 发送失败、会话重建等） | **跳过进度确认，改为重新派发完整任务消息**（按 refs/task-dispatch.md 格式，走完整派发流程的第 3 步 tmux_dispatch，第 1、2 步已在之前完成不需重复） |

重新派发时在 Issue 写 【OPENCLAW】 评论说明：
```
【OPENCLAW】检测到 worker 可能未收到任务消息，重新派发。
```

> **注意：** 重新派发只补做 tmux_dispatch（第 3 步），不重复写派发评论和改 label（这些在原始派发时已完成）。

## openclaw 后续动作

下轮 Step 1 读取 Issue 最新评论，LLM 综合判断 Claude 回复的含义并路由：

| 判断结论 | 动作 |
|---------|------|
| 含完成信号 `【CLAUDE/CODEX】【完成】` | 正常推进状态 |
| 回复表示仍在进行、给出进度说明 | 更新最后活动时间戳，继续等待 |
| 回复表示不清楚该任务、未收到过任务 | **重新派发完整任务消息**（同上方派发丢失处理） |
| 回复表示遇到阻塞、无法继续 | label 加 `owner/shuzai`，Feishu 通知 HUMAN |
| 超过 1 小时无任何回复 | Feishu 通知 HUMAN（Claude 可能彻底卡死） |

## 注意

- 同一个 Issue 不重复发确认消息：检查最近评论中是否已有未回复的 `【OPENCLAW】【进度确认】`，有则跳过
- 进度确认消息本身会刷新最后活动记录，避免下轮重复触发
