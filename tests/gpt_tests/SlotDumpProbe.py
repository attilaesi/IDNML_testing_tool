# tests/gpt_tests/slot_dump_probe.py

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

from typing import Dict, Any, List
from core.base_test import BaseTest, TestResult, TestState


class SlotDumpProbe(BaseTest):
    """Debug probe: dump GPT slots and targeting."""

    async def setup(self, page, url: str) -> bool:
        js = "(() => !!(window.googletag && googletag.pubads && googletag.pubads().getSlots))()"
        return bool(await page.evaluate(js))

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        js = """
        () => {
          try {
            if (!window.googletag || !googletag.pubads) return null;
            const pubads = googletag.pubads();
            if (!pubads || !pubads.getSlots) return null;
            const slots = pubads.getSlots() || [];
            const out = [];
            slots.forEach(s => {
              const id = s.getSlotElementId && s.getSlotElementId();
              const adUnit = s.getAdUnitPath && s.getAdUnitPath();
              const keys = s.getTargetingKeys ? s.getTargetingKeys() : [];
              const kv = {};
              keys.forEach(k => {
                kv[k] = s.getTargeting(k) || [];
              });
              out.push({ id, adUnit, targeting: kv });
            });
            return out;
          } catch (e) {
            return null;
          }
        }
        """
        slots = await page.evaluate(js)
        if slots is None:
            result.state = TestState.SKIPPED
            result.warnings.append("GPT slots not available; skipping SlotDumpProbe.")
        else:
            result.data = {"slots": slots}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        # If we reached here with no explicit state set, treat as PASSED
        if result.state == TestState.PENDING:
            result.state = TestState.PASSED
        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return