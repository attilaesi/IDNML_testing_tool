# core/device_helpers.py
#
# Device type detection from viewport dimensions.
#
#   390x659  (iPhone 15 Pro)   → mobile
#   412x839  (Pixel 7)         → mobile
#   834x1194 (iPad Pro 11)     → tablet   (portrait, width >= 768)
#   768x1024 (iPad mini)       → tablet   (portrait, width >= 768)
#   1024x768 (iPad landscape)  → desktop  (landscape)
#   1280x720 (Desktop Chrome)  → desktop


# Minimum portrait width to classify as tablet rather than phone.
_TABLET_MIN_WIDTH = 768


def is_mobile_viewport(config: dict) -> bool:
    """Return True if the viewport is in portrait orientation (width < height)."""
    viewport = config.get("viewport") or {}
    w = int(viewport.get("width", 390))
    h = int(viewport.get("height", 844))
    return w < h


def device_label(config: dict) -> str:
    """Return 'mobile', 'tablet', or 'desktop' based on viewport dimensions.

    Portrait + narrow  → mobile
    Portrait + wide    → tablet  (width >= _TABLET_MIN_WIDTH)
    Landscape          → desktop
    """
    viewport = config.get("viewport") or {}
    w = int(viewport.get("width", 390))
    h = int(viewport.get("height", 844))

    if w >= h:
        return "desktop"
    if w >= _TABLET_MIN_WIDTH:
        return "tablet"
    return "mobile"


def device_display_name(config: dict) -> str:
    """Return the human-readable device name for log output.

    Uses config['device_name'] (e.g. 'iPhone 15 Pro', 'Pixel 7') when set,
    falls back to the viewport-derived label.
    """
    name = config.get("device_name", "")
    return name if name else device_label(config)


def bidder_lookup_device(device: str) -> str:
    """Tablets share the mobile bidder set — always query mobile rows."""
    return "mobile" if device == "tablet" else device
