# tests/gpt_tests/consent_tcf_test.py

"""
gpt:consent_tcf

What this test is meant to test
-------------------------------
Performs a *lightweight* sanity check that a TCFv2 consent string
is present somewhere if the site is expected to operate under GDPR.

This is *not* a full legal compliance test and does NOT look at
Prebid config (that's the job of the ConsentIntegrationTest in Prebid).

Test conditions
---------------
- We check for:
    - presence of a "gdpr" targeting key (0/1), AND/OR
    - presence of a plausible TCString in cookies (euconsent-v2).

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - For geo_mode "UK" or "EU", we find at least a plausible TCString
      OR a gdpr flag key.
- FAILED:
    - For geo_mode "UK"/"EU", neither gdpr nor a TCString-like value
      can be found.
- SKIPPED:
    - geo_mode not in {"UK","EU"} (e.g. "US", "ROW").
"""

from typing import Dict, Any
from core.base_test import BaseTest, TestResult, TestState


class ConsentTcfTest(BaseTest):
    """Lightweight TCFv2 consent presence sanity check (GPT side)."""

    async def setup(self, page, url: str) -> bool:
        # Always run; we may skip in validate based on geo_mode
        return True

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        geo_mode = str(self.config.get("geo_mode", "")).upper()

        js = """
        (geoMode) => {
          const out = { geoMode, gdprKey: null, tcString: null };

          try {
            if (window.googletag && googletag.pubads) {
              const pubads = googletag.pubads();
              if (pubads && pubads.getTargeting) {
                const gdprVals = pubads.getTargeting("gdpr") || [];
                if (gdprVals.length) {
                  out.gdprKey = String(gdprVals[0]);
                }
              }
            }
          } catch (e) {}

          try {
            const cookies = document.cookie || "";
            const m = cookies.match(/euconsent-v2=([^;]+)/i);
            if (m && m[1]) {
              out.tcString = m[1];
            }
          } catch (e) {}

          return out;
        }
        """
        diag = await page.evaluate(js, geo_mode)
        result.data = diag or {"geoMode": geo_mode, "gdprKey": None, "tcString": None}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        data: Dict[str, Any] = result.data or {}
        geo_mode = str(data.get("geoMode", "")).upper()
        gdpr_key = (data.get("gdprKey") or "").strip()
        tc = (data.get("tcString") or "").strip()

        # Non-EU geo: skip
        if geo_mode not in {"UK", "EU"}:
            result.state = TestState.SKIPPED
            result.warnings.append(f"geo_mode={geo_mode}; skipping TCF consent test.")
            return result

        if gdpr_key or tc:
            result.state = TestState.PASSED
        else:
            result.state = TestState.FAILED
            result.errors.append(
                "For geo_mode EU/UK, no gdpr targeting key and no euconsent-v2 TCString cookie found."
            )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return