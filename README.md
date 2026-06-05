# AgentForge — Multi-Agent Collaboration Platform v0.3

> API-driven multi-agent orchestration | Single-task + 4-stage pipeline | One API key is all you need

---

## What

A framework that chains multiple LLM agents into a structured development pipeline — **using API calls instead of external CLI tools**.

```
forge "Build a React calculator"
        │
        ▼
┌──────────────────────────────────────────────┐
│              AgentForge                       │
│                                              │
│  Stage 1: coding  → Claude Opus 4.8          │
│  Stage 2: review  → Claude Sonnet 4.6        │
│  Stage 3: bugfix  → Claude Sonnet 4.6        │
│  Stage 4: testing → Claude Haiku 4.5         │
│                                              │
│  Shared workdir   Context auto-pass   Archive │
└──────────────────────────────────────────────┘
```

**Not about agents chatting with each other** — deterministic task routing → agent relay → result aggregation.

**v0.3**: Replaced CLI subprocess calls with direct API invocation. Zero external CLI tools required.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/you615074-png/agent-forge.git
cd agent-forge

# 2. Install
pip install -r requirements.txt

# 3. Set your API key (all-Claude pipeline needs just one)
#    Windows PowerShell:
$env:ANTHROPIC_API_KEY = "sk-ant-xxx"
#    Linux/macOS:
export ANTHROPIC_API_KEY=sk-ant-xxx

# 4. Run
python forge.py --mock "build a hello world web app with Flask"  # dry run first
python forge.py "build a hello world web app with Flask"          # real execution
```

---

## Usage

### `forge` Smart Launcher (recommended)

```bash
python forge.py "build a login page"          # pipeline (default)
python forge.py -s "fix the broken middleware" # single task
python forge.py --mock "test"                 # dry-run mode
python forge.py                                # interactive REPL
```

### Interactive REPL

```bash
forge> build a calculator           # pipeline
forge> s fix the auth bug           # single task
forge> mock on                      # toggle mock mode
forge> help
forge> quit
```

### Direct CLI (also works)

```bash
# Pipeline mode
python orchestrator.py --pipeline full_dev_cycle "your task"

# Single-task mode (v0.1 compatible)
python orchestrator.py "your task"
```

---

## Agent Legion

Default config uses **all-Anthropic** — one API key runs the entire pipeline:

| Agent | Model | Role | Core Strength |
|---|---|---|---|
| coder | Claude Opus 4.8 | Full-stack development | coding 0.95 / architecture 0.90 |
| reviewer | Claude Sonnet 4.6 | Code review + analysis | review 0.95 / reasoning 0.92 |
| bugfixer | Claude Sonnet 4.6 | Bug fixing (conditional) | debugging 0.92 / quick_fix 0.95 |
| tester | Claude Haiku 4.5 | Test writing + QA | testing 0.95 / verification 0.95 |

### Mix Providers (optional)

Each agent can use a different provider — just edit `forge.yaml`:

```yaml
agents:
  coder:
    provider: anthropic        # Claude
    model: claude-opus-4-8
    api_key_env: ANTHROPIC_API_KEY

  bugfixer:
    provider: openai           # GPT
    model: gpt-5
    api_key_env: OPENAI_API_KEY

  tester:
    provider: gemini           # Gemini
    model: gemini-2.5-pro
    api_key_env: GEMINI_API_KEY
```

Supported providers: `anthropic` | `openai` | `gemini` | `deepseek`

---

## Pipeline Design

```
coding (Opus)  ──→  review (Sonnet)  ──→  bugfix (Sonnet)  ──→  testing (Haiku)
                                          ↑  conditional           │
                                     only if review finds issues   │
                                     (__HAS_ISSUES__ marker)       │
                                                             shared workdir relay
```

Each stage's files are visible to subsequent stages. Context passes automatically through prompt templates.

---

## Configuration

Everything lives in `forge.yaml` — no code changes needed:

```yaml
# Add a new agent
agents:
  my_agent:
    provider: anthropic
    model: claude-sonnet-4-6
    api_key_env: ANTHROPIC_API_KEY
    system_prompt: "You are a helpful assistant..."
    capabilities:
      coding: 0.85
      review: 0.70

# Add a new pipeline
pipelines:
  my_pipeline:
    stages:
      - id: step1
        type: coding
        prompt: '{original_task}'
      - id: step2
        type: review
        prompt: 'Review: {all_files}'
```

---

## Design Principles

1. **Scheduler is a dead program, not an agent** — keyword + weighted matching, no AI decisions in routing
2. **Each invocation is a fresh call** — stateless API requests, no session persistence
3. **Outputs land on disk** — all agents share a working directory, code output is directly visible
4. **Pipeline stages skip the classifier** — stage types are declared in YAML, no routing guesswork
5. **Failure doesn't block** — any stage failure continues to subsequent stages, final summary reports status

---

## Roadmap

| Version | Feature | Status |
|---|---|---|
| v0.1 | Single-task dispatch (classify + match + execute) | DONE |
| v0.2 | Pipeline relay + forge launcher + runner-up fallback | DONE |
| v0.3 | API-driven execution (Anthropic/OpenAI/Gemini/DeepSeek) | DONE |
| v0.4 | Multi-plan comparison (same task → all agents) | TODO |
| v0.5 | Context archiving + history replay + checkpoint resume | TODO |
| v0.6 | Self-evolving weights (adjust based on success rate) | TODO |

---

## License

MIT
