# 进度确认

## 触发条件

Step 1 检测到 `in-progress` Issue 满足以下条件，标记为"待确认"：
- 无完成信号（无 `【CLAUDE】【完成】` 或 `【CODEX】【完成】` 评论）
- 最后活动时间（Issue 最新评论 或 分支最新 commit，取较新者）距今 > 20 分钟

Step 2-P2（owner/claude）或 Step 3-P2（owner/codex）检测到"待确认"时，执行本流程。

**前置检查**：worker pane 必须 IDLE 才发确认消息。若仍 BUSY，跳过本轮（说明 worker 在工作，活动时间戳可能未刷新到 Issue）。

## 派发消息格式

```
【OPENCLAW】【进度确认】
Issue #{N}：{Issue标题}

距上次活动已超过 20 分钟，未检测到完成信号。
请描述当前进度，并在 Issue 中回复。

如已完成，请补写完成信号：
【CLAUDE】【完成】PR #{pr_number} related to #{N}
（纯文档/设计任务无 PR 时：【CLAUDE】【完成】无 PR，产出已在 Issue 评论中）
```

## openclaw 后续动作

下轮 Step 1 读取 Issue 最新评论，LLM 综合判断 worker 回复的含义并路由：

| 判断结论 | 动作 |
|---------|------|
| 含完成信号 `【CLAUDE/CODEX】【完成】` | 正常推进状态 |
| 回复表示仍在进行、给出进度说明 | 更新最后活动时间戳，继续等待 |
| 回复表示遇到阻塞、无法继续 | label 加 `owner/shuzai`，Feishu 通知 HUMAN |
| 超过 1 小时无任何回复 | Feishu 通知 HUMAN（worker 可能彻底卡死） |

## 注意

- 同一个 Issue 不重复发确认消息：检查最近评论中是否已有未回复的 `【OPENCLAW】【进度确认】`，有则跳过
- 进度确认消息本身会刷新最后活动记录，避免下轮重复触发
