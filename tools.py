"""
AgentForge — Agent Tool System (v0.4)

Each agent gets a toolset — it can read/write files, run shell commands,
and explore the project. This is what takes AgentForge from "text generator"
to "developer assistant".

Tool definitions follow OpenAI/DeepSeek function-calling schema.
Anthropic native tool_use is adapted at the provider layer.
"""

import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Callable, Optional

# ═══════════════════════════════════════════════════════════════
# Tool definition
# ═══════════════════════════════════════════════════════════════

@dataclass
class ToolDef:
    """Schema + handler for a single tool."""
    name: str
    description: str
    parameters: dict          # JSON Schema for the arguments
    handler: Callable         # (args: dict, workspace_dir: str) -> str
    dangerous: bool = False   # if True, requires explicit opt-in


# ═══════════════════════════════════════════════════════════════
# Tool implementations
# ═══════════════════════════════════════════════════════════════

def _read_file(args: dict, workspace_dir: str) -> str:
    """Read a file and return its contents."""
    path = _safe_path(args.get("path", ""), workspace_dir)
    if not os.path.isfile(path):
        return f"Error: file not found — '{args['path']}'"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        # Truncate large files with a note
        if len(content) > 12000:
            content = content[:12000] + (
                f"\n\n... [truncated: {len(content) - 12000} more chars]"
            )
        return content
    except Exception as e:
        return f"Error reading file: {e}"


def _write_file(args: dict, workspace_dir: str) -> str:
    """Create or overwrite a file."""
    path = _safe_path(args.get("path", ""), workspace_dir)
    content = args.get("content", "")
    if not path:
        return "Error: 'path' is required"
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    size = os.path.getsize(path)
    return f"OK: wrote {size} bytes to '{os.path.relpath(path, workspace_dir)}'"


def _list_files(args: dict, workspace_dir: str) -> str:
    """List files in the workspace directory."""
    subdir = _safe_path(args.get("subdir", "."), workspace_dir)
    if not os.path.isdir(subdir):
        return f"Error: directory not found — '{args.get('subdir', '.')}'"

    lines = []
    for root, dirs, filenames in os.walk(subdir):
        # Skip hidden dirs, __pycache__, node_modules, .git
        dirs[:] = [d for d in dirs if not d.startswith(".")
                    and d not in ("__pycache__", "node_modules", ".git")]
        relroot = os.path.relpath(root, workspace_dir)
        depth = 0 if relroot == "." else relroot.count(os.sep) + 1
        if depth < 3:
            indent = "  " * max(0, depth)
            if relroot != ".":
                lines.append(f"{indent}{os.path.basename(relroot)}/")
            for fn in sorted(filenames):
                if not fn.startswith(".") and not fn.startswith("_stage_"):
                    fp = os.path.join(root, fn)
                    size = os.path.getsize(fp)
                    lines.append(f"{indent}  {fn}  ({_fmt_size(size)})")

    result = "\n".join(lines[:60])
    if len(lines) > 60:
        result += f"\n... ({len(lines) - 60} more entries)"
    return result or "(empty directory)"


def _bash(args: dict, workspace_dir: str) -> str:
    """Run a shell command in the workspace directory."""
    command = args.get("command", "")
    if not command:
        return "Error: 'command' is required"
    # Safety blocklist
    dangerous = ["rm -rf /", "mkfs.", ":(){ :|:& };:", "> /dev/sda",
                 "dd if=", "format c:", "del /f /s", "shutdown",
                 "git push --force", "git reset --hard"]
    cmd_lower = command.lower()
    for d in dangerous:
        if d in cmd_lower:
            return f"Error: blocked dangerous command (matches '{d}')"

    try:
        result = subprocess.run(
            command, shell=True,
            capture_output=True, text=True,
            timeout=60,
            cwd=workspace_dir,
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        parts = []
        if out:
            parts.append(out[:3000])
        if err:
            parts.append(f"[stderr]\n{err[:1000]}")
        status = f"exit={result.returncode}"
        return "\n".join(parts) or status
    except subprocess.TimeoutExpired:
        return "Error: command timed out (60s)"
    except Exception as e:
        return f"Error: {e}"


def _grep(args: dict, workspace_dir: str) -> str:
    """Search for a pattern in files."""
    pattern = args.get("pattern", "")
    path_filter = args.get("path_filter", ".")
    if not pattern:
        return "Error: 'pattern' is required"
    search_dir = _safe_path(path_filter, workspace_dir)
    try:
        result = subprocess.run(
            ["rg", "--no-heading", "-n", "--color=never", pattern, search_dir],
            capture_output=True, text=True, timeout=15, cwd=workspace_dir,
        )
        out = result.stdout.strip()
        if not out:
            return "(no matches)"
        lines = out.split("\n")
        if len(lines) > 30:
            out = "\n".join(lines[:30]) + f"\n... ({len(lines) - 30} more matches)"
        return out[:3000]
    except FileNotFoundError:
        # Fallback to findstr on Windows or grep on Unix
        try:
            result = subprocess.run(
                ["grep", "-rn", "--color=never", pattern, search_dir],
                capture_output=True, text=True, timeout=15, cwd=workspace_dir,
            )
            out = result.stdout.strip()[:3000] or "(no matches)"
            return out
        except Exception:
            return f"Error: grep not available. Install ripgrep (rg) for search."


# ═══════════════════════════════════════════════════════════════
# Tool registry
# ═══════════════════════════════════════════════════════════════

ALL_TOOLS: dict[str, ToolDef] = {
    "read_file": ToolDef(
        name="read_file",
        description="Read the contents of a file in the workspace. Use this to examine existing code.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file (e.g. 'src/main.py')",
                }
            },
            "required": ["path"],
        },
        handler=_read_file,
    ),
    "write_file": ToolDef(
        name="write_file",
        description="Create or overwrite a file. Provide the full file content.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path for the new file (e.g. 'src/main.py')",
                },
                "content": {
                    "type": "string",
                    "description": "Complete file contents",
                },
            },
            "required": ["path", "content"],
        },
        handler=_write_file,
    ),
    "list_files": ToolDef(
        name="list_files",
        description="List files and directories in the workspace. Use to understand the project structure.",
        parameters={
            "type": "object",
            "properties": {
                "subdir": {
                    "type": "string",
                    "description": "Subdirectory to list (default: workspace root)",
                },
            },
        },
        handler=_list_files,
    ),
    "bash": ToolDef(
        name="bash",
        description=(
            "Run a shell command in the workspace directory. "
            "Use for: running tests (pytest, npm test), installing deps (pip install), "
            "checking Python/Node versions, linting, building. "
            "NOT for: destructive operations, git force push."
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to run",
                },
            },
            "required": ["command"],
        },
        handler=_bash,
        dangerous=True,
    ),
    "grep": ToolDef(
        name="grep",
        description="Search for a text pattern across all files in the workspace using ripgrep.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Text or regex pattern to search for",
                },
                "path_filter": {
                    "type": "string",
                    "description": "Limit search to this directory or file pattern (default: entire workspace)",
                },
            },
            "required": ["pattern"],
        },
        handler=_grep,
    ),
}


def get_tools_for_stage(stage_type: str) -> list[dict]:
    """
    Return tool definitions (as API-ready schemas) for a pipeline stage.

    Each stage gets tools appropriate to its role:
      coding:  write_file, read_file, list_files, bash
      review:  read_file, list_files, grep
      bugfix:  read_file, write_file, list_files, bash
      testing: read_file, write_file, list_files, bash
      default: all tools
    """
    stage_tools = {
        "coding":   ["write_file", "read_file", "list_files", "bash"],
        "review":   ["read_file", "list_files", "grep"],
        "bugfix":   ["read_file", "write_file", "list_files", "bash"],
        "testing":  ["read_file", "write_file", "list_files", "bash"],
        "analysis": ["read_file", "list_files", "grep", "bash"],
        "refactor": ["read_file", "write_file", "list_files", "bash", "grep"],
        "documentation": ["read_file", "list_files", "grep"],
    }

    tool_names = stage_tools.get(stage_type, list(ALL_TOOLS.keys()))
    return [_tool_to_api_schema(ALL_TOOLS[name]) for name in tool_names
            if name in ALL_TOOLS]


def execute_tool(name: str, args: dict, workspace_dir: str) -> str:
    """Execute a tool by name and return its output string."""
    tool = ALL_TOOLS.get(name)
    if not tool:
        return f"Error: unknown tool '{name}'"
    return tool.handler(args, workspace_dir)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _tool_to_api_schema(tool: ToolDef) -> dict:
    """Convert a ToolDef to OpenAI/DeepSeek function-calling format."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _safe_path(relpath: str, workspace_dir: str) -> str:
    """Resolve a relative path safely within the workspace."""
    # Prevent path traversal attacks
    unsafe = re.sub(r'\.\.+[\\/]', '', relpath)
    unsafe = unsafe.lstrip('/').lstrip('\\')
    return os.path.normpath(os.path.join(workspace_dir, unsafe))


def _fmt_size(size_bytes: int) -> str:
    """Human-readable file size."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    return f"{size_bytes / (1024 * 1024):.1f}MB"
