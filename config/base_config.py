# config/base_config.py

from config.site_urls import SITE_PROFILES


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

        # Browser-level settings
        self.browser_config = {
            "headless": True,
            # For now this is the single switch; we’ll refactor to device_mode later
            "mobile": True,
            # Playwright default timeout (ms)
            "timeout": 30000,
            # Viewport – keep in sync with mobile flag for now
            "viewport": {"width": 390, "height": 844},
            # "viewport": {"width": 1366, "height": 768},
        }

        # Framework / test behaviour
        self.test_config = {
            # Max number of URLs from the site profile to test in one run
            "max_pages": 10,

            # Run pages sequentially or in parallel
            "parallel_tests": False,
            "concurrency": 4,  # only used when parallel_tests=True

            # Debug / robustness settings
            "debug_screenshots": False,    # CMP / failure screenshots
            "cmp_timeout": 3.0,            # seconds to wait for CMP dismiss
            "prebid_ready_timeout": 20.0,  # seconds to wait for pbjs + GPT
            "page_type_timeout": 3.0,      # seconds to poll for pageType
            "warmup_pages": 3,             # number of pages to run before testing start

            # 🔸 Global trace switch for extra console logging in tests
            "trace": False,
        }

        # Output configuration
        self.output_config = {
            "output_file": "output/output.csv",
            "output_pagetype_file": "output/output_by_pagetype.csv",
            "cmp_debug_dir": "output/cmp_debug",
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

        # Attach cookies (application is decided in framework_manager based on URL)
        config["preprod_cookies"] = self.preprod_cookies

        # Attach site profile & URLs
        site_key = str(self.active_site).lower()
        site_profile = SITE_PROFILES[site_key]

        config["active_site"] = site_key
        config["site_url"] = site_profile["site_url"]

        # Single URL set per site and trim to max_pages
        all_urls = site_profile["urls"]
        max_pages = config.get("max_pages", 10)
        config["urls"] = all_urls[:max_pages]

        return config


# Convenience: import CONFIG directly from main.py
CONFIG = TestConfig().get_config()