"""
AgentForge — Pipeline Execution Engine (v0.5)

Multi-stage task relay with context passing between stages.
New in v0.5:
  - Test feedback loop: run tests → see failures → auto-fix → re-run
  - Git auto-commit after each successful stage (opt-in)
  - Stuck-agent detection with retry
"""

import os
import json
import hashlib
import subprocess
from datetime import datetime
from typing import Dict, Any

from matcher import match
from executor import execute


# ── Type display names ──
_TYPE_NAMES = {
    "coding": "[CODE] Coding",
    "review": "[REVIEW] Code Review",
    "bugfix": "[BUGFIX] Bug Fix",
    "testing": "[TEST] Test",
    "analysis": "[ANALYZE] Analysis",
    "refactor": "[REFACTOR] Refactor",
    "documentation": "[DOCS] Documentation",
}


def run_pipeline(pipeline_name: str, original_task: str,
                 config: dict, mock: bool = False) -> dict:
    """
    Execute a named pipeline.

    pipeline_name: key under pipelines in forge.yaml
    original_task: the user's task description
    config: full configuration dict (from load_config)
    mock: if True, skip actual agent calls
    """
    pipelines = config.get("pipelines", {})
    pipeline = pipelines.get(pipeline_name)

    if not pipeline:
        print(f"[ERROR] Unknown pipeline: {pipeline_name}")
        print(f"       Available: {list(pipelines.keys())}")
        return {"error": f"unknown pipeline: {pipeline_name}"}

    stages = pipeline.get("stages", [])
    if not stages:
        print(f"[ERROR] Pipeline {pipeline_name} has no stages")
        return {"error": "no stages defined"}

    # Shared working directory
    work_dir_root = os.path.join(
        os.path.dirname(__file__),
        config.get("executor", {}).get("work_dir", "./sessions")
    )
    task_hash = hashlib.md5(
        f"{pipeline_name}:{original_task}".encode()
    ).hexdigest()[:8]
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    session_dir = os.path.join(work_dir_root, f"pipeline-{ts}-{task_hash}")
    os.makedirs(session_dir, exist_ok=True)

    timeout = config.get("executor", {}).get("timeout_seconds", 120)
    agents = config["agents"]
    match_weights = config["match_weights"]

    # ── v0.5: Git config ──
    git_config = config.get("git", {})
    git_auto_commit = git_config.get("auto_commit", False)
    git_commit_template = git_config.get(
        "commit_message_template",
        "AgentForge: {stage_id} — {task_summary}"
    )

    # ── v0.5: Test loop config ──
    test_loop_config = config.get("test_loop", {})
    test_loop_enabled = test_loop_config.get("enabled", True)
    test_loop_max = test_loop_config.get("max_iterations", 3)
    test_fix_prompt_template = test_loop_config.get(
        "fix_prompt",
        "The tests failed with:\n{test_output}\n\nFix the code AND tests to make everything pass."
    )

    print("=" * 60)
    print(f"  AgentForge v0.5 — Pipeline Mode")
    print(f"  Pipeline: {pipeline_name} — {pipeline.get('description', '')}")
    print("=" * 60)
    print(f"\nTask: {original_task[:100]}")
    print(f"Dir:  {session_dir}\n")

    ctx: Dict[str, Any] = {
        "original_task": original_task,
        "stages": {},
        "previous_stage": None,
        "session_dir": session_dir,
        "git_auto_commit": git_auto_commit,
    }

    for i, stage in enumerate(stages):
        stage_id = stage["id"]
        stage_type = stage["type"]
        stage_prompt_template = stage["prompt"]

        print(f"\n{'─' * 60}")
        print(f"  Stage {i + 1}/{len(stages)}: {stage_id} "
              f"-> {_TYPE_NAMES.get(stage_type, stage_type)}")
        print(f"{'─' * 60}\n")

        # ── Condition check ──
        condition = stage.get("condition")
        if condition:
            cond_stage = condition.get("stage")
            cond_marker = condition.get("marker")
            cond_fallback = condition.get("fallback_check", False)

            if cond_stage in ctx["stages"]:
                prev_data = ctx["stages"][cond_stage]
                prev_out = prev_data.get("stdout", "")
                if not prev_data.get("success", False):
                    print(f"[SKIP] {stage_id} — "
                          f"previous stage {cond_stage} failed")
                    continue
                if cond_marker not in prev_out:
                    print(f"[SKIP] {stage_id} — "
                          f"no trigger marker '{cond_marker}' found")
                    continue
            elif not cond_fallback:
                print(f"[SKIP] {stage_id} — "
                      f"previous stage {cond_stage} not executed")
                continue

        # ── Build prompt ──
        prompt = _build_prompt(stage_prompt_template, ctx, stage_id)

        prompt_preview = prompt[:200].replace("\n", "\n   ")
        print(f"Prompt (first 200 chars):\n   {prompt_preview}...\n")

        # ── Classify (from stage definition) ──
        task_type = stage_type
        type_label = _TYPE_NAMES.get(task_type, f"? {task_type}")
        print(f"Classify: {type_label} (from stage definition)")

        # ── Match ──
        match_result = match(task_type, agents, match_weights)
        if "error" in match_result:
            print(f"[ERROR] Match failed: {match_result['error']}")
            ctx["stages"][stage_id] = {
                "id": stage_id, "type": stage_type,
                "agent": "N/A", "stdout": "",
                "files": [], "success": False,
                "score": 0, "duration_ms": 0,
                "error": match_result["error"],
            }
            ctx["previous_stage"] = stage_id
            continue

        selected_agent = match_result["selected"]
        score = match_result["score"]
        description = match_result["description"]

        print(f"Match:    {selected_agent} "
              f"(score: {score:.2f}) — {description}")

        for s in match_result["all_scores"]:
            bar = "#" * int(s["score"] * 20)
            marker = " <-" if s["name"] == selected_agent else ""
            print(f"   {s['name']:12s} {s['score']:.2f} {bar}{marker}")

        # ── Execute (with v0.5 enhancements) ──
        result = _execute_stage(
            stage_id=stage_id,
            stage_type=stage_type,
            selected_agent=selected_agent,
            agent_config=agents[selected_agent],
            prompt=prompt,
            work_dir_root=work_dir_root,
            session_dir=session_dir,
            timeout=timeout,
            mock=mock,
            match_result=match_result,
            agents=agents,
        )

        ctx["stages"][stage_id] = {
            "id": stage_id,
            "type": stage_type,
            "agent": selected_agent,
            "stdout": result.get("stdout", ""),
            "files": result.get("produced_files", []),
            "success": result.get("success", False),
            "score": score,
            "duration_ms": result.get("duration_ms", 0),
        }
        ctx["previous_stage"] = stage_id

        if result["success"]:
            print(f"[OK] {stage_id} — {result['duration_ms']}ms")
            if result.get("stdout"):
                out_preview = result["stdout"][:200].replace("\n", "\n   ")
                print(f"   output: {out_preview}")

            # ── v0.5: Git auto-commit after successful stage ──
            if git_auto_commit:
                _git_auto_commit(session_dir, stage_id, original_task, git_commit_template)

        else:
            err = result.get("error") or f"exit {result.get('exit_code')}"
            print(f"[WARN] {stage_id} failed — {err}")
            print(f"       Pipeline continues with subsequent stages")

        # ── v0.5: Test feedback loop ──
        if stage_type == "testing" and test_loop_enabled and result.get("success"):
            test_output = result.get("stdout", "")
            if _has_test_failures(test_output):
                _run_test_feedback_loop(
                    ctx=ctx,
                    stage_id=stage_id,
                    test_output=test_output,
                    test_fix_prompt_template=test_fix_prompt_template,
                    max_iterations=test_loop_max,
                    agents=agents,
                    match_weights=match_weights,
                    work_dir_root=work_dir_root,
                    session_dir=session_dir,
                    timeout=timeout,
                    mock=mock,
                    git_auto_commit=git_auto_commit,
                    git_commit_template=git_commit_template,
                    original_task=original_task,
                )

    # ── Final summary ──
    _print_summary(ctx)
    _save_summary(ctx, session_dir, pipeline_name)

    return ctx["stages"]


def _execute_stage(
    stage_id: str,
    stage_type: str,
    selected_agent: str,
    agent_config: dict,
    prompt: str,
    work_dir_root: str,
    session_dir: str,
    timeout: int,
    mock: bool,
    match_result: dict,
    agents: dict,
) -> dict:
    """Execute a single stage with runner-up fallback and retry."""
    agent_config = agents[selected_agent]
    exec_label = agent_config.get("provider") or agent_config.get("cli", "?")

    print(f"\nExec: {selected_agent} ({exec_label})")

    if mock:
        return {
            "success": True,
            "agent": selected_agent,
            "stdout": (
                f"[MOCK] {stage_id} stage output.\n"
                f"Task executed by {selected_agent}.\n"
                f"{'__HAS_ISSUES__' if stage_id == 'review' else ''}"
            ),
            "produced_files": [],
            "duration_ms": 0,
        }

    # ── Primary execution ──
    result = execute(
        agent_name=selected_agent,
        agent_config=agent_config,
        task=prompt,
        work_dir=work_dir_root,
        timeout=timeout,
        session_dir=session_dir,
        stage_prefix=stage_id,
    )

    # ── Runner-up fallback ──
    if not result["success"] and match_result.get("runner_up"):
        runner = match_result["runner_up"]
        print(f"   [FALLBACK] {selected_agent} failed, trying {runner}...")
        runner_agent = agents[runner]
        result = execute(
            agent_name=runner,
            agent_config=runner_agent,
            task=prompt,
            work_dir=work_dir_root,
            timeout=timeout,
            session_dir=session_dir,
            stage_prefix=stage_id,
        )
        if result["success"]:
            selected_agent = runner

    # ── v0.5: Retry with different prompt if stuck ──
    if not result["success"] and _should_retry(result):
        print(f"   [RETRY] Agent may be stuck — retrying with clarified prompt...")
        retry_prompt = (
            f"{prompt}\n\n"
            f"IMPORTANT: Your previous attempt did not produce a valid result. "
            f"Please provide a concrete, complete output. If you need to create "
            f"files, use the write_file tool. Be specific and avoid vague statements."
        )
        result = execute(
            agent_name=selected_agent,
            agent_config=agent_config,
            task=retry_prompt,
            work_dir=work_dir_root,
            timeout=timeout,
            session_dir=session_dir,
            stage_prefix=f"{stage_id}_retry",
        )

    return result


# ═══════════════════════════════════════════════════════════════
# Test feedback loop (v0.5)
# ═══════════════════════════════════════════════════════════════

def _has_test_failures(test_output: str) -> bool:
    """Check if test output indicates failures."""
    if not test_output:
        return False
    # Common failure indicators
    failure_markers = [
        "FAILED", "FAIL:", "failed", "AssertionError",
        "assert", "Error:", "ERROR:", "exit=1",
        "tests failed", "failing",
    ]
    return any(m in test_output for m in failure_markers)


def _run_test_feedback_loop(
    ctx: dict,
    stage_id: str,
    test_output: str,
    test_fix_prompt_template: str,
    max_iterations: int,
    agents: dict,
    match_weights: dict,
    work_dir_root: str,
    session_dir: str,
    timeout: int,
    mock: bool,
    git_auto_commit: bool,
    git_commit_template: str,
    original_task: str,
):
    """Auto-fix failing tests and re-run, up to max_iterations."""
    for iteration in range(1, max_iterations + 1):
        print(f"\n{'─' * 60}")
        print(f"  Test Fix Loop — Iteration {iteration}/{max_iterations}")
        print(f"{'─' * 60}\n")

        # Use bugfixer agent to fix the failing tests
        bugfixer_config = agents.get("bugfixer")
        if not bugfixer_config:
            print("[SKIP] No bugfixer agent configured")
            break

        fix_prompt = test_fix_prompt_template.replace("{test_output}", test_output[:3000])
        fix_prompt = fix_prompt.replace("{original_task}", original_task)

        # Add workspace context
        from workspace import inline_workspace_files
        all_files = inline_workspace_files(session_dir, max_total_bytes=12000)
        fix_prompt = f"{fix_prompt}\n\nCurrent workspace files:\n{all_files}"

        print(f"Fixing test failures ({len(test_output)} chars of test output)...\n")

        fix_result = execute(
            agent_name="bugfixer",
            agent_config=bugfixer_config,
            task=fix_prompt,
            work_dir=work_dir_root,
            timeout=timeout,
            session_dir=session_dir,
            stage_prefix=f"{stage_id}_fix_{iteration}",
        )

        if not fix_result.get("success"):
            print(f"[WARN] Fix iteration {iteration} failed — stopping loop")
            _save_stage_result(ctx, f"{stage_id}_fix_{iteration}", {
                "id": f"{stage_id}_fix_{iteration}",
                "type": "bugfix",
                "agent": "bugfixer",
                "stdout": fix_result.get("stdout", ""),
                "files": fix_result.get("produced_files", []),
                "success": False,
                "score": 0,
                "duration_ms": fix_result.get("duration_ms", 0),
            })
            break

        # Now re-run tests
        tester_config = agents.get("tester")
        if not tester_config:
            print("[SKIP] No tester agent configured")
            break

        re_test_prompt = (
            f"The tests were failing and have been fixed. "
            f"Please run the tests again to verify they pass.\n\n"
            f"Original task: {original_task}\n\n"
            f"Previous test failures:\n{test_output[:1000]}\n\n"
            f"Run the tests and report the results. If tests still fail, "
            f"explain why. If they pass, confirm with 'ALL TESTS PASSED'."
        )

        from tools import get_tools_for_stage
        print("Re-running tests after fix...\n")

        re_test_result = execute(
            agent_name="tester",
            agent_config=tester_config,
            task=re_test_prompt,
            work_dir=work_dir_root,
            timeout=timeout,
            session_dir=session_dir,
            stage_prefix=f"{stage_id}_retest_{iteration}",
        )

        new_output = re_test_result.get("stdout", "")

        _save_stage_result(ctx, f"{stage_id}_retest_{iteration}", {
            "id": f"{stage_id}_retest_{iteration}",
            "type": "testing",
            "agent": "tester",
            "stdout": new_output,
            "files": re_test_result.get("produced_files", []),
            "success": re_test_result.get("success", False),
            "score": 0,
            "duration_ms": re_test_result.get("duration_ms", 0),
        })

        if re_test_result.get("success"):
            if not _has_test_failures(new_output) or "ALL TESTS PASSED" in new_output:
                print(f"[OK] All tests pass after {iteration} fix iteration(s)!")
                if git_auto_commit:
                    _git_auto_commit(session_dir, f"{stage_id}_fixed", original_task, git_commit_template)
                break
            else:
                print(f"[RETRY] Tests still failing — iteration {iteration} complete")
                test_output = new_output  # Use new failures as input for next iteration
        else:
            print(f"[WARN] Re-test execution failed in iteration {iteration}")
            break
    else:
        print(f"[WARN] Test fix loop exhausted ({max_iterations} iterations) — manual intervention needed")


def _save_stage_result(ctx: dict, stage_id: str, result: dict):
    """Save a dynamic stage result (for test loop stages)."""
    ctx["stages"][stage_id] = result


# ═══════════════════════════════════════════════════════════════
# Prompt building
# ═══════════════════════════════════════════════════════════════

def _build_prompt(template: str, ctx: dict, stage_id: str) -> str:
    """Replace template placeholders with inline context values."""
    previous_stage = ctx.get("previous_stage")
    prev_data = ctx["stages"].get(previous_stage) if previous_stage else None
    session_dir = ctx.get("session_dir", "")

    prompt = template.replace("{original_task}", ctx["original_task"])
    prompt = prompt.replace("{stage_id}", stage_id)

    if prev_data:
        prompt = prompt.replace(
            "{previous_agent}", prev_data.get("agent", "unknown")
        )
        prompt = prompt.replace(
            "{previous_stdout}", prev_data.get("stdout", "")
        )
        prompt = prompt.replace(
            "{previous_files}",
            _inline_files(session_dir, prev_data.get("files", []))
        )
    else:
        prompt = prompt.replace("{previous_agent}", "(none)")
        prompt = prompt.replace("{previous_stdout}", "")
        prompt = prompt.replace("{previous_files}", "(none)")

    # All stages' files merged
    all_files: list = []
    for sdata in ctx.get("stages", {}).values():
        all_files.extend(sdata.get("files", []))
    prompt = prompt.replace("{all_files}", _inline_files(session_dir, all_files))

    prompt = prompt.replace(
        "{stages_summary}",
        _format_stages_summary(ctx["stages"])
    )

    return prompt


def _inline_files(session_dir: str, files: list) -> str:
    """Inline actual file contents into prompt (v0.4)."""
    if not files:
        return "(no files produced)"

    if not session_dir or not os.path.isdir(session_dir):
        return _format_file_list(files)

    from workspace import inline_workspace_files
    paths = [f["path"] for f in files]
    return inline_workspace_files(
        session_dir,
        pick=paths,
        max_total_bytes=24000,
    )


def _format_file_list(files: list) -> str:
    """Fallback: format file list as path+size."""
    if not files:
        return "(none)"
    lines = []
    for f in files:
        lines.append(f"  - {f['path']} ({f['size']} bytes)")
    return "\n".join(lines)


def _format_stages_summary(stages: dict) -> str:
    """Format all completed stage summaries."""
    if not stages:
        return "(none)"
    lines = []
    for sid, sdata in stages.items():
        status = "[OK]" if sdata.get("success") else "[FAIL]"
        lines.append(
            f"{status} {sid}: {sdata.get('agent', '?')} "
            f"({sdata.get('duration_ms', 0)}ms)"
        )
        stdout = sdata.get("stdout", "")
        if stdout:
            lines.append(f"   output: {stdout[:300]}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Git helpers (v0.5)
# ═══════════════════════════════════════════════════════════════

def _git_auto_commit(
    session_dir: str,
    stage_id: str,
    original_task: str,
    template: str,
):
    """Auto-commit changes in the session directory to git."""
    try:
        # Check if session_dir is inside a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
            cwd=session_dir,
        )
        if result.returncode != 0:
            return  # Not a git repo — skip

        task_summary = original_task[:50].replace('"', "'")
        msg = template.replace("{stage_id}", stage_id)
        msg = msg.replace("{task_summary}", task_summary)

        subprocess.run(
            ["git", "add", "-A"],
            capture_output=True, timeout=10,
            cwd=session_dir,
        )
        result = subprocess.run(
            ["git", "commit", "-m", msg, "--allow-empty"],
            capture_output=True, text=True, timeout=10,
            cwd=session_dir,
        )
        if result.returncode == 0:
            short_hash = result.stdout.strip().split("\n")[0][:72] if result.stdout else "?"
            print(f"   [GIT] Committed: {short_hash}")
        else:
            # Probably nothing to commit — that's fine
            pass
    except FileNotFoundError:
        pass  # Git not installed
    except Exception:
        pass  # Silently skip git errors — pipeline shouldn't fail on git issues


# ═══════════════════════════════════════════════════════════════
# Retry / Stuck detection (v0.5)
# ═══════════════════════════════════════════════════════════════

def _should_retry(result: dict) -> bool:
    """Determine if we should retry based on the error."""
    error = result.get("error", "")
    if not error:
        return False

    # Retry on transient errors
    retry_indicators = [
        "timeout", "timed out", "connection",
        "rate limit", "429", "503", "502",
        "internal server error", "server error",
        "max turns", "stuck",
    ]
    error_lower = error.lower()
    return any(ind in error_lower for ind in retry_indicators)


# ═══════════════════════════════════════════════════════════════
# Summary / Archive
# ═══════════════════════════════════════════════════════════════

def _print_summary(ctx: dict):
    """Print pipeline completion summary."""
    stages = ctx.get("stages", {})
    print(f"\n{'=' * 60}")
    print(f"  Pipeline Summary")
    print(f"{'=' * 60}\n")

    for sid, sdata in stages.items():
        status = "[OK]" if sdata["success"] else "[FAIL]"
        files_count = len(sdata.get("files", []))
        print(f"  {status} {sid}: {sdata['agent']} "
              f"({sdata.get('duration_ms', 0)}ms) — {files_count} files")


def _save_summary(ctx: dict, session_dir: str, pipeline_name: str):
    """Save pipeline result summary to JSON."""
    summary = {
        "pipeline": pipeline_name,
        "original_task": ctx["original_task"],
        "session_dir": ctx["session_dir"],
        "stages": {
            sid: {
                "id": sdata.get("id", sid),
                "type": sdata.get("type", ""),
                "agent": sdata.get("agent", ""),
                "success": sdata.get("success", False),
                "score": sdata.get("score", 0),
                "duration_ms": sdata.get("duration_ms", 0),
                "files_count": len(sdata.get("files", [])),
                "stdout_preview": (sdata.get("stdout", "") or "")[:500],
            }
            for sid, sdata in ctx.get("stages", {}).items()
        },
        "timestamp": datetime.now().isoformat(),
    }
    summary_path = os.path.join(session_dir, "pipeline_result.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\nArchive: {session_dir}")
    print(f"Summary: pipeline_result.json")
