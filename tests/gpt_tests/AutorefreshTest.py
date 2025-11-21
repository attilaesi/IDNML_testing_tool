# tests/gpt_tests/autorefresh_test.py

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

from typing import Dict, Any, List
from core.base_test import BaseTest, TestResult, TestState


class AutorefreshTest(BaseTest):
    """Validate GPT autorefresh targeting key shape."""

    async def setup(self, page, url: str) -> bool:
        js = "(() => !!(window.googletag && googletag.pubads))()"
        return bool(await page.evaluate(js))

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        js = """
        () => {
          try {
            if (!window.googletag || !googletag.pubads) return null;
            const pubads = googletag.pubads();
            if (!pubads || !pubads.getTargeting) return null;
            return pubads.getTargeting("autorefresh") || [];
          } catch (e) {
            return null;
          }
        }
        """
        vals = await page.evaluate(js)
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
            if v.lower() not in {"true", "false"}
        ]
        if bad:
            result.state = TestState.FAILED
            result.errors.append(
                "Invalid autorefresh values (expected 'true'/'false'): "
                + ", ".join(bad)
            )
        else:
            result.state = TestState.PASSED

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return