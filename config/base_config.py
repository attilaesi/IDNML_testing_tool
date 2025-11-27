# config/base_config.py

from config.site_urls import SITE_PROFILES


class TestConfig:
    """Base configuration for the ad testing framework.

    All knobs are set here in code – no environment variables.
    """

    def __init__(self):
        # ─────────────────────────────────────────────
        # Core switches you actually tweak
        # ─────────────────────────────────────────────
        # Which site config to use: "independent" or "standard"
        self.active_site = "independent"

        # UAT vs LIVE
        #   False => use live URLs from SITE_PROFILES
        #   True  => use UAT URLs + basic auth + feature cookies
        self.uat_mode = True

        # Browser-level settings
        self.browser_config = {
            "headless": False,
            # For now this is the single switch; we’ll refactor to device_mode later
            "mobile": True,
            # Playwright default timeout (ms)
            "timeout": 30000,
            # Viewport – keep in sync with mobile flag for now
            "viewport": {"width": 390, "height": 844},
        }

        # Framework / test behaviour
        self.test_config = {
            # Max number of URLs from the site profile to test in one run
            "max_pages": 10,

            # Run pages sequentially or in parallel
            "parallel_tests": False,
            "concurrency": 4,  # only used when parallel_tests=True

            # Debug / robustness settings
            "debug_screenshots": True,   # CMP / failure screenshots
            "cmp_timeout": 3.0,          # seconds to wait for CMP dismiss
            "prebid_ready_timeout": 10.0,  # seconds to wait for pbjs + GPT
            "page_type_timeout": 3.0,      # seconds to poll for pageType

            # 🔸 Global trace switch for extra console logging in tests
            "trace": False,
        }

        # Output configuration
        self.output_config = {
        "output_file": "output/output.csv",
        "output_pagetype_file": "output/output_by_pagetype.csv",
        "cmp_debug_dir": "output/cmp_debug",
}

        # 🔹 UAT-specific feature flag cookies
        # These are only applied when uat_mode=True; the domain is patched
        # dynamically per URL in framework_manager._set_context_cookies().
        self.uat_cookies = [
            {"name": "feat__ad_api",            "value": "true", "path": "/"},
            {"name": "feat__ad_refresh",        "value": "true", "path": "/"},
            {"name": "feat__cmp_force_enable",  "value": "true", "path": "/"},
            {"name": "feat__primis_new_design", "value": "true", "path": "/"},
        ]

    def get_config(self):
        """Return merged configuration dict with site URLs embedded."""
        config = {}
        config.update(self.browser_config)
        config.update(self.test_config)
        config.update(self.output_config)

        # Attach UAT flags
        config["uat_cookies"] = self.uat_cookies
        config["uat_mode"] = self.uat_mode

        # Attach site profile & URLs
        site_profile = SITE_PROFILES[self.active_site]
        config["active_site"] = self.active_site
        config["site_url"] = site_profile["site_url"]

        # Choose URL set by mode and trim to max_pages
        all_urls = site_profile["uat_urls"] if self.uat_mode else site_profile["live_urls"]
        max_pages = config.get("max_pages", 10)
        config["urls"] = all_urls[:max_pages]

        return config


# Convenience: import CONFIG directly from main.py
CONFIG = TestConfig().get_config()