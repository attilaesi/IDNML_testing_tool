# tests/gpt_tests/article_id_test.py

"""
gpt:article

What this test is meant to test
-------------------------------
Checks that GPT page-level targeting exposes a stable article identifier
for article pages (e.g. an "article" or "articleId" key), and that it
is non-empty and looks like a proper ID (not "undefined"/"null"/empty).

Test conditions
---------------
- googletag.pubads() must be present.
- The pageType targeting key (if present) is inspected; if it suggests
  an article-like page (e.g. "article", "video", "image"), we expect
  an article ID key to be present.

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - For article-like pageTypes, at least one article ID key is present
      with a non-empty value.
- FAILED:
    - For article-like pageTypes, all candidate article ID keys are
      missing or hold only empty / obviously invalid values.
- SKIPPED:
    - googletag.pubads() targeting cannot be read, or
    - pageType is clearly non-article (e.g. "index", "homepage").
"""

from typing import Dict, Any, List
from core.base_test import BaseTest, TestResult, TestState


class ArticleIdTest(BaseTest):
    """Validate GPT article identifier targeting on article-like pages."""

    CANDIDATE_KEYS = ["article", "articleid", "article_id", "content_id"]

    async def setup(self, page, url: str) -> bool:
        js = "(() => !!(window.googletag && googletag.pubads))()"
        has_gpt = await page.evaluate(js)
        return bool(has_gpt)

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        js = """
        () => {
          try {
            if (!window.googletag || !googletag.pubads) return null;
            const pubads = googletag.pubads();
            if (!pubads || !pubads.getTargetingKeys) return null;

            const out = {};
            const keys = pubads.getTargetingKeys() || [];
            keys.forEach(k => {
              out[k] = pubads.getTargeting(k) || [];
            });
            return out;
          } catch (e) {
            return null;
          }
        }
        """
        targeting = await page.evaluate(js)
        result.data = targeting or {}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        data: Dict[str, Any] = result.data or {}
        if not data:
            result.state = TestState.SKIPPED
            result.warnings.append("googletag.pubads() targeting not available.")
            return result

        # Check pageType
        page_type_vals = data.get("pageType") or data.get("pagetype") or []
        page_type = (page_type_vals[0].lower() if page_type_vals else "").strip()

        # Treat "index" / "homepage" as non-article; skip in that case
        if page_type in {"index", "homepage"}:
            result.state = TestState.SKIPPED
            result.warnings.append(f"pageType '{page_type}' treated as non-article; skipping ArticleIdTest.")
            return result

        # For all other pageTypes (including missing), we expect an article ID
        normalized: Dict[str, List[str]] = {}
        for key, vals in data.items():
            norm_key = key.lower()
            normalized[norm_key] = [str(v).strip() for v in (vals or [])]

        found_valid = False
        missing_keys: List[str] = []
        empty_keys: List[str] = []

        for cand in self.CANDIDATE_KEYS:
            vals = normalized.get(cand, [])
            if cand not in normalized:
                missing_keys.append(cand)
                continue

            # Filter out obviously bad values
            good = [
                v for v in vals
                if v and v.lower() not in {"null", "none", "undefined"}
            ]
            if good:
                found_valid = True
            else:
                empty_keys.append(cand)

        if found_valid:
            result.state = TestState.PASSED
        else:
            result.state = TestState.FAILED
            result.errors.append(
                "No valid article ID targeting found. "
                f"Missing keys: {', '.join(missing_keys)}; "
                f"empty/invalid keys: {', '.join(empty_keys)}"
            )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return