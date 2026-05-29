# tests/gpt_tests/gpt_mantis_context_test.py

"""
gpt:mantis_context

What this test is meant to test
-------------------------------
Checks that the GPT targeting key "mantis_context" is present and contains
at least one non-empty string value.

Test conditions
---------------
- googletag.pubads() must be present.

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - "mantis_context" is present with at least one non-empty string value.
- FAILED:
    - "mantis_context" key is missing from GPT targeting.
    - "mantis_context" is present but all values are empty/whitespace.
- SKIPPED:
    - GPT targeting not available.
"""

from typing import List
from core.gpt_base_test import GptBaseTest
from core.base_test import TestResult, TestState

class GptMantisContextTest(GptBaseTest):

    """Validate GPT 'mantis_context' targeting shape when present."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        js = """
        () => {
          try {
            if (!window.googletag || !googletag.pubads) return null;
            const pubads = googletag.pubads();
            if (!pubads || !pubads.getTargeting) return null;
            const keys = pubads.getTargetingKeys ? pubads.getTargetingKeys() : [];
            const present = keys.includes("mantis_context");
            return {
              present,
              values: present ? (pubads.getTargeting("mantis_context") || []) : [],
            };
          } catch (e) {
            return null;
          }
        }
        """
        raw = await page.evaluate(js)
        result.data = raw or {}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        raw = result.data or {}

        if not raw:
            result.state = TestState.SKIPPED
            result.errors.append("GPT targeting not available.")
            return result

        if not raw.get("present"):
            result.state = TestState.FAILED
            result.errors.append("mantis_context key not found in GPT targeting.")
            return result

        vals: List[str] = [str(v).strip() for v in raw.get("values") or []]
        non_empty = [v for v in vals if v]
        if non_empty:
            result.state = TestState.PASSED
        else:
            result.state = TestState.FAILED
            result.errors.append(
                "mantis_context targeting present but contains only empty values."
            )
        return result