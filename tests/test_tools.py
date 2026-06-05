"""Tests for tools.py — agent tool system (read, write, list, bash, grep)."""
import pytest
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools import execute_tool, get_tools_for_stage, ALL_TOOLS, ToolDef


class TestTools:
    @pytest.fixture
    def workspace(self):
        """Create a temporary workspace directory."""
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    def test_all_tools_registered(self):
        """All 5 tools should be registered."""
        assert len(ALL_TOOLS) == 5
        for name in ["read_file", "write_file", "list_files", "bash", "grep"]:
            assert name in ALL_TOOLS
            assert isinstance(ALL_TOOLS[name], ToolDef)

    def test_tool_selection_per_stage(self):
        """Each stage type gets appropriate tools."""
        coding_tools = get_tools_for_stage("coding")
        assert len(coding_tools) == 4  # write, read, list, bash
        tool_names = [t["function"]["name"] for t in coding_tools]
        assert "write_file" in tool_names
        assert "bash" in tool_names

        review_tools = get_tools_for_stage("review")
        review_names = [t["function"]["name"] for t in review_tools]
        assert "write_file" not in review_names  # Reviewer can't write
        assert "grep" in review_names

        bugfix_tools = get_tools_for_stage("bugfix")
        bugfix_names = [t["function"]["name"] for t in bugfix_tools]
        assert "write_file" in bugfix_names

    def test_read_file(self, workspace):
        filepath = os.path.join(workspace, "test.txt")
        with open(filepath, "w") as f:
            f.write("hello world")

        result = execute_tool("read_file", {"path": "test.txt"}, workspace)
        assert "hello world" in result

    def test_read_file_missing(self, workspace):
        result = execute_tool("read_file", {"path": "nonexistent.txt"}, workspace)
        assert result.startswith("Error: file not found")

    def test_read_file_large_truncation(self, workspace):
        filepath = os.path.join(workspace, "large.txt")
        with open(filepath, "w") as f:
            f.write("x" * 15000)

        result = execute_tool("read_file", {"path": "large.txt"}, workspace)
        assert "truncated" in result
        assert len(result) < 15000  # Should be truncated

    def test_write_file(self, workspace):
        result = execute_tool("write_file", {"path": "new.py", "content": "print(1)"}, workspace)
        assert result.startswith("OK:")
        assert os.path.isfile(os.path.join(workspace, "new.py"))
        with open(os.path.join(workspace, "new.py")) as f:
            assert f.read() == "print(1)"

    def test_write_file_creates_dirs(self, workspace):
        result = execute_tool("write_file", {"path": "sub/dir/file.py", "content": "x"}, workspace)
        assert result.startswith("OK:")
        assert os.path.isfile(os.path.join(workspace, "sub", "dir", "file.py"))

    def test_write_file_no_path(self, workspace):
        result = execute_tool("write_file", {"path": "", "content": "x"}, workspace)
        assert result.startswith("Error:")

    def test_list_files(self, workspace):
        os.makedirs(os.path.join(workspace, "src"))
        with open(os.path.join(workspace, "src", "main.py"), "w") as f:
            f.write("code")
        with open(os.path.join(workspace, "README.md"), "w") as f:
            f.write("readme")

        result = execute_tool("list_files", {"subdir": "."}, workspace)
        assert "main.py" in result
        assert "src/" in result
        assert "README.md" in result

    def test_list_files_missing_dir(self, workspace):
        result = execute_tool("list_files", {"subdir": "nonexistent"}, workspace)
        assert result.startswith("Error: directory not found")

    def test_bash_dangerous_blocked(self, workspace):
        dangerous_cmds = ["rm -rf /", "shutdown", "git push --force"]
        for cmd in dangerous_cmds:
            result = execute_tool("bash", {"command": cmd}, workspace)
            assert result.startswith("Error: blocked")

    def test_bash_simple_command(self, workspace):
        result = execute_tool("bash", {"command": "echo hello"}, workspace)
        assert "hello" in result

    def test_bash_no_command(self, workspace):
        result = execute_tool("bash", {"command": ""}, workspace)
        assert result.startswith("Error: 'command' is required")

    def test_grep_requires_pattern(self, workspace):
        result = execute_tool("grep", {"pattern": ""}, workspace)
        assert result.startswith("Error: 'pattern' is required")

    def test_unknown_tool(self, workspace):
        result = execute_tool("nonexistent_tool", {}, workspace)
        assert result.startswith("Error: unknown tool")

    def test_safe_path_blocks_traversal(self, workspace):
        """Path traversal attacks should be neutralized."""
        result = execute_tool("read_file", {"path": "../../../etc/passwd"}, workspace)
        assert "Error:" in result  # File shouldn't exist

    def test_write_with_traversal_blocked(self, workspace):
        """Writing outside workspace should be blocked by path normalization."""
        # The _safe_path function strips ../ sequences
        result = execute_tool("write_file", {"path": "../outside.txt", "content": "bad"}, workspace)
        # Should write to workspace/outside.txt, not parent dir
        assert not os.path.exists(os.path.join(os.path.dirname(workspace), "outside.txt"))
