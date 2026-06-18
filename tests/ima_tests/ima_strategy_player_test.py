"""
ima:strategy_player

What this test is meant to test
--------------------------------
Captures which JW Player strategy rules profile was selected for the
hero player.  The player logs the decision to the console as:
  "Strategy Rules <profile name>"

Known profiles: Premium player, Commercial player, Sensitive player,
Bulletin hero player, Default player with sound on, Default player
with sound off.

This is an informational test — it records which player profile was
active so the value appears in trace output and the results sheet,
enabling regression detection if the profile selection changes unexpectedly.

Test conditions
---------------
- Page must be identified as a video page (GPT pageType == "video_article"
  or similar).
- The JW Player must have initialised and emitted a strategy rules console
  log before the test timeout.

What counts as PASS / FAIL / SKIPPED
--------------------------------------
- PASSED:
    - A JW Player strategy rules profile name was captured from the console log.
- FAILED:
    - No strategy rules log was found — player may not have initialised
      or the console log format changed.
- SKIPPED:
    - Page is not a video page so no player is expected.
"""

from core.base_test import VideoOnlyTest, TestResult, TestState


class ImaStrategyPlayerTest(VideoOnlyTest):

    """Record the JW Player strategy rules profile in use on video pages."""

    async def _video_setup(self, page, url: str) -> bool:
        return True

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url
        player = await page.evaluate("window.__strategyPlayer || null")
        result.data = {"strategy_player": player}
        if self.config.get("trace") and player:
            print(f"[{self.name}] Strategy player: {player}")
        return result

    async def validate(self, result: TestResult) -> TestResult:
        player = (result.data or {}).get("strategy_player")
        if not player:
            result.state = TestState.FAILED
            result.errors.append("No JW Player strategy rules log captured.")
            return result
        result.state = TestState.PASSED
        return result
