"""Tests for compare.py — multi-plan comparison engine (mock mode)."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from compare import compare_plans, _score_output, _build_comparison_table


# Minimal config for testing
CONFIG = {
    "agents": {
        "coder": {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "api_key_env": "DEEPSEEK_API_KEY",
            "api_key": "sk-test",
            "description": "Test coder",
        },
        "tester": {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "api_key_env": "DEEPSEEK_API_KEY",
            "api_key": "sk-test",
            "description": "Test tester",
        },
    },
    "executor": {"work_dir": tempfile.gettempdir(), "timeout_seconds": 30},
}


class TestCompare:
    def test_score_high_quality_output(self):
        """A comprehensive output should score well."""
        result = {
            "success": True,
            "agent": "coder",
            "stdout": (
                '"""Module docstring."""\n'
                "import sys\n\n"
                "def process(data):\n"
                '    """Transform data."""\n'
                "    try:\n"
                "        if not data:\n"
                '            raise ValueError("empty")\n'
                "        return [x * 2 for x in data]\n"
                "    except Exception as e:\n"
                '        return {"error": str(e)}\n\n'
                "def test_process():\n"
                "    assert process([1, 2]) == [2, 4]\n"
                "    assert process([]) == []\n"
            ),
            "produced_files": [
                {"path": "main.py", "size": 300},
                {"path": "test_main.py", "size": 150},
                {"path": "README.md", "size": 100},
            ],
        }
        score = _score_output(result, "coder")
        assert score["total"] > 50
        assert score["has_tests"] == 10.0
        assert score["has_docs"] == 10.0
        assert score["has_errors"] == 10.0

    def test_score_low_quality_output(self):
        """A minimal output should score poorly."""
        result = {
            "success": True,
            "agent": "coder",
            "stdout": "x = 1",
            "produced_files": [{"path": "one.py", "size": 10}],
        }
        score = _score_output(result, "coder")
        assert score["total"] < 30
        assert score["has_tests"] == 0.0
        assert score["has_docs"] < 10.0

    def test_score_neutralizes_blank_output(self):
        result = {"success": True, "agent": "empty", "stdout": "", "produced_files": []}
        score = _score_output(result, "empty")
        assert score["total"] >= 0

    def test_compare_mock_mode(self):
        """compare_plans in mock mode should return results for all agents."""
        result = compare_plans("build a function", CONFIG, mock=True)
        assert result["winner"] in ["coder", "tester"]
        assert len(result["rankings"]) == 2
        assert result["winner"] == result["rankings"][0]["agent"]
        assert "★" in result["summary"]
        assert os.path.isdir(result["session_dir"])

    def test_compare_with_filter(self):
        """Filter should limit which agents participate."""
        result = compare_plans(
            "test task",
            CONFIG,
            mock=True,
            agents_filter=["tester"],
        )
        assert len(result["results"]) == 1
        assert result["results"][0]["agent"] == "tester"

    def test_compare_empty_agents(self):
        result = compare_plans("test", {"agents": {}}, mock=True)
        assert "error" in result

    def test_build_comparison_table(self):
        results = [
            {
                "agent": "alice",
                "score": 85.0,
                "produced_files": [{"path": "a.py"}],
                "duration_ms": 100,
                "score_detail": {
                    "code_lines": 8, "has_docs": 10, "has_tests": 10,
                    "has_errors": 8, "file_count": 5, "structure": 7,
                },
            },
            {
                "agent": "bob",
                "score": 45.0,
                "produced_files": [{"path": "b.py"}],
                "duration_ms": 50,
                "score_detail": {
                    "code_lines": 3, "has_docs": 2, "has_tests": 0,
                    "has_errors": 1, "file_count": 2, "structure": 3,
                },
            },
        ]
        rankings = sorted(results, key=lambda r: r["score"], reverse=True)
        table = _build_comparison_table(results, rankings, "alice", "test task")
        assert "★ alice" in table
        assert "85" in table
        assert "45" in table
