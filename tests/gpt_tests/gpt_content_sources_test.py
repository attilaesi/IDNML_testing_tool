# tests/gpt_tests/gpt_content_sources_test.py

"""
gpt:contentSources

What this test is meant to test
-------------------------------
Checks GPT targeting key "contentSources" which often lists one or
more editorial / syndication sources.

Test conditions
---------------
- googletag.pubads() must be present.
- If "contentSources" exists, we sanity-check that it is non-empty.

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - "contentSources" is not present, OR
    - "contentSources" contains at least one non-empty string.
- FAILED:
    - "contentSources" is present but all values are empty or whitespace.
- SKIPPED:
    - GPT targeting not available.
"""

from typing import List
from core.gpt_base_test import GptBaseTest
from core.base_test import TestResult, TestState

class GptContentSourcesTest(GptBaseTest):

    """Validate GPT 'contentSources' targeting when present."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        js = """
        () => {
          try {
            if (!window.googletag || !googletag.pubads) return null;
            const pubads = googletag.pubads();
            if (!pubads || !pubads.getTargeting) return null;
            return pubads.getTargeting("contentSources") || [];
          } catch (e) {
            return null;
          }
        }
        """
        vals = await page.evaluate(js)
        result.data = {"contentSources": vals or []}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        vals: List[str] = [
            str(v).strip() for v in (result.data or {}).get("contentSources", [])
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
                "contentSources targeting present but all values are empty / whitespace."
            )

        return result