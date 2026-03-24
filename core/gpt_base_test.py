# core/gpt_base_test.py
#
# Base class for GPT targeting tests. Provides the standard setup
# (check googletag.pubads is available) and a no-op cleanup so that
# individual tests only need to implement execute() and validate().

from core.base_test import BaseTest, TestResult


class GptBaseTest(BaseTest):
    """Base for GPT tests that require googletag.pubads()."""

    async def setup(self, page, url: str) -> bool:
        js = "(() => !!(window.googletag && googletag.pubads))()"
        return bool(await page.evaluate(js))

    async def cleanup(self, page, result: TestResult) -> None:
        return
