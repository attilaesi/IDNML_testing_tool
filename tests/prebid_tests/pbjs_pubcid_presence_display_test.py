"""
prebid: PbjsDisplayPubcidPresenceTest

What this test checks
---------------------
Validates that PubCommonId (pubcid) is present in every display bidder's requests.
Inspects bids in window.__pbjsBidEventsDisplay for userId.pubCommonId or a matching
userIdAsEids entry (source hints pubcommon / pubcid).

Test conditions
---------------
- window.pbjs must be present (otherwise skipped).
- DISPLAY bidRequested events must have been captured.

What counts as PASS / FAIL / SKIP
-----------------------------------
- PASSED: every display bidder has pubcid in at least one of its bids.
- FAILED: pbjs present but no DISPLAY bidRequested events captured.
- FAILED: at least one display bidder is missing pubcid across all of its bids.
- SKIPPED: window.pbjs not present on the page.
"""
from pathlib import Path
from core.base_test import BaseTest, TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "pbjs_pubcid_presence_display.js").read_text()

class PbjsDisplayPubcidPresenceTest(BaseTest):

    """
    Validate PubCommonId (pubcid) for DISPLAY auctions only.

    Rule:
      PASS only if *every bidder* that appears in DISPLAY bidRequested bids
      has pubcid present in at least one of its bids.

    In-scope bidders:
      - derived from bids in window.__pbjsBidEventsDisplay (type="bidRequested")

    pubcid can be present via:
      a) bid.userId.pubCommonId   (string or {id:"..."} shape)
      OR
      b) bid.userIdAsEids contains an eid whose source hints pubcommon/pubcid
         and has at least one uid.id.

    FAIL:
      - pbjs exists but no DISPLAY bidRequested events captured
      - OR at least one DISPLAY bidder missing pubcid

    SKIP:
      - window.pbjs missing
    """

    name = "PbjsDisplayPubcidPresenceTest"

    async def setup(self, page, url: str) -> bool:
        return True

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        data = await page.evaluate(_JS)

        result.data = {
            "hasPbjs": data.get("hasPbjs"),
            "pbjsVersion": data.get("pbjsVersion"),
            "store": data.get("store"),
            "eventsLen": data.get("eventsLen"),
            "bidRequestedEvents": data.get("bidRequestedEvents"),
            "bidsScanned": data.get("bidsScanned"),
            "biddersSeen": data.get("biddersSeen"),
            "biddersWithPubcid": data.get("biddersWithPubcid"),
            "biddersMissingPubcid": data.get("biddersMissingPubcid"),
            # keep perBidder small; still useful for debugging
            "perBidder": data.get("perBidder"),
        }

        if not data.get("hasPbjs"):
            result.state = TestState.SKIPPED
            result.errors.append("window.pbjs not found; cannot validate pubcid in display bids.")
            return result

        if int(data.get("bidRequestedEvents") or 0) == 0:
            result.state = TestState.FAILED
            result.errors.append("No DISPLAY bidRequested events captured; cannot confirm pubcid for display bidders.")
            return result

        missing = data.get("biddersMissingPubcid") or []
        if missing:
            result.state = TestState.FAILED
            result.errors.append(f"pubcid missing for DISPLAY bidders: {', '.join(missing)}")
            return result

        result.state = TestState.PASSED
        return result

    async def validate(self, result: TestResult) -> TestResult:
        return result

