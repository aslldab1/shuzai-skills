#!/usr/bin/env python3
"""
派发判断逻辑单元测试

覆盖以下确定性逻辑：
1. 评论前缀分类（系统 / CLAUDE / HUMAN）
2. 人工反馈检测（最近一条派发评论之后，是否有 HUMAN 评论）
3. "任务已完成" pane 内容判断
4. jq -r 解码（确保输出为原始 UTF-8，不含 \\uXXXX）

测试场景对应 tests/scenarios.yaml 中的 J01-J04。
"""
import subprocess
import sys
import unittest


# ---------------------------------------------------------------------------
# 工具函数（与 SKILL 逻辑保持一致）
# ---------------------------------------------------------------------------

SYSTEM_PREFIXES = ("【OPENCLAW】", "【CLAUDE】")


def classify_comment(body: str) -> str:
    """返回 'system'、'claude' 或 'human'。"""
    if body.startswith("【OPENCLAW】"):
        return "system"
    if body.startswith("【CLAUDE】"):
        return "claude"
    return "human"


def has_human_feedback_after_dispatch(comments: list[dict]) -> tuple[bool, str]:
    """
    在最近一条 【OPENCLAW】已将此任务派发给 评论之后，
    找第一条 HUMAN 评论。返回 (found, body)。
    """
    dispatch_idx = -1
    for i, c in enumerate(comments):
        if c["body"].startswith("【OPENCLAW】已将此任务派发给"):
            dispatch_idx = i

    if dispatch_idx == -1:
        return False, ""

    for c in comments[dispatch_idx + 1:]:
        if classify_comment(c["body"]) == "human":
            return True, c["body"]

    return False, ""


def pane_shows_done(pane_lines: list[str]) -> bool:
    """
    判断 pane 末尾 30 行是否包含"已完成/已处理/无需重复执行"等完成信号。
    """
    done_keywords = ["已完成", "已处理", "无需重复执行", "task done", "completed"]
    tail = pane_lines[-30:]
    for line in tail:
        for kw in done_keywords:
            if kw in line.lower():
                return True
    return False


def jq_decode(json_text: str) -> str:
    """
    使用 jq -r 解码 JSON 字符串，确保输出原始 UTF-8 而非 \\uXXXX 序列。
    """
    result = subprocess.run(
        ["jq", "-r", "."],
        input=json_text,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"jq error: {result.stderr}")
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# 测试用例
# ---------------------------------------------------------------------------

class TestCommentClassification(unittest.TestCase):
    """评论前缀分类。"""

    def test_openclaw_prefix(self):
        self.assertEqual(classify_comment("【OPENCLAW】已将此任务派发给 @claude"), "system")

    def test_claude_prefix(self):
        self.assertEqual(classify_comment("【CLAUDE】方案概要：已完成登录模块"), "claude")

    def test_human_no_prefix(self):
        self.assertEqual(classify_comment("请优化一下错误提示文案"), "human")

    def test_human_looks_like_prefix_but_isnt(self):
        # 只有行首完全匹配才算前缀
        self.assertEqual(classify_comment("修改建议：【CLAUDE】风格"), "human")


class TestHumanFeedbackDetection(unittest.TestCase):
    """场景 J01 / J02 / J04：人工反馈检测。"""

    def _make_comments(self, entries):
        return [{"body": b} for b in entries]

    def test_j01_no_human_feedback(self):
        """J01：最近派发之后没有 HUMAN 评论 → False。"""
        comments = self._make_comments([
            "【OPENCLAW】已将此任务派发给 @claude，开始执行。",
            "【CLAUDE】方案概要：已实现功能 X",
        ])
        found, _ = has_human_feedback_after_dispatch(comments)
        self.assertFalse(found)

    def test_j02_human_feedback_present(self):
        """J02：最近派发之后有 HUMAN 评论 → True，正确提取内容。"""
        comments = self._make_comments([
            "【OPENCLAW】已将此任务派发给 @claude，开始执行。",
            "【CLAUDE】方案概要：已实现功能 X",
            "请优化错误提示，改成中文",
        ])
        found, body = has_human_feedback_after_dispatch(comments)
        self.assertTrue(found)
        self.assertEqual(body, "请优化错误提示，改成中文")

    def test_j04_claude_reply_without_prefix_treated_as_human(self):
        """J04：Claude 回复缺少 【CLAUDE】 前缀 → 被误判为 HUMAN 反馈（应触发派发）。"""
        comments = self._make_comments([
            "【OPENCLAW】已将此任务派发给 @claude，开始执行。",
            "方案概要：已实现功能 X（缺少前缀的 Claude 回复）",
        ])
        found, body = has_human_feedback_after_dispatch(comments)
        # 缺前缀 → classify 为 human → 被当作人工反馈触发
        self.assertTrue(found)
        self.assertIn("缺少前缀", body)

    def test_no_dispatch_comment_returns_false(self):
        """没有任何派发评论 → False。"""
        comments = self._make_comments([
            "【CLAUDE】方案概要：初稿",
            "请调整样式",
        ])
        found, _ = has_human_feedback_after_dispatch(comments)
        self.assertFalse(found)

    def test_picks_latest_dispatch_comment(self):
        """多轮派发：以最后一条派发评论为基准。"""
        comments = self._make_comments([
            "【OPENCLAW】已将此任务派发给 @claude，开始执行。",
            "第一轮人工反馈",
            "【OPENCLAW】已将此任务派发给 @claude，开始执行。",   # 第二轮
            "【CLAUDE】第二轮方案",
        ])
        found, _ = has_human_feedback_after_dispatch(comments)
        self.assertFalse(found)  # 第二轮派发后没有 HUMAN 评论


class TestPaneDoneDetection(unittest.TestCase):
    """场景 J03：pane 内容显示任务已完成。"""

    def test_j03_pane_shows_done(self):
        """J03：pane 包含'已完成' → 判断为不需要重新派发。"""
        lines = [
            "✻ Conversation compacted",
            "正在检查代码...",
            "【CLAUDE】已完成 issue #51 的修改，PR 已提交。",
            "> ",
        ]
        self.assertTrue(pane_shows_done(lines))

    def test_pane_idle_no_done(self):
        """pane 空闲但没有完成信号 → False（需要正常派发）。"""
        lines = [
            "✻ Conversation compacted",
            "> ",
        ]
        self.assertFalse(pane_shows_done(lines))

    def test_pane_done_keyword_case_insensitive(self):
        """英文 completed 也能匹配。"""
        lines = ["Task completed successfully", "> "]
        self.assertTrue(pane_shows_done(lines))


class TestJqDecoding(unittest.TestCase):
    """jq -r 解码：确保中文从 \\uXXXX 转为原始 UTF-8。"""

    def test_chinese_decoded(self):
        """\\u4e2d\\u6587 → 中文。"""
        json_input = '"\\u4e2d\\u6587\\u5185\\u5bb9"'
        decoded = jq_decode(json_input)
        self.assertEqual(decoded, "中文内容")

    def test_plain_string_unchanged(self):
        """纯 ASCII 字符串不受影响。"""
        json_input = '"hello world"'
        decoded = jq_decode(json_input)
        self.assertEqual(decoded, "hello world")

    def test_mixed_content(self):
        """混合内容（中英文）正确解码。"""
        json_input = '"Issue #51: \\u767b\\u5f55\\u529f\\u80fd"'
        decoded = jq_decode(json_input)
        self.assertEqual(decoded, "Issue #51: 登录功能")


if __name__ == "__main__":
    # 运行时打印每个测试名，便于定位失败点
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
