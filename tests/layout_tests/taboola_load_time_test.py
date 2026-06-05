# tests/layout_tests/taboola_load_time_test.py

"""
taboola: TaboolaLoadTimeTest

What this test checks
---------------------
Measurement probe for Taboola render timing — not a pass/fail correctness test.
Tracks three specific placements by container ID:
  - taboola-mid-article-thumbnails-ii   (mid-article, hybrid)
  - taboola-carousel-thumbnails          (carousel, sponsored)
  - taboola-mid-article-thumbnails-iii  (second mid-article, hybrid)

A placement is considered "rendered" when Taboola has injected a .trc_rbox_container
child into its anchor div. Timings are measured as deltas from loader.js responseEnd
(Resource Timing API) and relative to navigation start.

Test conditions
---------------
- Taboola loader.js must appear in the Resource Timing entries; otherwise skipped.

What counts as PASS / FAIL / SKIP
-----------------------------------
- PASSED: Taboola loader.js found; render timings reported as informational warnings.
- SKIPPED: loader.js not found in Resource Timing (Taboola not active on this page).
"""

from pathlib import Path
from typing import Dict, Any
from core.base_test import BaseTest, TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "taboola_load_time.js").read_text()


PLACEMENTS = [
    ("mid_article_ii",  "taboola-mid-article-thumbnails-ii"),
    ("carousel",        "taboola-carousel-thumbnails"),
    ("mid_article_iii", "taboola-mid-article-thumbnails-iii"),
]


class TaboolaLoadTimeTest(BaseTest):

    async def setup(self, page, url: str) -> bool:
        loader_url = self.config.get("taboola_loader_url", "")
        has_loader = await page.evaluate(
            """(loaderUrl) => {
                return performance.getEntriesByType("resource").some(
                    function(e) { return e.name.indexOf(loaderUrl) !== -1; }
                );
            }""",
            loader_url,
        )
        return bool(has_loader)

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        timeout_ms = int(self.config.get("taboola_wait_timeout", 15)) * 1000

        # Build a JS array of [key, containerId] pairs to pass in
        placement_pairs = [[key, cid] for key, cid in PLACEMENTS]

        loader_url = self.config.get("taboola_loader_url", "")
        page.set_default_timeout(timeout_ms + 5000)
        data = await page.evaluate(_JS, [loader_url, timeout_ms, placement_pairs])
        result.data = data or {}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        data: Dict[str, Any] = result.data or {}

        if not data.get("loaderPresent", False):
            result.state = TestState.SKIPPED
            result.warnings.append("Taboola loader script not found on page")
            return result

        t_script_start = data.get("tScriptStart", 0)
        t_script       = data.get("tScript", 0)
        deltas         = data.get("deltas") or {}
        timed_out      = data.get("timedOutAfterMs", 0)

        result.state = TestState.PASSED

        print(f"         📡 Taboola  loader started: {t_script_start}ms  |  loader ready: {t_script}ms  (from page start)")
        for key, cid in PLACEMENTS:
            delta = deltas.get(key)
            val   = f"+{delta}ms" if delta is not None else f"NOT LOADED (waited {timed_out}ms)"
            print(f"            {cid:<42}  {val}")

        result.metadata["t_script_start_ms"] = t_script_start
        result.metadata["t_script_ms"]        = t_script
        result.metadata["timed_out_ms"]        = timed_out
        for key, _ in PLACEMENTS:
            result.metadata[f"delta_{key}_ms"] = deltas.get(key)

        return result
