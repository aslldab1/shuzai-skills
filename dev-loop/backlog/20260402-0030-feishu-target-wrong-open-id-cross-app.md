# P0: 飞书通知目标地址错误导致连续发送失败

## 问题级别

P0

## 问题表现

SKILL.md 第 98 行飞书通知目标为 `ou_92ebef681150322a26c3af3d1d79072e`，实际发送时返回 `open_id cross app`（Feishu 400 / code 99992361）。连续 2 轮（00:21、00:27）通知均发送失败。

项目根目录 CLAUDE.md 中的正确目标为 `ou_c5bd4c88f78cbf338f76dbb5e8f64fed`，该地址在更早的轮次中发送成功（message id: om_x100b53e781c8c8a0c3797c2d2aa09d0）。

## P0 判定依据

cron-log-review SKILL.md 原文：
> "状态推进错误：把 Issue 推到了错误的状态（如任务还在执行就被标为完成）"

飞书通知是 SKILL.md 明确标注的"不可省略的每轮必要输出"，目标地址错误导致通知系统性失败属于配置错误引发的功能丧失。

## 影响分析

- 用户无法收到开发进度通知，失去对自动编排系统的可见性
- 连续失败但 cron 状态显示 error（delivery channel 配置问题叠加），掩盖了根因

## 解决方案

将 SKILL.md 中飞书目标从 `ou_92ebef681150322a26c3af3d1d79072e` 改回 `ou_c5bd4c88f78cbf338f76dbb5e8f64fed`。

## 修复 PR

PR #17 (已合并)
