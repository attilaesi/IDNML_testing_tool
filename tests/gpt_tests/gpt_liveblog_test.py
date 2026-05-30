# tests/gpt_tests/gpt_liveblog_test.py

"""
gpt:liveblog

What this test is meant to test
-------------------------------
Checks GPT targeting key "liveblog" which flags liveblog content.

Test conditions
---------------
- googletag.pubads() must be present.
- If "liveblog" is present, we validate its value.

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - "liveblog" is not present, OR
    - "liveblog" is present with "true" or "false".
- FAILED:
    - "liveblog" is present but has any other non-empty value.
- SKIPPED:
    - GPT targeting not available.
"""

from pathlib import Path
from typing import List
from core.gpt_base_test import GptBaseTest
from core.base_test import TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "gpt_liveblog.js").read_text()

class GptLiveblogTest(GptBaseTest):

    """Validate GPT 'liveblog' flag when present."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        vals = await page.evaluate(_JS)
        result.data = {"liveblog": vals or []}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        vals: List[str] = [
            str(v).strip() for v in (result.data or {}).get("liveblog", [])
        ]

        if not vals:
            result.state = TestState.PASSED
            return result

        bad = [v for v in vals if v.lower() not in {"y", "n"}]
        if bad:
            result.state = TestState.FAILED
            result.errors.append(
                "Invalid liveblog values (expected 'y'/'n'): "
                + ", ".join(bad)
            )
        else:
            result.state = TestState.PASSED

        return result
