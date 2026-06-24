# tests/gpt_tests/gpt_consent_tcf_test.py

"""
gpt:permutive consent / TCF test

What this test is meant to test
-------------------------------
Verifies that TCF / GDPR consent is exposed for EU/UK traffic.

For INM, we treat:
  - Locale = "UK"  -> EU/UK user (consent required/expected)
  - Locale = "US"  -> non-EU user (TCF not required by this test)

Test conditions
---------------
We look for:

  1) A "gdpr" targeting key on GPT, and/or
  2) An "euconsent-v2" cookie (TCString)

What counts as PASS / FAIL / SKIPPED / N/A
------------------------------------------
- PASSED:
    - Locale == "UK" and we find either:
        * a "gdpr" targeting value, or
        * a non-empty euconsent-v2 TCString.

- FAILED:
    - Locale == "UK" and we cannot find *either* gdpr targeting or a TCString.

- SKIPPED:
    - GPT targeting is not available at all.

- N/A:
    - Locale != "UK" (e.g. US) — TCF consent is not enforced outside UK.
"""

from pathlib import Path
from typing import Dict, Any

from core.base_test import BaseTest, TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "gpt_consent_tcf.js").read_text()

class GptConsentTcfTest(BaseTest):

    """Validate TCF consent exposure based on Locale cookie."""

    async def setup(self, page, url: str) -> bool:
        # Always run; we may skip in validate based on locale.
        return True

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        # Locale is injected by the framework_manager based on the Locale cookie.
        locale = getattr(self, "locale", "UK")
        result.metadata["locale"] = locale

        diag = await page.evaluate(_JS)
        if not isinstance(diag, dict):
            diag = {}

        result.data = {
            "locale": locale,
            "hasGpt": bool(diag.get("hasGpt")),
            "gdprKey": diag.get("gdprKey"),
            "tcString": diag.get("tcString"),
            "errors": diag.get("errors") or [],
        }
        return result

    async def validate(self, result: TestResult) -> TestResult:
        data: Dict[str, Any] = result.data or {}
        locale = str(data.get("locale", "UK")).upper()
        has_gpt = bool(data.get("hasGpt"))
        gdpr_key = (data.get("gdprKey") or "").strip()
        tc_string = (data.get("tcString") or "").strip()
        errors = data.get("errors") or []

        # If GPT isn't even available, treat as SKIPPED – something more basic is wrong.
        if not has_gpt:
            result.state = TestState.SKIPPED
            result.warnings.append(
                "googletag.pubads() / getTargeting not available; skipping GptConsentTcfTest."
            )
            return result

        # Non-EU traffic: not applicable (Locale != UK)
        if locale != "UK":
            result.state = TestState.NOT_APPLICABLE
            result.warnings.append(
                f"Locale={locale} — TCF consent not enforced outside UK."
            )
            return result

        # At this point: UK traffic. We expect a gdpr key and/or TCString.
        if not gdpr_key and not tc_string:
            result.state = TestState.FAILED
            result.errors.append(
                "For Locale=UK, neither a 'gdpr' GPT targeting key nor an 'euconsent-v2' TCString was found."
            )
            # Also propagate any extraction errors
            for e in errors:
                result.errors.append(f"Extraction error: {e}")
            return result

        # Passed
        result.state = TestState.PASSED
        # Still record any extraction warnings
        for e in errors:
            result.warnings.append(f"Extraction warning: {e}")
        return result
