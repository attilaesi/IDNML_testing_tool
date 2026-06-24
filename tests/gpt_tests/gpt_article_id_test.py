# tests/gpt_tests/gpt_article_id_test.py

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

What counts as PASS / FAIL / SKIPPED / N/A
------------------------------------------
- PASSED:
    - For article-like pageTypes, at least one article ID key is present
      with a non-empty value.
- FAILED:
    - For article-like pageTypes, all candidate article ID keys are
      missing or hold only empty / obviously invalid values.
- SKIPPED:
    - googletag.pubads() targeting cannot be read.
- N/A:
    - pageType is index or homepage — article ID is not expected on non-article pages.
"""

from pathlib import Path
from typing import Dict, Any, List
from core.gpt_base_test import GptBaseTest
from core.base_test import TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "gpt_article_id.js").read_text()

class GptArticleIdTest(GptBaseTest):

    """Validate GPT article identifier targeting on article-like pages."""

    CANDIDATE_KEYS = ["article", "articleid", "article_id", "content_id"]

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        targeting = await page.evaluate(_JS)
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

        # Treat "index" / "homepage" as non-article; not applicable
        if page_type in {"index", "homepage"}:
            result.state = TestState.NOT_APPLICABLE
            result.warnings.append(f"pageType '{page_type}' — article ID not expected on non-article pages.")
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