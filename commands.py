"""
AgentForge — Slash Command System (v0.5)

Slash commands are the UX backbone — they let users control the forge
without leaving the REPL. Inspired by Claude Code's /commands but
tuned for multi-agent pipeline orchestration.

Architecture:
  Each command is a function decorated with @register_command(...).
  The REPL (forge.py) invokes dispatch(line) which strips the leading
  '/' and routes to the correct handler. Unknown commands get a
  friendly "did you mean?" suggestion.
"""

import os
import sys
import json
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from console import (
    cprint, header, section, dim, bold, green, red, yellow, cyan, magenta,
    ok, fail, Colors, format_file_view, format_config_line, file_item,
)

# ── Command registry ──

_COMMANDS: dict[str, dict] = {}


def register_command(
    name: str,
    description: str,
    aliases: Optional[list[str]] = None,
    usage: Optional[str] = None,
    category: str = "general",
):
    """Register a slash command. Each command is a dict with metadata + handler."""

    def dec(fn: Callable):
        cmd = {
            "name": name,
            "description": description,
            "aliases": aliases or [],
            "usage": usage or f"/{name}",
            "category": category,
            "handler": fn,
        }
        _COMMANDS[name] = cmd
        for alias in (aliases or []):
            _COMMANDS[alias] = cmd
        return fn

    return dec


def get_all_commands() -> dict[str, dict]:
    """Return the command registry."""
    return _COMMANDS


def dispatch(line: str, ctx: dict) -> Optional[str]:
    """
    Route a slash-command line to its handler.

    line: the raw input line (e.g., "/help", "/config show")
    ctx: shared context dict with keys:
         - config: the loaded forge.yaml config
         - session_dir: current session directory
         - mock: bool, whether mock mode is on
         - workspace: path to current workspace

    Returns an optional string to display to the user.
    Commands that change ctx state return the changed ctx keys in their result.
    """
    if not line.startswith("/"):
        return None

    # Strip the leading slash and split
    parts = line[1:].strip().split()
    if not parts:
        return "Type /help to see available commands."

    cmd_name = parts[0].lower()
    args = parts[1:]

    cmd = _COMMANDS.get(cmd_name)
    if not cmd:
        # Friendly suggestions
        suggestions = _suggest(cmd_name, list(_COMMANDS.keys()))
        if suggestions:
            return f"Unknown command '/{cmd_name}'. Did you mean: {', '.join(suggestions)}?"
        return f"Unknown command '/{cmd_name}'. Type /help for available commands."

    try:
        result = cmd["handler"](args, ctx)
        return result
    except Exception as e:
        return f"Command error: {e}"


def _suggest(name: str, candidates: list[str]) -> list[str]:
    """Suggest similar command names using simple prefix/substring matching."""
    matches = []
    for c in set(candidates):
        if c.startswith(name[:2]) or name in c or c in name:
            matches.append(f"/{c}")
    return matches[:3]


# ═══════════════════════════════════════════════════════════════
# COMMAND IMPLEMENTATIONS
# ═══════════════════════════════════════════════════════════════

# ── /help ──

@register_command(
    "help",
    description="Show available commands and their usage",
    aliases=["h", "?"],
    usage="/help [command]",
    category="general",
)
def cmd_help(args: list, ctx: dict) -> str:
    if args:
        # Help for a specific command
        cmd_name = args[0].lstrip("/")
        cmd = _COMMANDS.get(cmd_name)
        if not cmd:
            return f"No help for '{magenta(f'/{cmd_name}')}' — command not found."
        aliases_str = ', '.join(magenta('/' + a) for a in cmd.get('aliases', [])) or dim('none')
        return (
            f"{bold(magenta('/' + cmd['name']))} — {cmd['description']}\n"
            f"  Usage: {cmd['usage']}\n"
            f"  Aliases: {aliases_str}\n"
            f"  Category: {cmd.get('category', 'general')}"
        )

    # Group commands by category
    categories: dict[str, list[dict]] = {}
    seen: set[str] = set()
    for name, cmd in sorted(_COMMANDS.items()):
        if cmd["name"] in seen:
            continue
        seen.add(cmd["name"])
        cat = cmd.get("category", "general")
        categories.setdefault(cat, []).append(cmd)

    # Build output as a string (returned, not printed)
    lines = [
        bold("═" * 56),
        bold("  AgentForge v0.5 — Slash Commands"),
        bold("═" * 56),
        "",
    ]
    for cat, cmds in sorted(categories.items()):
        lines.append(bold(f"  ── {cat.upper()} ──"))
        for c in cmds:
            aliases = ""
            if c.get("aliases"):
                aliases = dim(f" (/{', /'.join(c['aliases'])})")
            # Pad first, then color — avoids ANSI codes breaking column width
            padded_name = ('/' + c['name']).ljust(20)
            lines.append(f"  {magenta(padded_name)} {c['description']}{aliases}")
        lines.append("")

    lines.extend([
        dim("  Type /help <command> for detailed usage."),
        dim("  Use 'mock on' to toggle mock mode."),
        dim("  Use 'quit' or 'exit' to leave."),
    ])
    return "\n".join(lines)


# ── /clear ──

@register_command(
    "clear",
    description="Clear the terminal screen",
    aliases=["cls"],
    usage="/clear",
    category="general",
)
def cmd_clear(args: list, ctx: dict) -> str:
    os.system("cls" if os.name == "nt" else "clear")
    return ""  # Already cleared


# ── /doctor ──

@register_command(
    "doctor",
    description="Check system: Python, deps, API keys, tools",
    usage="/doctor",
    category="general",
)
def cmd_doctor(args: list, ctx: dict) -> str:
    lines = [
        bold("═" * 56),
        bold("  AgentForge — System Check"),
        bold("═" * 56),
        "",
    ]

    # Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 9)
    lines.append(f"  {'Python:':<14s} {py_ver}  {ok() if py_ok else fail('need 3.9+')}")

    # Dependencies — key=display-name, value=(pip-package, import-name)
    deps = {
        "pyyaml": ("pyyaml",      "yaml"),
        "httpx":  ("httpx",       "httpx"),
        "dotenv": ("python-dotenv","dotenv"),
        "flask":  ("flask",       "flask"),
    }
    for label, (pip_pkg, import_name) in deps.items():
        try:
            __import__(import_name)
            lines.append(f"  {label:<14s} {ok('installed')}")
        except ImportError:
            lines.append(f"  {label:<14s} {fail('missing')} — pip install {pip_pkg}")

    # API keys (from config or env)
    config = ctx.get("config", {})
    agents = config.get("agents", {})
    providers_seen: set[str] = set()
    for agent_name, agent in agents.items():
        provider = agent.get("provider", "")
        if provider in providers_seen:
            continue
        providers_seen.add(provider)
        key_env = agent.get("api_key_env", "")
        key_val = os.getenv(key_env, "") if key_env else agent.get("api_key", "")
        status = ok("set") if key_val else fail("not set")
        lines.append(f"  {provider:<14s} {status}  {dim(f'({key_env or \"inline\"})')}")

    # Git availability
    import subprocess
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
        git_ver = result.stdout.strip().split()[-1] if result.stdout else "?"
        lines.append(f"  {'git:':<14s} {ok(git_ver)}")
    except Exception:
        lines.append(f"  {'git:':<14s} {dim('not found (optional)')}")

    # Tools
    lines.append("")
    lines.append(bold("  ── Agent Tools ──"))
    from tools import ALL_TOOLS
    for name, tool in ALL_TOOLS.items():
        danger = yellow(" ⚠ dangerous") if tool.dangerous else ""
        lines.append(f"  {cyan(name):<14s} {tool.description[:50]}...{danger}")

    # Config
    lines.append("")
    lines.append(bold("  ── Configuration ──"))
    lines.append(f"  Config file:  {ctx.get('config_path', 'forge.yaml')}")
    lines.append(f"  Agents:       {len(agents)}")
    pipelines = config.get("pipelines", {})
    lines.append(f"  Pipelines:    {len(pipelines)} ({', '.join(pipelines.keys())})")
    lines.append(f"  Work dir:     {config.get('executor', {}).get('work_dir', './sessions')}")

    return "\n".join(lines)


# ── /init ──

@register_command(
    "init",
    description="Initialize a new project with forge.yaml + CLAUDE.md",
    usage="/init [project-name]",
    category="general",
)
def cmd_init(args: list, ctx: dict) -> str:
    project_name = args[0] if args else os.path.basename(os.getcwd())
    cwd = os.getcwd()

    # Create forge.yaml if it doesn't exist
    forge_yaml_path = os.path.join(cwd, "forge.yaml")
    claude_md_path = os.path.join(cwd, "CLAUDE.md")
    env_example_path = os.path.join(cwd, ".env.example")

    created = []

    if not os.path.exists(forge_yaml_path):
        # Copy default config
        default_config = _get_default_forge_yaml()
        with open(forge_yaml_path, "w", encoding="utf-8") as f:
            f.write(default_config)
        created.append("forge.yaml")

    if not os.path.exists(claude_md_path):
        claude_md = _get_default_claude_md(project_name)
        with open(claude_md_path, "w", encoding="utf-8") as f:
            f.write(claude_md)
        created.append("CLAUDE.md")

    if not os.path.exists(env_example_path):
        env_example = (
            "# AgentForge API Keys\n"
            "ANTHROPIC_API_KEY=sk-ant-xxx\n"
            "OPENAI_API_KEY=sk-xxx\n"
            "GEMINI_API_KEY=xxx\n"
            "DEEPSEEK_API_KEY=sk-xxx\n"
        )
        with open(env_example_path, "w", encoding="utf-8") as f:
            f.write(env_example)
        created.append(".env.example")

    if not os.path.exists(".gitignore"):
        gitignore = (
            ".env\n"
            "sessions/\n"
            "__pycache__/\n"
            "*.pyc\n"
            "dist/\n"
            "build/\n"
            "*.spec\n"
        )
        with open(os.path.join(cwd, ".gitignore"), "w", encoding="utf-8") as f:
            f.write(gitignore)
        created.append(".gitignore")

    if created:
        return (
            f"✓ Initialized {project_name} with: {', '.join(created)}\n\n"
            f"  Next steps:\n"
            f"  1. Set your API keys in .env (cp .env.example .env)\n"
            f"  2. Review forge.yaml — customize agents if needed\n"
            f"  3. Run: forge \"your first task\""
        )
    else:
        return "Project already initialized. Use /config to customize."


# ── /status ──

@register_command(
    "status",
    description="Show current state: mock mode, session, config",
    aliases=["st"],
    usage="/status",
    category="general",
)
def cmd_status(args: list, ctx: dict) -> str:
    mock = ctx.get("mock", False)
    session_dir = ctx.get("session_dir", "")  # raw path, may be empty
    workspace = ctx.get("workspace", os.getcwd())
    model = ctx.get("model", "default")

    mock_status = yellow("ON (no API calls)") if mock else green("OFF")
    session_display = session_dir if session_dir else dim("(none)")
    lines = [
        bold("  AgentForge Status"),
        "",
        f"  Mock mode:    {mock_status}",
        f"  Model:        {cyan(model)}",
        f"  Workspace:    {workspace}",
        f"  Session dir:  {session_display}",
    ]

    # Show recent sessions
    work_dir = ctx.get("config", {}).get("executor", {}).get("work_dir", "./sessions")
    if os.path.isdir(work_dir):
        sessions = sorted(
            [d for d in os.listdir(work_dir) if os.path.isdir(os.path.join(work_dir, d))],
            reverse=True,
        )[:5]
        if sessions:
            session_basename = os.path.basename(session_dir) if session_dir else ""
            lines.append(f"\n  {bold('Recent sessions')} ({len(sessions)}):")
            for s in sessions[:5]:
                marker = cyan("●") if s == session_basename else dim("○")
                lines.append(f"    {marker} {dim(s)}")

    return "\n".join(lines)


# ── /agents ──

@register_command(
    "agents",
    description="List available agents with capabilities",
    usage="/agents [agent-name]",
    category="agent",
)
def cmd_agents(args: list, ctx: dict) -> str:
    config = ctx.get("config", {})
    agents = config.get("agents", {})

    if not agents:
        return "No agents configured. Run /init to create a default forge.yaml."

    if args:
        # Show details for a specific agent
        name = args[0]
        agent = agents.get(name)
        if not agent:
            suggestions = _suggest(name, list(agents.keys()))
            hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
            return f"Agent '{name}' not found.{hint}"
        return _format_agent_detail(name, agent)

    # List all agents
    lines = [
        bold("═" * 56),
        bold("  Agent Legion"),
        bold("═" * 56),
        "",
    ]
    for name, agent in agents.items():
        caps = agent.get("capabilities", {})
        top_caps = sorted(caps.items(), key=lambda x: x[1], reverse=True)[:3]
        caps_str = ", ".join(f"{k}:{v:.0%}" for k, v in top_caps)
        provider = agent.get("provider", agent.get("cli", "?"))
        model = agent.get("model", "?")
        lines.append(f"  {cyan(name):<14s} {model:<22s} {dim('via ' + provider)}")
        lines.append(f"  {'':14s} {dim(agent.get('description', '')[:60])}")
        lines.append(f"  {'':14s} {dim('top:')} {caps_str}")
        lines.append("")

    lines.append(f"  {len(agents)} agents total.")
    lines.append(f"  {magenta('/agents')} <name> for full capability breakdown.")
    return "\n".join(lines)


def _format_agent_detail(name: str, agent: dict) -> str:
    lines = [
        f"═" * 56,
        f"  Agent: {name}",
        f"═" * 56,
        f"  Description: {agent.get('description', 'N/A')}",
        f"  Provider:    {agent.get('provider', agent.get('cli', '?'))}",
        f"  Model:       {agent.get('model', '?')}",
        f"  API Key Env: {agent.get('api_key_env', 'N/A')}",
        "",
        f"  ── Capabilities ──",
    ]
    caps = agent.get("capabilities", {})
    for k, v in sorted(caps.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(v * 20) + "░" * (20 - int(v * 20))
        lines.append(f"  {k:<16s} {bar} {v:.0%}")

    tech = agent.get("tech_preference", [])
    if tech:
        lines.append(f"\n  Tech preferences: {', '.join(tech)}")

    sp = agent.get("system_prompt", "")
    if sp:
        lines.append(f"\n  ── System Prompt (first 200 chars) ──")
        lines.append(f"  {sp[:200]}...")

    return "\n".join(lines)


# ── /pipeline ──

@register_command(
    "pipeline",
    description="Run a named pipeline with a task",
    aliases=["pl", "run"],
    usage="/pipeline [name] <task>",
    category="agent",
)
def cmd_pipeline(args: list, ctx: dict) -> str:
    if not args:
        config = ctx.get("config", {})
        pipelines = config.get("pipelines", {})
        lines = ["Available pipelines:"]
        for name, pl in pipelines.items():
            stages_count = len(pl.get("stages", []))
            lines.append(f"  {name}: {pl.get('description', 'N/A')} ({stages_count} stages)")
        return "\n".join(lines) or "No pipelines configured."

    config = ctx.get("config", {})
    pipelines = config.get("pipelines", {})

    # Check if first arg is a pipeline name
    if args[0] in pipelines:
        pipeline_name = args[0]
        task = " ".join(args[1:]) if len(args) > 1 else ""
    else:
        pipeline_name = "full_dev_cycle"
        task = " ".join(args)

    if not task:
        return f"Usage: /pipeline [{pipeline_name}] <task description>"

    if pipeline_name not in pipelines:
        return f"Pipeline '{pipeline_name}' not found. Available: {list(pipelines.keys())}"

    # Trigger pipeline execution
    from pipeline import run_pipeline
    mock = ctx.get("mock", False)
    print(f"\n  Running pipeline: {pipeline_name}")
    print(f"  Task: {task[:100]}")
    print()
    run_pipeline(pipeline_name, task, config, mock=mock)
    return ""  # Pipeline already printed its output


# ── /compare ──

@register_command(
    "compare",
    description="Run one task through all agents and compare results (v0.6)",
    aliases=["cmp"],
    usage="/compare <task>  or  /compare <task> --agents coder,tester",
    category="agent",
)
def cmd_compare(args: list, ctx: dict) -> str:
    """Multi-plan comparison: same task → all agents → scored ranking."""
    if not args:
        return "Usage: /compare <task description>"

    # Parse optional --agents filter
    agent_filter: list[str] | None = None
    task_parts: list[str] = []
    for a in args:
        if a.startswith("--agents="):
            agent_filter = a.split("=", 1)[1].split(",")
        else:
            task_parts.append(a)

    task = " ".join(task_parts)
    if not task:
        return "Usage: /compare <task description>  [--agents=a,b,c]"

    config = ctx.get("config", {})
    mock = ctx.get("mock", False)

    from compare import compare_plans
    result = compare_plans(task, config, mock=mock, agents_filter=agent_filter)

    if "error" in result:
        return fail(result["error"])

    # Update session tracking
    ctx["session_dir"] = result.get("session_dir", "")
    ctx["workspace"] = result.get("session_dir", ctx.get("workspace", ""))

    return result.get("summary", "Comparison complete.")


# ── /session ──

@register_command(
    "session",
    description="Manage sessions: list, resume, compact, rewind (v0.7)",
    aliases=["sess"],
    usage="/session [list|resume <id>|compact|rewind|info]",
    category="general",
)
def cmd_session(args: list, ctx: dict) -> str:
    """Session lifecycle management."""
    from sessions import (
        list_sessions, resume_session, compact_sessions,
        rewind_session, session_info,
    )

    subcmd = args[0].lower() if args else "list"

    if subcmd == "list":
        config = ctx.get("config", {})
        work_dir = os.path.join(
            os.path.dirname(__file__),
            config.get("executor", {}).get("work_dir", "sessions")
        )
        return list_sessions(work_dir)

    elif subcmd == "resume":
        if len(args) < 2:
            return "Usage: /session resume <session-id>"
        session_id = args[1]
        config = ctx.get("config", {})
        mock = ctx.get("mock", False)
        work_dir = os.path.join(
            os.path.dirname(__file__),
            config.get("executor", {}).get("work_dir", "sessions")
        )
        return resume_session(session_id, work_dir, config, mock)

    elif subcmd == "compact":
        config = ctx.get("config", {})
        work_dir = os.path.join(
            os.path.dirname(__file__),
            config.get("executor", {}).get("work_dir", "sessions")
        )
        keep_days = int(args[1]) if len(args) > 1 else 7
        return compact_sessions(work_dir, keep_days=keep_days)

    elif subcmd == "rewind":
        session_dir = ctx.get("session_dir", "")
        if not session_dir:
            return "No active session. Run a pipeline first, then use /session rewind."
        return rewind_session(session_dir)

    elif subcmd == "info":
        session_dir = ctx.get("session_dir", "")
        if not session_dir:
            session_id = args[1] if len(args) > 1 else ""
            if session_id:
                config = ctx.get("config", {})
                work_dir = os.path.join(
                    os.path.dirname(__file__),
                    config.get("executor", {}).get("work_dir", "sessions")
                )
                session_dir = os.path.join(work_dir, session_id)
        if not session_dir or not os.path.isdir(session_dir):
            return "No session found. Use /session list to see available sessions."
        return session_info(session_dir)

    else:
        return (
            f"Unknown subcommand: {subcmd}\n"
            f"  Available: list, resume <id>, compact [days], rewind, info [id]"
        )


# ── /model ──

@register_command(
    "model",
    description="Show or set the default model for agents",
    usage="/model [model-name]",
    category="config",
)
def cmd_model(args: list, ctx: dict) -> str:
    config = ctx.get("config", {})
    agents = config.get("agents", {})

    if not args:
        # Show current models
        lines = ["Current agent models:"]
        for name, agent in agents.items():
            model = agent.get("model", "?")
            provider = agent.get("provider", "?")
            lines.append(f"  {name:<12s} → {model} (via {provider})")
        return "\n".join(lines)

    # Set model for all agents
    new_model = args[0]
    # Just a display — actual config change requires forge.yaml edit
    ctx["model"] = new_model
    return (
        f"Model set to '{new_model}' for this session.\n"
        f"  To persist: edit forge.yaml and change each agent's 'model' field.\n"
        f"  Current session will use agents' configured models unless overridden."
    )


# ── /switch ──

@register_command(
    "switch",
    description="Switch all agents to a provider profile (deepseek/anthropic/openai/gemini)",
    aliases=["sw"],
    usage="/switch [profile-name]",
    category="config",
)
def cmd_switch(args: list, ctx: dict) -> str:
    """
    Switch all agents to use a predefined provider profile.
    Reads profiles from forge.yaml and applies them to the agents section
    using targeted field replacement (preserves file formatting).

    Examples:
      /switch deepseek    — all agents → DeepSeek
      /switch anthropic   — all agents → Anthropic (Claude)
      /switch openai      — all agents → OpenAI (GPT)
      /switch gemini      — all agents → Gemini
      /switch             — list available profiles
    """
    import re
    import yaml as _yaml

    config = ctx.get("config", {})
    config_path = ctx.get("config_path", "")
    if not config_path:
        config_path = os.path.join(os.path.dirname(__file__), "forge.yaml")

    profiles = config.get("profiles", {})

    if not args:
        if not profiles:
            return "No profiles defined in forge.yaml. Add a 'profiles' section."
        lines = ["Available profiles (use /switch <name>):"]
        for name, profile in profiles.items():
            desc = profile.get("description", "")
            agent_count = len(profile.get("agents", {}))
            lines.append(f"  {name:<14s} — {desc} ({agent_count} agents)")
        return "\n".join(lines)

    profile_name = args[0]
    profile = profiles.get(profile_name)

    if not profile:
        available = list(profiles.keys())
        return (
            f"Unknown profile '{profile_name}'.\n"
            f"  Available: {', '.join(available)}"
        )

    profile_agents = profile.get("agents", {})

    # Read the raw forge.yaml text
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
    except Exception as e:
        return f"Error reading forge.yaml: {e}"

    # For each agent, replace provider/model/api_key_env/description fields
    # using regex that matches the YAML structure
    updated = []
    errors = []

    for agent_name, overrides in profile_agents.items():
        # Match the agent block and replace specific fields
        # Pattern: agent_name: followed by its fields
        agent_pattern = re.compile(
            rf'^  {re.escape(agent_name)}:\s*\n((?:    .*\n?)*)',
            re.MULTILINE,
        )
        match = agent_pattern.search(raw_text)
        if not match:
            errors.append(f"{agent_name}: not found in forge.yaml")
            continue

        agent_block = match.group(0)
        modified_block = agent_block

        for field, value in overrides.items():
            # Replace or insert the field
            field_pattern = re.compile(
                rf'(\n    {re.escape(field)}:\s*).*?(\n    \S|$)',
                re.DOTALL,
            )
            if field_pattern.search(modified_block):
                # Field exists — replace value
                modified_block = field_pattern.sub(
                    rf'\g<1>{value}\2', modified_block
                )
            else:
                # Field doesn't exist — insert after the agent name line
                lines = modified_block.split("\n")
                # Insert after first line (agent name)
                indent = "    "
                lines.insert(1, f"{indent}{field}: {value}")
                modified_block = "\n".join(lines)

        raw_text = raw_text.replace(agent_block, modified_block)
        updated.append(agent_name)

        # Also update in-memory config
        agents = config.get("agents", {})
        if agent_name in agents:
            for key, value in overrides.items():
                agents[agent_name][key] = value

    if not updated:
        return f"No agents were updated. Errors: {', '.join(errors)}"

    # ── Backup + validate + write ──
    # Keep a backup in case the regex corrupts the YAML
    backup_path = config_path + ".bak"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            backup_text = f.read()
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(backup_text)
    except Exception:
        backup_text = None  # Can't back up — proceed carefully

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(raw_text)
    except Exception as e:
        return f"Error saving forge.yaml: {e}"

    # Validate: does the result parse as valid YAML?
    import yaml as _yaml2
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            _yaml2.safe_load(f)
    except Exception as parse_err:
        # Restore from backup
        if backup_text is not None:
            try:
                with open(config_path, "w", encoding="utf-8") as f:
                    f.write(backup_text)
                return (
                    f"{fail('Switch failed')}: invalid YAML after write — restored backup.\n"
                    f"  Parse error: {parse_err}\n"
                    f"  Your forge.yaml is unchanged."
                )
            except Exception:
                pass
        return f"{fail('Switch failed')}: produced invalid YAML: {parse_err}"

    # Clean up backup on success
    try:
        if os.path.exists(config_path + ".bak"):
            os.remove(config_path + ".bak")
    except Exception:
        pass

    ctx["config"] = config
    desc = profile.get("description", profile_name)
    lines = [
        f"  {ok('Switched to:')} {bold(profile_name)}",
        f"  {dim(desc)}",
        f"  {bold('Updated:')} {', '.join(cyan(a) for a in updated)}",
    ]
    if errors:
        lines.append(f"  {yellow('⚠')} Warnings: {', '.join(errors)}")
    lines.append("")
    lines.append(f"  {bold('Agent configuration:')}")
    agents = config.get("agents", {})
    for name in updated:
        agent = agents[name]
        lines.append(f"  {cyan(name):<12s} → {agent['model']} {dim('(' + agent['provider'] + ')')}")
    lines.append("")
    lines.append(dim("  Re-run your task to use the new profile."))

    return "\n".join(lines)


# ── /review ──

@register_command(
    "review",
    description="Review code in the workspace (uses reviewer agent)",
    usage="/review [file-pattern]",
    category="agent",
)
def cmd_review(args: list, ctx: dict) -> str:
    from orchestrator import load_config
    from executor import execute

    config = ctx.get("config", {})
    if not config:
        config = load_config()

    file_pattern = args[0] if args else "all files"
    task = f"Review the code in the workspace. Focus on: {file_pattern}. "
    task += "Identify bugs, security issues, edge cases, and style problems."

    reviewer = config.get("agents", {}).get("reviewer")
    if not reviewer:
        return "No 'reviewer' agent configured. Check your forge.yaml."

    session_dir = ctx.get("session_dir") or os.path.join(
        os.getcwd(), config.get("executor", {}).get("work_dir", "./sessions"),
        f"review-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    )
    os.makedirs(session_dir, exist_ok=True)

    print(f"\n  Running reviewer ({reviewer.get('model', '?')})...\n")
    result = execute(
        agent_name="reviewer",
        agent_config=reviewer,
        task=task,
        work_dir=os.path.dirname(session_dir),
        session_dir=session_dir,
        stage_prefix="review",
    )

    if result.get("success"):
        return result.get("stdout", "Review complete — no output.")
    else:
        return f"Review failed: {result.get('error', 'unknown error')}"


# ── /test ──

@register_command(
    "test",
    description="Run tests in the workspace",
    usage="/test [test-args]",
    category="agent",
)
def cmd_test(args: list, ctx: dict) -> str:
    import subprocess

    ws = ctx.get("workspace", os.getcwd())
    test_args = " ".join(args) if args else ""

    # Try pytest first, then other frameworks
    commands = [
        f"pytest {test_args} -v --tb=short",
        f"python -m pytest {test_args} -v --tb=short",
    ]

    # Check for JS/TS test frameworks
    if os.path.exists(os.path.join(ws, "package.json")):
        commands.extend([
            f"npm test -- {test_args}",
            f"npx jest {test_args}",
            f"npx vitest run {test_args}",
        ])

    for cmd in commands:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=120, cwd=ws,
            )
            out = result.stdout.strip()
            err = result.stderr.strip()
            if out:
                return out[:4000]
            if err:
                return f"[stderr]\n{err[:2000]}"
            return f"Tests completed (exit {result.returncode})"
        except subprocess.TimeoutExpired:
            continue
        except Exception:
            continue

    return "No test runner found. Tried: pytest, npm test, jest, vitest."


# ── /file ──

@register_command(
    "file",
    description="Read a file from the workspace and display it",
    usage="/file <path>",
    category="file",
)
def cmd_file(args: list, ctx: dict) -> str:
    if not args:
        return "Usage: /file <path>"

    ws = ctx.get("workspace", os.getcwd())
    session_dir = ctx.get("session_dir", "")

    # Search order: 1) session_dir  2) workspace
    search_dirs = [d for d in (session_dir, ws) if d]
    found_path = None
    for base in search_dirs:
        candidate = os.path.join(base, args[0])
        if os.path.exists(candidate):
            found_path = candidate
            break

    if not found_path:
        searched = "\n  ".join(search_dirs)
        return f"File not found: {args[0]}\n  Searched in:\n  {searched}"

    path = found_path

    if os.path.isdir(path):
        # List directory
        entries = sorted(os.listdir(path))
        lines = [f"Directory: {args[0]}", ""]
        for e in entries[:50]:
            full = os.path.join(path, e)
            marker = "/" if os.path.isdir(full) else ""
            size = f" ({os.path.getsize(full)}B)" if os.path.isfile(full) else ""
            lines.append(f"  {e}{marker}{size}")
        if len(entries) > 50:
            lines.append(f"  ... ({len(entries) - 50} more entries)")
        return "\n".join(lines)

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        return f"{fail()} Error reading file: {e}"

    return format_file_view(args[0], content)


# ── /workspace ──

@register_command(
    "workspace",
    description="Show workspace directory structure",
    aliases=["ws", "ls"],
    usage="/workspace [subdir]",
    category="file",
)
def cmd_workspace(args: list, ctx: dict) -> str:
    from workspace import list_workspace

    ws = ctx.get("workspace", os.getcwd())
    session_dir = ctx.get("session_dir", "")
    # Prefer session_dir for latest pipeline output, fall back to workspace
    base = session_dir if session_dir and os.path.isdir(session_dir) else ws
    subdir = args[0] if args else base
    if not os.path.isabs(subdir):
        subdir = os.path.join(base, subdir)

    if not os.path.isdir(subdir):
        return f"Directory not found: {subdir}"

    tree = list_workspace(subdir, max_depth=3)
    return f"Workspace: {subdir}\n\n{tree}"


# ── /config ──

@register_command(
    "config",
    description="Show or set configuration values",
    aliases=["cfg"],
    usage="/config [show|set <key> <value>]",
    category="config",
)
def cmd_config(args: list, ctx: dict) -> str:
    if not args or args[0] == "show":
        config = ctx.get("config", {})
        return _format_config_summary(config)

    if args[0] == "set":
        if len(args) < 3:
            return "Usage: /config set <key> <value>\n  Example: /config set executor.timeout_seconds 600"
        # Note: config changes only apply to current session
        key = args[1]
        value = args[2]
        # Try to parse value
        if value.lower() in ("true", "false"):
            value = value.lower() == "true"
        elif value.isdigit():
            value = int(value)

        config = ctx.get("config", {})
        # Support dot notation: executor.timeout_seconds
        keys = key.split(".")
        target = config
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

        return (
            f"Set {key} = {value} (session only)\n"
            f"  To persist, edit forge.yaml directly."
        )

    return f"Unknown config subcommand: {args[0]}. Use: /config show  or  /config set <key> <value>"


def _format_config_summary(config: dict) -> str:
    lines = [
        bold("═" * 56),
        bold("  Configuration"),
        bold("═" * 56),
        "",
    ]

    # API settings
    api = config.get("api", {})
    lines.append(bold("  ── API ──"))
    for k, v in api.items():
        lines.append(format_config_line(k, v))

    # Agents
    agents = config.get("agents", {})
    lines.append(f"\n  {bold('── Agents')} ({len(agents)}) {bold('──')}")
    for name, agent in agents.items():
        provider = agent.get("provider", "?")
        model = agent.get("model", "?")
        lines.append(f"  {cyan(name)}: {model} {dim('via ' + provider)}")

    # Pipelines
    pipelines = config.get("pipelines", {})
    lines.append(f"\n  {bold('── Pipelines')} ({len(pipelines)}) {bold('──')}")
    for name, pl in pipelines.items():
        stages = pl.get("stages", [])
        stage_ids = [s.get("id", "?") for s in stages]
        lines.append(f"  {magenta(name)}: {' → '.join(stage_ids)}")

    # Executor
    exe = config.get("executor", {})
    lines.append(f"\n  {bold('── Executor')} {bold('──')}")
    for k, v in exe.items():
        lines.append(format_config_line(k, v))

    return "\n".join(lines)


# ── /git ──

@register_command(
    "git",
    description="Git operations: status, commit, log",
    usage="/git [status|commit|log]",
    category="general",
)
def cmd_git(args: list, ctx: dict) -> str:
    import subprocess

    ws = ctx.get("workspace", os.getcwd())
    subcmd = args[0] if args else "status"

    if subcmd == "status":
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True, text=True, timeout=10,
                cwd=ws,
            )
            out = result.stdout.strip()
            return out if out else "(clean — nothing to commit)"
        except Exception as e:
            return f"Git not available: {e}"

    elif subcmd == "commit":
        msg = " ".join(args[1:]) if len(args) > 1 else "AgentForge auto-commit"
        try:
            # Stage all changes
            subprocess.run(["git", "add", "-A"], capture_output=True, cwd=ws, timeout=10)
            result = subprocess.run(
                ["git", "commit", "-m", msg],
                capture_output=True, text=True, timeout=10,
                cwd=ws,
            )
            out = result.stdout.strip()
            err = result.stderr.strip()
            if result.returncode == 0:
                return f"✓ Committed:\n{out}"
            return f"Commit failed:\n{err}"
        except Exception as e:
            return f"Git not available: {e}"

    elif subcmd == "log":
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-10"],
                capture_output=True, text=True, timeout=10,
                cwd=ws,
            )
            out = result.stdout.strip()
            if out:
                return f"Recent commits:\n{out}"
            return "(no commits yet)"
        except Exception as e:
            return f"Git not available: {e}"

    else:
        return f"Unknown git subcommand: {subcmd}. Use: status, commit, log"


# ── /memory ──

@register_command(
    "memory",
    description="Show project memory (CLAUDE.md)",
    usage="/memory",
    category="file",
)
def cmd_memory(args: list, ctx: dict) -> str:
    ws = ctx.get("workspace", os.getcwd())
    claude_md = os.path.join(ws, "CLAUDE.md")

    if not os.path.exists(claude_md):
        # Also check parent directories
        current = ws
        for _ in range(3):
            parent = os.path.dirname(current)
            if parent == current:
                break
            claude_md = os.path.join(parent, "CLAUDE.md")
            if os.path.exists(claude_md):
                break
            current = parent
        else:
            return (
                "No CLAUDE.md found in workspace.\n"
                "  Run /init to create one.\n"
                "  CLAUDE.md stores project knowledge, conventions, and context."
            )

    try:
        with open(claude_md, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return f"Error reading CLAUDE.md: {e}"

    return f"CLAUDE.md ({len(content)} chars):\n{'─' * 56}\n{content}"


# ── /save ──

@register_command(
    "save",
    description="Save current session summary to file",
    usage="/save [filename]",
    category="general",
)
def cmd_save(args: list, ctx: dict) -> str:
    session_dir = ctx.get("session_dir", "")
    if not session_dir or not os.path.isdir(session_dir):
        return "No active session to save."

    filename = args[0] if args else f"session-summary-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    filepath = os.path.join(session_dir, filename)

    # Collect session info
    lines = [
        f"# AgentForge Session Summary",
        f"Date: {datetime.now().isoformat()}",
        f"",
    ]

    # List produced files
    for root, dirs, filenames in os.walk(session_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fn in filenames:
            if fn.startswith("_stage_"):
                lines.append(f"## {fn}")
                try:
                    with open(os.path.join(root, fn), "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()[:1000]
                    lines.append(f"```\n{content}\n```\n")
                except Exception:
                    pass

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return f"Session saved to: {filepath}"


# ═══════════════════════════════════════════════════════════════
# Default config / CLAUDE.md templates
# ═══════════════════════════════════════════════════════════════

def _get_default_forge_yaml() -> str:
    return textwrap.dedent("""\
    # ============================================================
    # AgentForge — Multi-Agent Orchestration Platform
    # ============================================================
    #
    # Quick start:
    #   1. cp .env.example .env  (and fill in your API keys)
    #   2. pip install -r requirements.txt
    #   3. forge "build a calculator in Python"
    #
    # Or launch the GUI:
    #   forge --gui
    # ============================================================

    api:
      base_delay_ms: 500
      max_retries: 2
      timeout_seconds: 300

    agents:
      coder:
        description: "Primary developer — Claude Opus 4.8"
        provider: anthropic
        model: claude-opus-4-8
        api_key_env: ANTHROPIC_API_KEY
        system_prompt: |
          You are an expert software engineer. Write clean, well-structured,
          production-quality code. Include comments for non-obvious logic.
          Prefer standard libraries over third-party dependencies.
          When asked to create a project, produce complete, runnable files.
        capabilities:
          coding: 0.95
          architecture: 0.90
          fullstack: 0.88
          debugging: 0.75
          review: 0.60
          testing: 0.55
          reasoning: 0.80
          quick_fix: 0.70
          documentation: 0.70
        tech_preference:
          - python
          - typescript
          - react
          - node.js

      reviewer:
        description: "Code reviewer — Claude Sonnet 4.6"
        provider: anthropic
        model: claude-sonnet-4-6
        api_key_env: ANTHROPIC_API_KEY
        system_prompt: |
          You are a thorough code reviewer. For every file you examine:
          1. Identify bugs, edge cases, and logic errors
          2. Flag security vulnerabilities (injection, auth, data leaks)
          3. Suggest performance improvements
          4. Note style/readability issues

          If you find ANY issues that need fixing, append __HAS_ISSUES__
          to the END of your response.
        capabilities:
          coding: 0.72
          architecture: 0.75
          fullstack: 0.60
          debugging: 0.75
          review: 0.95
          testing: 0.55
          reasoning: 0.92
          quick_fix: 0.60
          documentation: 0.92
        tech_preference:
          - any

      bugfixer:
        description: "Bug fixer — Claude Sonnet 4.6"
        provider: anthropic
        model: claude-sonnet-4-6
        api_key_env: ANTHROPIC_API_KEY
        system_prompt: |
          You are a bug-fixing specialist. Given a code review that identifies
          issues, fix every problem listed. For each fix:
          1. Explain what was wrong (1-2 lines)
          2. Provide the corrected code
        capabilities:
          coding: 0.75
          architecture: 0.55
          fullstack: 0.50
          debugging: 0.92
          review: 0.60
          testing: 0.50
          reasoning: 0.72
          quick_fix: 0.95
          documentation: 0.50
        tech_preference:
          - any

      tester:
        description: "Test engineer — Claude Haiku 4.5"
        provider: anthropic
        model: claude-haiku-4-5
        api_key_env: ANTHROPIC_API_KEY
        system_prompt: |
          You are a test engineer. Write comprehensive tests for the provided
          code. Include unit tests, edge case coverage, and basic integration
          tests where applicable.
        capabilities:
          coding: 0.65
          architecture: 0.60
          fullstack: 0.55
          debugging: 0.70
          review: 0.70
          testing: 0.95
          reasoning: 0.75
          quick_fix: 0.55
          documentation: 0.75
          verification: 0.95
        tech_preference:
          - any

    classifier:
      rules:
        - type: testing
          keywords: ["test", "验证", "验收", "单元测试"]
          targets: []
        - type: review
          keywords: ["审查", "review", "检查", "code review", "check", "audit"]
          targets: []
        - type: bugfix
          keywords: ["修复", "bug", "报错", "异常", "fix", "error", "broken"]
          targets: []
        - type: refactor
          keywords: ["重构", "优化", "改进", "refactor", "optimize", "improve"]
          targets: []
        - type: documentation
          keywords: ["文档", "注释", "readme", "docs", "documentation"]
          targets: []
        - type: analysis
          keywords: ["分析", "解释", "为什么", "原理", "analyze", "explain"]
          targets: []
        - type: coding
          keywords: ["写", "开发", "实现", "创建", "搭建", "生成", "build", "create", "implement", "develop", "write", "make", "code"]
          targets: []
      fallback: coding

    match_weights:
      coding:
        coding: 1.0
        architecture: 0.6
        fullstack: 0.5
      review:
        review: 1.0
        reasoning: 0.6
        documentation: 0.3
      bugfix:
        debugging: 1.0
        quick_fix: 0.9
        coding: 0.4
      testing:
        testing: 1.0
        verification: 0.8
        debugging: 0.3
      analysis:
        reasoning: 1.0
        review: 0.5
        architecture: 0.4
      refactor:
        coding: 1.0
        architecture: 0.7
        review: 0.3
      documentation:
        documentation: 1.0
        reasoning: 0.5
        review: 0.3

    executor:
      timeout_seconds: 300
      work_dir: "sessions"

    # ── Git integration (new in v0.5) ──
    git:
      auto_commit: false
      commit_message_template: "AgentForge: {task_summary}"
      branch_prefix: "forge/"

    # ── Test feedback loop (new in v0.5) ──
    test_loop:
      enabled: true
      max_iterations: 3
      fix_prompt: |
        The tests you wrote failed with the following output:

        {test_output}

        Fix the failing tests AND the source code if necessary. Make all tests pass.

    pipelines:
      full_dev_cycle:
        description: "Code → Review → Fix(conditional) → Test"
        stages:
          - id: coding
            type: coding
            prompt: '{original_task}'
          - id: review
            type: review
            prompt: |
              Original task: {original_task}

              The following files were produced by the coding stage and are
              available in the working directory:

              {previous_files}

              Review each file thoroughly.
              If you find ANY issues, append __HAS_ISSUES__ at the end.
            pass_files: true
          - id: bugfix
            type: bugfix
            prompt: |
              Original task: {original_task}

              The code review identified these issues:
              {previous_stdout}

              All project files are in the working directory:
              {all_files}

              Fix every issue listed above.
            pass_files: true
            condition:
              stage: review
              marker: "__HAS_ISSUES__"
              fallback_check: true
          - id: testing
            type: testing
            prompt: |
              Original task: {original_task}

              Project files in working directory:
              {all_files}

              Write comprehensive tests, then RUN them to verify they pass.
              If tests fail, fix them until they pass.
            pass_files: true
    """)


def _get_default_claude_md(project_name: str) -> str:
    return textwrap.dedent(f"""\
    # {project_name} — Project Knowledge

    ## Architecture
    (Describe your project architecture here)

    ## Conventions
    - (e.g., Use TypeScript strict mode)
    - (e.g., Prettier for formatting, ESLint for linting)

    ## Tech Stack
    - (List your primary technologies)

    ## Testing
    - (Describe your testing strategy)

    ## AgentForge
    This project uses AgentForge for multi-agent development workflows.
    See `forge.yaml` for agent and pipeline configuration.
    """)
