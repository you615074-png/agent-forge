"""Tests for executor.py — agent execution with mock providers."""
import pytest
import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from executor import execute, _generate_task_id, _extract_code_blocks, _scan_files


class TestExecutor:
    @pytest.fixture
    def agent_config(self):
        return {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "api_key_env": "DEEPSEEK_API_KEY",
            "api_key": "sk-test",
        }

    @pytest.fixture
    def work_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    def test_invalid_agent_config(self, work_dir):
        """Agent with neither cli nor provider should return error."""
        result = execute(
            agent_name="bad_agent",
            agent_config={"description": "no cli or provider"},
            task="do something",
            work_dir=work_dir,
        )
        assert result["success"] is False
        assert result["exit_code"] == -1
        assert "must include either" in result["error"]

    def test_cli_mode_not_installed(self, work_dir):
        """CLI mode with nonexistent command should return clear error."""
        result = execute(
            agent_name="missing_cli",
            agent_config={"cli": "nonexistent-command-xyz"},
            task="test",
            work_dir=work_dir,
        )
        assert result["success"] is False
        assert "not found" in result.get("error", "")

    def test_api_mode_requires_key(self, work_dir):
        """API mode with invalid key should fail gracefully."""
        agent = {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "api_key_env": "NONEXISTENT_ENV_VAR_XYZ123",
        }
        result = execute(
            agent_name="coder",
            agent_config=agent,
            task="write hello world",
            work_dir=work_dir,
        )
        assert result["success"] is False
        assert result["error"] is not None
        assert "NONEXISTENT_ENV_VAR_XYZ123" in result["error"]

    def test_generate_task_id_consistent(self):
        """Same task should generate same hash."""
        id1 = _generate_task_id("build a calculator")
        id2 = _generate_task_id("build a calculator")
        # Hashes are same, timestamps differ
        hash1 = id1.split("-")[-1]
        hash2 = id2.split("-")[-1]
        assert hash1 == hash2

    def test_extract_code_blocks(self):
        text = """Here is some code:

```python main.py
def hello():
    return "world"
```

And another file:

```javascript app.js
console.log("hi");
```
"""
        with tempfile.TemporaryDirectory() as tmp:
            files = _extract_code_blocks(text, tmp)
            assert len(files) == 2
            paths = [f["path"] for f in files]
            assert "main.py" in paths
            assert any(p.endswith(".js") for p in paths)

    def test_extract_code_blocks_empty(self):
        files = _extract_code_blocks("No code blocks here", tempfile.gettempdir())
        assert files == []

    def test_scan_files(self, work_dir):
        with open(os.path.join(work_dir, "a.py"), "w") as f:
            f.write("test")
        with open(os.path.join(work_dir, "b.txt"), "w") as f:
            f.write("notes")
        os.makedirs(os.path.join(work_dir, "subdir"))
        with open(os.path.join(work_dir, "subdir", "c.py"), "w") as f:
            f.write("nested")

        files = _scan_files(work_dir)
        assert len(files) == 3
        assert any(f["path"] == "a.py" for f in files)

    def test_scan_files_exclude(self, work_dir):
        with open(os.path.join(work_dir, "keep.py"), "w") as f:
            f.write("ok")
        with open(os.path.join(work_dir, "_stage_test_output.txt"), "w") as f:
            f.write("exclude me")

        files = _scan_files(work_dir, exclude_prefixes=["_stage_"])
        assert len(files) == 1
        assert files[0]["path"] == "keep.py"

    def test_session_dir_creation(self, work_dir):
        """execute() should create the session directory."""
        result = execute(
            agent_name="test",
            agent_config={"cli": "echo"},
            task="hello",
            work_dir=work_dir,
        )
        assert os.path.isdir(result["session_dir"])
        assert result["task_id"] in result["session_dir"]
