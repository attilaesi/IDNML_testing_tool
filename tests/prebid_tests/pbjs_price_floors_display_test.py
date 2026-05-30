"""
prebid: PbjsPriceFloorsDisplayTest

What this test checks
---------------------
Validates that Prebid price floors are configured and active for DISPLAY auctions.
Uses window.__pbjsBidEventsDisplay (populated by BrowserManager) to confirm display
activity occurred, then checks the priceFloors module and rule configuration.

Test conditions
---------------
- window.__pbjsBidEventsDisplay must be present and contain bidRequested events.
- If no display activity is observed the test is skipped (cannot validate floors).

What counts as PASS / FAIL / SKIP
-----------------------------------
- PASSED: priceFloors module installed (or config present), enabled, floor rules exist,
  and at least one display-applicable rule is configured.
- FAILED: priceFloors module not installed and no floors config present.
- FAILED: floors config present but disabled (floors.enabled === false).
- FAILED: floors config enabled but no floor rules configured.
- FAILED: no display-applicable floor rules found.
- SKIPPED: no display Prebid activity observed on this page.
"""
# tests/prebid_tests/pbjs_prebid_price_floors_display_test.py

from pathlib import Path
from typing import Any, Dict, List, Optional

from core.base_test import BaseTest, TestResult, TestState
from core.data_extractor import DataExtractor

_JS = (Path(__file__).parent.parent / "js" / "pbjs_price_floors_display.js").read_text()

class PbjsPriceFloorsDisplayTest(BaseTest):

    """
    Validates Prebid price floors configuration for DISPLAY auctions.

    Uses the existing display event store populated by BrowserManager:
      - window.__pbjsBidEventsDisplay

    Answers:
      - Did we observe any DISPLAY Prebid activity?
      - Is the priceFloors module/config present & enabled?
      - Are there any floor rules configured?
      - Are there any floor rules that look DISPLAY/BANNER-applicable?

    Notes:
      - "display-applicable" is determined heuristically:
          * rule.mediaType == 'banner' OR rule.mediaTypes includes 'banner'
          * OR mediaType is missing (treated as applies-to-all)
      - This is intentionally conservative: we want to avoid false FAILs when
        rules are generic (no mediaType field).
    """

    name = "PbjsPriceFloorsDisplayTest"

    # Wait a little to allow auctions to happen if your harness navigates fast
    WAIT_AFTER_DOM_MS = 1500

    async def setup(self, page, url: str) -> bool:
        try:
            await page.wait_for_load_state("domcontentloaded")
            try:
                await page.wait_for_timeout(self.WAIT_AFTER_DOM_MS)
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"[PbjsPriceFloorsDisplayTest] setup error: {e}")
            return False

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        result.state = TestState.PASSED
        result.data = {}

        try:
            # Optional: basic page metrics for context
            basic_data = await DataExtractor.extract_basic_data(page, url)
            result.data.update(basic_data)

            diag = await page.evaluate(_JS)

            result.data["prebid_floors_display"] = diag

        except Exception as e:
            result.state = TestState.ERROR
            result.errors.append(f"JS extraction failed: {e}")

        return result

    async def validate(self, result: TestResult) -> TestResult:
        if result.state == TestState.ERROR:
            return result

        floors = (result.data or {}).get("prebid_floors_display", {}) or {}

        errors: List[str] = []
        warnings: List[str] = []

        # JS-side errors
        for err in floors.get("errors", []) or []:
            warnings.append(f"Extraction warning: {err}")

        # Require display store & some display activity, otherwise SKIP (can’t validate display floors)
        has_store = bool(floors.get("has_display_store"))
        display_bidreq = int(floors.get("display_bidrequested_events") or 0)

        if not has_store or display_bidreq == 0:
            result.state = TestState.SKIPPED
            result.warnings.append(
                "No display Prebid activity observed (window.__pbjsBidEventsDisplay missing or no bidRequested)."
            )
            result.metadata.update(
                {
                    "display_events_total": int(floors.get("display_events_total") or 0),
                    "display_bidrequested_events": display_bidreq,
                }
            )
            return result

        module_present = bool(floors.get("module_present"))
        has_cfg = bool(floors.get("has_floors_config"))
        enabled = bool(floors.get("enabled"))
        rules_count = int(floors.get("rules_count") or 0)
        display_rules = int(floors.get("display_applicable_rules_count") or 0)
        provider = floors.get("provider")

        # 1) Module/config presence
        if not module_present and not has_cfg:
            errors.append("Display floors: priceFloors module not installed and no floors config present")

        if not module_present and has_cfg:
            warnings.append("Display floors: floors config present but priceFloors not listed in pbjs.installedModules")

        # 2) Enabled
        if has_cfg and not enabled:
            errors.append("Display floors: floors config present but disabled (floors.enabled === false)")

        # 3) Rules
        if has_cfg and enabled and rules_count == 0:
            errors.append("Display floors: no floor rules configured (floors.data.values / floors.values empty or missing)")
        elif has_cfg and enabled and display_rules == 0:
            errors.append("Display floors: no banner/display-applicable floor rules found")

        # 4) Provider optional
        if has_cfg and enabled and not provider:
            warnings.append("Display floors: provider not specified")

        if errors:
            result.state = TestState.FAILED
            # Keep roundup clean (short message), details go to metadata
            result.errors.append("Display floors invalid")
            result.errors.extend(errors)
        else:
            result.state = TestState.PASSED

        if warnings:
            result.warnings.extend(warnings)

        result.metadata.update(
            {
                "display_events_total": int(floors.get("display_events_total") or 0),
                "display_bidrequested_events": int(floors.get("display_bidrequested_events") or 0),
                "floors_module_present": module_present,
                "floors_has_config": has_cfg,
                "floors_enabled": enabled,
                "floors_rules_count": rules_count,
                "floors_display_applicable_rules_count": display_rules,
                "floors_provider": provider,
            }
        )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return