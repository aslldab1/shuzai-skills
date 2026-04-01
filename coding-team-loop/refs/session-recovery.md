# Session 恢复

## Stale In-Progress 处理

**已由 refs/progress-confirm.md 接管。**

Step 1 检测 `in-progress` + 20 分钟无活动 → 标记为"待确认"，Step 2 向 Claude 发送进度确认消息，由 Claude 回复决定后续动作。不再自动 reset label。

## Claude 会话缺失

```bash
tmux has-session -t {claude-session} 2>/dev/null || echo "missing"
```

重建步骤：
1. `tmux new-session -d -s {claude-session} -c {project-dir}`
2. `tmux send-keys -t {claude-session} "claude" Enter`
3. 等待启动完成（pane 出现 `❯` 提示符）
4. 从 Step 1 重新开始当轮
