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

每轮执行固定 5 步，按顺序执行，不跳步。

### Step 1：收集本地使用数据（OpenClaw）

```bash
DATETIME=$(date +%Y%m%d_%H%M)
SKILL_DIR=~/workspace/AI/git/shuzai-skills/usage-review
python3 $SKILL_DIR/scripts/collect_usage_data.py \
  --days 7 \
  --output $SKILL_DIR/data/usage_data_${DATETIME}.json
```

产出：`usage_data.json`，包含以下维度：
- **history**: 总输入数、会话数、项目分布、每日活跃度、Slash 命令使用
- **tools**: 工具调用分布、Bash/专用工具/Agent 比率、按项目和日期的工具使用
- **costs**: Token 用量、费用趋势、模型使用分布
- **compactions**: 上下文压缩次数和趋势
- **projects**: 活跃项目元数据
- **sessions**: 会话文件统计

### Step 2：历史感知 + 搜索规划（Claude）

1. 读取 `usage-review/data/` 下所有 `insights_*.json` 文件，汇总历史建议：
   ```bash
   ls ~/workspace/AI/git/shuzai-skills/usage-review/data/insights_*.json 2>/dev/null
   ```
   对每个文件，提取 `recommendations[].title` 和 `recommendations[].description`。

2. 构建 **已覆盖话题清单**：将历史建议按方向归类（如"工具使用"、"会话管理"、"并行能力"、"配置优化"等），记录每个方向被推荐的次数。

3. 对比 Step 1 的 `usage_data.json`，识别 **本周关注方向**：
   - 偏离健康范围（参见 refs/analysis-framework.md）且历史推荐次数最少的指标 → 优先
   - 历史推荐过但指标恶化的方向 → 可换角度再推
   - 历史推荐过且指标已达标的方向 → 排除

4. 基于本周关注方向，动态生成 **5 个搜索关键词**，规则参见 → [refs/external-sources.md](refs/external-sources.md)

产出：已覆盖话题清单 + 5 个搜索关键词（不写文件，作为上下文传递给 Step 3）。

### Step 3：搜索外部资料（Claude）

使用 Step 2 产出的 5 个搜索关键词执行搜索。搜索来源不变，但关键词由 Step 2 动态决定。

从以下来源搜索最新的 AI 辅助编程经验和最佳实践：

| 来源 | URL | 搜索重点 |
|------|-----|---------|
| Anthropic Engineering | https://www.anthropic.com/engineering | Claude Code 官方最佳实践、新功能 |
| Reddit r/ClaudeAI | https://www.reddit.com/r/ClaudeAI/ | 社区使用技巧、工作流分享 |
| OpenAI Codex Forum | https://community.openai.com/c/codex/37 | AI coding agent 通用经验（跨工具借鉴） |

搜索策略参见 → [refs/external-sources.md](refs/external-sources.md)

产出：结构化的最佳实践摘要，包含来源 URL 和关键洞察。

### Step 4：对比分析并生成建议（Claude）

将 Step 1 的使用数据与 Step 3 的外部资料对比，从以下维度分析：

分析框架参见 → [refs/analysis-framework.md](refs/analysis-framework.md)

**去重：** Step 2 已完成历史建议分析。本步骤直接使用 Step 2 的已覆盖话题清单，遵守以下规则：
- 已覆盖且指标达标的方向 → 在 strengths 中作为「已改善」提及，不再推荐
- 已覆盖但指标恶化的方向 → 从新角度推荐（不同的切入点和操作建议）
- 未覆盖的方向 → 优先推荐
- 每条建议必须包含结构化 `playbook` 字段（含 `steps`、`before_after`、`measure`），由 Claude 基于外部资料和使用数据动态生成，不使用预设模板。`playbook` 是报告渲染 Playbook: step-by-step 折叠面板的数据源，缺失则报告无法展示操作手册

产出：`insights_<DATETIME>.json`，写入 `usage-review/data/insights_<DATETIME>.json`（DATETIME 格式 YYYYMMDD_HHmm，与 Step 1 的变量一致），格式：

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
      "your_value": "用户当前指标值（如 Bash 55.8%）",
      "best_practice": "最佳实践目标值（如 <40%）",
      "playbook": {
        "steps": [
          {
            "do": "步骤描述",
            "example": "示例命令或代码（可选）",
            "expect": "预期结果（可选）"
          }
        ],
        "before_after": {
          "before": "改进前的典型做法",
          "after": "改进后的推荐做法"
        },
        "measure": "衡量标准：如何确认改进生效"
      }
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

### Step 5：生成报告并通知（OpenClaw + Claude）

1. 生成 HTML 报告：

```bash
DATETIME=$(date +%Y%m%d_%H%M)
SKILL_DIR=~/workspace/AI/git/shuzai-skills/usage-review
python3 $SKILL_DIR/scripts/generate_report.py \
  --data $SKILL_DIR/data/usage_data_${DATETIME}.json \
  --insights $SKILL_DIR/data/insights_${DATETIME}.json \
  --output $SKILL_DIR/data/report_${DATETIME}.html
```

2. 发送飞书通知（链接指向 index.html 并通过 hash 定位到当前报告）：

```bash
SKILL_DIR=~/workspace/AI/git/shuzai-skills/usage-review
openclaw message send --channel feishu --target "ou_c5bd4c88f78cbf338f76dbb5e8f64fed" \
  -m "【Claude Code 周报】报告已生成，查看: file:///${SKILL_DIR}/data/index.html#report_${DATETIME}.html"
```

## 数据隐私

- 所有数据处理在本地完成，不上传任何代码或会话内容
- 外部搜索仅用于获取公开的最佳实践文章
- 报告和数据存储在本地 `data/` 目录，按日期归档
