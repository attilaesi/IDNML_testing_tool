# tests/gpt_tests/gpt_page_type_test.py

"""
gpt:pagetype

What this test is meant to test
-------------------------------
Checks GPT page-level targeting key "pageType" for presence and sanity.

Test conditions
---------------
- googletag.pubads() must be present.
- We expect pageType to be a single, non-empty string.

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - pageType present with a non-empty string (any value).
- FAILED:
    - pageType missing, OR
    - present but empty / whitespace only.
- SKIPPED:
    - GPT targeting not available.
"""

from pathlib import Path
from typing import List
from core.gpt_base_test import GptBaseTest
from core.base_test import TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "gpt_page_type.js").read_text()

class GptPageTypeTest(GptBaseTest):

    """Validate GPT 'pageType' targeting is present and non-empty."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        vals = await page.evaluate(_JS)
        result.data = {"pageType": vals or []}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        vals: List[str] = [
            str(v).strip() for v in (result.data or {}).get("pageType", [])
        ]

        if not vals:
            result.state = TestState.FAILED
            result.errors.append("pageType targeting key missing or empty.")
        else:
            non_empty = [v for v in vals if v]
            if non_empty:
                result.state = TestState.PASSED
            else:
                result.state = TestState.FAILED
                result.errors.append("pageType targeting contains only empty values.")

        return result
