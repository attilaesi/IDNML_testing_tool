# tests/prebid_tests/pbjs_mantis_signals_bid_test.py
"""
prebid: PbjsMantisSignalsBidTest

What this test checks
---------------------
Inspects outgoing Prebid bidder requests (RTB payload) to verify that Mantis contextual
signals are present in every bidder's request:
  - site.ext.data.mantis        (brand safety labels, e.g. "Technology-GREEN")
  - site.ext.data.mantis_context (topic tokens, e.g. "tech_news")

Test conditions
---------------
- window.pbjs must be present (otherwise skipped).
- At least one bidder must have made requests (otherwise skipped).
- Both paths must exist, be non-empty arrays, and match expected formats:
    - mantis: entries matching <label>-<GREEN|AMBER|RED>
    - mantis_context: lowercase snake_case tokens

What counts as PASS / FAIL / SKIP
-----------------------------------
- PASSED: both site.ext.data.mantis and site.ext.data.mantis_context are present,
  non-empty arrays with correctly formatted entries for every bidder that made requests.
- FAILED: either path is missing, wrong type, empty, or contains malformed entries.
- SKIPPED: window.pbjs missing or no bidder requests found.
"""

from pathlib import Path
from typing import List, Any, Dict
import re

from core.base_test import BaseTest, TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "pbjs_mantis_signals_bid.js").read_text()

class PbjsMantisSignalsBidTest(BaseTest):

    # ORTB2 paths we inspect and record into diag
    PATH_KEYS: List[str] = [
        "site.ext.data.mantis",
        "site.ext.data.mantis_context",
    ]

    # Expectations (same rules for all bidders)
    EXPECTATIONS: Dict[str, Dict[str, Any]] = {
        "site.ext.data.mantis": {"required": True},
        "site.ext.data.mantis_context": {"required": True},
    }

    # Strict patterns (Option C)
    _MANTIS_ENTRY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*-(GREEN|AMBER|RED)$")
    _MANTIS_CONTEXT_ENTRY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

    # --- Setup ---

    async def setup(self, page, url: str) -> bool:
        has_pbjs = await page.evaluate("() => !!window.pbjs")
        return bool(has_pbjs)

    # --- Execute ---

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        diag = await page.evaluate(_JS)
        result.data = diag or {}

        if self.config.get("trace"):
            print(
                "[PbjsMantisSignalsBidTest] execute diag summary: "
                + f'hasPbjs={bool(diag.get("hasPbjs"))}, '
                + f'totalRequests={diag.get("totalRequests", 0)}, '
                + f"biddersSeen={(diag.get('biddersSeen') or [])}, "
                + f'eventsLen={(diag.get("debug") or {}).get("eventsLen", 0)}, '
                + f'eventTypes={(diag.get("debug") or {}).get("eventTypes", [])}'
            )

            per_bidder = (diag.get("perBidder") or {})
            for bidder, info in per_bidder.items():
                paths = info.get("paths") or {}

                def s(path):
                    p = paths.get(path) or {}
                    return {
                        "seen": bool(p.get("seen")),
                        "type": p.get("type"),
                        "count": p.get("count"),
                        "sample": (p.get("sample") or [])[:10],
                    }

                print(
                    f"[PbjsMantisSignalsBidTest] bidder={bidder}, "
                    f"requests={info.get('requestCount', 0)}, "
                    f"mantis={s('site.ext.data.mantis')}, "
                    f"mantis_context={s('site.ext.data.mantis_context')}"
                )

        return result

    # --- Validate ---

    async def validate(self, result: TestResult) -> TestResult:
        diag = result.data or {}

        if not diag.get("hasPbjs"):
            result.state = TestState.SKIPPED
            result.warnings.append("pbjs not present")
            return result

        if diag.get("totalRequests", 0) == 0:
            result.state = TestState.SKIPPED
            result.warnings.append("No bidder requests found")
            return result

        per_bidder = diag.get("perBidder", {}) or {}
        bidders = list(per_bidder.keys())

        if not bidders:
            result.state = TestState.SKIPPED
            result.warnings.append("No bidders found in requests")
            return result

        any_fail = False
        summary: List[str] = []

        def _validate_array(path_name: str, obs: Dict[str, Any]) -> List[str]:
            """Structural checks for Option C."""
            errs: List[str] = []
            seen = bool(obs.get("seen"))
            typ = obs.get("type")
            count = int(obs.get("count") or 0)

            if not seen:
                errs.append(f"{path_name}: missing")
                return errs

            if typ != "array":
                errs.append(f"{path_name}: wrong type (expected array, got {typ})")
                return errs

            if count <= 0:
                errs.append(f"{path_name}: empty array")
                return errs

            return errs

        # Tests ALL bidders observed
        for bidder in sorted(bidders):
            info = per_bidder.get(bidder) or {}
            if info.get("requestCount", 0) == 0:
                summary.append(f"{bidder}: SKIPPED (no requests)")
                continue

            failures: List[str] = []
            paths_info = info.get("paths", {}) or {}

            mantis_obs = paths_info.get("site.ext.data.mantis", {}) or {}
            mantis_ctx_obs = paths_info.get("site.ext.data.mantis_context", {}) or {}

            # 1) Presence + type(array) + non-empty
            failures.extend(_validate_array("site.ext.data.mantis", mantis_obs))
            failures.extend(_validate_array("site.ext.data.mantis_context", mantis_ctx_obs))

            # 2) Pattern validation (only if structural checks passed)
            if not failures:
                mantis_vals = [str(x) for x in (mantis_obs.get("sample") or []) if str(x)]
                mantis_ctx_vals = [str(x) for x in (mantis_ctx_obs.get("sample") or []) if str(x)]

                bad_mantis = [v for v in mantis_vals if not self._MANTIS_ENTRY_RE.match(v)]
                bad_ctx = [v for v in mantis_ctx_vals if not self._MANTIS_CONTEXT_ENTRY_RE.match(v)]

                if bad_mantis:
                    failures.append(
                        "site.ext.data.mantis: invalid entries (sample) -> "
                        + ", ".join(bad_mantis[:10])
                        + (" ..." if len(bad_mantis) > 10 else "")
                    )

                if bad_ctx:
                    failures.append(
                        "site.ext.data.mantis_context: invalid entries (sample) -> "
                        + ", ".join(bad_ctx[:10])
                        + (" ..." if len(bad_ctx) > 10 else "")
                    )

            if failures:
                any_fail = True
                summary.append(f"{bidder}: FAIL ({'; '.join(failures)})")
            else:
                summary.append(f"{bidder}: PASS")

        if any_fail:
            result.state = TestState.FAILED
            result.errors.append("FAILED\n" + "\n".join(summary))
        else:
            result.state = TestState.PASSED
            result.warnings.append("PASSED\n" + "\n".join(summary))

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return