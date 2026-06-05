#!/usr/bin/env python3
"""
AgentForge v0.5 — Smart Launcher

用法:
  forge "task"              # 流水线 (默认)
  forge -s "task"           # 单任务
  forge --mock "task"       # 流水线 + mock
  forge -s --mock "task"    # 单任务 + mock
  forge                     # 交互 REPL (支持 / 命令)
  forge --gui               # 启动 Web GUI
  forge --serve [port]      # 启动 API 服务器
  forge --build-exe         # 打包为 .exe

Slash Commands (REPL):
  /help       — 查看所有命令
  /clear      — 清屏
  /doctor     — 系统诊断
  /init       — 初始化项目
  /status     — 显示当前状态
  /agents     — 列出可用 Agent
  /pipeline   — 运行流水线
  /model      — 查看/切换模型
  /review     — 代码审查
  /test       — 运行测试
  /file       — 查看文件
  /workspace  — 浏览工作区
  /config     — 查看/修改配置
  /git        — Git 操作
  /memory     — 查看项目知识
  /save       — 保存会话
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
    print("AgentForge v0.5 — Multi-Agent Orchestration Platform")
    print()
    print("用法:")
    print('  forge "task"              # 流水线 (默认)')
    print('  forge -s "task"           # 单任务')
    print('  forge --mock "task"       # 流水线 + mock')
    print('  forge -s --mock "task"    # 单任务 + mock')
    print("  forge                     # 交互 REPL (支持 / 命令)")
    print("  forge --gui               # 启动 Web GUI")
    print("  forge --serve [port]      # 启动 API 服务器")
    print("  forge --build-exe         # 打包为 .exe")
    print()
    print("示例:")
    print('  forge "build a login page with React"')
    print('  forge -s "fix the broken auth middleware"')
    print('  forge --mock "test drive the pipeline"')
    print('  forge                      # 进入交互模式')
    print()
    print("Slash Commands (REPL):")
    print("  /help, /doctor, /init, /status, /agents, /pipeline,")
    print("  /model, /review, /test, /file, /workspace, /config,")
    print("  /git, /memory, /save, /clear")


def _print_repl_help():
    print("""
  AgentForge v0.5 — Interactive REPL
  ==================================

  Quick Start:
    <task>              Run task through pipeline (default)
    s <task>            Run task as single task
    mock on/off         Toggle mock mode

  Slash Commands (/):
    /help               Show this help
    /clear              Clear the screen
    /doctor             Check system (Python, deps, API keys)
    /init [name]        Initialize a new project
    /status             Show current session status
    /agents [name]      List agents or show agent detail
    /pipeline [name] <t>Run a named pipeline
    /model [name]       Show or set model
    /review [pattern]   Review code in workspace
    /test [args]        Run tests
    /file <path>        View a file with line numbers
    /workspace [dir]    Browse workspace
    /config [show|set]  View or modify configuration
    /git [status|commit|log]  Git operations
    /memory             Show CLAUDE.md project knowledge
    /save [file]        Save session summary

  Control:
    quit / exit         Leave the REPL
    Ctrl+C              Cancel current operation
""".strip())


def interactive_mode():
    """Interactive REPL with slash-command support (v0.5)."""
    print("=" * 57)
    print("  AgentForge v0.5 — Interactive Mode")
    print("=" * 57)
    print("  Type /help for slash commands | help for quick ref")
    print("  Type 'quit' or 'exit' to leave")
    print()

    mock_mode = False
    config = load_config()
    config_path = os.path.join(os.path.dirname(__file__), "forge.yaml")
    workspace = os.getcwd()

    # Build shared context for slash commands
    def _make_ctx():
        return {
            "config": config,
            "config_path": config_path,
            "session_dir": None,
            "mock": mock_mode,
            "workspace": workspace,
            "model": "default",
        }

    while True:
        try:
            raw = input("forge> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not raw:
            continue

        # ── Slash commands ──
        if raw.startswith("/"):
            from commands import dispatch as cmd_dispatch
            ctx = _make_ctx()
            result = cmd_dispatch(raw, ctx)

            # Update state from command results
            if "mock" in ctx:
                mock_mode = ctx["mock"]

            if result:
                print(result)
            continue

        # ── Built-in REPL commands ──
        cmd = raw.lower()

        if cmd in ("quit", "exit"):
            print("Bye!")
            break

        if cmd == "help":
            _print_repl_help()
            continue

        if cmd == "mock on":
            mock_mode = True
            print("[mock: ON] — Agent APIs will not be called")
            continue

        if cmd == "mock off":
            mock_mode = False
            print("[mock: OFF] — Live API mode")
            continue

        if cmd == "status":
            ctx = _make_ctx()
            from commands import cmd_status
            print(cmd_status([], ctx))
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

        # ── Default: pipeline ──
        task = raw
        if mock_mode:
            print(f"[mock] pipeline: {task[:60]}")
        _run_pipeline_wrapper(task, mock=mock_mode)


# ═══════════════════════════════════════════════════════════════
# CLI entry
# ═══════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        interactive_mode()
        return

    args = sys.argv[1:]

    # ── Special modes ──

    if "-h" in args or "--help" in args:
        _print_cli_help()
        return

    if "--gui" in args:
        _start_gui(args)
        return

    if "--serve" in args:
        _start_server(args)
        return

    if "--build-exe" in args:
        _build_exe()
        return

    # ── Task modes ──

    single = "-s" in args
    mock = "--mock" in args

    task_parts = [a for a in args if a not in ("-s", "--mock")]
    task = " ".join(task_parts)

    if not task or task == "​":
        _print_cli_help()
        return

    if single:
        _run_single_wrapper(task, mock=mock)
    else:
        _run_pipeline_wrapper(task, mock=mock)


def _start_gui(args: list):
    """Launch the Flask web GUI."""
    try:
        from server import create_app
    except ImportError as e:
        print(f"GUI requires Flask: pip install flask")
        print(f"  Error: {e}")
        print(f"  Run: forge --serve 8080  (headless API mode)")
        sys.exit(1)

    port = 8080
    for i, a in enumerate(args):
        if a == "--gui" and i + 1 < len(args):
            try:
                port = int(args[i + 1])
            except ValueError:
                pass

    host = "127.0.0.1"
    print(f"Starting AgentForge Web GUI...")
    print(f"  Open: http://{host}:{port}")
    print(f"  Press Ctrl+C to stop.")
    print()

    app = create_app()
    app.run(host=host, port=port, debug=False)


def _start_server(args: list):
    """Launch the headless Flask API server."""
    try:
        from server import create_app
    except ImportError as e:
        print(f"Server requires Flask: pip install flask")
        print(f"  Error: {e}")
        sys.exit(1)

    port = 8080
    serve_idx = args.index("--serve")
    if serve_idx + 1 < len(args):
        try:
            port = int(args[serve_idx + 1])
        except ValueError:
            pass

    host = "127.0.0.1"
    print(f"AgentForge API Server v0.5")
    print(f"  Listening: http://{host}:{port}")
    print(f"  Endpoints:")
    print(f"    GET  /api/health        — health check")
    print(f"    POST /api/run           — run pipeline")
    print(f"    GET  /api/status/<id>   — check status")
    print(f"    GET  /api/files/<id>    — list produced files")
    print(f"    GET  /api/config        — get configuration")
    print()

    app = create_app()
    app.run(host=host, port=port, debug=False)


def _build_exe():
    """Package the project as a standalone .exe using PyInstaller."""
    print("AgentForge — Building .exe")
    print("=" * 56)
    print()
    print("This requires PyInstaller: pip install pyinstaller")
    print()

    # Check for PyInstaller
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller not found. Installing...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print()

    # Read build config
    import json
    build_config = {
        "name": "AgentForge",
        "entry": "forge.py",
        "icon": None,
        "onefile": True,
        "console": True,
        "add_data": ["forge.yaml", "templates/", "static/"],
        "hidden_imports": [
            "yaml", "httpx", "dotenv", "commands", "orchestrator",
            "pipeline", "executor", "matcher", "classifier",
            "api_client", "tools", "workspace",
        ],
    }

    print("Build configuration:")
    print(json.dumps(build_config, indent=2))
    print()

    import subprocess

    # Build PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", build_config["name"],
        "--onefile" if build_config["onefile"] else "--onedir",
        "--console" if build_config["console"] else "--windowed",
        "--clean",
        "--noconfirm",
    ]

    for imp in build_config["hidden_imports"]:
        cmd.extend(["--hidden-import", imp])

    for data in build_config["add_data"]:
        sep = ";" if os.name == "nt" else ":"
        cmd.extend(["--add-data", f"{data}{sep}."])

    cmd.append(build_config["entry"])

    print("Running PyInstaller...")
    print(f"  {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, cwd=os.path.dirname(__file__))
    if result.returncode == 0:
        print()
        print("=" * 56)
        print("  Build successful!")
        print(f"  Output: dist/{build_config['name']}.exe")
        print("=" * 56)
    else:
        print()
        print("Build failed. Check the output above for errors.")
        print("Common fixes:")
        print("  1. Ensure all dependencies are installed: pip install -r requirements.txt")
        print("  2. Try running PyInstaller directly:")
        print(f"     pyinstaller --onefile --name AgentForge forge.py")


if __name__ == "__main__":
    main()
