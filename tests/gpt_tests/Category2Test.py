# tests/gpt_tests/category2_test.py

"""
gpt:category2

What this test is meant to test
-------------------------------
Checks GPT targeting key "category2" (second-level taxonomy) for
presence and non-empty value on article-like pages.

Test conditions
---------------
- googletag.pubads() must be present.
- For article-like pageTypes, we expect a non-empty category2 when
  it is part of the taxonomy model.

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - category2 has at least one non-empty value on article-like pages,
      or
    - no category2 key present but category1 is present (taxonomy still
      partially configured) -> we treat as PASS.
- FAILED:
    - category2 is present but all values are empty.
- SKIPPED:
    - GPT targeting not available or pageType is clearly non-article
      (index/homepage).
"""

from typing import Dict, Any, List
from core.base_test import BaseTest, TestResult, TestState


class Category2Test(BaseTest):
    """Validate GPT category2 targeting on article-like pages (if used)."""

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

            return {
              pageType: pubads.getTargeting("pageType") || [],
              category1: pubads.getTargeting("category1") || [],
              category2: pubads.getTargeting("category2") || []
            };
          } catch (e) {
            return null;
          }
        }
        """
        payload = await page.evaluate(js)
        result.data = payload or {"pageType": [], "category1": [], "category2": []}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        data: Dict[str, Any] = result.data or {}
        page_type_vals: List[str] = data.get("pageType", [])
        page_type = (page_type_vals[0].lower() if page_type_vals else "").strip()

        if page_type in {"index", "homepage"}:
            result.state = TestState.SKIPPED
            result.warnings.append(
                f"pageType '{page_type}' treated as non-article; skipping Category2Test."
            )
            return result

        cat1_vals = [str(v).strip() for v in data.get("category1", []) if str(v).strip()]
        cat2_vals = [str(v).strip() for v in data.get("category2", []) if str(v).strip()]

        # If taxonomy uses only category1, treat as PASS
        if not cat2_vals and cat1_vals:
            result.state = TestState.PASSED
            return result

        if cat2_vals:
            result.state = TestState.PASSED
        else:
            result.state = TestState.FAILED
            result.errors.append(
                "category2 targeting present but empty / invalid for article-like page."
            )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return