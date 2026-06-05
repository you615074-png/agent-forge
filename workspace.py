"""
AgentForge — Workspace Manager (v0.4)

Handles shared state across pipeline stages: file listing, content
reading with size limits, and tracking which files each stage produced.
"""

import os
from typing import Optional


def list_workspace(
    session_dir: str,
    max_depth: int = 3,
    exclude_patterns: tuple = ("_stage_", "__pycache__", ".git", "node_modules"),
) -> str:
    """
    Return a human-readable tree of the workspace directory.
    Used to give the agent an overview of the project.
    """
    lines: list[str] = []
    _walk(session_dir, session_dir, "", 0, max_depth, exclude_patterns, lines)
    return "\n".join(lines[:80]) or "(empty workspace)"


def _walk(
    root: str,
    current: str,
    prefix: str,
    depth: int,
    max_depth: int,
    exclude: tuple,
    lines: list[str],
):
    if depth > max_depth:
        return
    try:
        entries = sorted(os.listdir(current))
    except PermissionError:
        return

    dirs = [e for e in entries if os.path.isdir(os.path.join(current, e))
            and not e.startswith(".") and e not in exclude]
    files = [e for e in entries if os.path.isfile(os.path.join(current, e))
             and not e.startswith(".") and not any(e.startswith(x) for x in exclude)]

    for fn in files:
        fp = os.path.join(current, fn)
        size = os.path.getsize(fp)
        lines.append(f"{prefix}  {fn}  ({_fmt(size)})")

    for i, dn in enumerate(dirs):
        is_last = (i == len(dirs) - 1) and not files
        connector = "└──" if is_last else "├──"
        lines.append(f"{prefix}{connector} {dn}/")
        new_prefix = prefix + ("    " if is_last else "│   ")
        _walk(root, os.path.join(current, dn), new_prefix,
               depth + 1, max_depth, exclude, lines)


def read_file_content(
    session_dir: str,
    relpath: str,
    max_bytes: int = 8000,
) -> str:
    """
    Read a file's content, with truncation for large files.
    Returns a formatted string suitable for inlining into prompts.
    """
    filepath = os.path.normpath(os.path.join(session_dir, relpath))
    if not os.path.isfile(filepath):
        return f"(file not found: {relpath})"

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        return f"(error reading {relpath}: {e})"

    size = len(content)
    if size > max_bytes:
        head = content[:max_bytes // 2]
        tail = content[-(max_bytes // 2):]
        return (
            f"--- {relpath} ({_fmt(size)}, showing first+last {max_bytes // 2} chars) ---\n"
            f"{head}\n"
            f"... [{_fmt(size - max_bytes)} truncated] ...\n"
            f"{tail}\n"
            f"--- end {relpath} ---"
        )
    return (
        f"--- {relpath} ({_fmt(size)}) ---\n"
        f"{content}\n"
        f"--- end {relpath} ---"
    )


def inline_workspace_files(
    session_dir: str,
    exclude_prefixes: Optional[list] = None,
    max_total_bytes: int = 24000,
    pick: Optional[list[str]] = None,
) -> str:
    """
    Inline the contents of workspace files into a single string.

    Parameters
    ----------
    session_dir : str
        Root of the session workspace.
    exclude_prefixes : list or None
        Filename prefixes to skip (default: ['_stage_']).
    max_total_bytes : int
        Hard cap on total inlined content.
    pick : list or None
        If provided, only inline these specific relative paths.
        Otherwise, inline all files found.
    """
    if exclude_prefixes is None:
        exclude_prefixes = ["_stage_"]

    if pick:
        filepaths = [os.path.normpath(os.path.join(session_dir, p)) for p in pick]
    else:
        filepaths = _collect_files(session_dir, exclude_prefixes)

    blocks: list[str] = []
    consumed = 0

    for fp in filepaths:
        if not os.path.isfile(fp):
            continue
        rel = os.path.relpath(fp, session_dir)
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            continue

        size = len(content)
        remaining = max_total_bytes - consumed
        if remaining <= 200:
            blocks.append(f"... ({len(filepaths) - len(blocks)} more files omitted: total limit reached)")
            break

        if size > remaining:
            content = content[:remaining] + f"\n... [truncated: {size - remaining} more bytes]"

        blocks.append(f"--- {rel} ({_fmt(size)}) ---\n{content}\n--- end {rel} ---")
        consumed += len(blocks[-1])

    return "\n\n".join(blocks) if blocks else "(no files in workspace)"


def _collect_files(session_dir: str, exclude_prefixes: list) -> list[str]:
    """Walk directory and return sorted list of file paths."""
    files: list[str] = []
    for root, dirs, filenames in os.walk(session_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")
                    and d not in ("__pycache__", "node_modules", ".git")]
        for fn in filenames:
            if any(fn.startswith(p) for p in exclude_prefixes):
                continue
            files.append(os.path.join(root, fn))
    return sorted(files)


def _fmt(size: int) -> str:
    if size < 1024:
        return f"{size}B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    return f"{size / (1024 * 1024):.1f}MB"
