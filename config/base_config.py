# config/base_config.py

import os
from pathlib import Path

from config.site_urls import SITE_PROFILES
from config.device_config import ACTIVE_DEVICE


def _load_env_local() -> None:
    """Load env.local from the repo root into os.environ if the file exists."""
    env_file = Path(__file__).resolve().parent.parent / "env.local"
    if not env_file.is_file():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_env_local()


class TestConfig:
    """Base configuration for the ad testing framework.

    All knobs are set here in code – no environment variables.
    """

    def __init__(self):
        # ─────────────────────────────────────────────
        # Core switch you actually tweak
        # ─────────────────────────────────────────────
        # Which site profile to use:
        #   "independent", "independent_uat", "independent_staging",
        #   "standard", "standard_uat", "standard_staging"
        # self.active_site = "independent"
        self.active_site = "independent_uat"
        # self.active_site = "independent_staging"
        # self.active_site = "standard"
        # self.active_site = "standard_dev_master"

        # Force the lighter ad layout rule set.
        # When True, sets cookie feat__use_light_ad_rules=true on every page load.
        # When False, sets feat__use_light_ad_rules=false.
        # Set to None to leave the cookie unset (page uses its own default).
        self.light_ad_rules = False

        # Independent feature branch override.
        # When set, uses the "independent" URL list but replaces the live domain
        # with this base URL. Cookies (incl. feed=prod) are applied automatically
        # because "feat" appears in the hostname.
        # Example:
        #   self.indy_feat_branch = "https://indy-2739-chore-remove-snippetcontent-web.independent.co.uk"
        self.indy_feat_branch = None

        # Browser-level settings
        # Device profile drives viewport, user agent, touch, and is_mobile.
        # Change ACTIVE_DEVICE in config/device_config.py to switch devices.
        self.browser_config = {
            "headless": True,
            "timeout": 30,        # seconds — Playwright nav timeout
            "slow_mo": 0,         # milliseconds between Playwright actions (local only)
            "device_name": ACTIVE_DEVICE,
            "basic_auth_user": "demo",
            "basic_auth_pass": "review",
        }

        # Geo override — set via --geo uk / --geo us at the CLI.
        # When set, overrides Locale-cookie detection and sets BrowserStack geoLocation.
        # Leave as None to infer from the page's Locale cookie (legacy behaviour).
        self.geo = None  # "uk" | "us" | None

        # BrowserStack Automate — off by default.
        # Enable via --browserstack CLI flag or set browserstack_enabled=True here.
        # Credentials are read from BROWSERSTACK_USERNAME / BROWSERSTACK_ACCESS_KEY env vars.
        # Build and session names are auto-derived from active_site + geo + device.
        self.browserstack_config = {
            "browserstack_enabled": False,
        }

        # Framework / test behaviour
        self.test_config = {
            # Max number of URLs from the site profile to test in one run
            "max_pages": 10,

            # Per-URL concurrency: 1 = sequential, N = up to N pages in parallel
            "concurrency": 1,

            # Per-device concurrency in multi-device runs: 1 = sequential, N = up to N devices in parallel
            "device_concurrency": 1,

            # Debug / robustness settings
            "debug_screenshots": False,    # CMP / failure screenshots
            "prebid_ready_timeout": 20.0,  # seconds to wait for pbjs + GPT
            "page_type_timeout": 3.0,      # seconds to poll for pageType
            "warmup_pages": 3,             # number of pages to run before testing start

            # Global trace switch for extra console logging in tests
            "trace": False,

            # Detailed IMA/video milestone logging with timestamps.
            # Enable when diagnosing click-to-play or IMA capture timing issues.
            "video_trace": True,

            # Terminal matrix display
            "matrix_max_test_width": 36,
            "matrix_max_cell_width": 22,
            "progress_inline": True,
            "trace_spacing_between_tests": True,
        }

        # Taboola settings
        self.taboola_config = {
            "taboola_loader_url": "https://cdn.taboola.com/libtrc/eslmedia-theindependent/loader.js",
            "taboola_wait_timeout": 15,   # seconds
        }

        # ─────────────────────────────────────────────────────────────
        # Supabase — regression tracking
        # ─────────────────────────────────────────────────────────────
        # Credentials are read from env vars (SUPABASE_URL, SUPABASE_ANON_KEY).
        # Override here if needed (not recommended — keep secrets out of source).
        self.supabase_config = {
            "supabase_url": None,       # falls back to SUPABASE_URL env var
            "supabase_anon_key": None,  # falls back to SUPABASE_ANON_KEY env var
        }

        # ─────────────────────────────────────────────────────────────
        # Google Sheets output
        # ─────────────────────────────────────────────────────────────
        # Set sheets_enabled = True to write a new timestamped Google Sheet
        # at the end of every run (single-device and multi-device).
        # Auth uses OAuth — set sheets_oauth_credentials to your Desktop App
        # client secret JSON path (see README → Google Sheets Setup).
        self.sheets_config = {
            "sheets_enabled": True,
            "sheets_share_email": "attila.horvath@independent.co.uk",
            "sheets_drive_folder_id": "105n-HOfxy_6hLDN-wgQBawb3ZNyUqyCA",
            # OAuth user credentials (recommended — files created as you, no quota issues).
            # First run opens a browser to authenticate; after that it's fully headless.
            "sheets_oauth_credentials": "~/.config/adunit-oauth-client.json",
        }

        # Feature flag cookies for preprod (UAT / staging)
        # NOTE: application of these cookies should be decided from the URL
        # (uat-web / staging-web / feat / dev) in framework_manager.
        self.preprod_cookies = [
            {"name": "feat__ad_api",            "value": "true", "path": "/"},
            {"name": "feat__ad_refresh",        "value": "true", "path": "/"},
            {"name": "feat__cmp_force_enable",  "value": "true", "path": "/"},
            {"name": "feat__primis_new_design", "value": "true", "path": "/"},
            {"name": "feed",                   "value": "prod", "path": "/"},
        ]

    def get_config(self):
        """Return merged configuration dict with site URLs embedded."""
        config = {}
        config.update(self.browser_config)
        config.update(self.test_config)
        config.update(self.taboola_config)
        config.update(self.supabase_config)
        config.update(self.sheets_config)
        config.update(self.browserstack_config)

        # Attach cookies (application is decided in framework_manager based on URL)
        config["preprod_cookies"] = self.preprod_cookies
        config["light_ad_rules"] = self.light_ad_rules
        if self.geo:
            config["geo"] = self.geo.strip().lower()

        # Attach site profile & URLs
        site_key = str(self.active_site).lower()
        site_profile = SITE_PROFILES[site_key]

        if self.indy_feat_branch:
            # Swap the UAT Independent domain for the feature branch base URL.
            live_base = SITE_PROFILES["independent_uat"]["site_url"].rstrip("/")
            feat_base = self.indy_feat_branch.rstrip("/")
            all_urls = [
                u.replace(live_base, feat_base)
                for u in SITE_PROFILES["independent_uat"]["urls"]
            ]
            config["active_site"] = "independent_feat"
            config["site_url"] = feat_base
        else:
            config["active_site"] = site_key
            config["site_url"] = site_profile["site_url"]
            all_urls = site_profile["urls"]

        # Single URL set per site and trim to max_pages
        max_pages = config.get("max_pages", 10)
        config["urls"] = all_urls[:max_pages]

        return config


# Convenience: import CONFIG directly from main.py
CONFIG = TestConfig().get_config()