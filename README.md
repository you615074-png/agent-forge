# AgentForge v0.5 — Multi-Agent Collaboration Platform

> API-driven multi-agent orchestration | 4-stage pipeline | Slash commands | Web GUI | .exe ready

---

## What is AgentForge?

A framework that chains multiple LLM agents into a structured development pipeline — **using API keys instead of external CLI tools**. Think of it as a multi-agent template for Claude Code-like experiences.

```
forge "Build a React calculator"
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│                     AgentForge                            │
│                                                          │
│  Stage 1: coding  → Claude Opus 4.8    (write_file)      │
│  Stage 2: review  → Claude Sonnet 4.6  (read_file)       │
│  Stage 3: bugfix  → Claude Sonnet 4.6  (conditional)     │
│  Stage 4: testing → Claude Haiku 4.5   (bash: pytest)    │
│                                                          │
│  Test fails? → auto-fix loop (v0.5)                      │
│  Git auto-commit after each stage (v0.5, opt-in)         │
│  Shared workdir  |  Context inlining  |  Archive          │
└──────────────────────────────────────────────────────────┘
```

**v0.5 highlights**: Slash commands (`/help`, `/doctor`, `/agents`, ...), Web GUI, test feedback loop (auto-fix failing tests), git integration, .exe packaging.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/you615074-png/agent-forge.git
cd agent-forge

# 2. Install
pip install -r requirements.txt

# 3. Set your API key
#    Windows PowerShell:
$env:ANTHROPIC_API_KEY = "sk-ant-xxx"
#    Linux/macOS:
export ANTHROPIC_API_KEY=sk-ant-xxx

# 4. Run
python forge.py "build a hello world web app with Flask"
```

**Don't have an Anthropic key?** Use DeepSeek (cheaper):
```bash
$env:DEEPSEEK_API_KEY = "sk-xxx"
# Edit forge.yaml: change each agent's `provider: anthropic` to `provider: deepseek`
# and `model: claude-opus-4-8` to `model: deepseek-chat`
```

---

## Usage

### CLI Modes

```bash
forge "task"                    # Pipeline mode (default)
forge -s "task"                 # Single task mode
forge --mock "task"             # Dry run (no API calls)
forge                           # Interactive REPL with /commands
forge --gui                     # Launch Web GUI (Flask, port 8080)
forge --serve 9090              # Launch headless API server
```

### Interactive REPL with Slash Commands

```
forge> /help                    Show all slash commands
forge> /doctor                  System check (Python, deps, API keys)
forge> /init my-project         Initialize project with forge.yaml + CLAUDE.md
forge> /status                  Show current session status
forge> /agents                  List all agents with capabilities
forge> /agents coder            Show coder agent details
forge> /pipeline full_dev_cycle Build a Python CLI tool
forge> /model                   Show current models
forge> /review                  Review code in workspace
forge> /test -v                 Run tests
forge> /file src/main.py        View file with line numbers
forge> /workspace               Browse workspace tree
forge> /config show             View configuration
forge> /git status              Git status
forge> /git commit "message"    Auto-commit changes
forge> /memory                  Show CLAUDE.md project knowledge
forge> /save                    Save session summary
forge> /clear                   Clear screen

forge> mock on                  Toggle mock mode
forge> s fix the auth bug       Single task
forge> build a calculator       Pipeline (default)
forge> quit                     Exit
```

### Web GUI

```bash
python forge.py --gui
# Open http://127.0.0.1:8080
```

Features:
- Task input with pipeline selection
- Real-time pipeline progress (4-stage badges + progress bar)
- Live output viewer with success/failure indicators
- File browser (click to view content)
- Session history browser
- Configuration viewer
- Agent capability viewer
- Quick action buttons (Doctor, Review, Test, Git)

---

## Agent Legion

Default config uses **all-Anthropic** — one API key runs the entire pipeline:

| Agent | Model | Role | Core Strength |
|---|---|---|---|
| coder | Claude Opus 4.8 | Full-stack development | coding 0.95 / architecture 0.90 |
| reviewer | Claude Sonnet 4.6 | Code review + analysis | review 0.95 / reasoning 0.92 |
| bugfixer | Claude Sonnet 4.6 | Bug fixing (conditional) | debugging 0.92 / quick_fix 0.95 |
| tester | Claude Haiku 4.5 | Test writing + QA | testing 0.95 / verification 0.95 |

### Agent Tools (v0.4+)

Each agent has access to tools appropriate for its role:

| Tool | coding | review | bugfix | testing |
|---|---|---|---|---|
| `read_file` | ✓ | ✓ | ✓ | ✓ |
| `write_file` | ✓ | | ✓ | ✓ |
| `list_files` | ✓ | ✓ | ✓ | ✓ |
| `bash` | ✓ | | ✓ | ✓ |
| `grep` | | ✓ | | |

### Supported Providers

| Provider | Models | Config |
|---|---|---|
| `anthropic` | claude-opus-4-8, claude-sonnet-4-6, claude-haiku-4-5 | `ANTHROPIC_API_KEY` |
| `openai` | gpt-4.1, gpt-5, gpt-4o | `OPENAI_API_KEY` |
| `gemini` | gemini-2.5-pro, gemini-2.5-flash | `GEMINI_API_KEY` |
| `deepseek` | deepseek-chat, deepseek-reasoner | `DEEPSEEK_API_KEY` |

Mixing providers per agent is supported — just edit `forge.yaml`.

---

## Pipeline Design

```
coding (Opus) ──→ review (Sonnet) ──→ bugfix (Sonnet) ──→ testing (Haiku)
                                        ↑ conditional           │
                                   only if __HAS_ISSUES__       │
                                                           test loop (v0.5)
                                                           failures → fix → retest
```

### Test Feedback Loop (v0.5)

The testing stage now detects test failures and auto-triggers a fix→retest loop:

```
Testing writes + runs tests
    │
    ├── All pass → ✅ Done
    │
    └── Failures detected
           │
           ▼
       Bugfixer fixes code
           │
           ▼
       Re-run tests
           │
           ├── All pass → ✅ Done
           │
           └── Still failing → Retry (max 3 iterations)
```

Configure in `forge.yaml`:
```yaml
test_loop:
  enabled: true
  max_iterations: 3
```

---

## Configuration

Everything lives in `forge.yaml`. Key sections:

```yaml
# API settings
api:
  base_delay_ms: 500
  max_retries: 2
  timeout_seconds: 300

# Agent definitions
agents:
  coder:
    provider: anthropic
    model: claude-opus-4-8
    api_key_env: ANTHROPIC_API_KEY
    system_prompt: "You are an expert software engineer..."
    capabilities:
      coding: 0.95
      architecture: 0.90

# Task classification rules
classifier:
  rules:
    - type: coding
      keywords: ["build", "create", "implement", "write", "make"]
  fallback: coding

# Capability weights per task type
match_weights:
  coding:
    coding: 1.0
    architecture: 0.6

# Git integration (v0.5)
git:
  auto_commit: false          # Set true to auto-commit after each stage
  commit_message_template: "AgentForge: {stage_id} — {task_summary}"
  branch_prefix: "forge/"

# Test feedback loop (v0.5)
test_loop:
  enabled: true
  max_iterations: 3

# Pipeline definitions
pipelines:
  full_dev_cycle:
    description: "Code → Review → Fix(conditional) → Test"
    stages:
      - id: coding
        type: coding
        prompt: '{original_task}'
      - id: review
        type: review
        prompt: 'Review: {previous_files}'
        pass_files: true
      - id: bugfix
        type: bugfix
        condition:
          stage: review
          marker: "__HAS_ISSUES__"
      - id: testing
        type: testing
        prompt: 'Write tests for: {all_files}'
        pass_files: true
```

---

## REST API

When running in server mode (`forge --serve` or `forge --gui`):

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/config` | Get configuration (keys redacted) |
| GET | `/api/agents` | List agents with capabilities |
| GET | `/api/pipelines` | List available pipelines |
| POST | `/api/run` | Run a pipeline (`{"task": "...", "pipeline": "full_dev_cycle"}`) |
| GET | `/api/status` | List recent sessions |
| GET | `/api/status/<id>` | Get session status and stage results |
| GET | `/api/files/<id>` | List files produced by a session |
| GET | `/api/file/<id>/<path>` | Read a specific file |
| GET | `/api/sessions` | List disk sessions |
| GET | `/api/templates` | Get project templates |

---

## Building .exe (Windows)

Package AgentForge as a standalone executable:

```bash
# 1. Install PyInstaller
pip install pyinstaller

# 2. Build
python forge.py --build-exe

# Or manually:
pyinstaller --onefile --name AgentForge forge.py

# 3. Output
# dist/AgentForge.exe  (~15-30 MB)
```

The .exe bundles Python + all dependencies. No Python installation needed to run it.

**Release workflow:**
1. Build the .exe: `python forge.py --build-exe`
2. Create a GitHub Release
3. Upload `dist/AgentForge.exe`
4. Users download and run directly

---

## Project Structure

```
agent-forge/
├── forge.py              # Smart launcher (REPL + CLI)
├── forge.yaml             # Configuration (agents, pipelines, rules)
├── commands.py            # Slash command system (v0.5)
├── server.py              # Flask web GUI + REST API (v0.5)
├── orchestrator.py        # Single-task dispatch
├── pipeline.py            # Pipeline engine + test loop (v0.5)
├── executor.py            # Dual-mode executor (CLI + API)
├── api_client.py          # LLM API clients (4 providers)
├── tools.py               # Agent tool system (5 tools)
├── workspace.py           # Workspace manager + file inlining
├── classifier.py          # Keyword-based task classifier
├── matcher.py             # Weighted capability matcher
├── templates/
│   └── index.html         # Web GUI frontend
├── static/
│   ├── style.css          # GUI styles (dark theme)
│   └── app.js             # GUI JavaScript
├── requirements.txt       # Python dependencies
├── .env.example           # API key template
├── CLAUDE.md              # Project knowledge file
├── BUILD.md               # .exe packaging guide
├── README.md              # This file
└── sessions/              # Pipeline output archive
```

---

## Design Principles

1. **Scheduler is a dead program, not an agent** — keyword + weighted matching, no AI decisions in routing
2. **Each invocation is a fresh call** — stateless API requests, no session persistence between invocations
3. **Outputs land on disk** — all agents share a working directory, code output is directly visible
4. **Pipeline stages skip the classifier** — stage types are declared in YAML, no routing guesswork
5. **Failure doesn't block** — any stage failure continues to subsequent stages, final summary reports status
6. **Tools over text** — agents use `write_file`/`read_file`/`bash` tools, not markdown code blocks
7. **Runner-up fallback** — first-choice agent fails? second-best takes over automatically

---

## Comparison

| Feature | AgentForge | Claude Code CLI | Codex CLI |
|---|---|---|---|
| Multi-agent pipeline | ✅ Core feature | ❌ Single agent | ❌ Single agent |
| Provider flexibility | ✅ 4 providers | ❌ Anthropic only | ❌ OpenAI only |
| Zero CLI dependency | ✅ API keys | ❌ Requires CLI install | ❌ Requires CLI install |
| Slash commands | ✅ 16 commands | ✅ Many commands | ✅ Some commands |
| Web GUI | ✅ Built-in | ❌ | ❌ |
| Tool_use agents | ✅ 5 tools | ✅ 20+ tools | ✅ 10+ tools |
| Test feedback loop | ✅ v0.5 | ✅ | ❌ |
| Git auto-commit | ✅ v0.5 (opt-in) | ✅ | ❌ |
| .exe packaging | ✅ PyInstaller | ❌ | ❌ |
| Interactive REPL | ✅ | ✅ | ✅ |
| Open source | ✅ MIT | ❌ Proprietary | ❌ Proprietary |

---

## Roadmap

| Version | Feature | Status |
|---|---|---|
| v0.1 | Single-task dispatch (classify + match + execute) | ✅ Done |
| v0.2 | Pipeline relay + forge launcher + runner-up fallback | ✅ Done |
| v0.3 | API-driven execution (Anthropic/OpenAI/Gemini/DeepSeek) | ✅ Done |
| v0.4 | Tool_use agents (read/write/bash/grep/list) + content inlining | ✅ Done |
| v0.5 | Slash commands + Web GUI + test loop + git integration + .exe | ✅ Done |
| v0.6 | Multi-plan comparison (same task → all agents → best result) | 🔜 Planned |
| v0.7 | Self-evolving weights (adjust based on success rate) | 🔜 Planned |
| v0.8 | Interactive diff editing (approve/reject per-file changes) | 🔜 Planned |

---

## License

MIT — see [LICENSE](LICENSE)

---

[中文](#chinese) | [English](#agentforge-v05--multi-agent-collaboration-platform)

---

## 中文说明

### 这是什么

AgentForge 是一个多 Agent 协作的代码生成框架。你只需要填入 API Key，它就能调度多个 LLM Agent 按流水线接力完成任务：编码 → 审查 → 修复 → 测试。

### 快速开始

```bash
pip install -r requirements.txt
# 设置 API Key
$env:DEEPSEEK_API_KEY = "sk-xxx"
# 修改 forge.yaml 中每个 agent 的 provider 为 deepseek，model 为 deepseek-chat
python forge.py "用Python写一个计算器"
```

### v0.5 新特性

- **斜杠命令系统** (`/help`, `/doctor`, `/init`, `/agents`, `/pipeline`, `/model`, `/review`, `/test`, `/file`, `/workspace`, `/config`, `/git`, `/memory`, `/save`, `/clear`)
- **Web 图形界面** (`forge --gui`)
- **测试反馈循环** (测试失败 → 自动修复 → 重新测试，最多3轮)
- **Git 集成** (可选自动提交)
- **.exe 打包** (`forge --build-exe`)
- **强化错误处理** (检测 Agent 卡住、自动重试、指数退避)
