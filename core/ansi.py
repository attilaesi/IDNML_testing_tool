# core/ansi.py
#
# Minimal ANSI colour helpers — no external dependencies.
# Falls back to plain text when stdout is not a TTY (CI, file redirection, etc.).

import sys

_RESET = "\033[0m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_DIM = "\033[2m"


def _tty() -> bool:
    try:
        return bool(getattr(sys.stdout, "isatty", lambda: False)())
    except Exception:
        return False


def green(s: str) -> str:
    return f"{_GREEN}{s}{_RESET}" if _tty() else s


def red(s: str) -> str:
    return f"{_RED}{s}{_RESET}" if _tty() else s


def yellow(s: str) -> str:
    return f"{_YELLOW}{s}{_RESET}" if _tty() else s


def cyan(s: str) -> str:
    return f"{_CYAN}{s}{_RESET}" if _tty() else s


def dim(s: str) -> str:
    return f"{_DIM}{s}{_RESET}" if _tty() else s


def colour_state(state_value: str) -> str:
    """Apply colour to a TestState string value."""
    v = state_value.upper()
    if v == "PASSED":
        return green(state_value)
    if v in ("FAILED", "ERROR"):
        return red(state_value)
    if v == "SKIPPED":
        return yellow(state_value)
    return state_value


def colour_cell(cell: str) -> str:
    """Apply colour to a matrix cell string (PASS, FAIL, SKIP, ERROR, -)."""
    if cell.startswith("PASS"):
        return green(cell)
    if cell.startswith("FAIL") or cell.startswith("ERROR"):
        return red(cell)
    if cell.startswith("SKIP"):
        return yellow(cell)
    return cell
