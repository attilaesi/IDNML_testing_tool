import asyncio
from typing import Dict, Any, Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page


class BrowserManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.playwright = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def start(self):
        """Initialize Playwright, browser and context."""
        self.playwright = await async_playwright().start()

        # ---- Launch browser ----
        launch_options: Dict[str, Any] = {
            "headless": self.config.get("headless", True),
        }
        if self.config.get("mobile", True):
            # Helps window sizing for mobile emulation
            launch_options["args"] = ["--window-size=390,844"]

        self.browser = await self.playwright.chromium.launch(**launch_options)

        # ---- Build context options (mobile / desktop) ----
        context_kwargs: Dict[str, Any] = {}

        if self.config.get("mobile", True):
            # Try to use built-in device profile, fall back to manual settings
            try:
                device = self.playwright.devices["iPhone 14"]
                context_kwargs.update(device)
            except KeyError:
                context_kwargs.update(
                    {
                        "user_agent": (
                            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                            "Mobile/15A372 Safari/604.1"
                        ),
                        "viewport": {"width": 390, "height": 844},
                        "device_scale_factor": 3,
                        "is_mobile": True,
                        "has_touch": True,
                    }
                )
        else:
            # Simple desktop-like context
            context_kwargs.update(
                {
                    "user_agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/115 Safari/537.36"
                    ),
                    "viewport": self.config.get(
                        "viewport", {"width": 1280, "height": 720}
                    ),
                    "is_mobile": False,
                    "has_touch": False,
                }
            )

        # ---- Optional HTTP Basic Auth for UAT/DEV ----
        if self.config.get("uat_mode", False):
            context_kwargs["http_credentials"] = {
                "username": "demo",
                "password": "review",
            }
            print("🔐 UAT/DEV detected — HTTP basic auth enabled (demo/review)")
        else:
            print("🌐 LIVE mode — no HTTP auth required")

        # ---- Create context ----
        self.context = await self.browser.new_context(**context_kwargs)

        # ---- Init script: hook Prebid events on every page ----
        # This runs before any page scripts and makes sure that once pbjs is
        # available, we attach onEvent listeners and push their args into
        # window.__pbjsBidEvents for later inspection by tests.
        await self.context.add_init_script(
            """
            (function () {
              try {
                // Global store for Prebid events
                window.__pbjsBidEvents = window.__pbjsBidEvents || [];

                function hookPrebidEvents() {
                  try {
                    var pb = window.pbjs;
                    if (!pb || typeof pb.onEvent !== 'function' || pb.__permSignalsHooked) {
                      return;
                    }

                    pb.__permSignalsHooked = true;

                    ['auctionInit', 'bidRequested', 'auctionEnd'].forEach(function (ev) {
                      try {
                        pb.onEvent(ev, function (args) {
                          try {
                            window.__pbjsBidEvents.push({ type: ev, args: args });
                          } catch (e) {
                            // ignore push errors
                          }
                        });
                      } catch (e) {
                        // ignore per-event hook failure
                      }
                    });
                  } catch (e) {
                    // ignore hook errors
                  }
                }

                // Ensure pbjs + que exist, then queue our hook so it runs
                // once Prebid is fully initialised.
                window.pbjs = window.pbjs || {};
                window.pbjs.que = window.pbjs.que || [];
                window.pbjs.que.push(hookPrebidEvents);
              } catch (e) {
                // swallow any init-script errors
              }
            })();
            """
        )

    async def new_page(self) -> Page:
        """Create a new page."""
        if not self.context:
            await self.start()
        return await self.context.new_page()

    async def close(self):
        """Close browser and cleanup."""
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None