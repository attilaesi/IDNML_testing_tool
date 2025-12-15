"""
prebid: BidderPresenceTest

What this test checks
---------------------
For the current page:

1. Looks at *actual Prebid bid requests* (not just ad unit config).

   SINGLE SOURCE (new):
     - window.__pbjsBidEvents events of type "bidRequested"
       (populated by the global pbjs.onEvent() hook in BrowserManager)

2. Builds the set of bidder codes that actually emitted bid requests
   (e.g. "appnexus", "ix", "pubmatic", etc.).

3. Determines the expected bidders for this page by querying Supabase:

   - publisher  = config['active_site']  (e.g. "independent")
   - device     = "mobile" / "desktop"   (from config['mobile'])
   - geo        = Locale cookie value, normalised to lowercase ("uk", "us")
   - page_type  = **DB page_type**, derived from GPT pageType + liveblog:

       pageType=index                      -> index
       pageType=video & liveblog=y         -> blog_article
       pageType=video & liveblog!=y / null -> video_article
       pageType=image                      -> image_article
       pageType=gallery                    -> gallery_article
       else                                -> pageType (or "unknown")

   Supabase is queried against the `bidder_configs_enriched` table
   for matching rows, and we take the distinct bidder codes.

4. Compares:
     expected (from Supabase) vs seen (from bid requests)

   - missing    = bidders in expected list that did *not* emit a bid request
   - unexpected = bidders that *did* emit a bid request but are not in the
                  expected list for this (publisher, device, geo, page_type)

PASS / FAIL logic
-----------------
* SKIPPED:
    - window.pbjs is missing, or
    - Supabase not configured / no expected bidders returned for this context

* FAILED:
    - Any missing bidders, or
    - Any unexpected bidders

* PASSED:
    - All expected bidders that should be active for this (publisher,device,
      geo,page_type) emitted at least one bid request, and there are no
      unexpected bidders.
"""

from typing import Any, Dict, List, Set
import os

import aiohttp

from core.base_test import BaseTest, TestResult, TestState


def _map_pagetype_to_db(page_type: str, liveblog: str) -> str:
    """
    Map GPT pageType + liveblog targeting into DB page_type values.

    Rules:

      pageType: index                -> index
      pageType: video & liveblog=y   -> blog_article
      pageType: video & !liveblog=y  -> video_article
      pageType: image                -> image_article
      pageType: gallery              -> gallery_article
      else                           -> pageType (or "unknown")
    """
    pt = (page_type or "").strip().lower()
    lb = (liveblog or "").strip().lower()

    if pt == "index":
        return "index"

    if pt == "video":
        if lb in ("y", "yes", "true", "1"):
            return "blog_article"
        return "video_article"

    if pt == "image":
        return "image_article"

    if pt == "gallery":
        return "gallery_article"

    # Fallback: use the raw pageType, or "unknown" if empty
    return pt or "unknown"


class BidderPresenceTest(BaseTest):
    """Presence of bidders that actually emit bid requests, driven by Supabase."""

    name = "BidderPresenceTest"

    async def setup(self, page, url: str) -> bool:
        """Basic DOM readiness; framework already waited for pbjs/GPT."""
        try:
            await page.wait_for_load_state("domcontentloaded")
            return True
        except Exception as e:
            if self.config.get("trace"):
                print(f"[BidderPresenceTest] setup error for {url}: {e}")
            return False

    async def execute(self, page, url: str) -> TestResult:
        """
        Collect bidder presence diagnostics from the page.

        We return:
          {
            hasPbjs: bool,
            locale: "UK" | "US" | null,
            pageType: str | null,       // GPT pageType
            liveblog: str | null,       // GPT liveblog flag (e.g. "y")
            biddersFromRequests: [ "appnexus", "ix", ... ],
            biddersFromAdUnits: [ "appnexus", "ix", ... ],
            source: "__pbjsBidEvents" | null
          }
        """
        result = TestResult(self.name)
        result.url = url

        js = """
        () => {
          const out = {
            hasPbjs: !!window.pbjs,
            locale: null,
            pageType: null,
            liveblog: null,
            biddersFromRequests: [],
            biddersFromAdUnits: [],
            source: "__pbjsBidEvents",
          };

          const w = window;
          const pbjs = w.pbjs;
          if (!pbjs) {
            return out;
          }

          // --- Locale from cookie (used as geo) ---
          try {
            const m = document.cookie.match(/(?:^|;\\s*)Locale=([^;]+)/i);
            if (m && m[1]) {
              out.locale = decodeURIComponent(m[1]).toUpperCase();
            }
          } catch (e) {
            // ignore; locale stays null
          }

          // --- PageType & liveblog from GPT targeting ---
          try {
            if (w.googletag && w.googletag.pubads) {
              const pubads = w.googletag.pubads();
              if (pubads && typeof pubads.getTargeting === "function") {
                const pt = pubads.getTargeting("pageType");
                if (pt && pt[0]) {
                  out.pageType = String(pt[0]).toLowerCase();
                }
                const lb = pubads.getTargeting("liveblog");
                if (lb && lb[0]) {
                  out.liveblog = String(lb[0]).toLowerCase();
                }
              }
            }
          } catch (e) {
            // best-effort only
          }

          // --- Bidders from adUnits (config) ---
          try {
            const adUnits = Array.isArray(pbjs.adUnits) ? pbjs.adUnits : [];
            const adUnitSet = new Set();
            adUnits.forEach(u => {
              (u && Array.isArray(u.bids) ? u.bids : []).forEach(b => {
                if (b && typeof b.bidder === "string" && b.bidder.trim()) {
                  adUnitSet.add(b.bidder.trim());
                }
              });
            });
            out.biddersFromAdUnits = Array.from(adUnitSet);
          } catch (e) {
            // best-effort only
          }

          const reqSet = new Set();
          const addBidder = (code) => {
            if (typeof code === "string") {
              const trimmed = code.trim();
              if (trimmed) reqSet.add(trimmed);
            }
          };

          // ------------------------------------------------------------------
          // ONLY SOURCE: global pbjs.onEvent hook (__pbjsBidEvents)
          // ------------------------------------------------------------------
          try {
            const events = Array.isArray(w.__pbjsBidEvents)
              ? w.__pbjsBidEvents
              : [];

            const requests = events
              .filter(e => e && e.type === "bidRequested" && e.args)
              .map(e => e.args);

            requests.forEach(req => {
              if (!req) return;
              if (req.bidderCode) addBidder(req.bidderCode);
              else if (req.bidder) addBidder(req.bidder);
            });
          } catch (e) {
            // ignore; reqSet just stays as-is
          }

          out.biddersFromRequests = Array.from(reqSet);
          return out;
        }
        """

        diag = await page.evaluate(js)
        result.data = diag or {}

        if self.config.get("trace"):
            print(
                "[BidderPresenceTest] execute diag:",
                {
                    "url": url,
                    "hasPbjs": result.data.get("hasPbjs"),
                    "locale": result.data.get("locale"),
                    "pageType": result.data.get("pageType"),
                    "liveblog": result.data.get("liveblog"),
                    "source": result.data.get("source"),
                    "biddersFromRequests": result.data.get(
                        "biddersFromRequests", []
                    ),
                    "biddersFromAdUnits": result.data.get(
                        "biddersFromAdUnits", []
                    ),
                },
            )

        return result

    async def _fetch_expected_bidders_from_supabase(
        self,
        publisher: str,
        device: str,
        geo: str,
        page_type: str,
    ) -> List[str]:
        """
        Query Supabase for expected bidders for this (publisher, device, geo, page_type).

        Env resolution priority:
          1. self.config['supabase_url'] / self.config['supabase_anon_key']
          2. NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY
          3. SUPABASE_URL / SUPABASE_ANON_KEY

        Table and column names are configurable via:
          - config['supabase_bidders_table'] (default: 'bidder_configs_enriched')
        """
        supabase_url = (
            self.config.get("supabase_url")
            or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
            or os.getenv("SUPABASE_URL")
        )
        supabase_key = (
            self.config.get("supabase_anon_key")
            or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
            or os.getenv("SUPABASE_ANON_KEY")
        )
        table = self.config.get(
            "supabase_bidders_table",
            "bidder_configs_enriched",
        )

        if not supabase_url or not supabase_key:
            if self.config.get("trace"):
                print(
                    "[BidderPresenceTest] Supabase not configured "
                    "(supabase_url / supabase_anon_key / NEXT_PUBLIC_* missing)"
                )
            return []

        api_url = supabase_url.rstrip("/") + f"/rest/v1/{table}"

        params = {
            "select": "bidder",
            "publisher": f"eq.{publisher}",
            "device": f"eq.{device}",
            "geo": f"eq.{geo}",
            "page_type": f"eq.{page_type}",
        }

        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Accept": "application/json",
        }

        if self.config.get("trace"):
            print(
                "[BidderPresenceTest] Supabase request:",
                {
                    "supabase_url": supabase_url,
                    "table": table,
                    "api_url": api_url,
                    "params": params,
                },
            )

        bidders: Set[str] = set()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        if self.config.get("trace"):
                            body = await resp.text()
                            print(
                                "[BidderPresenceTest] Supabase HTTP error:",
                                resp.status,
                                body,
                            )
                        return []

                    data = await resp.json()
        except Exception as e:
            if self.config.get("trace"):
                print("[BidderPresenceTest] Supabase request failed:", e)
            return []

        if self.config.get("trace"):
            print("[BidderPresenceTest] Supabase raw response:", data)

        for row in data:
            code = (row or {}).get("bidder")
            if isinstance(code, str) and code.strip():
                bidders.add(code.strip())

        if self.config.get("trace"):
            print(
                "[BidderPresenceTest] Supabase expected bidders:",
                {
                    "publisher": publisher,
                    "device": device,
                    "geo": geo,
                    "page_type": page_type,
                    "bidders": sorted(bidders),
                },
            )

        return sorted(bidders)

    async def validate(self, result: TestResult) -> TestResult:
        """
        Compare bidders that actually emitted bid requests vs the expected
        list for this (publisher, device, geo, page_type) context.
        """
        diag: Dict[str, Any] = result.data or {}
        has_pbjs: bool = bool(diag.get("hasPbjs"))

        if not has_pbjs:
            result.state = TestState.SKIPPED
            result.warnings.append(
                "window.pbjs not present; cannot run BidderPresenceTest."
            )
            return result

        # Raw values from page
        locale: str = (diag.get("locale") or "UK").strip().upper()
        gpt_page_type: str = diag.get("pageType") or "unknown"
        liveblog: str = diag.get("liveblog") or ""

        # Map to DB page_type
        db_page_type = _map_pagetype_to_db(gpt_page_type, liveblog)

        seen_bidders: Set[str] = set(diag.get("biddersFromRequests") or [])

        publisher = str(self.config.get("active_site", "independent")).lower()
        device = "mobile" if self.config.get("mobile", True) else "desktop"

        # Supabase stores geo lowercase ("uk", "us")
        geo = locale.lower()

        if self.config.get("trace"):
            print(
                "[BidderPresenceTest] validate context:",
                {
                    "publisher": publisher,
                    "device": device,
                    "geo": geo,
                    "gpt_page_type": gpt_page_type,
                    "liveblog": liveblog,
                    "db_page_type": db_page_type,
                    "seen_bidders": sorted(seen_bidders),
                },
            )

        expected_list = await self._fetch_expected_bidders_from_supabase(
            publisher=publisher,
            device=device,
            geo=geo,
            page_type=db_page_type,
        )

        if not expected_list:
            result.state = TestState.SKIPPED
            msg = (
                f"[BidderPresenceTest] SKIPPED — Supabase returned 0 rows.\n"
                f"Context:\n"
                f"  publisher={publisher}\n"
                f"  device={device}\n"
                f"  geo={geo}\n"
                f"  gpt_page_type={gpt_page_type}\n"
                f"  liveblog={liveblog}\n"
                f"  db_page_type={db_page_type}\n"
            )
            result.warnings.append(msg)

            if self.config.get("trace"):
                print(msg)

            # Attach metadata for debugging
            result.metadata = {
                "publisher": publisher,
                "device": device,
                "geo": geo,
                "gpt_page_type": gpt_page_type,
                "liveblog": liveblog,
                "db_page_type": db_page_type,
                "expected_bidders": [],
                "seen_bidders": sorted(seen_bidders),
                "missing_bidders": [],
                "unexpected_bidders": [],
                "source": diag.get("source"),
            }
            return result

        expected: Set[str] = set(expected_list)

        missing = sorted(expected - seen_bidders)
        unexpected = sorted(seen_bidders - expected)

        if missing or unexpected:
            result.state = TestState.FAILED

            if missing:
                result.errors.append(
                    f"Missing bidders for context "
                    f"(publisher={publisher}, device={device}, geo={geo}, "
                    f"db_page_type={db_page_type}): "
                    + ", ".join(missing)
                )
            if unexpected:
                result.errors.append(
                    f"Unexpected bidders present for context "
                    f"(publisher={publisher}, device={device}, geo={geo}, "
                    f"db_page_type={db_page_type}): "
                    + ", ".join(unexpected)
                )
        else:
            result.state = TestState.PASSED

        if result.metadata is None or not isinstance(result.metadata, dict):
            result.metadata = {}

        result.metadata.update(
            {
                "publisher": publisher,
                "device": device,
                "geo": geo,
                "gpt_page_type": gpt_page_type,
                "liveblog": liveblog,
                "db_page_type": db_page_type,
                "expected_bidders": expected_list,
                "seen_bidders": sorted(seen_bidders),
                "missing_bidders": missing,
                "unexpected_bidders": unexpected,
                "source": diag.get("source"),
            }
        )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        """No-op for now; hook reserved for future debug screenshots if needed."""
        return