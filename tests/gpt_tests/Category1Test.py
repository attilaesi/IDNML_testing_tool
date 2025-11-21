# tests/gpt_tests/category1_test.py

"""
gpt:category1

What this test is meant to test
-------------------------------
Checks that GPT targeting key "category1" (top-level section/category)
is present and non-empty on article-like pages.

Test conditions
---------------
- googletag.pubads() must be present.
- If pageType is article-like (article, video, image) we expect
  category1 to be set.

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - category1 has at least one non-empty value on article-like pages, or
    - pageType clearly non-article (index/homepage) -> SKIPPED.
- FAILED:
    - For article-like pages, category1 is missing or only empty strings.
- SKIPPED:
    - GPT targeting not available.
"""

from typing import Dict, Any, List
from core.base_test import BaseTest, TestResult, TestState


class Category1Test(BaseTest):
    """Validate GPT category1 targeting on article-like pages."""

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
              category1: pubads.getTargeting("category1") || []
            };
          } catch (e) {
            return null;
          }
        }
        """
        payload = await page.evaluate(js)
        result.data = payload or {"pageType": [], "category1": []}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        data: Dict[str, Any] = result.data or {}
        page_type_vals: List[str] = data.get("pageType", [])
        page_type = (page_type_vals[0].lower() if page_type_vals else "").strip()

        # Non-article pageTypes: skip
        if page_type in {"index", "homepage"}:
            result.state = TestState.SKIPPED
            result.warnings.append(
                f"pageType '{page_type}' treated as non-article; skipping Category1Test."
            )
            return result

        vals: List[str] = [str(v).strip() for v in data.get("category1", [])]
        vals = [v for v in vals if v]

        if vals:
            result.state = TestState.PASSED
        else:
            result.state = TestState.FAILED
            result.errors.append(
                "category1 targeting missing or empty on article-like page."
            )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return