"""
pbjs:display_floors_prices

What this test checks
---------------------
For every banner ad unit active in the Prebid auction, verifies that:
  1. A price floor is configured in the Prebid floors module.
  2. The configured floor matches the expected value in the prebid_floor_prices
     Supabase table for the current publisher and geo.

Test conditions
---------------
- window.pbjs must be present.
- Supabase must be configured (otherwise skipped).
- At least one DISPLAY bidRequested event must have been captured.

What counts as PASS / FAIL / SKIP
-----------------------------------
- PASSED:  every banner ad unit has a floor configured, and all values match the DB.
- FAILED:  one or more units have no floor configured in Prebid.
- FAILED:  one or more units have a floor that differs from the DB value.
- SKIPPED: window.pbjs missing, Supabase not configured, or no display activity observed.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import aiohttp

from core.base_test import BaseTest, TestResult, TestState
from core.supabase_helpers import get_supabase_credentials, is_supabase_configured
from core.url_context_helpers import publisher_from_url

_JS = (Path(__file__).parent.parent / "js" / "pbjs_display_price_floors.js").read_text()

# Maps publisher_from_url() short name → domain used in prebid_floor_prices table
_PUBLISHER_DOMAIN = {
    "independent": "independent.co.uk",
    "standard":    "standard.co.uk",
}

# Geos recognised in the floor table; anything else falls back to ROW
_KNOWN_GEOS = {"UK", "US", "CAN", "ROW"}

# Floor values within this tolerance are considered matching
_FLOOR_TOLERANCE = 0.001


class PbjsDisplayFloorsPricesTest(BaseTest):

    name = "PbjsDisplayFloorsPricesTest"

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

    # ── Supabase floor lookup ─────────────────────────────────────────────────

    async def _fetch_expected_floors(
        self, publisher_domain: str, geo: str
    ):
        """
        Fetch all floor rows for (publisher, geo) + the ELSE catch-all.
        Returns {ad_unit: floor_usd} for media_type='banner', with ELSE fallback.
        """
        supabase_url, supabase_key = get_supabase_credentials(self.config)
        if not supabase_url or not supabase_key:
            return {}

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
                        return {}
                    rows = await resp.json()
        except Exception:
            return {}

        # Build lookup: prefer exact geo+unit over ELSE catch-all
        else_floor: Optional[float] = None
        floors: Dict[str, float] = {}

        for row in rows or []:
            row_geo = (row.get("geo") or "").upper()
            ad_unit = (row.get("ad_unit") or "").strip()
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

    # ── Validate ──────────────────────────────────────────────────────────────

    async def validate(self, result: TestResult) -> TestResult:
        diag: Dict[str, Any] = result.data or {}

        if not diag.get("hasPbjs"):
            result.state = TestState.SKIPPED
            result.warnings.append("window.pbjs not present.")
            return result

        if not diag.get("has_display_store") or not diag.get("display_bidrequested_events"):
            result.state = TestState.SKIPPED
            result.warnings.append("No DISPLAY bidRequested events observed — skipping floor check.")
            return result

        if not is_supabase_configured(self.config):
            result.state = TestState.SKIPPED
            result.warnings.append("Supabase not configured; cannot check expected floor values.")
            return result

        locale = (diag.get("locale") or "").upper().strip()
        geo = locale if locale in _KNOWN_GEOS else "ROW"

        publisher_short = publisher_from_url(result.url or "")
        publisher_domain = _PUBLISHER_DOMAIN.get(publisher_short, publisher_short)

        floors_data, else_floor = await self._fetch_expected_floors(publisher_domain, geo)

        configured: Dict[str, Any] = diag.get("configured_floors") or {}
        ad_units: List[Dict] = diag.get("ad_units") or []

        errors: List[str] = []
        missing_floor: List[str] = []    # units with no floor in Prebid config
        wrong_value: List[str] = []      # units with floor that doesn't match DB
        no_db_entry: List[str] = []      # units not in DB (no expected value to compare)

        for unit in ad_units:
            short_code = unit.get("short_code", "")
            if not short_code:
                continue

            key = f"{short_code}|banner"
            actual = configured.get(key)          # float or None
            expected = floors_data.get(short_code, else_floor)

            if actual is None:
                missing_floor.append(short_code)
            elif expected is None:
                no_db_entry.append(short_code)
            elif abs(float(actual) - float(expected)) > _FLOOR_TOLERANCE:
                wrong_value.append(
                    f"{short_code}: configured={actual:.4f}, expected={expected:.4f}"
                )

        if missing_floor:
            errors.append(
                f"No floor configured in Prebid for: {', '.join(sorted(missing_floor))}"
            )
        if wrong_value:
            errors.append(
                f"Floor value mismatch ({geo}): {'; '.join(wrong_value)}"
            )
        if no_db_entry and self.config.get("trace"):
            print(
                f"[PbjsDisplayFloorsPricesTest] Units with no DB entry (using ELSE): "
                f"{', '.join(no_db_entry)}"
            )

        if errors:
            result.state = TestState.FAILED
            result.errors.extend(errors)
        else:
            result.state = TestState.PASSED

        units_checked = [u.get("short_code") for u in ad_units if u.get("short_code")]
        result.metadata.update({
            "geo": geo,
            "publisher": publisher_domain,
            "units_checked": sorted(units_checked),
            "units_missing_floor": sorted(missing_floor),
            "units_wrong_value": wrong_value,
            "units_no_db_entry": sorted(no_db_entry),
            "floors_enabled": diag.get("floors_enabled"),
            "floors_currency": diag.get("floors_currency"),
        })

        return result
