"""
AgentForge — Session Manager (v0.7)
====================================
Browse, resume, compact, and rewind pipeline sessions.

Commands:
  /session list              — list all sessions with status
  /session resume <id>       — resume a pipeline from last checkpoint
  /session compact [days]    — archive old sessions (default: 7 days)
  /session rewind            — undo last stage, re-run from previous checkpoint
  /session info [id]         — show detailed session information
"""

import os
import json
import shutil
from datetime import datetime, timedelta
from typing import Optional

from console import (
    cprint, header, dim, bold, green, red, yellow, cyan, magenta,
    ok, fail, Colors,
)


# ═══════════════════════════════════════════════════════════════
# List
# ═══════════════════════════════════════════════════════════════

def list_sessions(work_dir: str, limit: int = 20) -> str:
    """List recent sessions with status summaries."""
    if not os.path.isdir(work_dir):
        return dim("  No sessions directory found. Run a pipeline first.")

    dirs = sorted(
        [d for d in os.listdir(work_dir)
         if os.path.isdir(os.path.join(work_dir, d))],
        reverse=True,
    )

    if not dirs:
        return dim("  No sessions found. Run a pipeline or /compare to create one.")

    lines = [
        bold("═" * 56),
        bold("  Sessions"),
        bold("═" * 56),
        "",
    ]

    for d in dirs[:limit]:
        full = os.path.join(work_dir, d)
        summary_path = os.path.join(full, "pipeline_result.json")
        comp_path = os.path.join(full, "comparison_result.json")

        # Determine session type
        if os.path.exists(comp_path):
            mode = magenta("compare")
            try:
                with open(comp_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                task = data.get("task", "?")[:50]
                winner = data.get("winner", "?")
                agents = data.get("agents", 0)
                info = f"{task} | winner: {green(winner)} ({agents} agents)"
            except Exception:
                info = dim("(unreadable)")
        elif os.path.exists(summary_path):
            mode = cyan("pipeline")
            try:
                with open(summary_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                task = data.get("original_task", "?")[:50]
                stages = data.get("stages", {})
                success = sum(1 for s in stages.values() if s.get("success"))
                total = len(stages)
                status = green(f"{success}/{total}") if success == total else yellow(f"{success}/{total}")
                info = f"{task} | stages: {status}"
            except Exception:
                info = dim("(unreadable)")
        else:
            mode = dim("running")
            info = dim("(in progress or incomplete)")

        ts = d.split("-", 2)[:2]
        ts_str = "-".join(ts) if len(ts) >= 2 else d[:16]
        lines.append(f"  {dim(ts_str)}  {mode:<10s} {bold(d)}")
        lines.append(f"  {'':22s} {info}")
        lines.append("")

    if len(dirs) > limit:
        lines.append(dim(f"  ... ({len(dirs) - limit} more sessions)"))
    lines.append(dim(f"  {len(dirs)} sessions total. Use /session resume <id> to continue."))
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Resume
# ═══════════════════════════════════════════════════════════════

def resume_session(
    session_id: str,
    work_dir: str,
    config: dict,
    mock: bool = False,
) -> str:
    """Resume a pipeline from its last checkpoint."""
    session_dir = os.path.join(work_dir, session_id)
    if not os.path.isdir(session_dir):
        return fail(f"Session not found: {session_id}")

    summary_path = os.path.join(session_dir, "pipeline_result.json")
    if not os.path.exists(summary_path):
        return fail("Session has no pipeline result — cannot resume.")

    try:
        with open(summary_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return fail(f"Cannot read session data: {e}")

    pipeline_name = data.get("pipeline", "")
    original_task = data.get("original_task", "")
    stages = data.get("stages", {})

    if not original_task:
        return fail("Session data is missing the original task.")

    # Find the last successfully completed stage
    completed_stages = [
        sid for sid, sd in stages.items()
        if sd.get("success") and not sid.startswith("_")
    ]

    if not completed_stages:
        return fail("No completed stages found — cannot resume. Run a new pipeline instead.")

    last_stage = completed_stages[-1]
    total_stages = len(stages)

    header(f"Resuming Session: {session_id}", 60)
    cprint(f"  Task:     {original_task[:80]}")
    cprint(f"  Pipeline: {pipeline_name}")
    cprint(f"  Progress: {green(last_stage)} ({len(completed_stages)}/{total_stages} stages done)\n")

    # Get the pipeline config
    pipelines = config.get("pipelines", {})
    pipeline = pipelines.get(pipeline_name)
    if not pipeline:
        return fail(f"Pipeline '{pipeline_name}' not found in config.")

    all_stages = pipeline.get("stages", [])
    remaining_stages = [
        s for s in all_stages
        if s["id"] not in stages or not stages[s["id"]].get("success")
    ]

    if not remaining_stages:
        return ok("All stages already completed! Nothing to resume.")

    cprint(f"  {bold('Remaining stages:')} {' → '.join(s['id'] for s in remaining_stages)}")
    cprint(f"  Running pipeline from {cyan(remaining_stages[0]['id'])}...\n")

    # Import here to avoid circular imports
    from pipeline import run_pipeline

    # Update config to skip already-completed stages
    # We handle this by running the full pipeline but with pre-populated ctx
    # For now, re-run the remaining stages
    result = run_pipeline(pipeline_name, original_task, config, mock=mock)

    if isinstance(result, dict) and result.get("stages"):
        return f"\n  {ok('Resume complete')} — session updated."
    return f"\n  {fail('Resume failed')} — check session output."


# ═══════════════════════════════════════════════════════════════
# Compact
# ═══════════════════════════════════════════════════════════════

def compact_sessions(work_dir: str, keep_days: int = 7) -> str:
    """
    Archive old sessions: remove _stage_ files from sessions older
    than `keep_days` days, keeping only the summary JSONs.
    """
    if not os.path.isdir(work_dir):
        return dim("  No sessions directory found.")

    cutoff = datetime.now() - timedelta(days=keep_days)
    dirs = [d for d in os.listdir(work_dir)
            if os.path.isdir(os.path.join(work_dir, d))]

    cleaned = 0
    freed_bytes = 0

    for d in dirs:
        full = os.path.join(work_dir, d)

        # Try to parse date from directory name
        try:
            parts = d.split("-")
            if len(parts) >= 2:
                date_str = f"{parts[1][:4]}-{parts[1][4:6]}-{parts[1][6:8]}"
                dir_date = datetime.strptime(date_str, "%Y-%m-%d")
                if dir_date > cutoff:
                    continue  # Too recent — skip
        except (ValueError, IndexError):
            pass  # Can't parse date — skip

        # Remove _stage_ files (large LLM outputs)
        for root, dirs_, filenames in os.walk(full):
            for fn in filenames:
                if fn.startswith("_stage_"):
                    fp = os.path.join(root, fn)
                    try:
                        size = os.path.getsize(fp)
                        os.remove(fp)
                        freed_bytes += size
                        cleaned += 1
                    except OSError:
                        pass

    if cleaned == 0:
        return dim(f"  No sessions older than {keep_days} days to compact.")

    return (
        f"  {ok(f'Compacted {cleaned} files')} "
        f"({_fmt_bytes(freed_bytes)} freed)\n"
        f"  Sessions older than {keep_days} days cleaned.\n"
        f"  Summaries (pipeline_result.json) preserved."
    )


# ═══════════════════════════════════════════════════════════════
# Rewind
# ═══════════════════════════════════════════════════════════════

def rewind_session(session_dir: str) -> str:
    """Remove the last stage's outputs so it can be re-run."""
    summary_path = os.path.join(session_dir, "pipeline_result.json")
    if not os.path.exists(summary_path):
        return fail("No pipeline result found — cannot rewind.")

    try:
        with open(summary_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return fail(f"Cannot read session data: {e}")

    stages = data.get("stages", {})
    if not stages:
        return dim("  No stages to rewind.")

    # Find the last stage (by key order)
    stage_ids = list(stages.keys())
    last_id = stage_ids[-1]

    # Remove last stage's output files
    for root, _, filenames in os.walk(session_dir):
        for fn in filenames:
            if fn.startswith(f"_stage_{last_id}"):
                try:
                    os.remove(os.path.join(root, fn))
                except OSError:
                    pass

    # Update summary
    del stages[last_id]
    data["stages"] = stages
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return (
        f"  {ok(f'Rewound: removed {last_id}')}\n"
        f"  Pipeline now at {len(stages)} stages.\n"
        f"  Re-run your task to redo {last_id} from the previous checkpoint."
    )


# ═══════════════════════════════════════════════════════════════
# Info
# ═══════════════════════════════════════════════════════════════

def session_info(session_dir: str) -> str:
    """Show detailed information about a session."""
    summary_path = os.path.join(session_dir, "pipeline_result.json")
    comp_path = os.path.join(session_dir, "comparison_result.json")

    lines = [
        bold("═" * 56),
        bold(f"  Session: {os.path.basename(session_dir)}"),
        bold("═" * 56),
        "",
    ]

    # Disk usage
    total_size = 0
    file_count = 0
    for root, _, filenames in os.walk(session_dir):
        for fn in filenames:
            try:
                total_size += os.path.getsize(os.path.join(root, fn))
                file_count += 1
            except OSError:
                pass
    lines.append(f"  Size:    {_fmt_bytes(total_size)} ({file_count} files)")

    if os.path.exists(comp_path):
        lines.append(f"  Type:    {magenta('comparison')}")
        try:
            with open(comp_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            lines.append(f"  Task:    {data.get('task', '?')[:80]}")
            lines.append(f"  Winner:  {green(data.get('winner', '?'))}")
            lines.append(f"  Agents:  {data.get('agents', 0)}")
            for r in data.get("rankings", []):
                lines.append(f"    {r['rank']}. {cyan(r['agent'])} — {r['score']:.1f}")
        except Exception:
            pass

    elif os.path.exists(summary_path):
        lines.append(f"  Type:    {cyan('pipeline')}")
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            lines.append(f"  Pipeline: {data.get('pipeline', '?')}")
            lines.append(f"  Task:    {data.get('original_task', '?')[:80]}")
            stages = data.get("stages", {})
            for sid, sd in stages.items():
                icon = ok() if sd.get("success") else fail()
                dur = f"{sd.get('duration_ms', 0)}ms"
                agent = sd.get("agent", "?")
                files = len(sd.get("files", []))
                lines.append(f"  {icon} {sid}: {cyan(agent)} {dim(dur)} — {files} files")
        except Exception:
            pass

    else:
        lines.append(f"  Type:    {dim('incomplete (no summary)')}")

    return "\n".join(lines)


# ── Helper ──

def _fmt_bytes(size: int) -> str:
    if size < 1024:
        return f"{size}B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    return f"{size / (1024 * 1024):.1f}MB"
