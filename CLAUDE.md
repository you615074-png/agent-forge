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
2. **commands.py** — Slash command system: `/help`, `/doctor`, `/init`, `/agents`, `/pipeline`, `/model`, `/review`, `/test`, `/file`, `/workspace`, `/config`, `/git`, `/memory`, `/save`, `/clear`
3. **pipeline.py** — Pipeline engine: 4-stage relay (coding→review→bugfix→testing), test feedback loop, git auto-commit
4. **executor.py** — Dual-mode executor: CLI subprocess (backward compat) + API mode with tool_use
5. **api_client.py** — Unified LLM API client: 4 providers with retry logic and tool_use loops
6. **tools.py** — Agent tool system: read_file, write_file, bash, list_files, grep with safety checks
7. **workspace.py** — Workspace manager: file listing, content reading, context inlining
8. **classifier.py** — Keyword-based task classification
9. **matcher.py** — Weighted capability scoring and agent selection
10. **server.py** — Flask web GUI + REST API server
11. **orchestrator.py** — Single-task dispatch (classify→match→execute)

## Conventions

- Python 3.9+ (uses type hints, f-strings)
- UTF-8 encoding for all files
- Provider pattern: `@register_provider("name")` decorator for extensibility
- Command pattern: `@register_command("name", ...)` decorator for slash commands
- Result dict shape is uniform: `{success, agent, stdout, stderr, exit_code, duration_ms, produced_files, error}`
- API keys: prefer `api_key_env` (environment variable name) over `api_key` (raw key in config)
- Tool definitions follow OpenAI/DeepSeek function-calling JSON Schema format
- Anthropic native tool_use format is converted at the provider layer

## Testing

- Test with DeepSeek API for cost-effective iteration
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

## Dependencies

- **Required**: pyyaml, httpx, python-dotenv
- **GUI**: flask
- **Build**: pyinstaller (optional, for .exe packaging)
