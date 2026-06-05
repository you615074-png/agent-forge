#!/usr/bin/env python3
"""
AgentForge — Smart Launcher

用法:
  forge "task"              # 流水线 (默认)
  forge -s "task"           # 单任务
  forge --mock "task"       # 流水线 + mock
  forge -s --mock "task"    # 单任务 + mock
  forge                     # 交互 REPL
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrator import load_config, dispatch
from pipeline import run_pipeline

PIPELINE_NAME = "full_dev_cycle"


def _run_pipeline_wrapper(task: str, mock: bool):
    config = load_config()
    run_pipeline(PIPELINE_NAME, task, config, mock=mock)


def _run_single_wrapper(task: str, mock: bool):
    dispatch(task, mock=mock)


def _print_cli_help():
    print("AgentForge v0.3")
    print()
    print("用法:")
    print('  forge "task"              # 流水线 (默认)')
    print('  forge -s "task"           # 单任务')
    print('  forge --mock "task"       # 流水线 + mock')
    print('  forge -s --mock "task"    # 单任务 + mock')
    print("  forge                     # 交互 REPL")
    print()
    print("示例:")
    print('  forge "build a login page with React"')
    print('  forge -s "fix the broken auth middleware"')
    print('  forge --mock "test drive the pipeline"')
    print('  forge                      # 进入交互模式')


def _print_repl_help():
    print("""
  Commands:
    <task>                Run task through pipeline (default)
    s <task>              Run task as single task
    mock on/off           Toggle mock mode
    help                  Show this help
    quit / exit           Exit

  Examples:
    forge> build a calculator
    forge> s fix the login bug
    forge> mock on
    forge> test task
""".strip())


def interactive_mode():
    """交互 REPL 模式"""
    print("=" * 50)
    print("  AgentForge v0.3 — Interactive Mode")
    print("=" * 50)
    print("  Default: pipeline | s=  single | mock on/off")
    print("  Type 'help' or 'quit'")
    print()

    mock_mode = False

    while True:
        try:
            raw = input("forge> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not raw:
            continue

        cmd = raw.lower()

        if cmd in ("quit", "exit"):
            print("Bye!")
            break

        if cmd == "help":
            _print_repl_help()
            continue

        if cmd == "mock on":
            mock_mode = True
            print("[mock: ON]  (Agent will not be invoked)")
            continue

        if cmd == "mock off":
            mock_mode = False
            print("[mock: OFF]")
            continue

        if cmd == "status":
            print(f"  mock: {'ON' if mock_mode else 'OFF'}")
            print(f"  mode: pipeline (use s= for single task)")
            continue

        if raw.startswith("s "):
            task = raw[2:].strip()
            if not task:
                print("  Usage: s <task description>")
                continue
            if mock_mode:
                print(f"[mock] single task: {task[:60]}")
            _run_single_wrapper(task, mock=mock_mode)
            continue

        # 默认：流水线
        task = raw
        if mock_mode:
            print(f"[mock] pipeline: {task[:60]}")
        _run_pipeline_wrapper(task, mock=mock_mode)


def main():
    if len(sys.argv) < 2:
        interactive_mode()
        return

    args = sys.argv[1:]

    if "-h" in args or "--help" in args:
        _print_cli_help()
        return

    single = "-s" in args
    mock = "--mock" in args

    task_parts = [a for a in args if a not in ("-s", "--mock")]
    task = " ".join(task_parts)

    if not task or task == "`\u200b`":
        _print_cli_help()
        return

    if single:
        _run_single_wrapper(task, mock=mock)
    else:
        _run_pipeline_wrapper(task, mock=mock)


if __name__ == "__main__":
    main()
