# tests/prebid_tests/bidder_presence_test.py

"""
prebid: BidderPresenceTest

What this test checks
---------------------
For the current page:

1. Looks at *actual Prebid bid requests* (not just ad unit config).
   - Tries, in order:
       - pbjs.getBidderRequests()
       - pbjs._bidsRequested
       - pbjs.getEvents() filtered to 'bidRequested'

2. Builds the set of bidder codes that actually emitted bid requests
   (e.g. "appnexus", "ix", "pubmatic", etc.).

3. Reads the `Locale` cookie (UK / US) to determine which expected bidder
   list to use (UK_BIDDERS / US_BIDDERS from config.test_settings).

4. Compares:
     expected vs seen

   - missing   = bidders in expected list that did *not* emit a bid request
   - unexpected = bidders that *did* emit a bid request but are not in the
                  expected list for this locale

PASS / FAIL logic
-----------------
* SKIPPED:
    - window.pbjs is missing

* FAILED:
    - Any missing bidders, or
    - Any unexpected bidders

* PASSED:
    - All expected bidders that should be active for this locale
      emitted at least one bid request, and there are no unexpected
      bidders.
"""

from typing import Any, Dict, List, Set

from core.base_test import BaseTest, TestResult, TestState

# 🔹 Expected bidders per locale (canonical bidder *codes*, not adapter names!)
# These should come from your central config so everything is in one place.
# Make sure UK_BIDDERS / US_BIDDERS look like: ["appnexus", "ix", "pubmatic", ...]
from config.test_settings import UK_BIDDERS, US_BIDDERS  # type: ignore


def _expected_bidders_for_locale(locale: str) -> List[str]:
    """Return expected bidder codes for this locale."""
    locale = (locale or "").upper()
    if locale == "US":
        return list(US_BIDDERS)
    # Default to UK config
    return list(UK_BIDDERS)


class BidderPresenceTest(BaseTest):
    """Presence of bidders that actually emit bid requests, per locale."""

    name = "BidderPresenceTest"

    async def setup(self, page, url: str) -> bool:
        """Basic DOM readiness; framework already waited for pbjs/GPT."""
        try:
            await page.wait_for_load_state("domcontentloaded")
            return True
        except Exception as e:
            if self.config.get("trace"):
                print(f"[BidderPresenceTest] setup error for {url}: {e}")
            return False

    async def execute(self, page, url: str) -> TestResult:
        """
        Collect bidder presence diagnostics from the page.

        We return:
          {
            hasPbjs: bool,
            locale: "UK" | "US" | null,
            biddersFromRequests: [ "appnexus", "ix", ... ],
            biddersFromAdUnits: [ "appnexus", "ix", ... ],
            source: "getBidderRequests" | "_bidsRequested" | "events" | null
          }
        """
        result = TestResult(self.name)
        result.url = url

        js = """
        () => {
          const out = {
            hasPbjs: !!window.pbjs,
            locale: null,
            biddersFromRequests: [],
            biddersFromAdUnits: [],
            source: null,
          };

          const w = window;
          const pbjs = w.pbjs;
          if (!pbjs) {
            return out;
          }

          // --- Locale from cookie ---
          try {
            const m = document.cookie.match(/(?:^|;\\s*)Locale=([^;]+)/i);
            if (m && m[1]) {
              out.locale = decodeURIComponent(m[1]).toUpperCase();
            }
          } catch (e) {
            // ignore; locale stays null
          }

          // --- Bidders from adUnits (config) ---
          try {
            const adUnits = Array.isArray(pbjs.adUnits) ? pbjs.adUnits : [];
            const adUnitSet = new Set();
            adUnits.forEach(u => {
              (u && Array.isArray(u.bids) ? u.bids : []).forEach(b => {
                if (b && typeof b.bidder === "string" && b.bidder.trim()) {
                  adUnitSet.add(b.bidder.trim());
                }
              });
            });
            out.biddersFromAdUnits = Array.from(adUnitSet);
          } catch (e) {
            // best-effort only
          }

          const reqSet = new Set();

          // Helper to add a bidder string safely
          const addBidder = (code) => {
            if (typeof code === "string") {
              const trimmed = code.trim();
              if (trimmed) reqSet.add(trimmed);
            }
          };

          // 1) Preferred: getBidderRequests()
          try {
            if (typeof pbjs.getBidderRequests === "function") {
              const reqs = pbjs.getBidderRequests() || [];
              reqs.forEach(r => {
                if (r && r.bidderCode) {
                  addBidder(r.bidderCode);
                } else if (r && r.bidder) {
                  addBidder(r.bidder);
                }
              });
            }
          } catch (e) {
            // ignore, fall back
          }

          if (reqSet.size) {
            out.source = "getBidderRequests";
            out.biddersFromRequests = Array.from(reqSet);
            return out;
          }

          // 2) Legacy: _bidsRequested
          try {
            const priv = Array.isArray(pbjs._bidsRequested) ? pbjs._bidsRequested : [];
            priv.forEach(r => {
              if (r && r.bidderCode) {
                addBidder(r.bidderCode);
              } else if (r && r.bidder) {
                addBidder(r.bidder);
              }
            });
          } catch (e) {
            // ignore
          }

          if (reqSet.size) {
            out.source = "_bidsRequested";
            out.biddersFromRequests = Array.from(reqSet);
            return out;
          }

          // 3) Fallback: events
          try {
            if (typeof pbjs.getEvents === "function") {
              const evts = pbjs.getEvents().filter(
                e => e && e.eventType === "bidRequested"
              );
              evts.forEach(e => {
                const a = e && e.args;
                if (!a) return;
                if (a.bidderCode) addBidder(a.bidderCode);
                else if (a.bidder) addBidder(a.bidder);
              });
            }
          } catch (e) {
            // ignore
          }

          if (reqSet.size) {
            out.source = "events";
          }

          out.biddersFromRequests = Array.from(reqSet);
          return out;
        }
        """

        diag = await page.evaluate(js)
        result.data = diag or {}

        if self.config.get("trace"):
            print(
                "[BidderPresenceTest] execute diag:",
                {
                    "url": url,
                    "hasPbjs": result.data.get("hasPbjs"),
                    "locale": result.data.get("locale"),
                    "source": result.data.get("source"),
                    "biddersFromRequests": result.data.get("biddersFromRequests", []),
                },
            )

        # Validation happens in validate()
        return result

    async def validate(self, result: TestResult) -> TestResult:
        """
        Compare bidders that actually emitted bid requests vs the expected
        list for this locale.
        """
        diag: Dict[str, Any] = result.data or {}
        has_pbjs: bool = bool(diag.get("hasPbjs"))
        locale: str = (diag.get("locale") or "UK").upper()
        seen_bidders: Set[str] = set(diag.get("biddersFromRequests") or [])

        if not has_pbjs:
            result.state = TestState.SKIPPED
            result.warnings.append(
                "window.pbjs not present; cannot run BidderPresenceTest."
            )
            return result

        expected_list = _expected_bidders_for_locale(locale)
        expected: Set[str] = set(expected_list)

        missing = sorted(expected - seen_bidders)
        unexpected = sorted(seen_bidders - expected)

        if missing or unexpected:
            result.state = TestState.FAILED

            if missing:
                result.errors.append(
                    f"Missing bidders for {locale}: " + ", ".join(missing)
                )
            if unexpected:
                result.errors.append(
                    f"Unexpected bidders present for {locale}: "
                    + ", ".join(unexpected)
                )
        else:
            result.state = TestState.PASSED

        # Helpful metadata for CSV / debug
        result.metadata.update(
            {
                "locale": locale,
                "expected_bidders": expected_list,
                "seen_bidders": sorted(seen_bidders),
                "missing_bidders": missing,
                "unexpected_bidders": unexpected,
                "source": diag.get("source"),
            }
        )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        """No-op for now; hook reserved for future debug screenshots if needed."""
        return