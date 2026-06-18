"""
pbjs:msft_keywords

What this test checks
---------------------
Verifies that the msft bidder's ortb2.user.keywords and ortb2.site.keywords
strings are correctly formed for Microsoft Advertising (Xandr) consumption.

  ortb2.user.keywords — must contain 'p_standard=' and 'permutive=' keys
  ortb2.site.keywords — must contain 'mantis=' and 'mantis_context=' keys
  Both strings — must have no spaces before or after comma separators

Test conditions
---------------
- window.pbjs must be present.
- At least one of user.keywords / site.keywords must be found (bidder-level
  ortb2 checked first, global ortb2 used as fallback).

What counts as PASS / FAIL / SKIP
-----------------------------------
- PASSED:  Both strings present, required keys found, no spaces around commas.
- FAILED:  Either string missing, required key absent, or spaces around commas.
- SKIPPED: window.pbjs missing, or neither keyword string found anywhere.
"""

from pathlib import Path

from core.base_test import BaseTest, TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "pbjs_msft_keywords.js").read_text()


class PbjsMsftKeywordsTest(BaseTest):

    name = "PbjsMsftKeywordsTest"

    async def setup(self, page, url: str) -> bool:
        try:
            await page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass
        return True

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        result.data = await page.evaluate(_JS) or {}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        diag = result.data or {}

        if not diag.get("hasPbjs"):
            result.state = TestState.SKIPPED
            result.warnings.append("window.pbjs not present.")
            return result

        user_kw = diag.get("user_keywords")
        site_kw = diag.get("site_keywords")

        # Skip if msft didn't participate in the display auction on this page/geo
        if not diag.get("msft_bid_observed"):
            result.state = TestState.SKIPPED
            result.warnings.append("msft not observed in display auction — skipping keyword check.")
            return result

        if user_kw is None and site_kw is None:
            result.state = TestState.SKIPPED
            result.warnings.append(
                "No ortb2.user.keywords or ortb2.site.keywords found "
                "in msft bidder config or global ortb2."
            )
            return result

        errors = []

        # ── user.keywords ─────────────────────────────────────────────────────
        if user_kw is None:
            errors.append("ortb2.user.keywords not found.")
        else:
            if not diag.get("user_has_p_standard"):
                errors.append("ortb2.user.keywords: 'p_standard=' key not present.")
            if not diag.get("user_has_permutive"):
                errors.append("ortb2.user.keywords: 'permutive=' key not present.")
            if diag.get("user_spaces_found"):
                errors.append(
                    "ortb2.user.keywords: spaces found around comma separators "
                    f"— value starts: '{user_kw[:100]}'"
                )

        # ── site.keywords ─────────────────────────────────────────────────────
        if site_kw is None:
            errors.append("ortb2.site.keywords not found.")
        else:
            if not diag.get("site_has_mantis"):
                errors.append("ortb2.site.keywords: 'mantis=' key not present.")
            if not diag.get("site_has_mantis_context"):
                errors.append("ortb2.site.keywords: 'mantis_context=' key not present.")
            if diag.get("site_spaces_found"):
                errors.append(
                    "ortb2.site.keywords: spaces found around comma separators "
                    f"— value starts: '{site_kw[:100]}'"
                )

        for e in diag.get("errors", []):
            result.warnings.append(f"JS: {e}")

        if errors:
            result.state = TestState.FAILED
            result.errors.extend(errors)
        else:
            result.state = TestState.PASSED

        if self.config.get("trace"):
            print(f"[{self.name}] user_keywords : {user_kw}")
            print(f"[{self.name}] site_keywords : {site_kw}")

        return result
