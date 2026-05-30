"""
prebid: PbjsVideoPubcidPresenceTest

What this test checks
---------------------
Validates that PubCommonId (pubcid) is present in every video bidder's hero_player requests.
Inspects bids in window.__pbjsBidEventsVideo filtered to hero_player (adUnitCode === "hero_player"
or mediaTypes.video present), checking userId.pubCommonId or a matching userIdAsEids entry.

Test conditions
---------------
- Page must be a video page (pageType == video); otherwise skipped.
- VIDEO hero_player bidRequested events must have been captured.

What counts as PASS / FAIL / SKIP
-----------------------------------
- PASSED: every video hero_player bidder has pubcid in at least one of its bids.
- FAILED: pbjs present but no VIDEO hero_player bidRequested bids captured.
- FAILED: at least one video bidder is missing pubcid across all of its bids.
- SKIPPED: window.pbjs not present on the page.
"""
from pathlib import Path
from core.base_test import VideoOnlyTest, TestResult, TestState

_JS = (Path(__file__).parent.parent / "js" / "pbjs_pubcid_presence_video.js").read_text()

class PbjsVideoPubcidPresenceTest(VideoOnlyTest):

    """
    Validate PubCommonId (pubcid) for VIDEO auctions only (hero_player).

    Rule:
      PASS only if *every bidder* that appears in VIDEO hero_player bids
      has pubcid present in at least one of its bids.

    In-scope bids:
      - window.__pbjsBidEventsVideo (type="bidRequested")
      - only bids that belong to hero_player video auction:
          (bid.adUnitCode === "hero_player") OR (bid.mediaTypes.video exists)

    FAIL:
      - pbjs exists but no VIDEO hero_player bidRequested bids captured
      - OR at least one VIDEO hero bidder missing pubcid

    SKIP:
      - window.pbjs missing
    """

    name = "PbjsVideoPubcidPresenceTest"

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
            "heroBidsConsidered": data.get("heroBidsConsidered"),
            "biddersSeen": data.get("biddersSeen"),
            "biddersWithPubcid": data.get("biddersWithPubcid"),
            "biddersMissingPubcid": data.get("biddersMissingPubcid"),
            "perBidder": data.get("perBidder"),
        }

        if not data.get("hasPbjs"):
            result.state = TestState.SKIPPED
            result.errors.append("window.pbjs not found; cannot validate pubcid in video bids.")
            return result

        # For VIDEO test, require hero-player bids specifically
        if int(data.get("heroBidsConsidered") or 0) == 0:
            result.state = TestState.FAILED
            result.errors.append("No VIDEO hero_player bids captured; cannot confirm pubcid for video bidders.")
            return result

        missing = data.get("biddersMissingPubcid") or []
        if missing:
            result.state = TestState.FAILED
            result.errors.append(f"pubcid missing for VIDEO bidders: {', '.join(missing)}")
            return result

        result.state = TestState.PASSED
        return result

    async def validate(self, result: TestResult) -> TestResult:
        return result

