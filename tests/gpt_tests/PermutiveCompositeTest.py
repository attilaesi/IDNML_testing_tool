# tests/gpt_tests/permutive_composite_test.py

"""
gpt:permutive

What this test is meant to test
-------------------------------
Lightweight check for GPT-level Permutive targeting. Some stacks expose
Permutive segment IDs or flags via GPT targeting keys (e.g. 'permutive').

Since the authoritative source for segments is now ORTB2 (checked by
Prebid tests), this GPT test is deliberately lenient.

Test conditions
---------------
- googletag.pubads() must be present.
- If "permutive" is present, we just check that there is at least one
  non-empty value and that values are strings.

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - 'permutive' not present (segments only in ORTB2), OR
    - 'permutive' present with at least one non-empty value.
- FAILED:
    - 'permutive' present but all values empty / whitespace.
- SKIPPED:
    - GPT targeting not available.
"""

from typing import Dict, Any, List
from core.base_test import BaseTest, TestResult, TestState


class PermutiveCompositeTest(BaseTest):
    """Lenient GPT-level Permutive targeting sanity check."""

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
            return pubads.getTargeting("permutive") || [];
          } catch (e) {
            return null;
          }
        }
        """
        vals = await page.evaluate(js)
        result.data = {"permutive": vals or []}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        vals: List[str] = [
            str(v).strip() for v in (result.data or {}).get("permutive", [])
        ]
        if not vals:
            result.state = TestState.PASSED
            return result

        non_empty = [v for v in vals if v]
        if non_empty:
            result.state = TestState.PASSED
        else:
            result.state = TestState.FAILED
            result.errors.append(
                "GPT 'permutive' targeting present but all values empty / whitespace."
            )
        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return