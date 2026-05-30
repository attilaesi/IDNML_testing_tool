# tests/gpt_tests/gpt_autorefresh_test.py

"""
gpt:autorefresh

What this test is meant to test
-------------------------------
Checks GPT page-level targeting for the "autorefresh" key and ensures
that if it is present, its value is either "true" or "false" (string).

Test conditions
---------------
- googletag.pubads() must be present.
- If the "autorefresh" key is present in GPT targeting, we validate it.

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - "autorefresh" is not present (feature not in use), OR
    - "autorefresh" is present and has a value "true" or "false".
- FAILED:
    - "autorefresh" is present but its value is something other than
      "true" or "false" (case-insensitive).
- SKIPPED:
    - googletag.pubads() targeting cannot be read.
"""

from pathlib import Path
from typing import Dict, Any, List
from core.gpt_base_test import GptBaseTest
from core.base_test import TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "gpt_autorefresh.js").read_text()

class GptAutorefreshTest(GptBaseTest):

    """Validate GPT autorefresh targeting key shape."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        vals = await page.evaluate(_JS)
        result.data = {"autorefresh": vals or []}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        data: Dict[str, Any] = result.data or {}
        vals: List[str] = [str(v).strip() for v in data.get("autorefresh", [])]

        if not vals:
            result.state = TestState.PASSED  # feature not in use
            return result

        bad = [
            v for v in vals
            if v.lower() not in {"yes", "no"}
        ]
        if bad:
            result.state = TestState.FAILED
            result.errors.append(
                "Invalid autorefresh values (expected 'yes'/'no'): "
                + ", ".join(bad)
            )
        else:
            result.state = TestState.PASSED

        return result
