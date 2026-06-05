"""Tests for matcher.py — weighted capability scoring and agent selection."""
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from matcher import match


AGENTS = {
    "coder": {
        "description": "Primary developer",
        "capabilities": {"coding": 0.95, "architecture": 0.90, "debugging": 0.75, "testing": 0.55},
    },
    "reviewer": {
        "description": "Code reviewer",
        "capabilities": {"review": 0.95, "reasoning": 0.92, "debugging": 0.75, "coding": 0.72},
    },
    "bugfixer": {
        "description": "Bug fix specialist",
        "capabilities": {"debugging": 0.92, "quick_fix": 0.95, "coding": 0.75, "testing": 0.50},
    },
    "tester": {
        "description": "Test engineer",
        "capabilities": {"testing": 0.95, "verification": 0.95, "debugging": 0.70, "coding": 0.65},
    },
}

WEIGHTS = {
    "coding":   {"coding": 1.0, "architecture": 0.6, "fullstack": 0.5},
    "review":   {"review": 1.0, "reasoning": 0.6, "documentation": 0.3},
    "bugfix":   {"debugging": 1.0, "quick_fix": 0.9, "coding": 0.4},
    "testing":  {"testing": 1.0, "verification": 0.8, "debugging": 0.3},
    "analysis": {"reasoning": 1.0, "review": 0.5, "architecture": 0.4},
    "refactor": {"coding": 1.0, "architecture": 0.7, "review": 0.3},
}


class TestMatch:
    def test_coding_selects_coder(self):
        result = match("coding", AGENTS, WEIGHTS)
        assert result["selected"] == "coder"
        assert result["score"] > 0.8
        assert result["runner_up"] is not None
        assert len(result["all_scores"]) == 4

    def test_review_selects_reviewer(self):
        result = match("review", AGENTS, WEIGHTS)
        assert result["selected"] == "reviewer"

    def test_bugfix_selects_bugfixer(self):
        result = match("bugfix", AGENTS, WEIGHTS)
        assert result["selected"] == "bugfixer"

    def test_testing_selects_tester(self):
        result = match("testing", AGENTS, WEIGHTS)
        assert result["selected"] == "tester"

    def test_unknown_type_returns_error(self):
        result = match("unknown_task_type", AGENTS, WEIGHTS)
        assert "error" in result

    def test_scores_are_normalized(self):
        result = match("coding", AGENTS, WEIGHTS)
        for s in result["all_scores"]:
            assert 0 <= s["score"] <= 1
            assert isinstance(s["name"], str)

    def test_empty_agents(self):
        result = match("coding", {}, WEIGHTS)
        assert "error" in result

    def test_runner_up_exists(self):
        result = match("coding", AGENTS, WEIGHTS)
        assert result["runner_up"] is not None
        assert result["runner_up"] != result["selected"]
        assert result["runner_up_score"] <= result["score"]

    def test_score_ordering(self):
        result = match("coding", AGENTS, WEIGHTS)
        scores = result["all_scores"]
        for i in range(len(scores) - 1):
            assert scores[i]["score"] >= scores[i + 1]["score"]
