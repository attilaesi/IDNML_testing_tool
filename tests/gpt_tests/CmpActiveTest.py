# tests/gpt_tests/cmp_active_test.py

"""
gpt:cmpActive

What this test is meant to test
-------------------------------
Checks whether GPT targeting exposes a "cmpActive" flag and, if present,
that the value is "true" or "false" as a string.

This is a *shape* / hygiene test, not a legal consent audit.

Test conditions
---------------
- googletag.pubads() must be present.
- We look for "cmpActive" key (case-sensitive).

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - "cmpActive" is not present (feature not in use), OR
    - "cmpActive" is present with value "true" or "false".
- FAILED:
    - "cmpActive" is present but has any other non-empty value.
- SKIPPED:
    - GPT targeting not available.
"""

from typing import Dict, Any, List
from core.base_test import BaseTest, TestResult, TestState


class CmpActiveTest(BaseTest):
    """Validate GPT 'cmpActive' flag shape when present."""

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
            return pubads.getTargeting("cmpActive") || [];
          } catch (e) {
            return null;
          }
        }
        """
        vals = await page.evaluate(js)
        result.data = {"cmpActive": vals or []}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        vals: List[str] = [
            str(v).strip() for v in (result.data or {}).get("cmpActive", [])
        ]

        if not vals:
            result.state = TestState.PASSED
            return result

        bad = [v for v in vals if v.lower() not in {"true", "false"}]
        if bad:
            result.state = TestState.FAILED
            result.errors.append(
                "Invalid cmpActive values (expected 'true'/'false'): "
                + ", ".join(bad)
            )
        else:
            result.state = TestState.PASSED

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return