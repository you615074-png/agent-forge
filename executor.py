"""
AgentForge — 执行器
调用本地 CLI Agent，捕获输出，管理超时
"""
import subprocess
import os
import json
import hashlib
from datetime import datetime
from typing import Optional, List


def execute(agent_name: str, cli_command: str, task: str,
            work_dir: str = "./sessions", timeout: int = 120,
            session_dir: Optional[str] = None,
            stage_prefix: Optional[str] = None) -> dict:
    """
    输入:
      agent_name: Agent 名称 (opencode/claudecode/codex/agy)
      cli_command: CLI 命令 (opencode/claude/codex/agy)
      task: 完整的 prompt
      work_dir: 工作目录根路径 (会话子目录会自动创建)
      timeout: 超时秒数
      session_dir: 指定会话目录路径，提供时跳过自动创建子目录
      stage_prefix: 阶段前缀，用于命名 prompt/output 文件

    输出:
      {
        success: bool,
        agent: str,
        task_id: str,
        session_dir: str,
        stdout: str,
        stderr: str,
        exit_code: int,
        error: str | None,
        duration_ms: int
      }
    """
    # 创建会话目录
    if session_dir is None:
        task_id = _generate_task_id(task)
        session_dir = os.path.join(work_dir, task_id)
    else:
        task_id = os.path.basename(session_dir)

    os.makedirs(session_dir, exist_ok=True)

    # 保存任务 prompt
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

    # 执行
    start_time = datetime.now()

    try:
        result = subprocess.run(
            [cli_command, task],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=session_dir,  # Agent 在会话目录中工作
        )

        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        success = result.returncode == 0

        # 保存输出
        output_file = os.path.join(session_dir, output_filename)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# Exit Code: {result.returncode}\n")
            f.write(f"# Duration: {duration_ms}ms\n")
            f.write("-" * 50 + "\n\n")
            f.write(stdout)
            if stderr:
                f.write("\n\n--- STDERR ---\n\n")
                f.write(stderr)

        # 扫描产出文件
        exclude_names = [prompt_filename, output_filename]
        exclude_prefixes = ["_stage_"] if stage_prefix else None
        produced_files = _scan_files(session_dir,
                                     exclude_names=exclude_names,
                                     exclude_prefixes=exclude_prefixes)

        return {
            "success": success,
            "agent": agent_name,
            "task_id": task_id,
            "session_dir": session_dir,
            "stdout": stdout if stage_prefix else stdout[:2000],
            "stdout_full_path": output_file,
            "stderr": stderr[:500] if stderr else "",
            "exit_code": result.returncode,
            "error": None,
            "duration_ms": duration_ms,
            "produced_files": produced_files,
        }

    except subprocess.TimeoutExpired:
        duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
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
            "error": f"CLI command '{cli_command}' not found. Is {agent_name} installed?",
            "duration_ms": 0,
            "produced_files": [],
        }


def _generate_task_id(task: str) -> str:
    """生成简短唯一任务 ID"""
    hash_hex = hashlib.md5(task.encode()).hexdigest()[:8]
    date_str = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"task-{date_str}-{hash_hex}"


def _scan_files(directory: str, exclude_names: Optional[List[str]] = None,
                exclude_prefixes: Optional[List[str]] = None) -> list:
    """扫描目录中产出的代码文件"""
    excluded_names = set(exclude_names) if exclude_names else set()
    excluded_prefixes_list = exclude_prefixes or []
    files = []
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
