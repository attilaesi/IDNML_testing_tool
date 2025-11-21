# tests/gpt_tests/testgroup_test.py

"""
gpt:testgroup

What this test is meant to test
-------------------------------
Checks GPT targeting key "testgroup" (AB test / experiment flag) if present.

Test conditions
---------------
- googletag.pubads() must be present.
- If "testgroup" exists, we just check it's non-empty.

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - 'testgroup' not present, OR
    - present with at least one non-empty value.
- FAILED:
    - present but all values empty/whitespace.
- SKIPPED:
    - GPT targeting not available.
"""

from typing import Dict, Any, List
from core.base_test import BaseTest, TestResult, TestState


class TestgroupTest(BaseTest):
    """Validate GPT 'testgroup' targeting (AB test marker) when present."""

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
            return pubads.getTargeting("testgroup") || [];
          } catch (e) {
            return null;
          }
        }
        """
        vals = await page.evaluate(js)
        result.data = {"testgroup": vals or []}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        vals: List[str] = [
            str(v).strip() for v in (result.data or {}).get("testgroup", [])
        ]

        if not vals:
            result.state = TestState.PASSED
            return result

        non_empty = [v for v in vals if v]
        if non_empty:
            result.state = TestState.PASSED
        else:
            result.state = TestState.FAILED
            result.errors.append("testgroup targeting present but empty/whitespace only.")
        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return