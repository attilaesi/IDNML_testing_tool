# tests/gpt_tests/gpt_reg_gate_test.py

"""
gpt:reg_gate

What this test is meant to test
-------------------------------
Checks GPT targeting key "reg_gate" which may indicate registration
gating / paywall logic.

Test conditions
---------------
- googletag.pubads() must be present.
- If "reg_gate" exists, it should be non-empty.

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - 'reg_gate' not present, OR
    - 'reg_gate' present with at least one non-empty value.
- FAILED:
    - 'reg_gate' present but all values empty/whitespace.
- SKIPPED:
    - GPT targeting not available.
"""

from pathlib import Path
from typing import List
from core.gpt_base_test import GptBaseTest
from core.base_test import TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "gpt_reg_gate.js").read_text()

class GptRegGateTest(GptBaseTest):

    """Validate GPT 'reg_gate' targeting when present."""

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        vals = await page.evaluate(_JS)
        result.data = {"reg_gate": vals or []}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        vals: List[str] = [
            str(v).strip() for v in (result.data or {}).get("reg_gate", [])
        ]

        if not vals:
            result.state = TestState.PASSED
            return result

        non_empty = [v for v in vals if v]
        if non_empty:
            result.state = TestState.PASSED
        else:
            result.state = TestState.FAILED
            result.errors.append("reg_gate targeting present but empty/whitespace only.")
        return result