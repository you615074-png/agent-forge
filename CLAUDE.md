# AgentForge — Project Knowledge

## Architecture

AgentForge is a multi-agent orchestration platform that chains LLM agents into structured development pipelines. The architecture is a **deterministic scheduler** (not an AI agent) that routes tasks through a pipeline of specialized AI agents.

### Core Pipeline

```
User Input → forge.py → pipeline.py → executor.py → api_client.py → LLM API
                │             │              │               │
           commands.py   classifier.py   tools.py       4 providers
                         matcher.py     workspace.py    (anthropic/openai/gemini/deepseek)
```

### Key Modules

1. **forge.py** — Smart launcher: CLI args, interactive REPL with slash commands, GUI/server modes
2. **commands.py** — Slash command system: `/help`, `/doctor`, `/init`, `/status`, `/agents`, `/pipeline`, `/compare`, `/model`, `/switch`, `/session`, `/review`, `/test`, `/file`, `/workspace`, `/config`, `/git`, `/memory`, `/save`, `/clear`
3. **console.py** — ANSI-styled terminal output: colors, headers, stage icons, file views, spinners (zero-dependency)
4. **logging_config.py** — Structured logging: colored console + file output, log rotation (v0.7)
5. **compare.py** — Multi-plan comparison engine: run one task through all agents, scored ranking (v0.6)
6. **sessions.py** — Session manager: list, resume, compact, rewind pipeline sessions (v0.7)
7. **pipeline.py** — Pipeline engine: 4-stage relay (coding→review→bugfix→testing), test feedback loop, git auto-commit
8. **executor.py** — Dual-mode executor: CLI subprocess (backward compat) + API mode with tool_use + plain-chat fallback
9. **api_client.py** — Unified LLM API client: 4 providers (Anthropic/OpenAI/Gemini/DeepSeek) with retry logic
10. **tools.py** — Agent tool system: read_file, write_file, bash, list_files, grep with safety checks
11. **workspace.py** — Workspace manager: file listing, content reading, context inlining
12. **classifier.py** — Keyword-based task classification
13. **matcher.py** — Weighted capability scoring and agent selection
14. **server.py** — Flask web GUI + REST API server (with token auth + session persistence v0.7)
15. **orchestrator.py** — Single-task dispatch (classify→match→execute)

## Conventions

- Python 3.9+ (uses type hints, f-strings)
- UTF-8 encoding for all files
- Provider pattern: `@register_provider("name")` decorator for extensibility
- Command pattern: `@register_command("name", ...)` decorator for slash commands
- Result dict shape is uniform: `{success, agent, stdout, stderr, exit_code, duration_ms, produced_files, error}`
- API keys: prefer `api_key_env` (environment variable name) over `api_key` (raw key in config)
- Tool definitions follow OpenAI/DeepSeek function-calling JSON Schema format
- Anthropic native tool_use format is converted at the provider layer
- Logging: use `logging_config.get_logger(__name__)` instead of `print()` for diagnostic messages
- Exception handling: catch specific types (ValueError, RuntimeError, OSError), never bare `except Exception`

## Testing

- Run tests: `pytest tests/ -v` (requires `pip install -r requirements-test.txt`)
- Use `forge --mock "task"` for pipeline structure testing without API calls
- Sessions are archived in `sessions/` directory with timestamps
- Pipeline results saved as `pipeline_result.json` in each session directory

## Configuration

- All configuration in `forge.yaml` — no code changes needed for:
  - Adding new agents (with capabilities, system prompts, provider/models)
  - Creating new pipelines (with stages, conditions, prompts)
  - Adding classification rules (keywords → task types)
  - Adjusting capability weights per task type
- `.env` file for API keys (not committed to git)
- `AGENTFORGE_API_TOKEN` env var enables Bearer token auth on REST API (optional)

## Dependencies

- **Required**: pyyaml, httpx, python-dotenv
- **GUI**: flask
- **Testing**: pytest (pip install -r requirements-test.txt)
- **Build**: pyinstaller (optional, for .exe packaging)
