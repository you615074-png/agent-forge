"""
AgentForge — Executor (v0.3)
Dual-mode: CLI subprocess (backward-compatible) + API (new)

The executor picks its path based on agent config:
  - `cli` field present      → subprocess.run([cli, task])
  - `provider` field present → api_client.create_provider(...).chat(task)
  - neither                  → error

The return dict shape is identical regardless of path, so callers
(pipeline.py, orchestrator.py) don't need to know how the agent runs.
"""

import os
import re
import subprocess
import hashlib
from datetime import datetime
from typing import Optional, List

from dotenv import load_dotenv

load_dotenv()


def execute(
    agent_name: str,
    agent_config: dict,
    task: str,
    work_dir: str = "./sessions",
    timeout: int = 120,
    session_dir: Optional[str] = None,
    stage_prefix: Optional[str] = None,
) -> dict:
    """Run an agent against a task. Returns a uniform result dict."""

    if session_dir is None:
        task_id = _generate_task_id(task)
        session_dir = os.path.join(work_dir, task_id)
    else:
        task_id = os.path.basename(session_dir)

    os.makedirs(session_dir, exist_ok=True)

    if stage_prefix:
        prompt_filename = f"_stage_{stage_prefix}_prompt.txt"
        output_filename = f"_stage_{stage_prefix}_output.txt"
    else:
        prompt_filename = "prompt.txt"
        output_filename = f"{agent_name}_output.txt"

    prompt_file = os.path.join(session_dir, prompt_filename)
    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(f"# Agent: {agent_name}\n")
        f.write(f"# Task ID: {task_id}\n")
        f.write(f"# Time: {datetime.now().isoformat()}\n")
        f.write("-" * 50 + "\n\n")
        f.write(task)

    cli_command = agent_config.get("cli")
    provider_name = agent_config.get("provider")

    if cli_command:
        return _execute_cli(
            agent_name=agent_name,
            cli_command=cli_command,
            task=task,
            session_dir=session_dir,
            task_id=task_id,
            output_filename=output_filename,
            prompt_filename=prompt_filename,
            timeout=timeout,
            stage_prefix=stage_prefix,
        )

    if provider_name:
        return _execute_api(
            agent_name=agent_name,
            agent_config=agent_config,
            provider_name=provider_name,
            task=task,
            session_dir=session_dir,
            task_id=task_id,
            output_filename=output_filename,
            prompt_filename=prompt_filename,
            timeout=timeout,
            stage_prefix=stage_prefix,
        )

    return {
        "success": False,
        "agent": agent_name,
        "task_id": task_id,
        "session_dir": session_dir,
        "stdout": "",
        "stdout_full_path": None,
        "stderr": "",
        "exit_code": -1,
        "error": (
            "Agent config must include either 'cli' (for subprocess mode) "
            "or 'provider' (for API mode)."
        ),
        "duration_ms": 0,
        "produced_files": [],
    }


# ═══════════════════════════════════════════════════════════════
# CLI execution path (backward-compatible)
# ═══════════════════════════════════════════════════════════════

def _execute_cli(
    agent_name: str,
    cli_command: str,
    task: str,
    session_dir: str,
    task_id: str,
    output_filename: str,
    prompt_filename: str,
    timeout: int,
    stage_prefix: Optional[str],
) -> dict:
    """Run an agent via subprocess (original v0.1/v0.2 behaviour)."""
    start_time = datetime.now()

    try:
        result = subprocess.run(
            [cli_command, task],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=session_dir,
        )
        duration_ms = int(
            (datetime.now() - start_time).total_seconds() * 1000
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        success = result.returncode == 0

        _write_output_file(session_dir, output_filename,
                           result.returncode, duration_ms, stdout, stderr)

        produced_files = _scan_files(
            session_dir,
            exclude_names=[prompt_filename, output_filename],
            exclude_prefixes=["_stage_"] if stage_prefix else None,
        )

        return {
            "success": success,
            "agent": agent_name,
            "task_id": task_id,
            "session_dir": session_dir,
            "stdout": stdout[:2000] if not stage_prefix else stdout,
            "stdout_full_path": os.path.join(session_dir, output_filename),
            "stderr": stderr[:500] if stderr else "",
            "exit_code": result.returncode,
            "error": None if success else f"exit code {result.returncode}",
            "duration_ms": duration_ms,
            "produced_files": produced_files,
        }

    except subprocess.TimeoutExpired:
        duration_ms = int(
            (datetime.now() - start_time).total_seconds() * 1000
        )
        return {
            "success": False,
            "agent": agent_name,
            "task_id": task_id,
            "session_dir": session_dir,
            "stdout": "",
            "stdout_full_path": None,
            "stderr": "",
            "exit_code": -1,
            "error": f"timeout after {timeout}s",
            "duration_ms": duration_ms,
            "produced_files": [],
        }

    except FileNotFoundError:
        return {
            "success": False,
            "agent": agent_name,
            "task_id": task_id,
            "session_dir": session_dir,
            "stdout": "",
            "stdout_full_path": None,
            "stderr": "",
            "exit_code": -1,
            "error": (
                f"CLI command '{cli_command}' not found. "
                f"Is {agent_name} installed? "
                f"Or switch to API mode by setting 'provider' in forge.yaml."
            ),
            "duration_ms": 0,
            "produced_files": [],
        }


# ═══════════════════════════════════════════════════════════════
# API execution path (new in v0.3)
# ═══════════════════════════════════════════════════════════════

def _execute_api(
    agent_name: str,
    agent_config: dict,
    provider_name: str,
    task: str,
    session_dir: str,
    task_id: str,
    output_filename: str,
    prompt_filename: str,
    timeout: int,
    stage_prefix: Optional[str],
) -> dict:
    """Run an agent via LLM API with tool_use support (v0.4)."""
    from api_client import create_provider
    from tools import get_tools_for_stage

    api_key = agent_config.get("api_key") or agent_config.get("api_key_env", "")
    model = agent_config.get("model", "")
    system_prompt = agent_config.get("system_prompt", None)
    base_delay_ms = agent_config.get("base_delay_ms", 500)
    max_retries = agent_config.get("max_retries", 2)
    max_turns = agent_config.get("max_turns", 10)

    start_time = datetime.now()

    try:
        provider = create_provider(
            provider_name=provider_name,
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            timeout=timeout,
            base_delay_ms=base_delay_ms,
            max_retries=max_retries,
        )

        # ── v0.5: Tool-enabled execution with plain-chat fallback ──
        # Map stage_prefix to stage type for tool selection
        stage_type = stage_prefix if stage_prefix else "coding"
        tools = get_tools_for_stage(stage_type)

        tool_files: list[dict] = []
        try:
            response_text, tool_files = provider.chat_with_tools(
                task=task,
                tools=tools,
                workspace_dir=session_dir,
                max_turns=max_turns,
            )
        except NotImplementedError:
            # Provider doesn't support tool calling (e.g. Gemini) —
            # fall back to plain chat() and extract code blocks from output
            tool_files = []
            response_text = provider.chat(task)

        duration_ms = int(
            (datetime.now() - start_time).total_seconds() * 1000
        )

        _write_output_file(
            session_dir, output_filename,
            0, duration_ms, response_text, stderr="",
        )

        # Extract code blocks as fallback (tool-created files take precedence)
        extracted_files = _extract_code_blocks(
            response_text, session_dir, stage_prefix
        )

        produced_files = _scan_files(
            session_dir,
            exclude_names=[prompt_filename, output_filename],
            exclude_prefixes=["_stage_"] if stage_prefix else None,
        )

        # Merge tool files + extracted code blocks
        seen = {f["path"] for f in produced_files}
        for tf in tool_files:
            if tf["path"] not in seen:
                fullpath = os.path.join(session_dir, tf["path"])
                if os.path.isfile(fullpath):
                    tf["size"] = os.path.getsize(fullpath)
                    produced_files.append(tf)
                    seen.add(tf["path"])
        for ef in extracted_files:
            if ef["path"] not in seen:
                produced_files.append(ef)
                seen.add(ef["path"])

        return {
            "success": True,
            "agent": agent_name,
            "task_id": task_id,
            "session_dir": session_dir,
            "stdout": response_text if stage_prefix else response_text[:2000],
            "stdout_full_path": os.path.join(session_dir, output_filename),
            "stderr": "",
            "exit_code": 0,
            "error": None,
            "duration_ms": duration_ms,
            "produced_files": produced_files,
        }

    except Exception as exc:
        duration_ms = int(
            (datetime.now() - start_time).total_seconds() * 1000
        )
        error_msg = str(exc)

        _write_output_file(
            session_dir, output_filename,
            -1, duration_ms, "", stderr=error_msg,
        )

        return {
            "success": False,
            "agent": agent_name,
            "task_id": task_id,
            "session_dir": session_dir,
            "stdout": "",
            "stdout_full_path": os.path.join(session_dir, output_filename),
            "stderr": error_msg[:500],
            "exit_code": -1,
            "error": error_msg,
            "duration_ms": duration_ms,
            "produced_files": [],
        }


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _write_output_file(
    session_dir: str,
    filename: str,
    exit_code: int,
    duration_ms: int,
    stdout: str,
    stderr: str,
):
    """Persist agent output to a timestamped file."""
    path = os.path.join(session_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Exit Code: {exit_code}\n")
        f.write(f"# Duration: {duration_ms}ms\n")
        f.write("-" * 50 + "\n\n")
        f.write(stdout)
        if stderr:
            f.write("\n\n--- STDERR ---\n\n")
            f.write(stderr)


def _extract_code_blocks(
    text: str,
    session_dir: str,
    stage_prefix: Optional[str] = None,
) -> list[dict]:
    """Extract fenced code blocks from LLM output and save them as files."""
    files: list[dict] = []

    fence_re = re.compile(
        r'^```(\w+)?(?:\s+[:/\\]?\s*([^\s`]+))?\s*$',
        re.MULTILINE,
    )

    blocks: list[tuple[str, str, str]] = []
    pos = 0
    while pos < len(text):
        m = fence_re.search(text, pos)
        if not m:
            break
        lang = (m.group(1) or "").strip()
        path_hint = (m.group(2) or "").strip()
        body_start = m.end()

        close_pos = text.find("\n```", body_start)
        if close_pos == -1:
            pos = body_start
            continue
        body = text[body_start:close_pos].strip()
        pos = close_pos + 4

        if not body:
            continue

        blocks.append((lang, path_hint, body))

    for i, (lang, path_hint, body) in enumerate(blocks):
        filename = _resolve_filename(lang, path_hint, i)
        filepath = os.path.join(session_dir, filename)

        parent = os.path.dirname(filepath)
        if parent:
            os.makedirs(parent, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(body)

        relpath = os.path.relpath(filepath, session_dir)
        size = os.path.getsize(filepath)
        files.append({"path": relpath, "size": size})

    return files


def _resolve_filename(lang: str, path_hint: str, index: int) -> str:
    """Determine the filename for an extracted code block."""
    if path_hint and ("." in path_hint or "/" in path_hint or "\\" in path_hint):
        return path_hint

    ext_map = {
        "python": "py", "py": "py",
        "javascript": "js", "js": "js", "typescript": "ts", "ts": "ts",
        "html": "html", "css": "css",
        "json": "json", "yaml": "yaml", "yml": "yml",
        "sql": "sql", "sh": "sh", "bash": "sh",
        "java": "java", "go": "go", "rust": "rs",
        "c": "c", "cpp": "cpp", "h": "h",
        "jsx": "jsx", "tsx": "tsx", "vue": "vue",
        "markdown": "md", "md": "md",
        "dockerfile": "Dockerfile", "docker": "Dockerfile",
        "toml": "toml", "ini": "ini", "cfg": "cfg",
        "xml": "xml", "svg": "svg",
    }
    ext = ext_map.get(lang.lower(), "txt")
    return f"extracted_{index}.{ext}"


def _generate_task_id(task: str) -> str:
    """Generate a short unique task ID."""
    hash_hex = hashlib.md5(task.encode()).hexdigest()[:8]
    date_str = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"task-{date_str}-{hash_hex}"


def _scan_files(
    directory: str,
    exclude_names: Optional[List[str]] = None,
    exclude_prefixes: Optional[List[str]] = None,
) -> list[dict]:
    """Walk a directory and return metadata for every non-excluded file."""
    excluded_names = set(exclude_names) if exclude_names else set()
    excluded_prefixes_list = exclude_prefixes or []
    files: list[dict] = []
    for root, _, filenames in os.walk(directory):
        for fn in filenames:
            if fn in excluded_names:
                continue
            if any(fn.startswith(p) for p in excluded_prefixes_list):
                continue
            filepath = os.path.join(root, fn)
            relpath = os.path.relpath(filepath, directory)
            size = os.path.getsize(filepath)
            files.append({"path": relpath, "size": size})
    return files
