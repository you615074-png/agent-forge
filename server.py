"""
AgentForge — Web GUI & REST API Server (v0.5)

Flask-based web interface for running pipelines, browsing output,
and managing configuration — all from a browser.

Start:
  forge --gui          # Web GUI on port 8080
  forge --serve 9090   # Headless API on port 9090

Endpoints:
  GET  /               Web GUI
  GET  /api/health     Health check
  POST /api/run        Run a pipeline
  GET  /api/status     List recent sessions
  GET  /api/status/<id>  Get session status
  GET  /api/files/<id>   List session files
  GET  /api/file/<id>/<path>  Read a file
  GET  /api/config     Get configuration
  GET  /api/agents     List agents
"""

import os
import json
import sys
import threading
import hashlib
import secrets
from datetime import datetime
from pathlib import Path

# Ensure the project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, request, jsonify, render_template
from logging_config import get_logger

log = get_logger("server")

# ── Auth ──
API_TOKEN = os.environ.get("AGENTFORGE_API_TOKEN", "")
SESSION_DIR = os.path.join(PROJECT_ROOT, "sessions")

def _check_auth() -> bool:
    """Return True if the request is authenticated (or if auth is disabled)."""
    if not API_TOKEN:
        return True  # Auth not configured — allow all (local-only assumed)
    auth_header = request.headers.get("Authorization", "")
    return auth_header == f"Bearer {API_TOKEN}"

def _require_auth():
    if not _check_auth():
        log.warning("Unauthorized API access from %s", request.remote_addr)
        return jsonify({"error": "unauthorized — set AGENTFORGE_API_TOKEN env var"}), 401
    return None


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(PROJECT_ROOT, "templates"),
        static_folder=os.path.join(PROJECT_ROOT, "static"),
    )

    # ── Session state (memory + disk) ──
    _sessions: dict[str, dict] = {}
    _lock = threading.Lock()

    def _load_sessions():
        """Load persisted sessions from disk into memory."""
        if not os.path.isdir(SESSION_DIR):
            return
        for d in os.listdir(SESSION_DIR):
            summary_path = os.path.join(SESSION_DIR, d, "pipeline_result.json")
            if os.path.exists(summary_path):
                try:
                    with open(summary_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    _sessions[d] = {
                        "id": d,
                        "task": data.get("original_task", ""),
                        "pipeline": data.get("pipeline", "?"),
                        "status": "completed",
                        "stages": data.get("stages", {}),
                        "completed_at": data.get("timestamp", ""),
                    }
                except (json.JSONDecodeError, OSError):
                    pass

    _load_sessions()  # Restore on startup

    def _save_session(session_id: str):
        """Persist a session to disk for crash recovery."""
        s = _sessions.get(session_id)
        if not s:
            return
        sess_dir = os.path.join(SESSION_DIR, session_id)
        os.makedirs(sess_dir, exist_ok=True)
        summary = {
            "pipeline": s.get("pipeline", "?"),
            "original_task": s.get("task", ""),
            "session_dir": sess_dir,
            "stages": s.get("stages", {}),
            "timestamp": datetime.now().isoformat(),
        }
        path = os.path.join(sess_dir, "pipeline_result.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
        except OSError as e:
            log.warning("Failed to persist session %s: %s", session_id, e)

    @app.route("/")
    def index():
        """Serve the web GUI."""
        return render_template("index.html")

    @app.route("/api/health")
    def health():
        return jsonify({
            "status": "ok",
            "version": "0.7",
            "auth_enabled": bool(API_TOKEN),
            "timestamp": datetime.now().isoformat(),
        })

    @app.route("/api/config")
    def get_config():
        """Return current forge.yaml configuration (redacted API keys)."""
        auth_err = _require_auth()
        if auth_err:
            return auth_err
        from orchestrator import load_config
        config = load_config()
        # Redact sensitive values
        for name, agent in config.get("agents", {}).items():
            agent = agent.copy()
            if "api_key" in agent:
                agent["api_key"] = "***"
            agent["api_key_env"] = agent.get("api_key_env", "N/A")
            config["agents"][name] = agent
        return jsonify(config)

    @app.route("/api/agents")
    def get_agents():
        """Return agent list with capabilities."""
        auth_err = _require_auth()
        if auth_err:
            return auth_err
        from orchestrator import load_config
        config = load_config()
        agents = config.get("agents", {})
        result = {}
        for name, agent in agents.items():
            result[name] = {
                "description": agent.get("description", ""),
                "provider": agent.get("provider", agent.get("cli", "?")),
                "model": agent.get("model", "?"),
                "capabilities": agent.get("capabilities", {}),
                "tech_preference": agent.get("tech_preference", []),
            }
        return jsonify(result)

    @app.route("/api/pipelines")
    def get_pipelines():
        """Return available pipelines."""
        from orchestrator import load_config
        config = load_config()
        pipelines = config.get("pipelines", {})
        result = {}
        for name, pl in pipelines.items():
            stages = pl.get("stages", [])
            result[name] = {
                "description": pl.get("description", ""),
                "stages": [{"id": s.get("id"), "type": s.get("type")} for s in stages],
            }
        return jsonify(result)

    @app.route("/api/run", methods=["POST"])
    def run_pipeline_api():
        """Run a pipeline asynchronously and return a session ID."""
        auth_err = _require_auth()
        if auth_err:
            return auth_err

        data = request.get_json(force=True)
        task = data.get("task", "").strip()
        pipeline_name = data.get("pipeline", "full_dev_cycle")
        mock = data.get("mock", False)

        if not task:
            return jsonify({"error": "task is required"}), 400

        # Generate session ID
        import hashlib
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        task_hash = hashlib.md5(f"{pipeline_name}:{task}".encode()).hexdigest()[:8]
        session_id = f"api-{ts}-{task_hash}"

        with _lock:
            _sessions[session_id] = {
                "id": session_id,
                "task": task,
                "pipeline": pipeline_name,
                "mock": mock,
                "status": "running",
                "started_at": datetime.now().isoformat(),
                "stages": {},
                "error": None,
            }

        # Run in background thread
        def _run():
            from orchestrator import load_config
            from pipeline import run_pipeline
            import io
            import contextlib

            config = load_config()

            # Capture stdout
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    pipeline_result = run_pipeline(pipeline_name, task, config, mock=mock)

                # run_pipeline returns {"stages": {...}, "session_dir": "..."}
                stages_dict = pipeline_result.get("stages", {}) if isinstance(pipeline_result, dict) else {}

                with _lock:
                    s = _sessions.get(session_id, {})
                    s["status"] = "completed"
                    s["completed_at"] = datetime.now().isoformat()
                    s["session_dir"] = pipeline_result.get("session_dir", "") if isinstance(pipeline_result, dict) else ""
                _save_session(session_id)
                    s["stages"] = {
                        sid: {
                            "id": sd.get("id", sid),
                            "type": sd.get("type", ""),
                            "agent": sd.get("agent", ""),
                            "success": sd.get("success", False),
                            "duration_ms": sd.get("duration_ms", 0),
                            "files_count": len(sd.get("files", [])),
                            "files": [f["path"] for f in sd.get("files", [])],
                            "stdout_preview": (sd.get("stdout", "") or "")[:500],
                        }
                        for sid, sd in stages_dict.items()
                    } if isinstance(stages_dict, dict) else {}
            except (ValueError, RuntimeError, OSError) as e:
                log.error("Pipeline run failed: %s", e)
                with _lock:
                    s = _sessions.get(session_id, {})
                    s["status"] = "failed"
                    s["error"] = str(e)
                _save_session(session_id)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        return jsonify({
            "session_id": session_id,
            "status": "running",
        })

    @app.route("/api/status")
    def list_sessions():
        """List recent sessions."""
        with _lock:
            sessions = sorted(
                _sessions.values(),
                key=lambda s: s.get("started_at", ""),
                reverse=True,
            )[:20]
        return jsonify(sessions)

    @app.route("/api/status/<session_id>")
    def get_session_status(session_id: str):
        """Get the status of a specific session."""
        # Check API-driven sessions first
        with _lock:
            if session_id in _sessions:
                return jsonify(_sessions[session_id])

        # Check disk sessions
        work_dir = os.path.join(PROJECT_ROOT, "sessions")
        session_dir = os.path.join(work_dir, session_id)
        if os.path.isdir(session_dir):
            summary_path = os.path.join(session_dir, "pipeline_result.json")
            if os.path.exists(summary_path):
                with open(summary_path, "r", encoding="utf-8") as f:
                    return jsonify(json.load(f))

        return jsonify({"error": "session not found"}), 404

    @app.route("/api/files/<session_id>")
    def list_session_files(session_id: str):
        """List all files produced by a session."""
        work_dir = os.path.join(PROJECT_ROOT, "sessions")
        session_dir = os.path.join(work_dir, session_id)
        if not os.path.isdir(session_dir):
            return jsonify({"error": "session not found"}), 404

        files = []
        for root, dirs, filenames in os.walk(session_dir):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for fn in filenames:
                if fn.startswith("_stage_"):
                    continue
                filepath = os.path.join(root, fn)
                relpath = os.path.relpath(filepath, session_dir)
                files.append({
                    "path": relpath,
                    "size": os.path.getsize(filepath),
                })
        return jsonify(files)

    @app.route("/api/file/<session_id>/<path:relpath>")
    def get_session_file(session_id: str, relpath: str):
        """Read a specific file from a session."""
        work_dir = os.path.join(PROJECT_ROOT, "sessions")
        filepath = os.path.normpath(os.path.join(work_dir, session_id, relpath))
        # Safety: ensure file is within the session directory
        if not filepath.startswith(os.path.join(work_dir, session_id)):
            return jsonify({"error": "path traversal denied"}), 403
        if not os.path.isfile(filepath):
            return jsonify({"error": "file not found"}), 404

        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify({
            "path": relpath,
            "size": len(content),
            "content": content,
        })

    @app.route("/api/templates")
    def get_templates():
        """Return default project templates."""
        templates = {
            "python": {
                "forge.yaml": _template_forge_yaml_python(),
                "CLAUDE.md": _template_claude_md("python-project"),
            },
            "nodejs": {
                "forge.yaml": _template_forge_yaml_nodejs(),
                "CLAUDE.md": _template_claude_md("nodejs-project"),
            },
            "generic": {
                "forge.yaml": _template_forge_yaml_generic(),
                "CLAUDE.md": _template_claude_md("my-project"),
            },
        }
        return jsonify(templates)

    @app.route("/api/sessions")
    def list_disk_sessions():
        """List sessions stored on disk."""
        work_dir = os.path.join(PROJECT_ROOT, "sessions")
        if not os.path.isdir(work_dir):
            return jsonify([])

        sessions = []
        for d in sorted(os.listdir(work_dir), reverse=True)[:30]:
            full = os.path.join(work_dir, d)
            if not os.path.isdir(full):
                continue
            summary_path = os.path.join(full, "pipeline_result.json")
            info = {
                "id": d,
                "has_summary": os.path.exists(summary_path),
            }
            if info["has_summary"]:
                try:
                    with open(summary_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    info["pipeline"] = data.get("pipeline", "?")
                    info["original_task"] = data.get("original_task", "")[:100]
                    info["timestamp"] = data.get("timestamp", "")
                    info["stages_count"] = len(data.get("stages", {}))
                    success_count = sum(
                        1 for s in data.get("stages", {}).values() if s.get("success")
                    )
                    info["stages_success"] = success_count
                except Exception:
                    pass
            sessions.append(info)
        return jsonify(sessions)

    return app


# ═══════════════════════════════════════════════════════════════
# Templates
# ═══════════════════════════════════════════════════════════════

def _template_forge_yaml_python() -> str:
    return """# AgentForge — Python Project
agents:
  coder:
    provider: anthropic
    model: claude-opus-4-8
    api_key_env: ANTHROPIC_API_KEY
    system_prompt: |
      You are an expert Python developer. Write clean, type-hinted code.
      Follow PEP 8. Use standard library where possible.
      Include docstrings for all public functions.
    capabilities:
      coding: 0.95
      architecture: 0.85
      testing: 0.60
  reviewer:
    provider: anthropic
    model: claude-sonnet-4-6
    api_key_env: ANTHROPIC_API_KEY
    capabilities:
      review: 0.95
      reasoning: 0.90
  bugfixer:
    provider: anthropic
    model: claude-sonnet-4-6
    api_key_env: ANTHROPIC_API_KEY
    capabilities:
      debugging: 0.92
      quick_fix: 0.95
  tester:
    provider: anthropic
    model: claude-haiku-4-5
    api_key_env: ANTHROPIC_API_KEY
    capabilities:
      testing: 0.95
"""


def _template_forge_yaml_nodejs() -> str:
    return """# AgentForge — Node.js Project
agents:
  coder:
    provider: anthropic
    model: claude-opus-4-8
    api_key_env: ANTHROPIC_API_KEY
    system_prompt: |
      You are an expert TypeScript/Node.js developer. Write clean code
      with proper types. Use ES modules. Handle errors gracefully.
    capabilities:
      coding: 0.95
      fullstack: 0.90
  reviewer:
    provider: anthropic
    model: claude-sonnet-4-6
    api_key_env: ANTHROPIC_API_KEY
    capabilities:
      review: 0.95
      reasoning: 0.90
  bugfixer:
    provider: anthropic
    model: claude-sonnet-4-6
    api_key_env: ANTHROPIC_API_KEY
    capabilities:
      debugging: 0.92
  tester:
    provider: anthropic
    model: claude-haiku-4-5
    api_key_env: ANTHROPIC_API_KEY
    capabilities:
      testing: 0.95
"""


def _template_forge_yaml_generic() -> str:
    return """# AgentForge — Generic Project
agents:
  coder:
    provider: anthropic
    model: claude-opus-4-8
    api_key_env: ANTHROPIC_API_KEY
    capabilities:
      coding: 0.95
  reviewer:
    provider: anthropic
    model: claude-sonnet-4-6
    api_key_env: ANTHROPIC_API_KEY
    capabilities:
      review: 0.95
  bugfixer:
    provider: anthropic
    model: claude-sonnet-4-6
    api_key_env: ANTHROPIC_API_KEY
    capabilities:
      debugging: 0.92
  tester:
    provider: anthropic
    model: claude-haiku-4-5
    api_key_env: ANTHROPIC_API_KEY
    capabilities:
      testing: 0.95
"""


def _template_claude_md(name: str) -> str:
    return f"""# {name} — Project Knowledge

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
"""


# ── Standalone entry point ──

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AgentForge API Server")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    print(f"AgentForge API Server v0.5")
    print(f"  http://{args.host}:{args.port}")
    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug)
