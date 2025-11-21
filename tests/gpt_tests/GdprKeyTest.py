# tests/gpt_tests/gdpr_key_test.py

"""
gpt:gdpr

What this test is meant to test
-------------------------------
Checks GPT targeting key "gdpr" which usually encodes whether the user
is under GDPR scope (0/1).

Test conditions
---------------
- geo_mode from config determines whether we expect a gdpr key.
- If geo_mode in {"UK","EU"} we expect gdpr to be present and 0 or 1.

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - geo_mode not in {"UK","EU"} and no gdpr key (test skipped), OR
    - geo_mode in {"UK","EU"} and gdpr value is "0" or "1".
- FAILED:
    - geo_mode in {"UK","EU"} and gdpr key missing or has any other value.
- SKIPPED:
    - GPT targeting not available.
"""

from typing import Dict, Any, List
from core.base_test import BaseTest, TestResult, TestState


class GdprKeyTest(BaseTest):
    """Validate GPT 'gdpr' targeting flag based on geo_mode."""

    async def setup(self, page, url: str) -> bool:
        # Always run; we may skip in validate
        return True

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        geo_mode = str(self.config.get("geo_mode", "")).upper()

        js = """
        () => {
          try {
            if (!window.googletag || !googletag.pubads) return null;
            const pubads = googletag.pubads();
            if (!pubads || !pubads.getTargeting) return null;
            return pubads.getTargeting("gdpr") || [];
          } catch (e) {
            return null;
          }
        }
        """
        vals = await page.evaluate(js)
        result.data = {
            "geo_mode": geo_mode,
            "gdpr": vals or []
        }
        return result

    async def validate(self, result: TestResult) -> TestResult:
        data: Dict[str, Any] = result.data or {}
        geo_mode = str(data.get("geo_mode", "")).upper()
        vals: List[str] = [str(v).strip() for v in data.get("gdpr", [])]

        if geo_mode not in {"UK", "EU"}:
            result.state = TestState.SKIPPED
            result.warnings.append(f"geo_mode={geo_mode}; skipping GdprKeyTest.")
            return result

        if not vals:
            result.state = TestState.FAILED
            result.errors.append("gdpr targeting key missing for geo_mode EU/UK.")
            return result

        allowed = {"0", "1"}
        bad = [v for v in vals if v not in allowed]
        if bad:
            result.state = TestState.FAILED
            result.errors.append(
                "Invalid gdpr value(s) for geo_mode EU/UK (expected '0' or '1'): "
                + ", ".join(bad)
            )
        else:
            result.state = TestState.PASSED

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return