# core/supabase_helpers.py
# Shared helpers for tests that query Supabase for expected bidder configs.

import os
from typing import Tuple, Optional


def get_supabase_credentials(config: dict) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve Supabase URL and anon key from config or environment variables.
    Returns (url, key) — either may be None if not configured.
    """
    url = (
        config.get("supabase_url")
        or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        or os.getenv("SUPABASE_URL")
    )
    key = (
        config.get("supabase_anon_key")
        or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
    )
    return url, key


def is_supabase_configured(config: dict) -> bool:
    """Return True only if both URL and key are available."""
    url, key = get_supabase_credentials(config)
    return bool(url and key)
