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

        self.context = await self.browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
        )

        # ---- Init script: hook Prebid events on every page ----
        # This runs before any page scripts and makes sure that once pbjs is
        # available, we attach onEvent listeners and push their args into
        # event stores for later inspection by tests.
        await self.context.add_init_script(
            """
            (function () {
              try {
                // ------------------------------------------------------------
                // Prebid event stores
                //
                // Keep the legacy combined store for backwards compatibility,
                // but ALSO split into display vs video streams.
                // ------------------------------------------------------------
                window.__pbjsBidEvents = window.__pbjsBidEvents || [];                 // legacy: combined
                window.__pbjsBidEventsDisplay = window.__pbjsBidEventsDisplay || [];   // new: display-only
                window.__pbjsBidEventsVideo = window.__pbjsBidEventsVideo || [];       // new: video-only

                // Tiny meta snapshot to help verification/debugging.
                window.__pbjsBidEventStoresMeta = window.__pbjsBidEventStoresMeta || {
                  displayCount: 0,
                  videoCount: 0,
                  last: null
                };

                // Prevent double-hooking on repeated navigations in the same context
                window.__pbjsEventHooked = window.__pbjsEventHooked || false;

                // Hook Permutive signals too (existing behaviour)
                window.__permSignalsHooked = window.__permSignalsHooked || false;

                const isObject = (x) => x && typeof x === "object";

                const isVideoBidLike = (bid) => {
                  try {
                    if (!bid) return false;

                    const adUnitCode = bid.adUnitCode != null ? String(bid.adUnitCode).toLowerCase() : "";
                    if (adUnitCode === "hero_player") return true;

                    const mt = isObject(bid.mediaTypes) ? bid.mediaTypes : null;
                    const video = mt && isObject(mt.video) ? mt.video : null;
                    if (video) return true;

                    const ortb2Imp = isObject(bid.ortb2Imp) ? bid.ortb2Imp : null;
                    const impVideo = ortb2Imp && isObject(ortb2Imp.video) ? ortb2Imp.video : null;
                    if (impVideo) return true;

                    return false;
                  } catch (e) {
                    return false;
                  }
                };

                const isVideoAdUnitLike = (u) => {
                  try {
                    if (!u) return false;

                    const code = u.code != null ? String(u.code).toLowerCase() : "";
                    if (code === "hero_player") return true;

                    const mt = isObject(u.mediaTypes) ? u.mediaTypes : null;
                    const video = mt && isObject(mt.video) ? mt.video : null;
                    if (video) return true;

                    return false;
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
                      return bids.some(isVideoBidLike) ? "video" : "display";
                    }

                    // auctionInit often includes adUnits
                    if (type === "auctionInit" && args) {
                      const aus = Array.isArray(args.adUnits) ? args.adUnits : [];
                      return aus.some(isVideoAdUnitLike) ? "video" : "display";
                    }

                    // auctionEnd may include adUnits / bidsReceived depending on stack
                    if (type === "auctionEnd" && args) {
                      const aus = Array.isArray(args.adUnits) ? args.adUnits : [];
                      if (aus.some(isVideoAdUnitLike)) return "video";

                      const bidsRec = Array.isArray(args.bidsReceived) ? args.bidsReceived : [];
                      if (bidsRec.some(isVideoBidLike)) return "video";
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

                    // Optional: hook Permutive once (existing behaviour)
                    try {
                      if (!window.__permSignalsHooked && window.permutive && window.permutive.addon) {
                        window.__permSignalsHooked = true;
                      }
                    } catch (e) {}

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