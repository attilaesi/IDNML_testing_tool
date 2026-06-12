"""
prebid: PbjsDisplayAuctionActivityTest

What this test checks
---------------------
Verifies that a Prebid auction has actually fired and produced observable bid data.
Primary source: window.__pbjsBidEventsDisplay (bidResponse events from global event hook).
Fallback: pbjs.getBidResponsesForAdUnitCode() and pbjs.getAllWinningBids().

Test conditions
---------------
- window.pbjs must be present.
- At least one bidRequest or bidResponse event must be observable.

What counts as PASS / FAIL / SKIP
-----------------------------------
- PASSED: at least one bid response recorded across any ad unit.
- PASSED (with warning): bidRequested events seen but bidResponse data unavailable
  (Prebid build has responses stripped); Prebid is running.
- FAILED: no bid responses and no bidRequested events observed at all.
- NOTE: absence of winning bids is a warning only, not a failure.
"""

from pathlib import Path
from core.base_test import BaseTest, TestResult, TestState
from core.data_extractor import DataExtractor

_JS = (Path(__file__).parent.parent / "js" / "pbjs_display_auction_activity.js").read_text()

class PbjsDisplayAuctionActivityTest(BaseTest):

    """
    Verifies that a Prebid auction has actually produced bids (as far as we can see).

    Answers:
      - Did any ad unit record bid responses?
      - Are there any winning bids recorded?
      - Which bidders responded and how many bids per ad unit?

    PRIMARY SOURCE:
      - window.__pbjsBidEvents events of type "bidResponse"
        (populated by the global pbjs.onEvent() hook in BrowserManager)

    FALLBACK:
      - pbjs.getBidResponsesForAdUnitCode(adUnitCode)
      - pbjs.getAllWinningBids()

    If no bid responses are visible but there ARE bidRequested events,
    we treat this as PASS with a warning (Prebid running, but responses
    not exposed by this build).

    Assumes:
      - Framework already navigated to the URL
      - CMP has been handled
      - Prebid/GPT readiness has been waited for
    """

    name = "PbjsDisplayAuctionActivityTest"

    async def setup(self, page, url: str) -> bool:
        """
        No navigation here – just ensure DOM is ready.
        """
        try:
            await page.wait_for_load_state("domcontentloaded")
            return True
        except Exception as e:
            print(f"[PbjsAuctionActivityTest] setup error: {e}")
            return False

    async def execute(self, page, url: str) -> TestResult:
        """
        Inspect Prebid auction activity via global event store,
        with fallback to older pbjs APIs if needed.
        """
        result = TestResult(self.name)
        result.url = url
        result.state = TestState.PASSED
        result.data = {}

        try:
            # Optional: basic page metrics for context
            basic_data = await DataExtractor.extract_basic_data(page, url)
            result.data.update(basic_data)

            auction_data = await page.evaluate(_JS)

            result.data["prebid_auction_activity"] = auction_data

            if self.config.get("trace"):
                dbg = auction_data.get("debug") or {}
                print(
                    "[PbjsAuctionActivityTest] execute diag:",
                    {
                        "url": url,
                        "source": auction_data.get("source"),
                        "total_bid_responses": auction_data.get("total_bid_responses"),
                        "winning_bids_count": len(auction_data.get("winning_bids") or []),
                        "eventsLen": dbg.get("eventsLen"),
                        "eventTypes": dbg.get("eventTypes"),
                        "bidRequestedCount": dbg.get("bidRequestedCount"),
                        "bidResponseCount": dbg.get("bidResponseCount"),
                    },
                )

        except Exception as e:
            result.state = TestState.ERROR
            result.errors.append(f"JS extraction failed: {e}")

        return result

    async def validate(self, result: TestResult) -> TestResult:
        """
        Validate the auction activity snapshot.
        """
        if result.state == TestState.ERROR:
            return result

        data = (result.data or {}).get("prebid_auction_activity", {}) or {}
        errors = []
        warnings = []

        debug = data.get("debug") or {}
        bid_requested_count = debug.get("bidRequestedCount", 0) or 0
        bid_response_count = debug.get("bidResponseCount", 0) or 0

        # Propagate JS-side errors
        for err in data.get("errors", []):
            errors.append(f"Extraction error: {err}")

        ad_units_with_responses = data.get("adUnits_with_responses") or []
        total_bid_responses = data.get("total_bid_responses", 0) or 0
        winning_bids = data.get("winning_bids") or []

        # --- core logic ---
        if total_bid_responses == 0:
            if bid_requested_count > 0:
                # We saw Prebid auctions running, but this build doesn't expose responses
                warnings.append(
                    "Prebid bidRequested events seen but no bidResponse data was "
                    "available (likely stripped in this Prebid build); treating as "
                    "PASS with warning."
                )
            else:
                errors.append(
                    "No bid responses recorded for any Prebid ad unit and no "
                    "bidRequested events seen."
                )

        # Winning bids are desirable; warn if none
        if total_bid_responses > 0 and not winning_bids:
            warnings.append("No winning bids reported by pbjs.getAllWinningBids()")

        # Aggregate bidder stats for metadata
        bidder_response_counts = {}
        for unit in ad_units_with_responses:
            for bidder in unit.get("bidders") or []:
                bidder_response_counts[bidder] = bidder_response_counts.get(bidder, 0) + 1

        # Final state
        if errors:
            result.state = TestState.FAILED
            result.errors.extend(errors)
        else:
            result.state = TestState.PASSED

        if warnings:
            result.warnings.extend(warnings)

        # Metadata for reporting
        result.metadata.update(
            {
                "auction_source": data.get("source"),
                "ad_units_with_responses_count": len(ad_units_with_responses),
                "total_bid_responses": total_bid_responses,
                "winning_bids_count": len(winning_bids),
                "bidder_response_counts": bidder_response_counts,
                "bidRequestedCount": bid_requested_count,
                "bidResponseCount": bid_response_count,
            }
        )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        """
        Optional: screenshot on failure, if debug_screenshots enabled.
        """
        if result.state == TestState.FAILED and self.config.get("debug_screenshots"):
            try:
                screenshot_path = f"debug/auction_activity_fail_{hash(result.url)}.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                result.metadata["debug_screenshot"] = screenshot_path
            except Exception:
                pass