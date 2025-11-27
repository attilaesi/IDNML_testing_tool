# tests/gpt_tests/GdprKeyTest.py

"""
gpt:gdpr key test

What this test is meant to test
-------------------------------
Checks the GPT "gdpr" targeting key for EU/UK traffic.

For INM:
  - Locale = "UK"  -> we expect a gdpr key with value "0" or "1"
  - Locale = "US"  -> we don't enforce the gdpr key; test is skipped.

Test conditions
---------------
We inspect:
  - googletag.pubads().getTargeting("gdpr")

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - Locale != "UK" and no gdpr key found (test skipped), OR
    - Locale == "UK" and at least one gdpr value is "0" or "1".

- FAILED:
    - Locale == "UK" and:
        * gdpr key missing, or
        * all values are something other than "0" or "1".

- SKIPPED:
    - Locale != "UK", OR
    - GPT targeting is not available at all.
"""

from typing import Dict, Any, List

from core.base_test import BaseTest, TestResult, TestState


class GdprKeyTest(BaseTest):
    """Validate GPT 'gdpr' targeting flag based on Locale cookie."""

    async def setup(self, page, url: str) -> bool:
        # Always run; we may skip in validate based on locale.
        return True

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        locale = getattr(self, "locale", "UK")
        result.metadata["locale"] = locale

        js = """
        () => {
          const out = {
            hasGpt: false,
            gdprValues: [],
            errors: []
          };

          try {
            const g = window.googletag;
            if (!g || !g.pubads || typeof g.pubads !== "function") {
              out.errors.push("googletag.pubads() not available");
              return out;
            }
            const pubads = g.pubads();
            if (!pubads || typeof pubads.getTargeting !== "function") {
              out.errors.push("pubads.getTargeting() not available");
              return out;
            }
            out.hasGpt = true;

            try {
              const vals = pubads.getTargeting("gdpr") || [];
              if (Array.isArray(vals)) {
                out.gdprValues = vals.map(v => String(v));
              }
            } catch (e) {
              out.errors.push("Error reading gdpr targeting: " + String(e));
            }
          } catch (e) {
            out.errors.push(String(e));
          }

          return out;
        }
        """

        diag = await page.evaluate(js)
        if not isinstance(diag, dict):
            diag = {}

        result.data = {
            "locale": locale,
            "hasGpt": bool(diag.get("hasGpt")),
            "gdprValues": diag.get("gdprValues") or [],
            "errors": diag.get("errors") or [],
        }
        return result

    async def validate(self, result: TestResult) -> TestResult:
        data: Dict[str, Any] = result.data or {}
        locale = str(data.get("locale", "UK")).upper()
        has_gpt = bool(data.get("hasGpt"))
        vals: List[str] = [str(v).strip() for v in data.get("gdprValues") or []]
        errors = data.get("errors") or []

        if not has_gpt:
            result.state = TestState.SKIPPED
            result.warnings.append(
                "googletag.pubads() / getTargeting not available; skipping GdprKeyTest."
            )
            return result

        # Non-EU/UK: skip
        if locale != "UK":
            result.state = TestState.SKIPPED
            result.warnings.append(
                f"Locale={locale}; skipping GdprKeyTest (only enforced for UK)."
            )
            return result

        # Locale = UK: must have gdpr values and at least one is 0 or 1
        if not vals:
            result.state = TestState.FAILED
            result.errors.append("gdpr targeting key missing for Locale=UK.")
            for e in errors:
                result.errors.append(f"Extraction error: {e}")
            return result

        valid = [v for v in vals if v in ("0", "1")]
        if not valid:
            result.state = TestState.FAILED
            result.errors.append(
                "Invalid gdpr value(s) for Locale=UK (expected '0' or '1'): "
                + ", ".join(vals)
            )
            for e in errors:
                result.errors.append(f"Extraction error: {e}")
            return result

        result.state = TestState.PASSED
        for e in errors:
            result.warnings.append(f"Extraction warning: {e}")
        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return