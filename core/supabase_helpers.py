# core/supabase_helpers.py
# Shared helpers for tests that query Supabase for expected bidder configs.

import os
import pathlib
from typing import Tuple, Optional

# Automatically load credentials from IDNML_config_ui/.env.local if present.
# That file uses NEXT_PUBLIC_ prefixed names which are also checked below.
_ENV_LOCAL = pathlib.Path(__file__).parents[2] / "IDNML_config_ui" / ".env.local"

def _load_env_local() -> None:
    if not _ENV_LOCAL.exists():
        return
    with open(_ENV_LOCAL) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)

_load_env_local()


def get_supabase_credentials(config: dict) -> Tuple[Optional[str], Optional[str]]:
    """
    Resolve Supabase URL and anon key from config or environment variables.
    Checks both plain names and NEXT_PUBLIC_ prefixed names (from .env.local).
    Returns (url, key) — either may be None if not configured.
    """
    url = (config.get("supabase_url")
           or os.getenv("SUPABASE_URL")
           or os.getenv("NEXT_PUBLIC_SUPABASE_URL"))
    key = (config.get("supabase_anon_key")
           or os.getenv("SUPABASE_ANON_KEY")
           or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY"))
    return url, key


def is_supabase_configured(config: dict) -> bool:
    """Return True only if both URL and key are available."""
    url, key = get_supabase_credentials(config)
    return bool(url and key)
