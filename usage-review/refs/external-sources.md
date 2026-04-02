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

## 搜索关键词（由 Step 2 动态生成）

关键词不再固定，由 Step 2 基于历史感知动态生成。生成规则：

1. **从关注方向到关键词**：Step 2 识别出的本周关注方向（如"hooks自动化"、"模型选择策略"），转换为英文搜索词
2. **拼接搜索模板**：`Claude Code {关注方向}` 或 `AI coding {关注方向} best practices`
3. **排除规则**：历史已覆盖 ≥ 2 次且指标已达标的方向，不生成对应关键词
4. **保底机制**：如果动态生成不足 5 个，用 `Claude Code new features {当前年月}` 和 `AI coding agent workflow {当前年月}` 补齐，确保搜到时效性内容
5. **数量**：每次固定生成 5 个关键词

示例（假设历史已覆盖"降Bash比率"和"Agent并行"，本周数据显示压缩率偏高、无 hooks 使用）：
1. `Claude Code context compaction optimization` — 压缩率偏高，历史未覆盖
2. `Claude Code hooks automation workflow` — 无 hooks 使用，历史未覆盖
3. `AI coding agent session management 2026` — 会话指标偏离，历史覆盖 1 次可换角度
4. `Claude Code new features April 2026` — 保底：时效性
5. `AI coding assistant cost optimization` — 成本趋势上升，历史未覆盖

## 输出要求

每个来源提取 2-5 条最相关的洞察，每条包含：
- **title**: 文章/帖子标题
- **url**: 原始链接
- **summary**: 50 字以内的关键要点
- **source**: 来源名称（Anthropic / Reddit / OpenAI Community）
- **relevance**: 与用户当前使用模式的关联度（high/medium/low）
