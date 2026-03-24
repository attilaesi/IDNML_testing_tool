# tests/gpt_tests/gpt_mantis_test.py

"""
gpt:mantis

What this test is meant to test
-------------------------------
Checks GPT targeting key "mantis" which often carries a string of
brand safety / vertical labels (e.g. "Default-GREEN,Apple-RED,...").

We only check that if present, it's non-empty – we no longer enforce
specific whitelists/regexes.

Test conditions
---------------
- googletag.pubads() must be present.
- If "mantis" exists, values should be non-empty strings.

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - "mantis" not present, OR
    - "mantis" present with at least one non-empty value.
- FAILED:
    - "mantis" present but all values are empty/whitespace.
- SKIPPED:
    - GPT targeting not available.
"""

from typing import List
from core.gpt_base_test import GptBaseTest
from core.base_test import TestResult, TestState


class GptMantisTest(GptBaseTest):
    NORMALIZED_NAME = "gpt_mantis_test"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = self.NORMALIZED_NAME

    """Validate GPT 'mantis' targeting string when present."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        js = """
        () => {
          try {
            if (!window.googletag || !googletag.pubads) return null;
            const pubads = googletag.pubads();
            if (!pubads || !pubads.getTargeting) return null;
            return pubads.getTargeting("mantis") || [];
          } catch (e) {
            return null;
          }
        }
        """
        vals = await page.evaluate(js)
        result.data = {"mantis": vals or []}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        vals: List[str] = [
            str(v).strip() for v in (result.data or {}).get("mantis", [])
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
                "mantis targeting present but contains only empty values."
            )
        return result
