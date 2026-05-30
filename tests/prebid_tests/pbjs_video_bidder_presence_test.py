"""
prebid: PbjsVideoBidderPresenceTest

What this test checks
---------------------
Validates video bidder presence on hero_player by comparing bidders actually seen in
VIDEO bidRequested events (window.__pbjsBidEventsVideo, filtered to hero_player bids)
against bidders expected from Supabase for the current publisher/environment context.

"Seen video bidders" are derived only from req.bids[] where adUnitCode === "hero_player"
or mediaTypes.video is present — bidderCode alone is not sufficient.

Test conditions
---------------
- Page must be a video page (pageType == video); otherwise skipped.
- window.pbjs must be present (otherwise skipped).
- Supabase must be configured (otherwise skipped).
- Publisher/env read from explicit runner config to avoid UAT URL-heuristic mismatches.

What counts as PASS / FAIL / SKIP
-----------------------------------
- PASSED: seen video bidders exactly match the expected set for hero_player.
- FAILED: Supabase returns 0 rows for the explicit context (configuration/mapping error).
- FAILED: expected video bidders missing from the observed hero_player auction.
- FAILED: video bidders observed that are not in the expected set.
- SKIPPED: non-video page, pbjs missing, or Supabase not configured.
"""

from pathlib import Path
from typing import Any, Dict, List, Set
import aiohttp

from core.base_test import VideoOnlyTest, TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "pbjs_video_bidder_presence.js").read_text()
from core.supabase_helpers import get_supabase_credentials, is_supabase_configured
from core.url_context_helpers import (
    map_pagetype_to_db,
    get_context_publisher,
    get_context_environment,
    has_explicit_ctx,
    bidder_lookup_env,
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

        diag = await page.evaluate(_JS)
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
        environment = bidder_lookup_env(get_context_environment(self.config, result.url))

        from core.device_helpers import device_label, bidder_lookup_device
        device = bidder_lookup_device(device_label(self.config))
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
