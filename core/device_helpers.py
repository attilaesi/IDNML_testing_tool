# core/device_helpers.py
#
# Device type detection from viewport dimensions.
# Portrait orientation (width < height) = mobile/tablet.
# Landscape orientation (width >= height) = desktop.
#
# This works for any viewport size without magic breakpoints:
#   390x844  (iPhone)        → mobile
#   1366x768 (laptop)        → desktop
#   768x1024 (iPad portrait) → mobile
#   1024x768 (iPad landscape)→ desktop


def is_mobile_viewport(config: dict) -> bool:
    """Return True if the configured viewport is portrait (width < height)."""
    viewport = config.get("viewport") or {}
    w = int(viewport.get("width", 390))
    h = int(viewport.get("height", 844))
    return w < h


def device_label(config: dict) -> str:
    """Return 'mobile' or 'desktop' based on viewport."""
    return "mobile" if is_mobile_viewport(config) else "desktop"
