# tests/gpt_tests/longread_test.py

"""
gpt:longread

What this test is meant to test
-------------------------------
Checks GPT targeting key "longread" which typically flags long-form
content for special placements or pricing.

Test conditions
---------------
- googletag.pubads() must be present.
- If "longread" exists, value should be "true" or "false".

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - "longread" not present, OR
    - "longread" present with 'true'/'false'.
- FAILED:
    - "longread" present but has any other non-empty value.
- SKIPPED:
    - GPT targeting not available.
"""

from typing import Dict, Any, List
from core.base_test import BaseTest, TestResult, TestState


class LongreadTest(BaseTest):
    """Validate GPT 'longread' flag when present."""

    async def setup(self, page, url: str) -> bool:
        js = "(() => !!(window.googletag && googletag.pubads))()"
        return bool(await page.evaluate(js))

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        js = """
        () => {
          try {
            if (!window.googletag || !googletag.pubads) return null;
            const pubads = googletag.pubads();
            if (!pubads || !pubads.getTargeting) return null;
            return pubads.getTargeting("longread") || [];
          } catch (e) {
            return null;
          }
        }
        """
        vals = await page.evaluate(js)
        result.data = {"longread": vals or []}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        vals: List[str] = [
            str(v).strip() for v in (result.data or {}).get("longread", [])
        ]

        if not vals:
            result.state = TestState.PASSED
            return result

        bad = [v for v in vals if v.lower() not in {"true", "false"}]
        if bad:
            result.state = TestState.FAILED
            result.errors.append(
                "Invalid longread values (expected 'true'/'false'): "
                + ", ".join(bad)
            )
        else:
            result.state = TestState.PASSED
        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return