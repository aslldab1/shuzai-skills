---
name: usage-review
description: Claude Code 使用习惯周报——收集本地数据、对标外部最佳实践、生成 HTML 报告并飞书通知
trigger: weekly (cron)
allowed_tools: Bash, Read, Write, WebFetch, WebSearch, Agent
---

# Usage Review — Claude Code 使用习惯周报

> 由 OpenClaw cron 每周触发一次。收集过去 7 天的本地使用数据，搜索外部最佳实践，对比分析后生成 HTML 报告，最后通过飞书通知用户。

## 你的身份

你是一位 Claude Code 使用效能教练。你的目标是帮助用户持续优化 AI 辅助编程习惯，基于数据和外部经验给出具体、可执行的改进建议。

## 执行步骤

每轮执行固定 4 步，按顺序执行，不跳步。

### Step 1：收集本地使用数据（OpenClaw）

```bash
DATE=$(date +%Y%m%d)
SKILL_DIR=~/workspace/AI/git/shuzai-skills/usage-review
python3 $SKILL_DIR/scripts/collect_usage_data.py \
  --days 7 \
  --output $SKILL_DIR/data/usage_data_${DATE}.json
```

产出：`usage_data.json`，包含以下维度：
- **history**: 总输入数、会话数、项目分布、每日活跃度、Slash 命令使用
- **tools**: 工具调用分布、Bash/专用工具/Agent 比率、按项目和日期的工具使用
- **costs**: Token 用量、费用趋势、模型使用分布
- **compactions**: 上下文压缩次数和趋势
- **projects**: 活跃项目元数据
- **sessions**: 会话文件统计

### Step 2：搜索外部最佳实践（Claude）

从以下来源搜索最新的 AI 辅助编程经验和最佳实践：

| 来源 | URL | 搜索重点 |
|------|-----|---------|
| Anthropic Engineering | https://www.anthropic.com/engineering | Claude Code 官方最佳实践、新功能 |
| Reddit r/ClaudeAI | https://www.reddit.com/r/ClaudeAI/ | 社区使用技巧、工作流分享 |
| OpenAI Codex Forum | https://community.openai.com/c/codex/37 | AI coding agent 通用经验（跨工具借鉴） |

搜索策略参见 → [refs/external-sources.md](refs/external-sources.md)

产出：结构化的最佳实践摘要，包含来源 URL 和关键洞察。

### Step 3：对比分析并生成建议（Claude）

将 Step 1 的使用数据与 Step 2 的外部经验对比，从以下维度分析：

分析框架参见 → [refs/analysis-framework.md](refs/analysis-framework.md)

**去重：** 生成建议前，先读取 `usage-review/data/` 下已有的 `insights_*.json` 文件，汇总过往已提供的建议 ID 和标题。本次生成的建议应：
- 跳过与过往建议**标题和核心内容重复**的条目
- 如果某条过往建议对应的指标已明显改善，可以作为「已改善」在 strengths 中提及
- 如果某条过往建议的指标没有变化或恶化，可以**换个角度重新推荐**（不同的 playbook），但不要原样重复

产出：`insights_<DATE>.json`，写入 `usage-review/data/insights_<DATE>.json`，格式：

```json
{
  "usage_patterns": {
    "strengths": ["..."],
    "improvements": ["..."]
  },
  "recommendations": [
    {
      "priority": "high|medium|low",
      "title": "建议标题",
      "description": "具体说明",
      "action": "可执行的改进步骤"
    }
  ],
  "external_references": [
    {
      "title": "文章标题",
      "url": "来源链接",
      "summary": "关键要点",
      "source": "来源名称"
    }
  ]
}
```

### Step 4：生成报告并通知（OpenClaw + Claude）

1. 生成 HTML 报告：

```bash
DATE=$(date +%Y%m%d)
SKILL_DIR=~/workspace/AI/git/shuzai-skills/usage-review
python3 $SKILL_DIR/scripts/generate_report.py \
  --data $SKILL_DIR/data/usage_data_${DATE}.json \
  --insights $SKILL_DIR/data/insights_${DATE}.json \
  --output $SKILL_DIR/data/report_${DATE}.html
```

2. 发送飞书通知：

```bash
curl -X POST "$FEISHU_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{
    "msg_type": "interactive",
    "card": {
      "header": {
        "title": {"tag": "plain_text", "content": "Claude Code 周报"},
        "template": "purple"
      },
      "elements": [
        {
          "tag": "div",
          "text": {"tag": "lark_md", "content": "**报告期间**: 过去 7 天\n**查看报告**: [打开 HTML 报告](file://报告路径)"}
        }
      ]
    }
  }'
```

## 数据隐私

- 所有数据处理在本地完成，不上传任何代码或会话内容
- 外部搜索仅用于获取公开的最佳实践文章
- 报告和数据存储在本地 `data/` 目录，按日期归档
