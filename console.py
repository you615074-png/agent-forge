"""
AgentForge — Console Output Module (v0.5)
==========================================
ANSI-styled terminal output for Windows (10+) / Linux / macOS.
Zero dependencies — pure Python + ctypes for VT mode on Windows.

Usage:
  from console import cprint, box, header, stage, Colors
  cprint("Success!", fg=Colors.GREEN)
  box("Pipeline", "4 stages completed")
"""

import os
import sys
import ctypes
import shutil
from typing import Optional


# ═══════════════════════════════════════════════════════════════
# VT / ANSI enablement (Windows)
# ═══════════════════════════════════════════════════════════════

_ANSI_ENABLED = False


def enable_vt():
    """Enable ANSI escape code processing on Windows 10+."""
    global _ANSI_ENABLED
    if _ANSI_ENABLED:
        return

    if os.name == "nt":
        # Try enabling VT processing on stdout
        kernel32 = ctypes.windll.kernel32
        for handle in [ctypes.c_void_p(-11), ctypes.c_void_p(-12)]:  # STDOUT, STDERR
            try:
                mode = ctypes.c_ulong()
                kernel32.GetConsoleMode(handle, ctypes.byref(mode))
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
            except Exception:
                pass

        # Also check for NO_COLOR / FORCE_COLOR env vars
        if os.environ.get("NO_COLOR"):
            _ANSI_ENABLED = False
            return

    _ANSI_ENABLED = True
    # If TERM is dumb, disable
    if os.environ.get("TERM") == "dumb":
        _ANSI_ENABLED = False


# Enable on import
enable_vt()


# ═══════════════════════════════════════════════════════════════
# ANSI escape sequences
# ═══════════════════════════════════════════════════════════════

class Colors:
    """ANSI color palette."""
    # Foreground
    BLACK   = "\033[30m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"

    # Bright foreground
    GRAY        = "\033[90m"
    BRIGHT_RED  = "\033[91m"
    BRIGHT_GREEN= "\033[92m"
    BRIGHT_YELLOW="\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_CYAN = "\033[96m"

    # Background
    BG_RED   = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE  = "\033[44m"
    BG_GRAY  = "\033[100m"

    # Styles
    BOLD      = "\033[1m"
    DIM       = "\033[2m"
    ITALIC    = "\033[3m"
    UNDERLINE = "\033[4m"

    # Reset
    RESET = "\033[0m"


# ── Color map for task types ──
STAGE_COLORS = {
    "coding":         Colors.CYAN,
    "review":         Colors.MAGENTA,
    "bugfix":         Colors.RED,
    "testing":        Colors.GREEN,
    "analysis":       Colors.BLUE,
    "refactor":       Colors.YELLOW,
    "documentation":  Colors.GRAY,
}

STAGE_ICONS = {
    "coding":         "◇",
    "review":         "◎",
    "bugfix":         "◆",
    "testing":        "✓",
    "analysis":       "○",
    "refactor":       "↻",
    "documentation":  "¶",
}


# ═══════════════════════════════════════════════════════════════
# Core output functions
# ═══════════════════════════════════════════════════════════════

def _style(text: str, fg: str = "", bg: str = "", style: str = "") -> str:
    """Wrap text with ANSI codes. Returns plain text if ANSI is off."""
    if not _ANSI_ENABLED:
        return text
    prefix = fg + bg + style
    if not prefix:
        return text
    return f"{prefix}{text}{Colors.RESET}"


def cprint(text: str, fg: str = "", bg: str = "", style: str = "", end: str = "\n"):
    """Print colored text to stdout."""
    print(_style(text, fg, bg, style), end=end)


def dim(text: str) -> str:
    return _style(text, style=Colors.DIM)


def bold(text: str) -> str:
    return _style(text, style=Colors.BOLD)


def green(text: str) -> str:
    return _style(text, fg=Colors.GREEN)


def red(text: str) -> str:
    return _style(text, fg=Colors.RED)


def yellow(text: str) -> str:
    return _style(text, fg=Colors.YELLOW)


def cyan(text: str) -> str:
    return _style(text, fg=Colors.CYAN)


def magenta(text: str) -> str:
    return _style(text, fg=Colors.MAGENTA)


def gray(text: str) -> str:
    return _style(text, fg=Colors.GRAY)


def ok(text: str = "OK") -> str:
    return _style(f"✓ {text}", fg=Colors.GREEN)


def fail(text: str = "FAIL") -> str:
    return _style(f"✗ {text}", fg=Colors.RED)


def warn(text: str = "WARN") -> str:
    return _style(f"⚠ {text}", fg=Colors.YELLOW)


# ═══════════════════════════════════════════════════════════════
# Layout helpers
# ═══════════════════════════════════════════════════════════════

def header(text: str, width: int = 60):
    """Print a large header block."""
    line = "═" * width
    print(_style(f"\n{line}", style=Colors.BOLD))
    print(_style(f"  {text}", style=Colors.BOLD))
    print(_style(f"{line}\n", style=Colors.BOLD))


def section(text: str, width: int = 60):
    """Print a section divider."""
    line = "─" * width
    cprint(f"\n{line}", style=Colors.DIM)
    cprint(f"  {text}", style=Colors.BOLD)
    cprint(f"{line}\n", style=Colors.DIM)


def box(title: str, body: str, border_color: str = Colors.CYAN) -> str:
    """Return a boxed string (doesn't print — returns it)."""
    lines = body.strip().split("\n")
    max_w = max(
        len(_strip_ansi(line)) for line in ([title] + lines)
    ) + 4
    max_w = min(max_w, shutil.get_terminal_size().columns - 2)

    top = _style(f"┌─ {title} {'─' * (max_w - len(_strip_ansi(title)) - 4)}┐", fg=border_color)
    bottom = _style(f"└{'─' * max_w}┘", fg=border_color)

    out = [top]
    for line in lines:
        stripped = _strip_ansi(line)
        padding = max_w - len(stripped) - 1
        out.append(_style(f"│ {line}{' ' * max(0, padding)}│", fg=border_color))
    out.append(bottom)
    return "\n".join(out)


def _strip_ansi(text: str) -> str:
    """Remove ANSI codes to get visible length."""
    import re
    return re.sub(r'\033\[[0-9;]*m', '', text)


# ═══════════════════════════════════════════════════════════════
# Pipeline / Stage display
# ═══════════════════════════════════════════════════════════════

def stage_header(stage_id: str, stage_type: str, index: int, total: int, width: int = 60):
    """Print a colored stage header."""
    color = STAGE_COLORS.get(stage_type, Colors.WHITE)
    icon = STAGE_ICONS.get(stage_type, "•")
    label = f"Stage {index}/{total}: {icon} {stage_id} → {stage_type.upper()}"
    line = "─" * width
    cprint(f"\n{line}", style=Colors.DIM)
    cprint(f"  {label}", fg=color, style=Colors.BOLD)
    cprint(f"{line}\n", style=Colors.DIM)


def status_line(ok_flag: bool, text: str):
    """Print a status line with check or cross."""
    if ok_flag:
        cprint(f"  {ok()}", end=" ")
    else:
        cprint(f"  {fail()}", end=" ")
    print(text)


def agent_match(agent_name: str, score: float, description: str):
    """Display an agent match result."""
    bar_len = int(score * 20)
    bar = "█" * bar_len + "░" * (20 - bar_len)
    score_color = Colors.GREEN if score > 0.8 else Colors.YELLOW if score > 0.5 else Colors.RED
    cprint(f"  {agent_name:<12s} ", fg=Colors.CYAN, end="")
    cprint(f"{bar} ", fg=score_color, end="")
    cprint(f"{score:.2f}", style=Colors.BOLD)
    cprint(f"  {'':12s} {description[:70]}", style=Colors.DIM)


def file_item(name: str, size: int, indent: int = 2):
    """Display a file with size."""
    prefix = " " * indent
    size_str = _fmt_size(size)
    print(f"{prefix}{_style(name, fg=Colors.CYAN)} {dim(f'({size_str})')}")


def _fmt_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    return f"{size_bytes / (1024 * 1024):.1f}MB"


# ═══════════════════════════════════════════════════════════════
# Spinner (simple inline)
# ═══════════════════════════════════════════════════════════════

class Spinner:
    """Simple inline spinner for long-running operations."""

    _frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, text: str = "Working"):
        self.text = text
        self._i = 0
        self._active = False

    def start(self):
        self._active = True

    def stop(self, final: str = ""):
        self._active = False
        if final:
            sys.stdout.write(f"\r\033[K{final}\n")
        else:
            sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    def tick(self):
        if not self._active:
            return
        frame = self._frames[self._i % len(self._frames)]
        self._i += 1
        sys.stdout.write(f"\r  {_style(frame, fg=Colors.CYAN)} {self.text}")
        sys.stdout.flush()


# ═══════════════════════════════════════════════════════════════
# Helpers for commands
# ═══════════════════════════════════════════════════════════════

def format_file_view(path: str, content: str, max_lines: int = 50) -> str:
    """Format file content with line numbers, truncated if large."""
    lines = content.split("\n")
    total = len(lines)

    if total > max_lines * 2 and len(content) > 5000:
        # Head + tail
        head = "\n".join(
            f"  {_style(str(i + 1).rjust(4), fg=Colors.GRAY)} {_style('│', fg=Colors.GRAY)} {l}"
            for i, l in enumerate(lines[:max_lines // 2])
        )
        tail = "\n".join(
            f"  {_style(str(i + 1).rjust(4), fg=Colors.GRAY)} {_style('│', fg=Colors.GRAY)} {l}"
            for i, l in enumerate(lines[-max_lines // 2:], total - max_lines // 2)
        )
        omitted = total - max_lines
        return (
            f"{_style(path, style=Colors.BOLD)} {dim(f'({_fmt_size(len(content))}, {total} lines)')}\n"
            f"{head}\n"
            f"  {dim(f'... {omitted} lines omitted ...')}\n"
            f"{tail}"
        )

    # Full file
    numbered = "\n".join(
        f"  {_style(str(i + 1).rjust(4), fg=Colors.GRAY)} {_style('│', fg=Colors.GRAY)} {l}"
        for i, l in enumerate(lines)
    )
    return (
        f"{_style(path, style=Colors.BOLD)} {dim(f'({_fmt_size(len(content))}, {total} lines)')}\n"
        f"{numbered}"
    )


def format_config_line(key: str, value, indent: int = 2) -> str:
    """Format a config key-value pair."""
    prefix = " " * indent
    key_str = _style(f"{key}:", style=Colors.BOLD)
    if isinstance(value, bool):
        val_str = green(str(value)) if value else dim(str(value))
    elif isinstance(value, (int, float)):
        val_str = cyan(str(value))
    elif value is None:
        val_str = dim("(none)")
    else:
        val_str = str(value)
    return f"{prefix}{key_str} {val_str}"
