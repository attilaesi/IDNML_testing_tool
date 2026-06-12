"""
prebid: PbjsVideoPriceFloorsTest

What this test checks
---------------------
Validates that Prebid price floors are configured and active for VIDEO auctions.
Uses window.__pbjsBidEventsVideo (populated by BrowserManager) to confirm video
activity occurred, then checks the priceFloors module and rule configuration.

Test conditions
---------------
- Page must be a video page (pageType == video); otherwise skipped.
- window.__pbjsBidEventsVideo must contain bidRequested events.

What counts as PASS / FAIL / SKIP
-----------------------------------
- PASSED: priceFloors module installed (or config present), enabled, floor rules exist,
  and at least one video-applicable rule is configured.
- FAILED: priceFloors module not installed and no floors config present.
- FAILED: floors config present but disabled.
- FAILED: floors config enabled but no rules configured.
- FAILED: no video-applicable floor rules found.
- SKIPPED: no video Prebid activity observed (non-video page or no events captured).
"""
# tests/prebid_tests/pbjs_prebid_price_floors_video_test.py

from pathlib import Path
from typing import Any, Dict, List

from core.base_test import VideoOnlyTest, TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "pbjs_video_price_floors.js").read_text()

class PbjsVideoPriceFloorsTest(VideoOnlyTest):

    """
    Validates Prebid price floors configuration for VIDEO auctions.

    Uses the existing video event store populated by BrowserManager:
      - window.__pbjsBidEventsVideo

    Answers:
      - Did we observe any VIDEO Prebid activity?
      - Is the priceFloors module/config present & enabled?
      - Are there any floor rules configured?
      - Are there any floor rules that look VIDEO-applicable?

    Notes:
      - "video-applicable" is determined heuristically:
          * rule.mediaType == 'video' OR rule.mediaTypes includes 'video'
          * OR mediaType is missing (treated as applies-to-all)
      - Banner-only rules are ignored for video.
    """

    name = "PbjsVideoPriceFloorsTest"

    WAIT_AFTER_DOM_MS = 1500

    async def _video_setup(self, page, url: str) -> bool:
        try:
            await page.wait_for_load_state("domcontentloaded")
            try:
                await page.wait_for_timeout(self.WAIT_AFTER_DOM_MS)
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"[PbjsVideoPriceFloorsTest] setup error: {e}")
            return False

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        result.state = TestState.PASSED
        result.data = {}

        try:
            diag = await page.evaluate(_JS)

            result.data["prebid_floors_video"] = diag

        except Exception as e:
            result.state = TestState.ERROR
            result.errors.append(f"JS extraction failed: {e}")

        return result

    async def validate(self, result: TestResult) -> TestResult:
        if result.state == TestState.ERROR:
            return result

        floors = (result.data or {}).get("prebid_floors_video", {}) or {}

        errors: List[str] = []
        warnings: List[str] = []

        for err in floors.get("errors", []) or []:
            warnings.append(f"Extraction warning: {err}")

        has_store = bool(floors.get("has_video_store"))
        bidreq = int(floors.get("video_bidrequested_events") or 0)

        if not has_store or bidreq == 0:
            result.state = TestState.SKIPPED
            result.warnings.append(
                "No video Prebid activity observed (window.__pbjsBidEventsVideo missing or no bidRequested)."
            )
            result.metadata.update(
                {
                    "video_events_total": int(floors.get("video_events_total") or 0),
                    "video_bidrequested_events": bidreq,
                }
            )
            return result

        module_present = bool(floors.get("module_present"))
        has_cfg = bool(floors.get("has_floors_config"))
        enabled = bool(floors.get("enabled"))
        rules_count = int(floors.get("rules_count") or 0)
        video_rules = int(floors.get("video_applicable_rules_count") or 0)
        provider = floors.get("provider")

        if not module_present and not has_cfg:
            errors.append("Video floors: priceFloors module not installed and no floors config present")

        if not module_present and has_cfg:
            warnings.append("Video floors: floors config present but priceFloors not listed in pbjs.installedModules")

        if has_cfg and not enabled:
            errors.append("Video floors: floors config present but disabled (floors.enabled === false)")

        if has_cfg and enabled and rules_count == 0:
            errors.append("Video floors: no floor rules configured")
        elif has_cfg and enabled and video_rules == 0:
            errors.append("Video floors: no video-applicable floor rules found")

        if has_cfg and enabled and not provider:
            warnings.append("Video floors: provider not specified")

        if errors:
            result.state = TestState.FAILED
            result.errors.append("Video floors invalid")
            result.errors.extend(errors)
        else:
            result.state = TestState.PASSED

        if warnings:
            result.warnings.extend(warnings)

        result.metadata.update(
            {
                "video_events_total": int(floors.get("video_events_total") or 0),
                "video_bidrequested_events": int(floors.get("video_bidrequested_events") or 0),
                "floors_module_present": module_present,
                "floors_has_config": has_cfg,
                "floors_enabled": enabled,
                "floors_rules_count": rules_count,
                "floors_video_applicable_rules_count": video_rules,
                "floors_provider": provider,
            }
        )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return