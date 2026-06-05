"""Tests for classifier.py — keyword-based task type detection."""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from classifier import classify


RULES = [
    {"type": "testing",      "keywords": ["test", "spec", "验证"], "targets": []},
    {"type": "review",       "keywords": ["review", "审查", "检查", "audit"], "targets": []},
    {"type": "bugfix",       "keywords": ["bug", "fix", "修复", "报错", "broken"], "targets": []},
    {"type": "refactor",     "keywords": ["refactor", "重构", "优化", "improve"], "targets": []},
    {"type": "documentation","keywords": ["文档", "readme", "docs", "注释"], "targets": []},
    {"type": "analysis",     "keywords": ["分析", "analyze", "解释", "explain"], "targets": []},
    {"type": "coding",       "keywords": ["写", "开发", "build", "create", "implement", "write", "make"], "targets": []},
]
FALLBACK = "coding"


class TestClassify:
    def test_coding_english(self):
        task_type, meta = classify("build a login page with React", RULES, FALLBACK)
        assert task_type == "coding"
        assert "build" in meta["matched_keywords"]

    def test_coding_chinese(self):
        task_type, meta = classify("写一个用户认证系统", RULES, FALLBACK)
        assert task_type == "coding"
        assert "写" in meta["matched_keywords"]

    def test_review(self):
        task_type, meta = classify("review this code for security issues", RULES, FALLBACK)
        assert task_type == "review"
        assert "review" in meta["matched_keywords"]

    def test_bugfix(self):
        task_type, meta = classify("fix the broken auth middleware", RULES, FALLBACK)
        assert task_type == "bugfix"
        assert "fix" in meta["matched_keywords"]

    def test_bugfix_chinese(self):
        task_type, meta = classify("修复登录bug", RULES, FALLBACK)
        assert task_type == "bugfix"

    def test_testing(self):
        task_type, meta = classify("write unit tests for the API", RULES, FALLBACK)
        assert task_type == "testing"
        assert "test" in meta["matched_keywords"]

    def test_fallback_to_coding(self):
        task_type, meta = classify("do something mysterious", RULES, FALLBACK)
        assert task_type == "coding"
        assert meta["reason"] == "no_rule_matched"

    def test_empty_task(self):
        task_type, meta = classify("", RULES, FALLBACK)
        assert task_type == "coding"
        assert meta["reason"] == "no_rule_matched"

    def test_targets_filter(self):
        """When targets are specified, they act as a required second filter."""
        rules_with_targets = [
            {"type": "testing", "keywords": ["test"], "targets": ["api", "unit"]},
        ]
        # Should NOT match because targets don't match
        task_type, meta = classify("test the login", rules_with_targets, FALLBACK)
        assert task_type == "coding"  # falls back
        # Should match because "api" target is in the text
        task_type, meta = classify("test the api endpoint", rules_with_targets, FALLBACK)
        assert task_type == "testing"

    def test_refactor(self):
        task_type, meta = classify("refactor the database layer", RULES, FALLBACK)
        assert task_type == "refactor"

    def test_case_insensitive(self):
        task_type, meta = classify("BUILD A WEBSITE", RULES, FALLBACK)
        assert task_type == "coding"
