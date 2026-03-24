"""
prebid: PbjsDisplayBidderPresenceTest

Checks display bidder presence by comparing:
  - bidders actually seen in DISPLAY bidRequested events (global store)
  - bidders expected from Supabase for the current context, excluding hero_player

Key fix (UAT publisher mismatch)
-------------------------------
This test MUST prefer the runner's explicit context (publisher/publication, env/environment)
over URL-derived heuristics.

Example:
  DB publisher: independent_uat
  URL host: uat-web.independent.co.uk  -> URL heuristic would return "independent" (WRONG)

So we read:
  self.config["publisher"] or self.config["publication"]
  self.config["environment"] or self.config["env"]

PASS / FAIL / SKIP
------------------
SKIPPED:
  - window.pbjs missing
  - Supabase not configured

FAILED:
  - Supabase returns 0 rows for context *when explicit ctx is provided* (likely mismatch or missing DB)
  - missing expected bidders (expected - seen)
  - unexpected bidders (seen - expected)

PASSED:
  - missing == [] and unexpected == []
"""

from typing import Any, Dict, List, Set
import os
import aiohttp

from core.base_test import BaseTest, TestResult, TestState
from core.url_context_helpers import (
    map_pagetype_to_db,
    get_context_publisher,
    get_context_environment,
    has_explicit_ctx,
)


class PbjsDisplayBidderPresenceTest(BaseTest):
    NORMALIZED_NAME = "pbjs_display_bidder_presence_test"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = self.NORMALIZED_NAME

    name = "PbjsDisplayBidderPresenceTest"

    async def setup(self, page, url: str) -> bool:
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
          const out = {
            hasPbjs: !!window.pbjs,
            locale: null,
            pageType: null,
            liveblog: null,
            source: "__pbjsBidEventsDisplay",
            biddersFromRequests: [],
            eventsLen: 0,
            bidRequestedEvents: 0
          };

          const w = window;
          if (!w.pbjs) return out;

          // Locale cookie
          try {
            const m = document.cookie.match(/(?:^|;\\s*)Locale=([^;]+)/i);
            if (m && m[1]) out.locale = decodeURIComponent(m[1]).toUpperCase();
          } catch (e) {}

          // GPT targeting
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

          const events = Array.isArray(w.__pbjsBidEventsDisplay) ? w.__pbjsBidEventsDisplay : [];
          out.eventsLen = events.length;

          const reqSet = new Set();
          const addBidder = (code) => {
            if (typeof code === "string") {
              const t = code.trim();
              if (t) reqSet.add(t);
            }
          };

          try {
            const bidReq = events.filter(e => e && e.type === "bidRequested" && e.args);
            out.bidRequestedEvents = bidReq.length;

            bidReq.forEach(ev => {
              const req = ev.args || {};
              if (req.bidderCode) addBidder(req.bidderCode);
              else if (req.bidder) addBidder(req.bidder);
            });
          } catch (e) {}

          out.biddersFromRequests = Array.from(reqSet);
          return out;
        }
        """

        diag = await page.evaluate(js)
        result.data = diag or {}

        if self.config.get("trace"):
            print(
                "[PbjsDisplayBidderPresenceTest] execute diag:",
                {
                    "url": url,
                    "hasPbjs": result.data.get("hasPbjs"),
                    "locale": result.data.get("locale"),
                    "pageType": result.data.get("pageType"),
                    "liveblog": result.data.get("liveblog"),
                    "eventsLen": result.data.get("eventsLen"),
                    "bidRequestedEvents": result.data.get("bidRequestedEvents"),
                    "biddersFromRequests": result.data.get("biddersFromRequests", []),
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
        table = self.config.get("supabase_bidders_table", "bidder_configs_enriched")

        if not supabase_url or not supabase_key:
            return []

        api_url = supabase_url.rstrip("/") + f"/rest/v1/{table}"

        params = {
            "select": "bidder",
            "publisher": f"eq.{publisher}",
            "environment": f"eq.{environment}",
            "geo": f"eq.{geo}",
            "device": f"eq.{device}",
            "page_type": f"eq.{page_type}",
            "slot": "neq.hero_player",
            "is_expected": "eq.true",
        }

        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Accept": "application/json",
        }

        if self.config.get("trace"):
            print("[PbjsDisplayBidderPresenceTest] Supabase request:", {"api_url": api_url, "params": params})

        bidders: Set[str] = set()

        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=headers, params=params) as resp:
                if resp.status != 200:
                    if self.config.get("trace"):
                        body = await resp.text()
                        print("[PbjsDisplayBidderPresenceTest] Supabase HTTP error:", resp.status, body)
                    return []
                data = await resp.json()

        for row in data or []:
            code = (row or {}).get("bidder")
            if isinstance(code, str) and code.strip():
                bidders.add(code.strip())

        return sorted(bidders)

    async def validate(self, result: TestResult) -> TestResult:
        diag: Dict[str, Any] = result.data or {}

        if not diag.get("hasPbjs"):
            result.state = TestState.SKIPPED
            result.warnings.append("window.pbjs not present; cannot run PbjsDisplayBidderPresenceTest.")
            return result

        locale = (diag.get("locale") or "UK").strip().upper()
        gpt_page_type = diag.get("pageType") or "unknown"
        liveblog = diag.get("liveblog") or ""
        db_page_type = map_pagetype_to_db(gpt_page_type, liveblog)

        # ✅ FIX: prefer explicit ctx from runner/config; fallback to URL heuristic only if missing
        publisher = get_context_publisher(self.config, result.url)
        environment = get_context_environment(self.config, result.url)

        device = "mobile" if self.config.get("mobile", True) else "desktop"
        geo = locale.lower()

        seen: Set[str] = set(diag.get("biddersFromRequests") or [])

        expected_list = await self._fetch_expected_bidders(
            publisher=publisher,
            environment=environment,
            device=device,
            geo=geo,
            page_type=db_page_type,
        )

        # Supabase not configured at all -> SKIP
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
        if not supabase_url or not supabase_key:
            result.state = TestState.SKIPPED
            result.warnings.append("Supabase not configured; cannot assert expected DISPLAY bidders.")
            return result

        # ✅ If ctx explicitly provided (publisher/env), empty expected should be a FAIL (likely mismatch / missing rows)
        if not expected_list:
            result.metadata.update(
                {
                    "publisher": publisher,
                    "environment": environment,
                    "geo": geo,
                    "device": device,
                    "db_page_type": db_page_type,
                    "expected_bidders": [],
                    "seen_bidders": sorted(seen),
                    "missing_bidders": [],
                    "unexpected_bidders": [],
                    "source": diag.get("source"),
                }
            )

            if has_explicit_ctx(self.config):
                result.state = TestState.FAILED
                result.errors.append(
                    "Supabase returned 0 expected DISPLAY bidders for context: "
                    f"publisher={publisher}, env={environment}, geo={geo}, device={device}, page_type={db_page_type}. "
                    "This usually indicates publisher/env/page_type mapping mismatch or missing DB rows."
                )
            else:
                result.state = TestState.SKIPPED
                result.warnings.append(
                    "Supabase returned 0 expected DISPLAY bidders for context: "
                    f"publisher={publisher}, env={environment}, geo={geo}, device={device}, page_type={db_page_type}"
                )
            return result

        expected: Set[str] = set(expected_list)

        missing = sorted(expected - seen)
        unexpected = sorted(seen - expected)

        if missing or unexpected:
            result.state = TestState.FAILED
            if missing:
                result.errors.append("Missing DISPLAY bidders: " + ", ".join(missing))
            if unexpected:
                result.errors.append("Unexpected DISPLAY bidders: " + ", ".join(unexpected))
        else:
            result.state = TestState.PASSED

        result.metadata.update(
            {
                "publisher": publisher,
                "environment": environment,
                "geo": geo,
                "device": device,
                "db_page_type": db_page_type,
                "expected_bidders": expected_list,
                "seen_bidders": sorted(seen),
                "missing_bidders": missing,
                "unexpected_bidders": unexpected,
                "source": diag.get("source"),
            }
        )

        return result
