"""
pbjs:display_get_floors

What this test checks
---------------------
Verifies that the Prebid price floors module is active and that bid.getFloors()
is callable and returns a valid floor value for every banner ad unit observed in
the display auction.

bid.getFloors() is the function the floors module adds to each bid object so
bidder adapters can look up the applicable floor at request time. Its presence
and correct return value confirms the floors module is wired up end-to-end, not
just configured.

Test conditions
---------------
- window.pbjs must be present.
- At least one DISPLAY bidRequested event must have been captured.

What counts as PASS / FAIL / SKIP
-----------------------------------
- PASSED:  bid.getFloors is callable on all observed banner bids and returns a
           positive floor value for every ad unit.
- FAILED:  bid.getFloors is not a function on any bid (module not active).
- FAILED:  getFloors returns null, 0, or throws for one or more ad units.
- SKIPPED: window.pbjs missing or no display bidRequested events captured.
"""

from pathlib import Path
from typing import Any, Dict, List

from core.base_test import BaseTest, TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "pbjs_display_get_floors.js").read_text()


class PbjsDisplayGetFloorsTest(BaseTest):

    name = "PbjsDisplayGetFloorsTest"

    async def setup(self, page, url: str) -> bool:
        try:
            await page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass
        return True

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        result.data = await page.evaluate(_JS) or {}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        diag: Dict[str, Any] = result.data or {}

        if not diag.get("hasPbjs"):
            result.state = TestState.SKIPPED
            result.warnings.append("window.pbjs not present.")
            return result

        if not diag.get("has_display_store") or not diag.get("display_bidrequested_events"):
            result.state = TestState.SKIPPED
            result.warnings.append(
                "No DISPLAY bidRequested events observed — cannot test bid.getFloors()."
            )
            return result

        get_floors_available: bool = bool(diag.get("get_floors_available"))
        units_with_floor: List[str] = diag.get("units_with_floor") or []
        units_without_floor: List[str] = diag.get("units_without_floor") or []
        results_per_unit: Dict[str, Any] = diag.get("results_per_unit") or {}

        errors: List[str] = []

        if not get_floors_available:
            errors.append(
                "bid.getFloors is not a function on any observed bid — "
                "priceFloors module is not active or not wired into the auction."
            )
        else:
            for unit in units_without_floor:
                info = results_per_unit.get(unit) or {}
                reason = info.get("error") or "no floor returned"
                errors.append(f"{unit}: getFloors() failed — {reason}")

        if errors:
            result.state = TestState.FAILED
            result.errors.extend(errors)
        else:
            result.state = TestState.PASSED

        result.metadata.update({
            "module_present": diag.get("module_present"),
            "get_floors_available": get_floors_available,
            "units_checked": sorted(units_with_floor + units_without_floor),
            "units_with_floor": sorted(units_with_floor),
            "units_without_floor": sorted(units_without_floor),
        })

        if self.config.get("trace"):
            for unit, info in results_per_unit.items():
                print(
                    f"[{self.name}] {unit}: "
                    f"floor={info.get('floor')} {info.get('currency', '')} "
                    f"worked={info.get('worked')} error={info.get('error')}"
                )

        return result
