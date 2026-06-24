"""
pbjs:display_get_floors

What this test checks
---------------------
Verifies that bid.getFloor() is callable on live bid objects from the display
auction, returns a positive value for every banner ad unit, and that the returned
value matches what is expected in the prebid_floor_prices Supabase table.

Test conditions
---------------
- window.pbjs must be present.
- At least one DISPLAY bidRequested event must have been captured.
- Supabase must be configured for the DB comparison step.

What counts as PASS / FAIL / ERROR
------------------------------------
- PASSED:  bid.getFloor() works on all units and all values match the DB.
- FAILED:  bid.getFloor is not a function on any bid (module not active).
- FAILED:  getFloor() throws or returns no floor for one or more units.
- FAILED:  getFloor() returns a value that doesn't match the DB for a unit.
- ERROR:   window.pbjs not found on page — Prebid did not load.
- ERROR:   Prebid loaded but no DISPLAY bid requests captured — auction did not fire.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import aiohttp

from core.base_test import BaseTest, TestResult, TestState
from core.supabase_helpers import get_supabase_credentials, is_supabase_configured
from core.url_context_helpers import publisher_from_url

_JS = (Path(__file__).parent.parent / "js" / "pbjs_display_get_floors.js").read_text()

_PUBLISHER_DOMAIN = {
    "independent": "independent.co.uk",
    "standard":    "standard.co.uk",
}
_KNOWN_GEOS = {"UK", "US", "CAN", "ROW"}
_FLOOR_TOLERANCE = 0.001


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

    async def _fetch_expected_floors(self, publisher_domain: str, geo: str):
        """Fetch floor rows for (publisher, geo) + ELSE catch-all from Supabase."""
        supabase_url, supabase_key = get_supabase_credentials(self.config)
        if not supabase_url or not supabase_key:
            return {}, None

        api_url = supabase_url.rstrip("/") + "/rest/v1/prebid_floor_prices"
        params = {
            "select": "geo,ad_unit,media_type,floor_usd",
            "publisher": f"eq.{publisher_domain}",
            "geo": f"in.({geo},ELSE)",
            "media_type": f"in.(banner,ELSE)",
        }
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Accept": "application/json",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        return {}, None
                    rows = await resp.json()
        except Exception:
            return {}, None

        else_floor: Optional[float] = None
        floors: Dict[str, float] = {}
        for row in rows or []:
            row_geo  = (row.get("geo") or "").upper()
            ad_unit  = (row.get("ad_unit") or "").strip()
            media_type = (row.get("media_type") or "").strip()
            try:
                floor = float(row["floor_usd"])
            except (KeyError, TypeError, ValueError):
                continue
            if row_geo == "ELSE" and ad_unit == "ELSE":
                else_floor = floor
            elif row_geo == geo and media_type == "banner":
                floors[ad_unit] = floor

        return floors, else_floor

    async def validate(self, result: TestResult) -> TestResult:
        diag: Dict[str, Any] = result.data or {}

        if not diag.get("hasPbjs"):
            result.state = TestState.ERROR
            result.errors.append("window.pbjs not found on page — Prebid did not load.")
            return result

        if not diag.get("has_display_store") or not diag.get("display_bidrequested_events"):
            result.state = TestState.ERROR
            result.errors.append(
                "Prebid loaded but no DISPLAY bid requests were observed — "
                "display auction did not fire (check pbjs_display_auction_activity for root cause)."
            )
            return result

        get_floors_available: bool = bool(diag.get("get_floors_available"))
        results_per_unit: Dict[str, Any] = diag.get("results_per_unit") or {}
        units_with_floor: List[str] = diag.get("units_with_floor") or []
        units_without_floor: List[str] = diag.get("units_without_floor") or []

        errors: List[str] = []

        # ── 1. Check getFloor() is callable and returns values ───────────────
        if not get_floors_available:
            result.state = TestState.FAILED
            result.errors.append(
                "bid.getFloor is not a function on any observed bid — "
                "priceFloors module is not active or not wired into the auction."
            )
            return result

        for unit in units_without_floor:
            info = results_per_unit.get(unit) or {}
            reason = info.get("error") or "no floor returned"
            errors.append(f"{unit}: getFloor() failed — {reason}")

        # ── 2. Compare returned values against Supabase ───────────────────────
        wrong_value: List[str] = []
        no_db_entry: List[str] = []

        if is_supabase_configured(self.config):
            locale = (diag.get("locale") or "").upper().strip()
            geo = locale if locale in _KNOWN_GEOS else "ROW"
            publisher_short = publisher_from_url(result.url or "")
            publisher_domain = _PUBLISHER_DOMAIN.get(publisher_short, publisher_short)

            floors_data, else_floor = await self._fetch_expected_floors(publisher_domain, geo)

            for unit in units_with_floor:
                info = results_per_unit.get(unit) or {}
                actual = info.get("floor")
                expected = floors_data.get(unit, else_floor)

                if expected is None:
                    no_db_entry.append(unit)
                elif actual is not None and abs(float(actual) - float(expected)) > _FLOOR_TOLERANCE:
                    wrong_value.append(
                        f"{unit}: getFloor()={actual:.4f}, expected={expected:.4f}"
                    )

            if wrong_value:
                errors.append(f"Floor value mismatch: {'; '.join(wrong_value)}")

            if no_db_entry and self.config.get("trace"):
                print(f"[{self.name}] Units with no DB entry: {', '.join(no_db_entry)}")
        else:
            result.warnings.append("Supabase not configured — DB value comparison skipped.")

        if errors:
            result.state = TestState.FAILED
            result.errors.extend(errors)
        else:
            result.state = TestState.PASSED

        result.metadata.update({
            "get_floors_available": get_floors_available,
            "units_checked": sorted(units_with_floor + units_without_floor),
            "units_with_floor": sorted(units_with_floor),
            "units_without_floor": sorted(units_without_floor),
            "units_wrong_value": wrong_value,
            "units_no_db_entry": sorted(no_db_entry),
        })

        if self.config.get("trace"):
            for unit, info in results_per_unit.items():
                print(
                    f"[{self.name}] {unit}: "
                    f"floor={info.get('floor')} {info.get('currency', '')} "
                    f"worked={info.get('worked')} error={info.get('error')}"
                )

        return result
