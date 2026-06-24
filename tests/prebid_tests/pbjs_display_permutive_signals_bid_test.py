"""
prebid: PbjsDisplayPermutiveSignalsBidTest

What this test checks
---------------------
Inspects outgoing Prebid bidder requests (RTB payload) to verify that Permutive RTD
signals are present for required bidders: ix, rubicon, msft, pubmatic.

Signals validated per required bidder:
  - user.ext.data.p_standard   (array of standard cohort IDs)
  - user.ext.data.permutive    (array of custom cohort IDs)
  - user.keywords              (contains p_standard=..., p_standard_aud=..., permutive=...)

Test conditions
---------------
- window.pbjs must be present (otherwise skipped).
- At least one required bidder must have made requests (otherwise skipped).

What counts as PASS / FAIL / ERROR
------------------------------------
- PASSED: all required bidders that made requests have the expected Permutive signal paths
  present with non-empty values.
- FAILED: a required bidder made requests but is missing one or more Permutive signal paths.
- FAILED: auction fired but none of the required Permutive-ecosystem bidders made requests.
- ERROR:  window.pbjs not found on page — Prebid did not load.
- ERROR:  Prebid loaded but no display bid requests captured — auction did not fire.
"""

from pathlib import Path
from typing import Dict, List, Any

from core.base_test import BaseTest, TestResult, TestState

_JS_TEMPLATE = (Path(__file__).parent.parent / "js" / "pbjs_display_permutive_signals_bid.js").read_text()

class PbjsDisplayPermutiveSignalsBidTest(BaseTest):

    """Checks Permutive signals inside bid requests."""

    # Only these bidders are validated
    REQUIRED_BIDDERS: List[str] = [ "ix", "rubicon", "msft", "pubmatic"]

    # ORTB2 paths we inspect and record into diag
    PATH_KEYS: List[str] = [
        "site.ext.permutive",
        "site.ext.permutive.p_standard",
        "user.ext.data.p_standard",
        "user.ext.data.permutive",
        "user.data[0].name",
        "user.data[1].name",
        "user.keywords",
    ]

    PERMUTIVE_EXPECTATIONS: Dict[str, Dict[str, Dict[str, Any]]] = {
        bidder: {
            "user.ext.data.p_standard": {"required": True},
            "user.ext.data.permutive": {"required": True},
            "user.keywords": {
                "required": True,
                "tokens_all": ["p_standard=", "p_standard_aud=", "permutive="],
            },
        }
        for bidder in REQUIRED_BIDDERS
    }

    # --- Token match helpers ---

    @staticmethod
    def _sample_has_token(sample: List[str], token: str) -> bool:
        if not sample:
            return False

        token = token.lower()
        for raw in sample:
            txt = str(raw).lower()

            if token in ("permutive", "p_standard", "p_standard_aud"):
                if token in txt:
                    return True
            else:
                if token in txt:
                    return True

        return False

    # --- Setup ---

    async def setup(self, page, url: str) -> bool:
        return True

    # --- Execute ---

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        import json
        js = _JS_TEMPLATE.replace("__REQUIRED_BIDDERS__", json.dumps(self.REQUIRED_BIDDERS))

        diag = await page.evaluate(js)
        result.data = diag or {}

        if self.config.get("trace"):
            print(
                "[PbjsPermutiveSignalsBidTest] execute diag summary: "
                + f'hasPbjs={bool(diag.get("hasPbjs"))}, '
                + f'totalRequests={diag.get("totalRequests", 0)}, '
                + f"requiredBidders={(diag.get('requiredBidders') or [])}, "
                + f"biddersSeen={(diag.get('biddersSeen') or [])}, "
                + f"ignoredBidders={(diag.get('ignoredBidders') or [])}"
            )

        return result

    # --- Validate ---

    async def validate(self, result: TestResult) -> TestResult:
        diag = result.data or {}

        if not diag.get("hasPbjs"):
            result.state = TestState.ERROR
            result.errors.append("window.pbjs not found on page — Prebid did not load.")
            return result

        if diag.get("totalRequests", 0) == 0:
            result.state = TestState.ERROR
            result.errors.append(
                "Prebid loaded but no display bid requests were captured — "
                "display auction did not fire (check pbjs_display_auction_activity for root cause)."
            )
            return result

        per_bidder = diag.get("perBidder", {}) or {}

        # Auction fired but required Permutive-ecosystem bidders made no requests — assertion failure.
        if not any((per_bidder.get(b) or {}).get("requestCount", 0) > 0 for b in self.REQUIRED_BIDDERS):
            result.state = TestState.FAILED
            result.errors.append(
                "Display auction fired but none of the required Permutive-ecosystem bidders made requests: "
                + ", ".join(self.REQUIRED_BIDDERS)
            )
            return result

        any_fail = False
        summary: List[str] = []

        for bidder in self.REQUIRED_BIDDERS:
            info = per_bidder.get(bidder)
            if not info or info.get("requestCount", 0) == 0:
                summary.append(f"{bidder}: SKIPPED (no requests)")
                continue

            failures: List[str] = []
            passes: List[str] = []

            expectations = self.PERMUTIVE_EXPECTATIONS.get(bidder, {})
            paths_info = info.get("paths", {}) or {}

            for path, rules in expectations.items():
                path_obs = paths_info.get(path, {}) or {}
                seen = bool(path_obs.get("seen"))
                sample = path_obs.get("sample") or []

                required = bool(rules.get("required"))
                tokens_all: List[str] = rules.get("tokens_all") or []
                tokens_any: List[str] = rules.get("tokens_any") or []

                path_failures: List[str] = []

                if required and not seen:
                    path_failures.append("missing")
                elif seen:
                    if tokens_all:
                        missing = [t for t in tokens_all if not self._sample_has_token(sample, t)]
                        if missing:
                            path_failures.append(f"missing tokens {', '.join(missing)}")

                    if tokens_any:
                        if not any(self._sample_has_token(sample, t) for t in tokens_any):
                            path_failures.append(f"no tokens from {', '.join(tokens_any)}")

                if path_failures:
                    failures.append(f"{path}: {'; '.join(path_failures)}")
                else:
                    # mark as present / passing only if the check actually succeeded
                    if seen:
                        passes.append(path)

            if failures:
                any_fail = True
                if passes:
                    summary.append(
                        f"{bidder}: FAIL ({'; '.join(failures)}; present: {', '.join(passes)})"
                    )
                else:
                    summary.append(f"{bidder}: FAIL ({'; '.join(failures)})")
            else:
                if passes:
                    summary.append(f"{bidder}: PASS ({', '.join(passes)})")
                else:
                    summary.append(f"{bidder}: PASS")

        if any_fail:
            result.state = TestState.FAILED
            result.errors.append(" | ".join(s for s in summary if "FAIL" in s))
        else:
            result.state = TestState.PASSED
            result.warnings.append("PASSED\n" + "\n".join(summary))

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return