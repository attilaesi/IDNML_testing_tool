# tests/gpt_tests/untested_keys_test.py

"""
gpt:untested_keys

What this test is meant to test
-------------------------------
Meta-test that enumerates all GPT targeting keys and lists any keys
that are not explicitly covered by a known set of GPT tests.

This helps you spot new / unexpected targeting keys, without failing
the run.

Test conditions
---------------
- googletag.pubads() must be present.

What counts as PASS / FAIL / SKIPPED
------------------------------------
- PASSED:
    - Always, if GPT is available. We only record untested keys in
      result.warnings so you can inspect them in CSV/logs.
- SKIPPED:
    - GPT targeting not available.
"""

from typing import Dict, Any, List, Set
from core.base_test import BaseTest, TestResult, TestState


class UntestedKeysTest(BaseTest):
    """List GPT targeting keys that have no explicit test."""

    # Keep this in sync with your actual GPT-test key coverage
    KNOWN_KEYS: Set[str] = {
        "pageType",
        "article",
        "articleId",
        "article_id",
        "content_id",
        "category1",
        "category2",
        "commercial",
        "liveblog",
        "longread",
        "reg_gate",
        "testgroup",
        "topictags",
        "mantis",
        "mantis_context",
        "gdpr",
        "autorefresh",
        "cmpActive",
        "contentSources",
        "referrer",
        "permutive",
        "AnonymisedSignalLift",
    }

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
            if (!pubads || !pubads.getTargetingKeys) return null;
            return pubads.getTargetingKeys() || [];
          } catch (e) {
            return null;
          }
        }
        """
        keys = await page.evaluate(js)
        result.data = {"keys": keys or []}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        keys: List[str] = [str(k) for k in (result.data or {}).get("keys", [])]
        if not keys:
            result.state = TestState.SKIPPED
            result.warnings.append("No GPT targeting keys available; skipping UntestedKeysTest.")
            return result

        untested = [k for k in keys if k not in self.KNOWN_KEYS]

        result.state = TestState.PASSED
        if untested:
            result.warnings.append(
                "Untested GPT targeting keys detected: " + ", ".join(sorted(untested))
            )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return