# core/log_helpers.py
from config.device_config import DEVICE_SUITE

_URL_W        = len("[url 10/10]") + 1
_MAX_DEVICE_W = max(len(f"[{d}]") for d in DEVICE_SUITE.values())


def log_line(stage: str, device: str = "", url_tag: str = "", message: str = "") -> str:
    parts = [f"[{stage}]"]
    device_len = 0
    if device:
        parts.append(f"[{device}]")
        device_len = len(f"[{device}]")
    if url_tag:
        # Compensate for shorter device names so the message column is always
        # at the same position regardless of which device is printing.
        extra = max(0, _MAX_DEVICE_W - device_len)
        parts.append(f"[{url_tag}]".ljust(_URL_W + extra))
    base = " ".join(parts)
    if not message:
        return base
    # url_tag padding already acts as separator; without url_tag add one space.
    return base + message if url_tag else f"{base} {message}"


def log_arrow_indent(stage: str, device: str, url_tag: str) -> int:
    """Column where ↳ lines start — aligns with the test name in the message."""
    return len(log_line(stage, device, url_tag)) + 2
