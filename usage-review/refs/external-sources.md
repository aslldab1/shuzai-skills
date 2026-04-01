# 外部经验来源搜索策略

## 搜索方法

### Anthropic Engineering Blog
- 使用 WebFetch 抓取 https://www.anthropic.com/engineering
- 关注关键词：Claude Code, best practices, workflow, tips, productivity
- 提取最近 30 天内的相关文章

### Reddit r/ClaudeAI
- 使用 WebSearch 搜索：`site:reddit.com/r/ClaudeAI Claude Code tips OR workflow OR best practices`
- 按最近 7 天排序
- 关注高赞帖子（upvotes > 20）和有深度的实践分享

### OpenAI Codex Community
- 使用 WebFetch 抓取 https://community.openai.com/c/codex/37?ascending=false&order=views
- 虽然是 Codex 社区，但 AI coding agent 的通用经验可跨工具借鉴
- 关注：context management, prompt engineering, workflow optimization

## 搜索关键词

按优先级排列：
1. `Claude Code workflow optimization` — 直接相关
2. `AI coding assistant best practices 2026` — 通用最佳实践
3. `context window management AI coding` — 上下文管理
4. `AI agent tool usage patterns` — 工具使用模式
5. `Claude Code CLAUDE.md tips` — 配置优化

## 输出要求

每个来源提取 2-5 条最相关的洞察，每条包含：
- **title**: 文章/帖子标题
- **url**: 原始链接
- **summary**: 50 字以内的关键要点
- **source**: 来源名称（Anthropic / Reddit / OpenAI Community）
- **relevance**: 与用户当前使用模式的关联度（high/medium/low）
