# 验收请求

## 触发条件

Issue label=`verifying` + `owner/codex`，Claude 空闲。

（`owner/shuzai` 的 verifying Issue 由 Step 1 转入时已发 Feishu 通知，不经过此流程）

## 派发消息格式

```
【OPENCLAW】【验收请求】
Issue #{N}：{Issue标题}

PR 已合并，请验证此功能的主干使用流程是否正常。

需确认：
① 核心功能端到端可用
② 主要用户路径无阻断性问题
③ 无明显回归

验收要点（来自 Issue 验收标准）：
{从 Issue 正文提取的验收条件，若无则省略此行}

完成后请回复：
- 通过：回复【验收通过】并简述验证内容
- 有问题：列出具体问题描述（每条一行）
```

## openclaw 后续动作

**Claude 回复【验收通过】：**
1. Issue label：`verifying` → `verified`
2. Claude 的回复内容以 【CLAUDE】 评论写入 Issue（Claude 自己写入）
3. openclaw 留 【OPENCLAW】 评论：验收通过，label → verified，建议 HUMAN 关闭

**Claude 列出问题：**
1. 为每个问题自动创建新 Issue（label=`pending`，无 owner，等待路由）
2. 新 Issue 正文中引用原 Issue 编号
3. 原 Issue 保持 `verifying`，等待修复后重验

## 按任务类型细化验收要点

- **功能类任务**：端到端操作验证，覆盖主路径和常见边界
- **测试类任务**：运行测试套件，确认覆盖率达标、无失败用例
- **文档类任务**：检查关键章节是否准确、示例可运行、链接有效
