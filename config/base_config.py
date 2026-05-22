# config/base_config.py

from config.site_urls import SITE_PROFILES
from config.device_config import ACTIVE_DEVICE


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
            # Playwright default timeout (ms)
            "timeout": 30000,
            "device_name": ACTIVE_DEVICE,
        }

        # Framework / test behaviour
        self.test_config = {
            # Max number of URLs from the site profile to test in one run
            "max_pages": 10,

            # Run pages sequentially or in parallel
            "parallel_tests": True,
            "concurrency": 2,       # only used when parallel_tests=True

            # Run all devices concurrently in multi-device runs
            "parallel_devices": True,

            # Debug / robustness settings
            "debug_screenshots": False,    # CMP / failure screenshots
            "cmp_timeout": 3.0,            # seconds to wait for CMP dismiss
            "prebid_ready_timeout": 20.0,  # seconds to wait for pbjs + GPT
            "page_type_timeout": 3.0,      # seconds to poll for pageType
            "warmup_pages": 3,             # number of pages to run before testing start

            # 🔸 Global trace switch for extra console logging in tests
            "trace": False,
        }

        # Taboola settings
        self.taboola_config = {
            "taboola_loader_url": "https://cdn.taboola.com/libtrc/eslmedia-theindependent/loader.js",
            "taboola_wait_timeout_ms": 15000,
        }

        # Output configuration
        self.output_config = {
            "output_file": "output/output.csv",
            "output_pagetype_file": "output/output_by_pagetype.csv",
            "cmp_debug_dir": "output/cmp_debug",
        }

        # ─────────────────────────────────────────────────────────────
        # Google Sheets output
        # ─────────────────────────────────────────────────────────────
        # Set sheets_enabled = True to write a new timestamped Google Sheet
        # at the end of every run (single-device and multi-device).
        #
        # Requires GOOGLE_SERVICE_ACCOUNT_JSON env var — see README for setup.
        #
        # sheets_share_email: your personal Google account email.
        #   The new sheet will be shared with this address automatically
        #   so it appears in your "Shared with me" Drive folder.
        #   Can also be set via SHEETS_SHARE_EMAIL env var.
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
        config.update(self.output_config)
        config.update(self.taboola_config)
        config.update(self.sheets_config)

        # Attach cookies (application is decided in framework_manager based on URL)
        config["preprod_cookies"] = self.preprod_cookies
        config["light_ad_rules"] = self.light_ad_rules

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