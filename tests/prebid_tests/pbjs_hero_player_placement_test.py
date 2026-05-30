"""
prebid: PbjsHeroPlayerPlacementTest (VIDEO)

What this test checks
---------------------
For the video ad unit "hero_player", inspects Prebid bidRequested events from the
VIDEO event store and validates each bid's placement fields:
  - Both `placement` and `plcmt` must be present.
  - Both must equal the expected value (1 by default).
  - Both must match each other (placement == plcmt).

Test conditions
---------------
- Page must be a video page (pageType == video); otherwise skipped.
- window.pbjs must be present (otherwise skipped).
- window.__pbjsBidEventsVideo (or fallback __pbjsBidEvents) must contain
  hero_player bidRequested events; otherwise skipped.

What counts as PASS / FAIL / SKIP
-----------------------------------
- PASSED: all bidders with hero_player bids have placement + plcmt present, valid, and equal.
- FAILED: at least one bidder's hero_player bid is missing placement or plcmt, has an
  invalid value, or placement != plcmt.
- SKIPPED: window.pbjs missing, event store missing/empty, or no hero_player bids found.
"""

from pathlib import Path
from typing import Any, Dict, List

from core.base_test import VideoOnlyTest, TestResult, TestState

_JS_TEMPLATE = (Path(__file__).parent.parent / "js" / "pbjs_hero_player_placement.js").read_text()

class PbjsHeroPlayerPlacementTest(VideoOnlyTest):

    name = "PbjsHeroPlayerPlacementTest"

    HERO_ADUNIT_CODE = "hero_player"
    EXPECTED_PLACEMENT = 1

    async def _video_setup(self, page, url: str) -> bool:
        try:
            await page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass

        has_pbjs = await page.evaluate("() => !!window.pbjs")
        return bool(has_pbjs)

    async def execute(self, page, url: str) -> TestResult:
        if self.config.get("trace"):
            print("🔥 PbjsHeroPlayerPlacementTest EXECUTING 🔥")

        result = TestResult(self.name)
        result.url = url

        expected_placement = int(
            self.config.get("hero_player_expected_placement", self.EXPECTED_PLACEMENT)
        )

        js = (
            _JS_TEMPLATE
            .replace("__EXPECTED_PLACEMENT__", str(expected_placement))
            .replace("__HERO_ADUNIT_CODE__", self.HERO_ADUNIT_CODE)
        )

        diag = await page.evaluate(js)
        result.data = diag or {}

        if self.config.get("trace"):
            d = result.data or {}
            print(
                f"[PbjsHeroPlayerPlacementTest] diag: source={d.get('source')}, hasPbjs={bool(d.get('hasPbjs'))}, "
                f"eventsLen={d.get('eventsLen', 0)}, bidRequestedEvents={d.get('bidRequestedEvents', 0)}, "
                f"heroBidsTotal={d.get('heroBidsTotal', 0)}, expectedPlacement={d.get('expectedPlacement')}"
            )
            per = (d.get("perBidder") or {})
            for bidder, info in per.items():
                print(
                    f"[PbjsHeroPlayerPlacementTest] bidder={bidder} bids={info.get('bids', 0)} "
                    f"missingPlacement={info.get('missingPlacement', 0)} invalidPlacement={info.get('invalidPlacement', 0)} "
                    f"missingPlcmt={info.get('missingPlcmt', 0)} invalidPlcmt={info.get('invalidPlcmt', 0)} "
                    f"mismatch={info.get('mismatch', 0)}"
                )
            sample = (d.get("debug") or {}).get("firstHeroBidSample")
            if sample:
                print("[PbjsHeroPlayerPlacementTest] firstHeroBidSample:", sample)

        return result

    async def validate(self, result: TestResult) -> TestResult:
        diag: Dict[str, Any] = result.data or {}

        if not diag.get("hasPbjs"):
            result.state = TestState.SKIPPED
            result.warnings.append("window.pbjs not present; cannot inspect hero_player bids.")
            return result

        events_len = int(diag.get("eventsLen", 0) or 0)
        if events_len == 0:
            result.state = TestState.SKIPPED
            src = diag.get("source") or "event store"
            result.warnings.append(f"{src} is empty; no Prebid events captured.")
            return result

        hero_bids_total = int(diag.get("heroBidsTotal", 0) or 0)
        if hero_bids_total == 0:
            result.state = TestState.SKIPPED
            result.warnings.append("No bids found for adUnitCode 'hero_player' in bidRequested events.")
            return result

        per_bidder: Dict[str, Dict[str, Any]] = diag.get("perBidder", {}) or {}

        any_fail = False
        lines: List[str] = []

        for bidder in sorted(per_bidder.keys()):
            info = per_bidder.get(bidder) or {}

            bids = int(info.get("bids", 0) or 0)

            miss_p = int(info.get("missingPlacement", 0) or 0)
            inv_p = int(info.get("invalidPlacement", 0) or 0)
            miss_c = int(info.get("missingPlcmt", 0) or 0)
            inv_c = int(info.get("invalidPlcmt", 0) or 0)
            mismatch = int(info.get("mismatch", 0) or 0)

            placement_vals = info.get("placement_values") or []
            placement_paths = info.get("placement_paths") or []
            plcmt_vals = info.get("plcmt_values") or []
            plcmt_paths = info.get("plcmt_paths") or []

            if miss_p == 0 and inv_p == 0 and miss_c == 0 and inv_c == 0 and mismatch == 0:
                lines.append(f"{bidder}: PASS ({bids} hero_player bids)")
                continue

            any_fail = True
            reasons = []
            if miss_p:
                reasons.append(f"missing placement={miss_p}")
            if inv_p:
                reasons.append(f"invalid placement={inv_p}")
            if miss_c:
                reasons.append(f"missing plcmt={miss_c}")
            if inv_c:
                reasons.append(f"invalid plcmt={inv_c}")
            if mismatch:
                reasons.append(f"placement/plcmt mismatch={mismatch}")

            p_vals = ", ".join(str(x) for x in placement_vals[:10])
            p_paths = ", ".join(str(x) for x in placement_paths[:10])
            c_vals = ", ".join(str(x) for x in plcmt_vals[:10])
            c_paths = ", ".join(str(x) for x in plcmt_paths[:10])

            lines.append(
                f"{bidder}: FAIL ({bids} bids; {', '.join(reasons)}; "
                f"placement_vals=[{p_vals}] placement_paths=[{p_paths}]; "
                f"plcmt_vals=[{c_vals}] plcmt_paths=[{c_paths}])"
            )

        if any_fail:
            result.state = TestState.FAILED
            result.errors.append("FAILED\n" + "\n".join(lines))
        else:
            result.state = TestState.PASSED

        result.metadata.update(
            {
                "hero_adunit": self.HERO_ADUNIT_CODE,
                "expected_placement": diag.get("expectedPlacement"),
                "hero_bids_total": hero_bids_total,
                "bidders_checked": sorted(per_bidder.keys()),
                "source": diag.get("source"),
                "bidder_detail": "\n".join(lines),
            }
        )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return