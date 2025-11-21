# tests/gpt_tests/topictags_test.py

"""
gpt:topictags

What this test is meant to test
-------------------------------
Checks GPT targeting key "topictags" which usually carries a list of
editorial tags / topics.

Test conditions
---------------
- googletag.pubads() must be present.
- If "topictags" exists, we expect at least one non-empty tag.

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - 'topictags' not present, OR
    - present with at least one non-empty tag.
- FAILED:
    - present but all tags empty/whitespace.
- SKIPPED:
    - GPT targeting not available.
"""

from typing import Dict, Any, List
from core.base_test import BaseTest, TestResult, TestState


class TopictagsTest(BaseTest):
    """Validate GPT 'topictags' targeting list when present."""

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
            return pubads.getTargeting("topictags") || [];
          } catch (e) {
            return null;
          }
        }
        """
        vals = await page.evaluate(js)
        result.data = {"topictags": vals or []}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        vals: List[str] = [
            str(v).strip() for v in (result.data or {}).get("topictags", [])
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
                "topictags targeting present but all tags empty / whitespace."
            )
        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return