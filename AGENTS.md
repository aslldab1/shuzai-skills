# shuzai-skills

本仓库存放用户级自定义 Claude Code Skills，每个 skill 是一个子目录，包含 `SKILL.md`。

## 目录结构

```
shuzai-skills/
├── AGENTS.md               # 本文件，说明安装规则
├── coding-team-loop/       # OpenClaw 双 worker 开发循环 skill
│   └── SKILL.md
├── cron-log-review/        # OpenClaw cron 定时任务日志分析 skill
│   └── SKILL.md
└── stitch-prototype/       # Google Stitch 产品原型设计 skill
    └── SKILL.md
```

## 安装规则

**使用软连接方式安装**，不要用 `cp` 复制，否则 skill 更新后无法同步：

```bash
# 安装单个 skill（用户级，所有会话可用）
ln -s /Users/lin/workspace/AI/git/shuzai-skills/<skill-name> ~/.claude/skills/<skill-name>

# 查看已安装的 skill
ls -la ~/.claude/skills/
```

新增 skill 后，在此文件的目录结构中补充说明，并按上述命令安装软连接。

## 已安装 Skills

| Skill | 触发命令 | 说明 |
|-------|---------|------|
| stitch-prototype | `/stitch-prototype` | 使用 Google Stitch MCP 进行产品原型设计，包含需求确认、Screen 生成、验收交付全流程 |
| coding-team-loop | `/coding-team-loop` | OpenClaw 协调 Claude + Codex 双 worker 开发循环，以 GitHub Issues 为任务数据库 |
| cron-log-review | `/cron-log-review` | 分析 OpenClaw cron 定时任务的执行日志，重点检查状态推进错误和流程执行问题 |
