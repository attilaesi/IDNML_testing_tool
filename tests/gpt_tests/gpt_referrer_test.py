# tests/gpt_tests/gpt_referrer_test.py

"""
gpt:referrer

What this test is meant to test
-------------------------------
Checks GPT targeting key "referrer" (if present) and compares it
loosely to document.referrer for basic sanity.

Test conditions
---------------
- googletag.pubads() must be present.
- If "referrer" exists, we grab its first value and the real document.referrer.

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - 'referrer' not present, OR
    - present and is a non-empty substring of document.referrer.
- FAILED:
    - 'referrer' present but does not match / is not found in document.referrer
      when document.referrer is non-empty.
- SKIPPED:
    - GPT targeting not available.
"""

from pathlib import Path
from typing import Dict, Any
from core.base_test import BaseTest, TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "gpt_referrer.js").read_text()

class GptReferrerTest(BaseTest):

    """Sanity-check GPT 'referrer' vs document.referrer when present."""

    async def setup(self, page, url: str) -> bool:
        return True  # we handle missing GPT in execute

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        diag = await page.evaluate(_JS)
        result.data = diag or {"gptReferrer": None, "docReferrer": "", "hasGpt": False}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        data: Dict[str, Any] = result.data or {}
        has_gpt = bool(data.get("hasGpt"))
        gpt_ref = (data.get("gptReferrer") or "").strip()
        doc_ref = (data.get("docReferrer") or "").strip()

        if not has_gpt:
            result.state = TestState.SKIPPED
            result.warnings.append("googletag.pubads() not available; skipping GptReferrerTest.")
            return result

        if not gpt_ref:
            # No GPT referrer configured; this is fine
            result.state = TestState.PASSED
            return result

        if not doc_ref:
            # Document has no referrer; nothing to compare
            result.state = TestState.PASSED
            return result

        if gpt_ref in doc_ref or doc_ref in gpt_ref:
            result.state = TestState.PASSED
        else:
            result.state = TestState.FAILED
            result.errors.append(
                f"GPT referrer '{gpt_ref}' does not resemble document.referrer '{doc_ref}'."
            )

        return result
