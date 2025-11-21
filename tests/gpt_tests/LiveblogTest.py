# tests/gpt_tests/liveblog_test.py

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

from typing import Dict, Any, List
from core.base_test import BaseTest, TestResult, TestState


class LiveblogTest(BaseTest):
    """Validate GPT 'liveblog' flag when present."""

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
            return pubads.getTargeting("liveblog") || [];
          } catch (e) {
            return null;
          }
        }
        """
        vals = await page.evaluate(js)
        result.data = {"liveblog": vals or []}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        vals: List[str] = [
            str(v).strip() for v in (result.data or {}).get("liveblog", [])
        ]

        if not vals:
            result.state = TestState.PASSED
            return result

        bad = [v for v in vals if v.lower() not in {"true", "false"}]
        if bad:
            result.state = TestState.FAILED
            result.errors.append(
                "Invalid liveblog values (expected 'true'/'false'): "
                + ", ".join(bad)
            )
        else:
            result.state = TestState.PASSED

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return