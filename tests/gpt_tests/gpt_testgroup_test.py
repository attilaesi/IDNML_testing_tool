# tests/gpt_tests/gpt_testgroup_test.py

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

from pathlib import Path
from typing import List
from core.gpt_base_test import GptBaseTest
from core.base_test import TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "gpt_testgroup.js").read_text()

class GptTestgroupTest(GptBaseTest):

    """Validate GPT 'testgroup' targeting (AB test marker) when present."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        vals = await page.evaluate(_JS)
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