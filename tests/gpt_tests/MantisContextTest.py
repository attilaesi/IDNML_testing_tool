# tests/gpt_tests/mantis_context_test.py

"""
gpt:mantis_context

What this test is meant to test
-------------------------------
Checks GPT targeting key "mantis_context" for basic shape/health:
non-empty list of strings when present. We no longer try to enforce
a particular whitelist; the main goal is to ensure the key isn't
present but completely empty.

Test conditions
---------------
- googletag.pubads() must be present.
- If "mantis_context" exists, its values should be non-empty strings.

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - "mantis_context" not present, OR
    - present with at least one non-empty string value.
- FAILED:
    - present but all values are empty/whitespace.
- SKIPPED:
    - GPT targeting not available.
"""

from typing import Dict, Any, List
from core.base_test import BaseTest, TestResult, TestState


class MantisContextTest(BaseTest):
    """Validate GPT 'mantis_context' targeting shape when present."""

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
            return pubads.getTargeting("mantis_context") || [];
          } catch (e) {
            return null;
          }
        }
        """
        vals = await page.evaluate(js)
        result.data = {"mantis_context": vals or []}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        vals: List[str] = [
            str(v).strip() for v in (result.data or {}).get("mantis_context", [])
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
                "mantis_context targeting present but contains only empty values."
            )
        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return