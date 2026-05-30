"""
prebid: PbjsDisplayBidderPresenceTest

What this test checks
---------------------
Validates display bidder presence by comparing bidders actually seen in DISPLAY
bidRequested events (window.__pbjsBidEventsDisplay) against bidders expected from
Supabase for the current publisher/environment context. hero_player bidders are excluded.

Publisher and environment are read from the runner's explicit config
(publisher/publication, environment/env) rather than derived from the URL, to avoid
mismatches on UAT where URL heuristics return "independent" instead of "independent_uat".

Test conditions
---------------
- window.pbjs must be present (otherwise skipped).
- Supabase must be configured (otherwise skipped).
- DISPLAY bidRequested events must have been captured.

What counts as PASS / FAIL / SKIP
-----------------------------------
- PASSED: seen display bidders exactly match the expected set (no missing, no unexpected).
- FAILED: Supabase returns 0 rows for the explicit context (configuration/mapping error).
- FAILED: expected bidders are present in DB but missing from the observed auction.
- FAILED: bidders observed in the auction that are not in the expected set.
- SKIPPED: window.pbjs missing or Supabase not configured.
"""

from pathlib import Path
from typing import Any, Dict, List, Set
import aiohttp

from core.base_test import BaseTest, TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "pbjs_display_bidder_presence.js").read_text()
from core.supabase_helpers import get_supabase_credentials, is_supabase_configured
from core.url_context_helpers import (
    map_pagetype_to_db,
    get_context_publisher,
    get_context_environment,
    has_explicit_ctx,
    bidder_lookup_env,
)

class PbjsDisplayBidderPresenceTest(BaseTest):

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

        diag = await page.evaluate(_JS)
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
        supabase_url, supabase_key = get_supabase_credentials(self.config)
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

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        if self.config.get("trace"):
                            body = await resp.text()
                            print("[PbjsDisplayBidderPresenceTest] Supabase HTTP error:", resp.status, body)
                        return []
                    data = await resp.json()
        except Exception as e:
            if self.config.get("trace"):
                print("[PbjsDisplayBidderPresenceTest] Supabase request failed:", e)
            return []

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
        environment = bidder_lookup_env(get_context_environment(self.config, result.url))

        from core.device_helpers import device_label, bidder_lookup_device
        device = bidder_lookup_device(device_label(self.config))
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
        if not is_supabase_configured(self.config):
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
