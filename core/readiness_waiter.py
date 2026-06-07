import asyncio
from core.log_helpers import log_line


class ReadinessWaiter:
    """Wait until pbjs and googletag are ready before running tests.

    On GPT video pages (pageType == "video"), also wait for a hero_player auction
    to start — unless require_hero_on_video is False (e.g. US geo where video
    Prebid does not run).
    """

    def __init__(self, timeout: float = 10.0, poll_interval: float = 0.5, require_hero_on_video: bool = True, device: str = "", url_tag: str = "", hero_player_timeout: float = 30.0):
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.require_hero_on_video = require_hero_on_video
        self.device = device
        self.url_tag = url_tag
        self.hero_player_timeout = hero_player_timeout  # extra window for hero_player after display is ready

    async def wait_for_prebid_and_gpt(self, page):
        hero_adunit = "hero_player"

        js_condition = f"""
        () => {{
            const w = window;

            const pbjsReady = !!(w.pbjs && Array.isArray(w.pbjs.que));
            const gptReady =
                !!(w.googletag &&
                   w.googletag.apiReady &&
                   w.googletag.pubads &&
                   w.googletag.pubadsReady);

            const adUnitsReady =
                !!(w.pbjs && Array.isArray(w.pbjs.adUnits) && w.pbjs.adUnits.length > 0);

            // ---- bidder count (informational only) ----
            const bidderSet = new Set();
            try {{
              if (w.pbjs && Array.isArray(w.pbjs.adUnits)) {{
                w.pbjs.adUnits.forEach(u => {{
                  (u && u.bids ? u.bids : []).forEach(b => {{
                    if (b && b.bidder) bidderSet.add(b.bidder);
                  }});
                }});
              }}
            }} catch (e) {{}}
            const bidderCount = bidderSet.size;

            // ---- GPT pageType detection (best-effort) ----
            let pageType = null;
            try {{
              if (w.googletag && w.googletag.apiReady && w.googletag.pubads) {{
                const pubads = w.googletag.pubads();
                if (pubads && typeof pubads.getTargeting === "function") {{
                  const v = pubads.getTargeting("pageType");
                  pageType = (v && v[0]) ? String(v[0]).toLowerCase() : null;
                }}
              }}
            }} catch (e) {{
              pageType = null;
            }}

            const isVideoPage = (pageType === "video");

            // ---- Detect whether at least one auction / bid request has fired (any adunit) ----
            let auctionStarted = false;
            try {{
              if (w.pbjs) {{
                if (typeof w.pbjs.getBidderRequests === "function") {{
                  const br = w.pbjs.getBidderRequests() || [];
                  if (br.length > 0) auctionStarted = true;
                }}
                if (!auctionStarted && Array.isArray(w.pbjs._bidsRequested)) {{
                  if (w.pbjs._bidsRequested.length > 0) auctionStarted = true;
                }}
                if (!auctionStarted && typeof w.pbjs.getEvents === "function") {{
                  const events = w.pbjs.getEvents() || [];
                  auctionStarted = events.some(e =>
                    e &&
                    (e.eventType === "auctionInit" ||
                     e.eventType === "bidRequested" ||
                     e.eventType === "auctionEnd")
                  );
                }}
              }}
            }} catch (e) {{
              // best-effort; ignore
            }}

            // ---- Detect whether a hero_player bidRequested has happened (video auction) ----
            const HERO = "{hero_adunit}".toLowerCase();
            let heroAuctionStarted = false;

            const displayStoreLen = Array.isArray(w.__pbjsBidEventsDisplay) ? w.__pbjsBidEventsDisplay.length : 0;
            const videoStoreLen = Array.isArray(w.__pbjsBidEventsVideo) ? w.__pbjsBidEventsVideo.length : 0;

            const hasHeroBidRequestedInPbjsBidEvents = () => {{
              try {{
                // Prefer the dedicated video store if present, fall back to legacy combined store.
                const store = Array.isArray(w.__pbjsBidEventsVideo)
                  ? w.__pbjsBidEventsVideo
                  : (Array.isArray(w.__pbjsBidEvents) ? w.__pbjsBidEvents : []);
                if (!store.length) return false;

                for (const ev of store) {{
                  if (!ev || ev.type !== "bidRequested" || !ev.args) continue;
                  const bids = Array.isArray(ev.args.bids) ? ev.args.bids : [];
                  for (const bid of bids) {{
                    if (!bid) continue;
                    const auc = bid.adUnitCode != null ? String(bid.adUnitCode).toLowerCase() : "";
                    if (auc === HERO) return true;
                  }}
                }}
              }} catch (e) {{}}
              return false;
            }};

            const hasHeroBidRequestedInPbjsEvents = () => {{
              try {{
                if (!w.pbjs || typeof w.pbjs.getEvents !== "function") return false;
                const events = w.pbjs.getEvents() || [];
                for (const ev of events) {{
                  if (!ev) continue;

                  // Prebid "getEvents" shape can vary a bit; try best-effort.
                  const t = (ev.eventType || ev.type || "").toString();
                  if (t !== "bidRequested") continue;

                  const args = ev.args || ev;
                  const bids = Array.isArray(args.bids) ? args.bids : [];
                  for (const bid of bids) {{
                    if (!bid) continue;
                    const auc = bid.adUnitCode != null ? String(bid.adUnitCode).toLowerCase() : "";
                    if (auc === HERO) return true;
                  }}
                }}
              }} catch (e) {{}}
              return false;
            }};

            const hasHeroBidRequestedInBidderRequests = () => {{
              try {{
                if (!w.pbjs || typeof w.pbjs.getBidderRequests !== "function") return false;
                const br = w.pbjs.getBidderRequests() || [];
                for (const req of br) {{
                  const bids = Array.isArray(req && req.bids) ? req.bids : [];
                  for (const bid of bids) {{
                    if (!bid) continue;
                    const auc = bid.adUnitCode != null ? String(bid.adUnitCode).toLowerCase() : "";
                    if (auc === HERO) return true;
                  }}
                }}
              }} catch (e) {{}}
              return false;
            }};

            // Try strongest sources first
            heroAuctionStarted =
              hasHeroBidRequestedInPbjsBidEvents() ||
              hasHeroBidRequestedInPbjsEvents() ||
              hasHeroBidRequestedInBidderRequests();

            return {{
              pbjsReady,
              gptReady,
              adUnitsReady,
              bidderCount,
              auctionStarted,
              pageType,
              isVideoPage,
              heroAuctionStarted,
              displayStoreLen,
              videoStoreLen
            }};
        }}
        """

        elapsed = 0.0
        last_status = None
        base_became_ready_at = None  # tracks when display/GPT first became ready

        while True:
            # Phase 1: wait up to self.timeout for base (display) readiness.
            # Phase 2: once base is ready on a video page, allow hero_player_timeout
            #          additional seconds — video player initialises later than display.
            if base_became_ready_at is None:
                if elapsed >= self.timeout:
                    break
            else:
                if (elapsed - base_became_ready_at) >= self.hero_player_timeout:
                    break

            try:
                status = await page.evaluate(js_condition)
                last_status = status or {}

                # Base readiness (always)
                base_ready = (
                    last_status.get("pbjsReady")
                    and last_status.get("gptReady")
                    and last_status.get("adUnitsReady")
                    and last_status.get("auctionStarted")
                )

                # On video pages, additionally require hero auction (unless geo skips it)
                if base_ready:
                    if base_became_ready_at is None:
                        base_became_ready_at = elapsed
                        # Scroll to trigger the video player as soon as display is ready.
                        # The hero player is lazy-loaded and won't fire its Prebid auction
                        # until it enters the viewport.
                        if last_status.get("isVideoPage") and self.require_hero_on_video:
                            try:
                                await page.evaluate("""
                                    () => {
                                        const target = (
                                            document.querySelector('.hero-video') ||
                                            document.querySelector('[class*="hero"]') ||
                                            document.querySelector('video') ||
                                            document.body
                                        );
                                        target.scrollIntoView({behavior: 'smooth', block: 'center'});
                                        window.scrollBy(0, 600);
                                    }
                                """)
                            except Exception:
                                pass
                    if last_status.get("isVideoPage") and self.require_hero_on_video:
                        if last_status.get("heroAuctionStarted"):
                            print(log_line("READINESS", self.device, self.url_tag,
                                message=(
                                    f"pbjs & GPT ready, auction started, hero_player auction started: "
                                    f"{last_status.get('bidderCount', 0)} bidders after {elapsed:.1f}s "
                                    f"(pageType={last_status.get('pageType')}, "
                                    f"displayEvents={last_status.get('displayStoreLen', 0)}, "
                                    f"videoEvents={last_status.get('videoStoreLen', 0)})"
                                )
                            ))
                            return True
                    else:
                        print(log_line("READINESS", self.device, self.url_tag,
                            message=(
                                f"pbjs & GPT ready, auction started: "
                                f"{last_status.get('bidderCount', 0)} bidders after {elapsed:.1f}s "
                                f"(pageType={last_status.get('pageType')}, "
                                f"displayEvents={last_status.get('displayStoreLen', 0)}, "
                                f"videoEvents={last_status.get('videoStoreLen', 0)})"
                            )
                        ))
                        return True
            except Exception:
                pass

            await asyncio.sleep(self.poll_interval)
            elapsed += self.poll_interval

        # Timeout diagnostics (keep it readable but useful)
        pt = None
        is_video = None
        hero_started = None
        display_len = None
        video_len = None
        if isinstance(last_status, dict):
            pt = last_status.get("pageType")
            is_video = last_status.get("isVideoPage")
            hero_started = last_status.get("heroAuctionStarted")
            display_len = last_status.get("displayStoreLen")
            video_len = last_status.get("videoStoreLen")

        print(log_line("READINESS", self.device, self.url_tag,
            message=f"Timeout after {elapsed:.1f}s "
                    f"(pageType={pt}, isVideoPage={is_video}, heroAuctionStarted={hero_started}, "
                    f"displayEvents={display_len}, videoEvents={video_len})"
        ))
        return False