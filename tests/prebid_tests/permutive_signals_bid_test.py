# tests/prebid_tests/permutive_signals_bid_test.py
"""
prebid: PermutiveSignalsBidTest

What this test is meant to test
-------------------------------
Checks whether outgoing Prebid bidder requests contain **both** of the
Permutive RTD segment arrays for key bidders (appnexus, ix, pubmatic, rubicon):

  - ortb2.user.ext.data.pstandard  (standard cohorts)
  - ortb2.user.ext.data.permutive (custom cohorts)

We inspect the bidder *requests* (RTB payload) rather than just the global
Prebid config, because that is what actually goes to the exchanges.

Test conditions
---------------
1. Prebid (window.pbjs) must be present on the page.
2. Prebid must expose bidder request objects via one of:
     - pbjs.getBidderRequests()
     - pbjs._bidsRequested
     - pbjs.getEvents() entries of type 'bidRequested'
3. For each "required" bidder (appnexus, ix, pubmatic, rubicon) that has at
   least one recorded request, we check if BOTH pstandard and permutive arrays
   are present and non-empty under ortb2.user.ext.data.

Pass / Fail / Skipped semantics
-------------------------------
* SKIPPED:
    - window.pbjs is missing, or
    - No bidder requests are visible at all (none of the APIs above return any).

* FAILED:
    - At least one required bidder has recorded requests but does NOT have both
      pstandard and permutive arrays populated.

* PASSED:
    - For every required bidder that has recorded requests, BOTH arrays are
      present and non-empty.
    - Required bidders that have no recorded requests are *warned* about but
      do not cause the test to fail (so pages without that bidder configured
      don’t automatically fail).

Reporting
---------
The CSV output for this test will include, in the cell for each URL, a multi-
line summary like:

    FAILED
    appnexus: FAIL (missing pstandard)
    ix: PASS (pstandard, permutive)
    pubmatic: FAIL (missing permutive)
    rubicon: PASS (pstandard, permutive)

so you can see per-bidder status at a glance.
"""

from typing import Dict, List, Any

from core.base_test import BaseTest, TestResult, TestState


class PermutiveSignalsBidTest(BaseTest):
    """See module docstring for full explanation."""

    # Bidders we expect to carry Permutive segments in their requests
    REQUIRED_BIDDERS: List[str] = ["appnexus", "ix", "pubmatic", "rubicon"]

    async def setup(self, page, url: str) -> bool:
        """
        Setup phase.

        Conditions:
        - We assume CMP / consent etc. are already handled by the framework.
        - We simply check that window.pbjs exists; if not, we skip.
        """
        has_pbjs = await page.evaluate("() => !!window.pbjs")
        if self.config.get("trace_tests"):
            print(
                f"[PermutiveSignalsBidTest] setup: "
                f"url={url}, has_pbjs={has_pbjs}"
            )
        if not has_pbjs:
            # No Prebid at all — nothing meaningful to test at bid level
            return False
        return True

    async def execute(self, page, url: str) -> TestResult:
        """
        Execute phase.

        We collect a diagnostic structure from the page that summarises:
        - whether pbjs is present
        - total number of bidder requests visible
        - for each bidder, whether pstandard and permutive were present.
        """
        result = TestResult(self.name)
        result.url = url

        js = """
        () => {
          const w = window;
          const diag = {
            hasPbjs: !!w.pbjs,
            totalRequests: 0,
            // perBidder[code] = {
            //   pstandard: boolean,
            //   permutive: boolean,
            //   pstandard_sample: [...],
            //   permutive_sample: [...]
            // }
            perBidder: {}
          };

          if (!w.pbjs) {
            return diag;
          }

          // Collect bidder requests from multiple possible APIs.

          // 1) Standard Prebid API
          const fromGetter =
            (typeof w.pbjs.getBidderRequests === 'function')
              ? (w.pbjs.getBidderRequests() || [])
              : [];

          // 2) Legacy private array
          const fromPrivate = Array.isArray(w.pbjs._bidsRequested)
            ? w.pbjs._bidsRequested
            : [];

          // 3) Events (newer wrappers sometimes put full ORTB2 in events)
          let fromEvents = [];
          try {
            if (typeof w.pbjs.getEvents === 'function') {
              fromEvents = (w.pbjs.getEvents() || [])
                .filter(e => e && e.eventType === 'bidRequested')
                .map(e => e.args || {})
                .filter(Boolean);
            }
          } catch (e) {
            // best effort; ignore
          }

          const allReqs = [...fromGetter, ...fromPrivate, ...fromEvents];
          if (!allReqs.length) {
            return diag;
          }

          diag.totalRequests = allReqs.length;

          const ensureBidder = (code) => {
            if (!diag.perBidder[code]) {
              diag.perBidder[code] = {
                pstandard: false,
                permutive: false,
                pstandard_sample: [],
                permutive_sample: []
              };
            }
          };

          allReqs.forEach(req => {
            const bidder = req.bidderCode || req.bidder || 'unknown';

            // Try to read ORTB2 user object from the request.
            const ortb2 = req.ortb2 || {};
            const user = ortb2.user || {};
            const userExt = user.ext || {};
            const extData = userExt.data || {};

            // pstandard may be under `pstandard` or older `p_standard`
            let pstandardArr = null;
            if (Array.isArray(extData.pstandard)) {
              pstandardArr = extData.pstandard;
            } else if (Array.isArray(extData.p_standard)) {
              pstandardArr = extData.p_standard;
            }

            const permutiveArr = Array.isArray(extData.permutive)
              ? extData.permutive
              : null;

            if (pstandardArr && pstandardArr.length) {
              ensureBidder(bidder);
              const b = diag.perBidder[bidder];
              b.pstandard = true;
              if (!b.pstandard_sample.length) {
                b.pstandard_sample = pstandardArr.slice(0, 5);
              }
            }

            if (permutiveArr && permutiveArr.length) {
              ensureBidder(bidder);
              const b = diag.perBidder[bidder];
              b.permutive = true;
              if (!b.permutive_sample.length) {
                b.permutive_sample = permutiveArr.slice(0, 5);
              }
            }
          });

          return diag;
        }
        """

        diag = await page.evaluate(js)
        result.data = diag or {}

        if self.config.get("trace_tests"):
            bidders_with_both = {
                code: info
                for code, info in (diag.get("perBidder") or {}).items()
                if info.get("pstandard") and info.get("permutive")
            }
            print(
                "[PermutiveSignalsBidTest] execute diag summary: "
                + f'{{"hasPbjs": {bool(diag.get("hasPbjs"))}, '
                + f'"totalRequests": {diag.get("totalRequests", 0)}, '
                + f'"bidders_with_both": {list(bidders_with_both.keys())}}}'
            )

        # State will be decided in validate()
        return result

    async def validate(self, result: TestResult) -> TestResult:
        diag: Dict[str, Any] = result.data or {}
        has_pbjs = diag.get("hasPbjs", False)
        total_requests = diag.get("totalRequests", 0)
        per_bidder: Dict[str, Dict[str, Any]] = diag.get("perBidder", {}) or {}

        if self.config.get("trace_tests"):
            print(
                "[PermutiveSignalsBidTest] validate input: "
                + f'{{"hasPbjs": {has_pbjs}, '
                + f'"totalRequests": {total_requests}, '
                + f'"perBidder_keys": {list(per_bidder.keys())}}}'
            )

        if not has_pbjs:
            result.state = TestState.SKIPPED
            result.warnings.append(
                "window.pbjs not present; no bid requests to inspect."
            )
            return result

        if total_requests == 0:
            result.state = TestState.SKIPPED
            result.warnings.append(
                "No bidder requests exposed; cannot verify Permutive signals."
            )
            return result

        missing_any: List[str] = []
        summary_lines: List[str] = []

        for bidder in self.REQUIRED_BIDDERS:
            info = per_bidder.get(bidder)

            if not info:
                summary_lines.append(f"{bidder}: SKIPPED (no recorded requests)")
                result.warnings.append(
                    f"Bidder '{bidder}' not present on this page."
                )
                continue

            has_pstandard = bool(info.get("pstandard"))
            has_permutive = bool(info.get("permutive"))

            if has_pstandard and has_permutive:
                summary_lines.append(
                    f"{bidder}: PASS (pstandard, permutive present)"
                )
            else:
                missing_parts = []
                if not has_pstandard:
                    missing_parts.append("pstandard")
                if not has_permutive:
                    missing_parts.append("permutive")

                summary_lines.append(
                    f"{bidder}: FAIL (missing {', '.join(missing_parts)})"
                )
                missing_any.append(f"{bidder} ({', '.join(missing_parts)})")

        if missing_any:
            result.state = TestState.FAILED

            cell_text = ["FAILED"]
            cell_text.extend(summary_lines)

            # ★ NEW CLEAN BLOCKED FORMATTING ★
            result.errors.append("\n".join(cell_text))

        else:
            result.state = TestState.PASSED

            cell_text = ["PASSED"]
            cell_text.extend(summary_lines)

            result.warnings.append("\n".join(cell_text))

        if self.config.get("trace_tests"):
            print(
                f"[PermutiveSignalsBidTest] result: {result.state.name}\n"
                + "\n".join(summary_lines)
            )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        """
        Cleanup phase.

        Currently a no-op for this test. Hook is kept so that in future we can:
        - capture debug screenshots on failure
        - dump diag structures to a log file, etc.
        """
        return