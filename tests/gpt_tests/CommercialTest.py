# tests/gpt_tests/commercial_test.py

"""
gpt:commercial

What this test is meant to test
-------------------------------
Checks GPT targeting key "commercial" which typically flags commercial /
sponsored / branded content pages.

Test conditions
---------------
- googletag.pubads() must be present.
- If "commercial" is present, we validate its value.

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - "commercial" is not present (editorial page), OR
    - "commercial" is present and equal to "true" or "false".
- FAILED:
    - "commercial" is present but has some other non-empty value.
- SKIPPED:
    - GPT targeting not available.
"""

from typing import Dict, Any, List
from core.base_test import BaseTest, TestResult, TestState


class CommercialTest(BaseTest):
    """Validate GPT 'commercial' flag shape."""

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
            return pubads.getTargeting("commercial") || [];
          } catch (e) {
            return null;
          }
        }
        """
        vals = await page.evaluate(js)
        result.data = {"commercial": vals or []}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        vals: List[str] = [
            str(v).strip() for v in (result.data or {}).get("commercial", [])
        ]

        if not vals:
            result.state = TestState.PASSED
            return result

        bad = [v for v in vals if v.lower() not in {"true", "false"}]
        if bad:
            result.state = TestState.FAILED
            result.errors.append(
                "Invalid commercial values (expected 'true'/'false'): "
                + ", ".join(bad)
            )
        else:
            result.state = TestState.PASSED

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return