# tests/gpt_tests/gpt_slot_dump_probe_test.py

"""
gpt:slot_dump

What this test is meant to test
-------------------------------
Utility / probe test that dumps GPT slot definitions and their key-values
into result.data for debugging and CSV inspection. It always PASSES.

Test conditions
---------------
- googletag.pubads() must be present.

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - Always, if GPT can be inspected.
- SKIPPED:
    - If googletag.pubads() is not available.
"""

from pathlib import Path
from typing import Dict, Any, List
from core.base_test import BaseTest, TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "gpt_slot_dump_probe.js").read_text()

class GptSlotDumpProbeTest(BaseTest):

    """Debug probe: dump GPT slots and targeting."""

    async def setup(self, page, url: str) -> bool:
        js = "(() => !!(window.googletag && googletag.pubads && googletag.pubads().getSlots))()"
        return bool(await page.evaluate(js))

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        slots = await page.evaluate(_JS)
        if slots is None:
            result.state = TestState.SKIPPED
            result.warnings.append("GPT slots not available; skipping GptSlotDumpProbeTest.")
        else:
            result.data = {"slots": slots}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        # If we reached here with no explicit state set, treat as PASSED
        if result.state == TestState.PENDING:
            result.state = TestState.PASSED
        return result
