import asyncio
from typing import Optional

from playwright.async_api import async_playwright


class BrowserManager:
    """Handles browser launch, context creation, and page creation."""

    def __init__(self, config: dict):
        self.config = config
        self.playwright = None
        self.browser = None
        self.context = None

    async def start(self):
        """Launch browser and create a single shared context."""
        self.playwright = await async_playwright().start()

        browser_type = self.playwright.chromium
        headless = bool(self.config.get("headless", True))
        slow_mo = int(self.config.get("slow_mo", 0) or 0)

        self.browser = await browser_type.launch(headless=headless, slow_mo=slow_mo)

        is_mobile = bool(self.config.get("mobile", True))

        # Default viewport & UA
        if is_mobile:
            viewport = {"width": 390, "height": 844}  # iPhone-ish
            user_agent = (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
                "Mobile/15E148 Safari/604.1"
            )
        else:
            viewport = {"width": 1365, "height": 768}
            user_agent = (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )

        # ---------------------------------------------------------------------
        # IMPORTANT: Basic auth for pre-prod MUST be done via Playwright
        # http_credentials, NOT by injecting demo:review@ into the URL.
        #
        # Injecting credentials into the URL breaks modern JS APIs on some pages:
        # - History.replaceState / pushState can throw SecurityError
        # - fetch() can throw when the base URL includes credentials
        #
        # Symptoms match your staging logs (replaceState + fetch errors),
        # and cause downstream failures (pbjs stub only, no config/modules, etc.).
        # ---------------------------------------------------------------------
        raw_site_url = (self.config.get("site_url", "") or "").lower()
        is_preprod = (
            any(tok in raw_site_url for tok in ("uat", "feat", "dev", "staging"))
            or self.config.get("active_site", "") == "independent_feat"
        )

        context_kwargs = {
            "viewport": viewport,
            "user_agent": user_agent,
        }

        if is_preprod:
            # Allow override via config, fallback to demo/review
            username = self.config.get("basic_auth_user", "demo")
            password = self.config.get("basic_auth_pass", "review")
            context_kwargs["http_credentials"] = {"username": username, "password": password}

        self.context = await self.browser.new_context(**context_kwargs)

        # ---- Init script: hook Prebid events on every page ----
        # This runs before any page scripts and makes sure that once pbjs is
        # available, we attach onEvent listeners and push their args into
        # event stores for later inspection by tests.
        #
        # IMPORTANT: "Video" stream here means HERO PLAYER stream (adUnitCode/code == hero_player),
        # NOT "anything with mediaTypes.video".
        await self.context.add_init_script(
            """
            (function () {
              try {
                // ------------------------------------------------------------
                // Prebid event stores
                // ------------------------------------------------------------
                window.__pbjsBidEvents = window.__pbjsBidEvents || [];                 // legacy: combined
                window.__pbjsBidEventsDisplay = window.__pbjsBidEventsDisplay || [];   // display stream (everything NOT hero_player)
                window.__pbjsBidEventsVideo = window.__pbjsBidEventsVideo || [];       // hero_player stream only

                // Tiny meta snapshot to help verification/debugging.
                window.__pbjsBidEventStoresMeta = window.__pbjsBidEventStoresMeta || {
                  displayCount: 0,
                  videoCount: 0,
                  last: null
                };

                // Prevent double-hooking on repeated navigations in the same context
                window.__pbjsEventHooked = window.__pbjsEventHooked || false;

                const HERO_CODES = new Set(["hero_player"]);

                const norm = (x) => {
                  try { return (x == null ? "" : String(x)).trim().toLowerCase(); }
                  catch (e) { return ""; }
                };

                const isHeroCode = (code) => HERO_CODES.has(norm(code));

                const isHeroBidLike = (bid) => {
                  try {
                    if (!bid) return false;
                    // For bidRequested, bid objects commonly have adUnitCode
                    // For some stacks, it may be code
                    const adUnitCode = norm(bid.adUnitCode || bid.code);
                    return isHeroCode(adUnitCode);
                  } catch (e) {
                    return false;
                  }
                };

                const isHeroAdUnitLike = (u) => {
                  try {
                    if (!u) return false;
                    // For auctionInit, adUnits commonly have code
                    const code = norm(u.code || u.adUnitCode);
                    return isHeroCode(code);
                  } catch (e) {
                    return false;
                  }
                };

                const classifyEventStream = (type, args) => {
                  try {
                    if (!type) return "display";

                    // Most reliable: bidRequested has a bids array
                    if (type === "bidRequested" && args) {
                      const bids = Array.isArray(args.bids) ? args.bids : [];
                      return bids.some(isHeroBidLike) ? "video" : "display";
                    }

                    // auctionInit often includes adUnits
                    if (type === "auctionInit" && args) {
                      const aus = Array.isArray(args.adUnits) ? args.adUnits : [];
                      return aus.some(isHeroAdUnitLike) ? "video" : "display";
                    }

                    // auctionEnd may include adUnits / bidsReceived depending on stack
                    if (type === "auctionEnd" && args) {
                      const aus = Array.isArray(args.adUnits) ? args.adUnits : [];
                      if (aus.some(isHeroAdUnitLike)) return "video";

                      const bidsRec = Array.isArray(args.bidsReceived) ? args.bidsReceived : [];
                      if (bidsRec.some(isHeroBidLike)) return "video";
                    }

                    // bidResponse / bidWon sometimes include adUnitCode directly
                    if ((type === "bidResponse" || type === "bidWon") && args) {
                      // args can be a single bid object in many prebid builds
                      return isHeroBidLike(args) ? "video" : "display";
                    }
                  } catch (e) {
                    // ignore
                  }
                  return "display";
                };

                const pushEvent = (ev) => {
                  try {
                    // Legacy combined store (keep existing tests working)
                    window.__pbjsBidEvents.push(ev);

                    // Split store
                    if (ev.stream === "video") {
                      window.__pbjsBidEventsVideo.push(ev);
                      window.__pbjsBidEventStoresMeta.videoCount += 1;
                    } else {
                      window.__pbjsBidEventsDisplay.push(ev);
                      window.__pbjsBidEventStoresMeta.displayCount += 1;
                    }

                    window.__pbjsBidEventStoresMeta.last = {
                      type: ev.type,
                      stream: ev.stream,
                      t: Date.now()
                    };
                  } catch (e) {
                    // ignore
                  }
                };

                // Poll until pbjs exists, then attach listeners once
                const hookPbjs = () => {
                  try {
                    if (!window.pbjs || typeof window.pbjs.onEvent !== "function") return false;
                    if (window.__pbjsEventHooked) return true;

                    window.__pbjsEventHooked = true;

                    const eventsToHook = [
                      "auctionInit",
                      "bidRequested",
                      "bidResponse",
                      "bidWon",
                      "auctionEnd",
                    ];

                    eventsToHook.forEach((type) => {
                      try {
                        window.pbjs.onEvent(type, function (args) {
                          const stream = classifyEventStream(type, args);
                          pushEvent({
                            type,
                            stream,
                            args,
                            ts: Date.now(),
                          });
                        });
                      } catch (e) {
                        // ignore
                      }
                    });

                    return true;
                  } catch (e) {
                    return false;
                  }
                };

                // Try immediately, then poll for up to ~15s
                if (!hookPbjs()) {
                  let tries = 0;
                  const maxTries = 60; // 60 * 250ms = 15s
                  const t = setInterval(() => {
                    tries++;
                    if (hookPbjs() || tries >= maxTries) {
                      clearInterval(t);
                    }
                  }, 250);
                }

                // ------------------------------------------------------------
                // GAM slot request store
                // Hook via googletag.cmd so the listener is queued inside
                // googletag's own init sequence — guaranteed to run before
                // any refresh()/display() calls fire slotRequested events.
                // ------------------------------------------------------------
                window.__gamSlotRequests = [];
                window.__gamSlotRequestHooked = false;

                // Ensure the googletag stub exists (pages do this themselves,
                // but we need it here in case our script runs first).
                window.googletag = window.googletag || {};
                window.googletag.cmd = window.googletag.cmd || [];

                window.googletag.cmd.push(function () {
                  try {
                    if (window.__gamSlotRequestHooked) return;
                    window.__gamSlotRequestHooked = true;
                    console.log("[GAM hook] slotRequested listener registered");

                    window.googletag.pubads().addEventListener("slotRequested", function (event) {
                      try {
                        const slot = event.slot;
                        const keys = slot.getTargetingKeys ? slot.getTargetingKeys() : [];
                        const targeting = {};
                        keys.forEach(function (k) { targeting[k] = slot.getTargeting(k); });
                        window.__gamSlotRequests.push({
                          adUnit: slot.getAdUnitPath ? slot.getAdUnitPath() : null,
                          slotId: slot.getSlotElementId ? slot.getSlotElementId() : null,
                          targeting: targeting,
                          ts: Date.now(),
                        });
                        console.log("[GAM hook] slotRequested captured:", slot.getAdUnitPath ? slot.getAdUnitPath() : "?");
                      } catch (e) { /* ignore */ }
                    });
                  } catch (e) {
                    console.log("[GAM hook] cmd.push error:", String(e));
                  }
                });

              } catch (e) {
                // ignore top-level errors
              }
            })();
            """
        )

    async def new_page(self):
        """Create a new page in the shared context."""
        if not self.context:
            raise RuntimeError("Browser context not started. Call start() first.")
        page = await self.context.new_page()
        page.on("console", lambda msg: print(f"  [browser] {msg.text}") if msg.text.startswith("[GAM hook]") else None)
        return page

    async def close(self):
        """Close context and browser cleanly."""
        try:
            if self.context:
                await self.context.close()
        except Exception:
            pass

        try:
            if self.browser:
                await self.browser.close()
        except Exception:
            pass

        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass

        self.playwright = None
        self.browser = None
        self.context = None