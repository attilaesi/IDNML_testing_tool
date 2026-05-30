# tests/gpt_tests/gpt_untested_keys_test.py

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

from pathlib import Path
from typing import List, Set
from core.gpt_base_test import GptBaseTest
from core.base_test import TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "gpt_untested_keys.js").read_text()

class GptUntestedKeysTest(GptBaseTest):

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

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        keys = await page.evaluate(_JS)
        result.data = {"keys": keys or []}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        keys: List[str] = [str(k) for k in (result.data or {}).get("keys", [])]
        if not keys:
            result.state = TestState.SKIPPED
            result.warnings.append("No GPT targeting keys available; skipping GptUntestedKeysTest.")
            return result

        untested = [k for k in keys if k not in self.KNOWN_KEYS]

        result.state = TestState.PASSED
        if untested:
            result.warnings.append(
                "Untested GPT targeting keys detected: " + ", ".join(sorted(untested))
            )

        return result