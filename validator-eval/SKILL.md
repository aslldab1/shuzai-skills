---
name: validator-eval
description: 评测 validator skill 的执行质量。分析 cron 执行日志，检查验收流程是否遵循三阶段方法论、是否真正分析截图、是否覆盖用户旅程。
---

# Validator Eval — 验收质量评测

## 背景

openclaw 通过定时任务（cron job）派发 `validator` skill，自动对 Issue 交付物进行多维度验收：
- Phase A：视觉扫描 + 首印象（不点击、只看）
- Phase B：用户旅程走通（站在用户角度操作）
- Phase C：系统性交互测试（补充覆盖）

每轮执行涉及 Playwright 浏览器操作、截图分析、用户旅程评估等，容易出现：
- **形式主义验收**：截了图但没分析，走了流程但没发现问题
- **阶段缺失**：跳过 Phase A 直接测功能，或跳过 Phase B 没走用户旅程
- **视觉盲区**：只用 DOM snapshot 推断，不分析截图中的视觉问题
- **旅程缺失**：没有在 Step 1 定义用户旅程，或定义了但没按旅程走
- **严格性不足**：对明显问题只给 WARN 不给 FAIL，违反严格性标尺
- **超时低效**：步骤冗余导致超过 15 分钟时间预算

## 用途

拉取 validator 定时任务的运行日志和 session 详情，**首要目标是评估验收质量**，其次是执行效率：

1. **三阶段执行完整性** — Phase A/B/C 是否都执行了，顺序是否正确
2. **截图分析质量** — 截图后是否有分析文本，还是只截图不分析
3. **用户旅程覆盖度** — Step 1 是否定义了旅程，Phase B 是否按旅程执行
4. **视觉检测能力** — 是否发现了布局、间距、对齐、溢出等视觉问题
5. **严格性评估** — FAIL/WARN/PASS 判定是否符合六条铁律和严格性标尺
6. **执行效率** — 阶段时间分配、冗余步骤、超时风险

## 数据源

### 1. 任务配置

```bash
cat ~/.openclaw/cron/jobs.json
```

字段说明：
- `id` — job UUID（validator job: `905d36b2-7b50-423f-84d8-571a030bd5e5`）
- `name` — 任务名
- `payload.timeoutSeconds` — 超时上限
- `state.lastRunStatus` — 最近一次状态（ok/error）
- `state.lastDurationMs` — 最近一次耗时
- `state.consecutiveErrors` — 连续错误次数

### 2. 运行历史

```bash
# 每个 job 一个 JSONL 文件，每行是一次执行记录
~/.openclaw/cron/runs/905d36b2-7b50-423f-84d8-571a030bd5e5.jsonl
```

每行字段：
| 字段 | 说明 |
|------|------|
| `ts` | 完成时间戳（ms） |
| `status` | `ok` 或 `error` |
| `error` | 错误原因（超时时为 `cron: job execution timed out`） |
| `durationMs` | 执行耗时 |
| `usage.input_tokens` | 输入 token 数 |
| `usage.output_tokens` | 输出 token 数 |
| `sessionId` | 对应 session 文件名 |
| `summary` | 执行摘要 |

### 3. Session 详情

```bash
# 每次执行的完整 tool call 记录
~/.openclaw/agents/main/sessions/{session-id}.jsonl
```

JSONL 格式，`type=message` 的行包含实际交互：
- `message.role=assistant` + `content[].type=toolCall` → 工具调用（name + arguments）
- `message.role=toolResult` → 工具返回结果
- `message.role=assistant` + `content[].type=text` → LLM 输出文本
- `type=custom` + `customType=openclaw:prompt-error` → 执行被中断（超时/abort）

## 分析流程

### Step 1 — 选择分析目标

用户可能指定：
- 最近 N 次执行
- 特定时间段
- 只看失败的
- 特定 session

如果用户未指定，默认分析**最近 5 次执行**。

从 `jobs.json` 读取 job 配置，找到对应的 runs 文件。

### Step 2 — 运行历史概览

使用分析脚本生成概览：

```bash
python3 scripts/analyze_runs.py --last {N}
```

脚本输出：
- 最近 N 次执行的状态、耗时、token 用量表格
- 超时/错误次数统计
- 耗时趋势（是否在恶化）
- Token 用量异常（哪次特别高）
- 截图数量统计（每次执行拍了多少截图）

**关注指标：**
- 耗时 > 超时上限 80% → 超时风险
- input_tokens 波动 > 2x → prompt 膨胀
- 连续 error → 系统性问题
- 截图数 < 5 → 可能跳过了视觉验收

### Step 3 — 深入分析验收质量

对 Step 2 标记的异常执行（以及看起来正常但需要抽检质量的执行），拉取 session 详情：

```bash
python3 scripts/analyze_runs.py --session {session-id} --steps
```

**分析维度：**

1. **三阶段执行审计**（最重要）：
   - 提取所有 `browser_navigate`、`browser_screenshot`、`browser_click` 等 Playwright 调用
   - 还原执行阶段：
     - Phase A 特征：`browser_navigate` + `browser_take_screenshot`（无 `browser_click`）
     - Phase B 特征：连续的 `browser_take_screenshot` → `browser_click` → `browser_take_screenshot` 序列（用户操作 + 前后对比）
     - Phase C 特征：针对具体 UI 元素的 `browser_click`、`browser_fill_form`、`browser_select_option`
   - 验证阶段顺序：必须 A → B → C，不得跳过或倒序
   - 标记缺失的阶段为 P0 问题

2. **截图分析质量**（P0 级别）：
   - 统计 `browser_take_screenshot` 调用次数
   - 对每次截图，检查紧随其后的 assistant text 是否包含视觉分析内容：
     - 合格：描述了布局、间距、对齐、颜色、可读性等
     - 不合格：只提到"截图已保存"、直接跳到下一个操作、或完全没有分析
   - 计算"截图分析率"= 有分析的截图数 / 总截图数
   - 截图分析率 < 80% → P0 问题（形式主义验收）

3. **用户旅程覆盖度**：
   - Step 1 输出中是否包含"用户旅程"定义（搜索"旅程"、"journey"关键词）
   - Phase B 是否有明确的旅程步骤执行（搜索"旅程 1"、"旅程 2"等）
   - 旅程是否走完（有入口操作和终态验证）
   - 无用户旅程定义 → P0 问题
   - 有定义但未执行 → P0 问题
   - 执行了但未走完 → P1 问题

4. **视觉检测能力**：
   - 在 assistant text 中搜索视觉相关关键词：布局、间距、对齐、溢出、截断、空白、比例、变形、色彩、字号
   - 统计发现的视觉问题数量
   - 最终报告中视觉问题占比（vs 纯功能问题）
   - 如果 0 个视觉发现 → P1 问题（可能视觉盲区）

5. **严格性评估**：
   - 提取最终验收结论（`【VALIDATOR】【验收通过】` 或 `【VALIDATOR】【验收不通过】`）
   - 统计 FAIL/WARN/PASS 数量
   - 检查是否有"应该 FAIL 但给了 WARN"的情况：
     - console error 存在但给了 WARN → 违反严格性标尺
     - 水平滚动但给了 WARN → 违反严格性标尺
     - 用户旅程中断但给了 WARN → 违反严格性标尺
   - 全部 PASS 0 问题 → 可疑（要么产品完美，要么验收走过场）

6. **Playwright 操作规范检查**：
   - 是否设置了视口 1280×800（搜索 `browser_resize`）
   - 是否检查了 console errors（搜索 `browser_console_messages`）
   - 交互前后是否都截图了（before/after 对比）
   - 是否有 `browser_snapshot` 但没有对应 `browser_take_screenshot`（只用 DOM 不看视觉）

7. **执行效率**：
   - 阶段时间分配是否合理
   - 冗余检测：同一页面重复导航、同一元素重复截图
   - 数据膨胀：哪个 tool result 返回数据量最大
   - 被中断位置：超时时在哪个阶段

8. **Issue 反馈质量**：
   - 提取 `gh issue comment` 调用中的评论内容
   - 检查是否包含结构化报告（有标题、有分类、有证据）
   - 问题描述是否具体可操作（vs 模糊的"有些问题"）
   - FAIL 项是否包含复现步骤

### Step 4 — 输出评测报告

按以下结构输出：

```
## 运行概览
最近 {N} 次执行统计表格

## 三阶段执行审计
逐次执行标注：
- ✅ Phase A/B/C 完整执行
- ❌ 缺失 Phase {X}
- ⚠️ 阶段顺序异常

## 截图分析质量
- 总截图数: {N}
- 有效分析数: {N}
- 截图分析率: {N}%
- 典型问题: {无分析的截图列表}

## 用户旅程覆盖
- 旅程定义: 有/无
- 旅程执行: 完整/部分/未执行
- 旅程评估: {质量评价}

## 视觉检测能力
- 视觉问题发现数: {N}
- 视觉 vs 功能问题比: {ratio}
- 检测盲区: {未覆盖的视觉维度}

## 严格性评分
- 评分: {A/B/C/D/F}
  - A: 严格执行铁律，FAIL/WARN 判定准确
  - B: 基本严格，偶有遗漏
  - C: 严格性不足，多处应 FAIL 给了 WARN
  - D: 走过场，大量问题未发现
  - F: 形式主义，截图不分析、旅程不走

## 发现的问题
按严重程度排序：
- P0: 阶段缺失、截图不分析、旅程未执行（验收质量不可信）
- P1: 视觉盲区、严格性不足、操作规范违反（验收质量下降）
- P2: 效率问题、冗余步骤、超时风险（影响执行效率）

## 优化建议
每个问题对应具体修改建议，标明：
- 改什么文件（validator/SKILL.md / validator/refs/*.md）
- 预期效果

## 趋势观察
- 验收质量是否在改善？（截图分析率趋势、视觉发现趋势）
- 执行效率是否在恶化？（耗时趋势、token 趋势）
- 是否有 validator 被反复派发同一 Issue 的情况？（说明验收反馈不够具体）
```
