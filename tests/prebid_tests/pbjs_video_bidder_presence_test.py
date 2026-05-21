"""
prebid: PbjsVideoBidderPresenceTest

Runs ONLY on video pages.

Checks video bidder presence by comparing:
  - bidders actually seen bidding on hero_player in VIDEO bidRequested events
  - bidders expected from Supabase for the current context, restricted to slot=hero_player

Key fixes
---------
1) Publisher/env must prefer explicit runner context (publisher/publication, env/environment)
   because UAT uses distinct publisher keys (e.g. independent_uat) and URL heuristics return
   "independent" which causes 0-row Supabase results + skips.

2) Supabase "0 rows" behavior:
   - If explicit ctx is provided -> FAIL (this is a configuration/mapping error we want to catch)
   - Else -> SKIP (we can't assert)

3) Keep the core correctness fix:
   - derive "seen video bidders" ONLY from req.bids[] that match hero_player (or mediaTypes.video)
   - do NOT treat req.bidderCode alone as sufficient unless at least one bid matches hero criteria

PASS / FAIL / SKIP
------------------
SKIPPED:
  - not a video page (pageType != video)
  - pbjs missing
  - Supabase not configured

FAILED:
  - Supabase returns 0 rows for context *when explicit ctx is provided*
  - missing expected video bidders
  - unexpected video bidders

PASSED:
  - sets match
"""

from typing import Any, Dict, List, Set
import aiohttp

from core.base_test import VideoOnlyTest, TestResult, TestState
from core.supabase_helpers import get_supabase_credentials, is_supabase_configured
from core.url_context_helpers import (
    map_pagetype_to_db,
    get_context_publisher,
    get_context_environment,
    has_explicit_ctx,
)

class PbjsVideoBidderPresenceTest(VideoOnlyTest):

    name = "PbjsVideoBidderPresenceTest"

    async def _video_setup(self, page, url: str) -> bool:
        try:
            await page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass
        return True

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        js = """
        () => {
          const HERO = "hero_player";

          const out = {
            hasPbjs: !!window.pbjs,
            locale: null,
            pageType: null,
            liveblog: null,

            source: "__pbjsBidEventsVideo",

            // raw store counts
            eventsLen: 0,
            bidRequestedEvents: 0,

            // hero_player-focused counts
            heroBidRequestedEvents: 0,     // number of bidRequested events that include >=1 hero_player bid
            heroBidsTotal: 0,              // total number of bids in req.bids[] that match hero_player (or mediaTypes.video)
            biddersFromHeroRequests: [],   // DISTINCT bidder codes that actually bid on hero_player

            // diagnostics (optional)
            heroBidSamples: [],            // up to N sample bid objects for debugging
          };

          const w = window;
          if (!w.pbjs) return out;

          // Locale cookie
          try {
            const m = document.cookie.match(/(?:^|;\\s*)Locale=([^;]+)/i);
            if (m && m[1]) out.locale = decodeURIComponent(m[1]).toUpperCase();
          } catch (e) {}

          // GPT targeting (pageType + liveblog)
          try {
            if (w.googletag && w.googletag.pubads) {
              const pubads = w.googletag.pubads();
              if (pubads && typeof pubads.getTargeting === "function") {
                const pt = pubads.getTargeting("pageType");
                if (pt && pt[0]) out.pageType = String(pt[0]).toLowerCase();
                const lb = pubads.getTargeting("liveblog");
                if (lb && lb[0]) out.liveblog = String(lb[0]).toLowerCase();
              }
            }
          } catch (e) {}

          const events = Array.isArray(w.__pbjsBidEventsVideo) ? w.__pbjsBidEventsVideo : [];
          out.eventsLen = events.length;

          const heroBidderSet = new Set();
          const heroSamples = [];
          const MAX_SAMPLES = 3;

          const norm = (v) => (typeof v === "string" ? v.trim() : "");

          // Treat a bid as hero-video if:
          //  1) adUnitCode === "hero_player"
          //  OR
          //  2) mediaTypes.video exists (best-effort fallback)
          const isHeroVideoBid = (bid) => {
            if (!bid || typeof bid !== "object") return false;

            const auc = norm(bid.adUnitCode);
            if (auc === HERO) return true;

            try {
              const mt = bid.mediaTypes || bid.mediaType || null;
              if (mt && typeof mt === "object") {
                if (mt.video && typeof mt.video === "object") return true;
              }
            } catch (e) {}

            return false;
          };

          try {
            const bidReqEvents = events.filter(e => e && e.type === "bidRequested" && e.args);
            out.bidRequestedEvents = bidReqEvents.length;

            bidReqEvents.forEach(ev => {
              const req = ev.args || {};
              const bidder = norm(req.bidderCode || req.bidder);

              const bids = Array.isArray(req.bids) ? req.bids : [];
              let matchedThisReq = false;

              for (const b of bids) {
                if (isHeroVideoBid(b)) {
                  matchedThisReq = true;
                  out.heroBidsTotal += 1;

                  if (bidder) heroBidderSet.add(bidder);

                  if (heroSamples.length < MAX_SAMPLES) {
                    heroSamples.push({
                      bidder: bidder || null,
                      adUnitCode: b && b.adUnitCode ? String(b.adUnitCode) : null,
                      hasMediaTypesVideo: !!(b && b.mediaTypes && b.mediaTypes.video),
                      mediaTypesKeys: b && b.mediaTypes ? Object.keys(b.mediaTypes) : [],
                    });
                  }
                }
              }

              if (matchedThisReq) {
                out.heroBidRequestedEvents += 1;
              }
            });
          } catch (e) {}

          out.biddersFromHeroRequests = Array.from(heroBidderSet);
          out.heroBidSamples = heroSamples;

          return out;
        }
        """

        diag = await page.evaluate(js)
        result.data = diag or {}

        if self.config.get("trace"):
            print(
                "[PbjsVideoBidderPresenceTest] execute diag:",
                {
                    "url": url,
                    "hasPbjs": result.data.get("hasPbjs"),
                    "locale": result.data.get("locale"),
                    "pageType": result.data.get("pageType"),
                    "liveblog": result.data.get("liveblog"),
                    "eventsLen": result.data.get("eventsLen"),
                    "bidRequestedEvents": result.data.get("bidRequestedEvents"),
                    "heroBidRequestedEvents": result.data.get("heroBidRequestedEvents"),
                    "heroBidsTotal": result.data.get("heroBidsTotal"),
                    "biddersFromHeroRequests": result.data.get("biddersFromHeroRequests", []),
                    "heroBidSamples": result.data.get("heroBidSamples", []),
                },
            )

        return result

    async def _fetch_expected_bidders(
        self,
        publisher: str,
        environment: str,
        device: str,
        geo: str,
        page_type: str,
    ) -> List[str]:
        supabase_url, supabase_key = get_supabase_credentials(self.config)
        table = self.config.get("supabase_bidders_table", "bidder_configs_enriched")

        if not supabase_url or not supabase_key:
            if self.config.get("trace"):
                print("[PbjsVideoBidderPresenceTest] Supabase not configured (url/key missing)")
            return []

        api_url = supabase_url.rstrip("/") + f"/rest/v1/{table}"

        params = {
            "select": "bidder",
            "publisher": f"eq.{publisher}",
            "environment": f"eq.{environment}",
            "geo": f"eq.{geo}",
            "device": f"eq.{device}",
            "page_type": f"eq.{page_type}",
            "slot": "eq.hero_player",
            "is_expected": "eq.true",
        }

        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Accept": "application/json",
        }

        if self.config.get("trace"):
            print("[PbjsVideoBidderPresenceTest] Supabase request:", {"api_url": api_url, "params": params})

        bidders: Set[str] = set()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        if self.config.get("trace"):
                            body = await resp.text()
                            print("[PbjsVideoBidderPresenceTest] Supabase HTTP error:", resp.status, body)
                        return []
                    data = await resp.json()
        except Exception as e:
            if self.config.get("trace"):
                print("[PbjsVideoBidderPresenceTest] Supabase request failed:", e)
            return []

        for row in data or []:
            code = (row or {}).get("bidder")
            if isinstance(code, str) and code.strip():
                bidders.add(code.strip())

        return sorted(bidders)

    async def validate(self, result: TestResult) -> TestResult:
        diag: Dict[str, Any] = result.data or {}

        if result.metadata is None or not isinstance(result.metadata, dict):
            result.metadata = {}

        if not diag.get("hasPbjs"):
            result.state = TestState.SKIPPED
            result.warnings.append("window.pbjs not present; cannot run PbjsVideoBidderPresenceTest.")
            return result


        locale = (diag.get("locale") or "UK").strip().upper()
        gpt_page_type = diag.get("pageType") or "unknown"
        liveblog = diag.get("liveblog") or ""
        db_page_type = map_pagetype_to_db(gpt_page_type, liveblog)

        # ✅ FIX: prefer explicit ctx from runner/config; fallback to URL heuristic only if missing
        publisher = get_context_publisher(self.config, result.url)
        environment = get_context_environment(self.config, result.url)

        from core.device_helpers import device_label
        device = device_label(self.config)
        geo = locale.lower()

        # ✅ only bidders that actually bid on hero_player
        seen: Set[str] = set(diag.get("biddersFromHeroRequests") or [])

        # attach context + capture counts for easy debugging
        result.metadata.update(
            {
                "publisher": publisher,
                "environment": environment,
                "geo": geo,
                "device": device,
                "gpt_page_type": gpt_page_type,
                "liveblog": liveblog,
                "db_page_type": db_page_type,
                "slot": "hero_player",
                "source": diag.get("source"),
                "eventsLen": diag.get("eventsLen"),
                "bidRequestedEvents": diag.get("bidRequestedEvents"),
                "heroBidRequestedEvents": diag.get("heroBidRequestedEvents"),
                "heroBidsTotal": diag.get("heroBidsTotal"),
                "heroBidSamples": diag.get("heroBidSamples", []),
            }
        )

        # Supabase not configured at all -> SKIP
        if not is_supabase_configured(self.config):
            result.state = TestState.SKIPPED
            result.warnings.append("Supabase not configured; cannot assert expected VIDEO bidders.")
            return result

        expected_list = await self._fetch_expected_bidders(
            publisher=publisher,
            environment=environment,
            device=device,
            geo=geo,
            page_type=db_page_type,
        )

        # ✅ If ctx explicitly provided (publisher/env), empty expected should be a FAIL (likely mismatch / missing rows)
        if not expected_list:
            result.metadata.update(
                {
                    "expected_bidders": [],
                    "seen_bidders": sorted(seen),
                    "missing_bidders": [],
                    "unexpected_bidders": [],
                }
            )

            if has_explicit_ctx(self.config):
                result.state = TestState.FAILED
                result.errors.append(
                    "Supabase returned 0 expected VIDEO bidders for context: "
                    f"publisher={publisher}, env={environment}, geo={geo}, device={device}, "
                    f"page_type={db_page_type}, slot=hero_player. "
                    "This usually indicates publisher/env/page_type mapping mismatch or missing DB rows."
                )
            else:
                result.state = TestState.SKIPPED
                result.warnings.append(
                    "Supabase returned 0 expected VIDEO bidders for context: "
                    f"publisher={publisher}, env={environment}, geo={geo}, device={device}, "
                    f"page_type={db_page_type}, slot=hero_player"
                )
            return result

        expected: Set[str] = set(expected_list)

        missing = sorted(expected - seen)
        unexpected = sorted(seen - expected)

        if missing or unexpected:
            result.state = TestState.FAILED
            if missing:
                result.errors.append("Missing VIDEO bidders (hero_player): " + ", ".join(missing))
            if unexpected:
                result.errors.append("Unexpected VIDEO bidders (hero_player): " + ", ".join(unexpected))
        else:
            result.state = TestState.PASSED

        result.metadata.update(
            {
                "expected_bidders": expected_list,
                "seen_bidders": sorted(seen),
                "missing_bidders": missing,
                "unexpected_bidders": unexpected,
            }
        )

        return result
