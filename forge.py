#!/usr/bin/env python3
"""
AgentForge v0.7.0 — Smart Launcher

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
  /switch     — 切换Provider配置
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
from console import cprint, styled, header, section, Colors, bold, dim, green, cyan, magenta, ok

PIPELINE_NAME = "full_dev_cycle"


def _run_pipeline_wrapper(task: str, mock: bool):
    config = load_config()
    result = run_pipeline(PIPELINE_NAME, task, config, mock=mock)
    return result.get("session_dir") if isinstance(result, dict) else None


def _run_single_wrapper(task: str, mock: bool):
    return dispatch(task, mock=mock)


def _print_cli_help():
    header("AgentForge v0.5 — Multi-Agent Orchestration Platform", 56)
    print()
    cprint("  Usage:", style=Colors.BOLD)
    print(f'  {cyan("forge")} "task"              {dim("# Pipeline (default)")}')
    print(f'  {cyan("forge")} -s "task"           {dim("# Single task")}')
    print(f'  {cyan("forge")} --mock "task"       {dim("# Pipeline + mock")}')
    print(f'  {cyan("forge")} -s --mock "task"    {dim("# Single task + mock")}')
    print(f"  {cyan('forge')}                     {dim('# Interactive REPL (/ commands)')}")
    print(f"  {cyan('forge')} --gui               {dim('# Launch Web GUI')}")
    print(f"  {cyan('forge')} --serve [port]      {dim('# Start API server')}")
    print(f"  {cyan('forge')} --build-exe         {dim('# Package as .exe')}")
    print()
    cprint("  Examples:", style=Colors.BOLD)
    print(f'  {cyan("forge")} "build a login page with React"')
    print(f'  {cyan("forge")} -s "fix the broken auth middleware"')
    print(f'  {cyan("forge")} --mock "test drive the pipeline"')
    print()
    cprint("  Slash Commands:", style=Colors.BOLD)
    print(f"  {magenta('/help')}, {magenta('/doctor')}, {magenta('/init')}, {magenta('/status')}, {magenta('/agents')}, {magenta('/pipeline')},")
    print(f"  {magenta('/compare')}, {magenta('/model')}, {magenta('/switch')}, {magenta('/review')}, {magenta('/test')},")
    print(f"  {magenta('/file')}, {magenta('/workspace')}, {magenta('/config')}, {magenta('/session')},")
    print(f"  {magenta('/git')}, {magenta('/memory')}, {magenta('/save')}, {magenta('/clear')}")


def _print_repl_help():
    header("AgentForge v0.5 — Interactive REPL")

    cprint("  Quick Start:", style=Colors.BOLD)
    print(f"    {cyan('<task>')}              {dim('Run task through pipeline (default)')}")
    print(f"    s <task>            {dim('Run task as single task')}")
    print(f"    {green('mock on')}/off         {dim('Toggle mock mode')}")

    cprint("\n  Slash Commands:", style=Colors.BOLD)
    commands_help = [
        ("/help",           "Show this help"),
        ("/clear",          "Clear the screen"),
        ("/doctor",         "Check system (Python, deps, API keys)"),
        ("/init [name]",    "Initialize a new project"),
        ("/status",         "Show current session status"),
        ("/agents [name]",  "List agents or show agent detail"),
        ("/pipeline [n] <t>","Run a named pipeline"),
        ("/compare <task>",  "Compare all agents on one task (v0.6)"),
        ("/model [name]",   "Show or set model"),
        ("/switch [profile]","Switch provider profile"),
        ("/session [cmd]",   "Manage sessions: list/resume/compact (v0.7)"),
        ("/review [pattern]","Review code in workspace"),
        ("/test [args]",    "Run tests"),
        ("/file <path>",    "View a file with line numbers"),
        ("/workspace [dir]", "Browse workspace"),
        ("/config [show|set]","View or modify configuration"),
        ("/git [status|commit|log]","Git operations"),
        ("/memory",         "Show CLAUDE.md project knowledge"),
        ("/save [file]",    "Save session summary"),
    ]
    for cmd, desc in commands_help:
        print(f"    {magenta(cmd):<22s} {desc}")

    cprint("\n  Control:", style=Colors.BOLD)
    print(f"    {cyan('quit')} / exit         Leave the REPL")
    print(f"    Ctrl+C              Cancel current operation")


def interactive_mode():
    """Interactive REPL with slash-command support (v0.5)."""
    header("AgentForge v0.5 — Interactive Mode", 57)
    cprint(f"  Type {magenta('/help')} for slash commands | {cyan('help')} for quick ref", style=Colors.DIM)
    cprint(f"  Type {cyan('quit')} or {cyan('exit')} to leave\n", style=Colors.DIM)

    mock_mode = False
    config = load_config()
    config_path = os.path.join(os.path.dirname(__file__), "forge.yaml")
    workspace = os.getcwd()
    last_session_dir = None  # Track latest pipeline session

    # Build shared context for slash commands
    def _make_ctx():
        return {
            "config": config,
            "config_path": config_path,
            "session_dir": last_session_dir,
            "mock": mock_mode,
            "workspace": last_session_dir or workspace,
            "model": "default",
        }

    while True:
        try:
            raw = input(styled("forge> ", fg=Colors.GREEN) + " ").strip()
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
            cprint(f"  {ok('Mock ON')} — Agent APIs will not be called")
            continue

        if cmd == "mock off":
            mock_mode = False
            cprint(f"  {green('Mock OFF')} — Live API mode")
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
            result = _run_single_wrapper(task, mock=mock_mode)
            if isinstance(result, dict):
                last_session_dir = result.get("session_dir", last_session_dir)
            continue

        # ── Default: pipeline ──
        task = raw
        if mock_mode:
            print(f"[mock] pipeline: {task[:60]}")
        sd = _run_pipeline_wrapper(task, mock=mock_mode)
        if sd:
            last_session_dir = sd


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
