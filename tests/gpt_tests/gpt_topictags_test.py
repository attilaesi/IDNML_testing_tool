# tests/gpt_tests/gpt_topictags_test.py

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

from pathlib import Path
from typing import List
from core.gpt_base_test import GptBaseTest
from core.base_test import TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "gpt_topictags.js").read_text()

class GptTopictagsTest(GptBaseTest):

    """Validate GPT 'topictags' targeting list when present."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        vals = await page.evaluate(_JS)
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