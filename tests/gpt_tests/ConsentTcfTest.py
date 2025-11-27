# tests/gpt_tests/ConsentTcfTest.py

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

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - Locale != "UK": test is SKIPPED, not a failure, OR
    - Locale == "UK" and we find either:
        * a "gdpr" targeting value, or
        * a non-empty euconsent-v2 TCString.

- FAILED:
    - Locale == "UK" and we cannot find *either* gdpr targeting or a TCString.

- SKIPPED:
    - Locale != "UK" (e.g. US),
    - OR GPT targeting is not available at all.
"""

from typing import Dict, Any

from core.base_test import BaseTest, TestResult, TestState


class ConsentTcfTest(BaseTest):
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

        js = """
        () => {
          const out = {
            hasGpt: false,
            gdprKey: null,
            tcString: null,
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
              const gdprVals = pubads.getTargeting("gdpr") || [];
              if (Array.isArray(gdprVals) && gdprVals.length) {
                out.gdprKey = String(gdprVals[0]);
              }
            } catch (e) {
              out.errors.push("Error reading gdpr targeting: " + String(e));
            }

            try {
              const cookies = document.cookie ? document.cookie.split(/;\\s*/) : [];
              const tcCookie = cookies.find(c => c.startsWith("euconsent-v2="));
              if (tcCookie) {
                const parts = tcCookie.split("=");
                out.tcString = parts.slice(1).join("=") || null;
              }
            } catch (e) {
              out.errors.push("Error reading euconsent-v2 cookie: " + String(e));
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
                "googletag.pubads() / getTargeting not available; skipping ConsentTcfTest."
            )
            return result

        # Non-EU traffic: skip (Locale != UK)
        if locale != "UK":
            result.state = TestState.SKIPPED
            result.warnings.append(
                f"Locale={locale}; skipping TCF consent test (only enforced for UK)."
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

    async def cleanup(self, page, result: TestResult) -> None:
        # No extra cleanup required for now
        return