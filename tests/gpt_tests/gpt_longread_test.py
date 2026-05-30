# tests/gpt_tests/gpt_longread_test.py

"""
gpt:longread

What this test is meant to test
-------------------------------
Checks GPT targeting key "longread" which typically flags long-form
content for special placements or pricing.

Test conditions
---------------
- googletag.pubads() must be present.
- If "longread" exists, value should be "true" or "false".

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - "longread" not present, OR
    - "longread" present with 'true'/'false'.
- FAILED:
    - "longread" present but has any other non-empty value.
- SKIPPED:
    - GPT targeting not available.
"""

from pathlib import Path
from typing import List
from core.gpt_base_test import GptBaseTest
from core.base_test import TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "gpt_longread.js").read_text()

class GptLongreadTest(GptBaseTest):

    """Validate GPT 'longread' flag when present."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        vals = await page.evaluate(_JS)
        result.data = {"longread": vals or []}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        vals: List[str] = [
            str(v).strip() for v in (result.data or {}).get("longread", [])
        ]

        if not vals:
            result.state = TestState.PASSED
            return result

        bad = [v for v in vals if v.lower() not in {"y", "n"}]
        if bad:
            result.state = TestState.FAILED
            result.errors.append(
                "Invalid longread values (expected 'y'/'n'): "
                + ", ".join(bad)
            )
        else:
            result.state = TestState.PASSED
        return result
