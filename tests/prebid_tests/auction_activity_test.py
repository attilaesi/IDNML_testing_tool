# tests/prebid_tests/auction_activity_test.py

from core.base_test import BaseTest, TestResult, TestState
from core.data_extractor import DataExtractor


class AuctionActivityTest(BaseTest):
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

    name = "AuctionActivityTest"

    async def setup(self, page, url: str) -> bool:
        """
        No navigation here – just ensure DOM is ready.
        """
        try:
            await page.wait_for_load_state("domcontentloaded")
            return True
        except Exception as e:
            print(f"[AuctionActivityTest] setup error: {e}")
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

            auction_data = await page.evaluate(
                """
                () => {
                    const out = {
                        source: null,  // "__pbjsBidEvents" | "pbjs.getBidResponsesForAdUnitCode"
                        adUnits_with_responses: [],
                        total_bid_responses: 0,
                        winning_bids: [],
                        errors: [],
                        debug: {
                          eventsLen: 0,
                          eventTypes: [],
                          bidRequestedCount: 0,
                          bidResponseCount: 0
                        }
                    };

                    const w = window;
                    const pbjs = w.pbjs;

                    if (!pbjs) {
                        out.errors.push("window.pbjs is not defined");
                        return out;
                    }

                    try {
                        const events = Array.isArray(w.__pbjsBidEvents)
                          ? w.__pbjsBidEvents
                          : [];

                        out.debug.eventsLen = events.length;
                        out.debug.eventTypes = Array.from(
                          new Set(events.map(e => e && e.type).filter(Boolean))
                        );

                        const bidRequestedEvents = events.filter(
                          e => e && e.type === "bidRequested" && e.args
                        );
                        const bidRespEvents = events.filter(
                          e => e && e.type === "bidResponse" && e.args
                        );

                        out.debug.bidRequestedCount = bidRequestedEvents.length;
                        out.debug.bidResponseCount = bidRespEvents.length;

                        // ---- primary: bidResponse events ----
                        if (bidRespEvents.length) {
                            out.source = "__pbjsBidEvents";

                            const perAdUnit = new Map();

                            bidRespEvents.forEach(ev => {
                                const b = ev.args || {};
                                const code = b.adUnitCode || b.adUnitCode;
                                if (!code) return;

                                let entry = perAdUnit.get(code);
                                if (!entry) {
                                    entry = { code, bids: [] };
                                    perAdUnit.set(code, entry);
                                }
                                entry.bids.push(b);
                            });

                            const adUnits_with_responses = [];
                            let total = 0;

                            perAdUnit.forEach(({ code, bids }) => {
                                const bidders = bids
                                  .map(b => b && b.bidder)
                                  .filter(Boolean);
                                adUnits_with_responses.push({
                                    code,
                                    bidCount: bids.length,
                                    bidders
                                });
                                total += bids.length;
                            });

                            out.adUnits_with_responses = adUnits_with_responses;
                            out.total_bid_responses = total;
                        }
                    } catch (e) {
                        out.errors.push("error reading __pbjsBidEvents: " + String(e));
                    }

                    // ---------------------------------------------
                    // FALLBACK: pbjs.getBidResponsesForAdUnitCode
                    // ---------------------------------------------
                    if (!out.total_bid_responses) {
                        try {
                            if (typeof pbjs.getBidResponsesForAdUnitCode !== "function") {
                                out.errors.push("pbjs.getBidResponsesForAdUnitCode is not available");
                            } else {
                                const adUnits = Array.isArray(pbjs.adUnits) ? pbjs.adUnits : [];
                                const adUnits_with_responses = [];
                                let total = 0;

                                adUnits.forEach((unit) => {
                                    const code = unit.code || unit.adUnitCode;
                                    if (!code) return;

                                    const resp = pbjs.getBidResponsesForAdUnitCode(code) || {};
                                    const bids = Array.isArray(resp.bids) ? resp.bids : [];

                                    if (bids.length > 0) {
                                        adUnits_with_responses.push({
                                            code,
                                            bidCount: bids.length,
                                            bidders: bids
                                                .map(b => b && b.bidder)
                                                .filter(Boolean)
                                        });
                                        total += bids.length;
                                    }
                                });

                                if (total > 0) {
                                    out.source = "pbjs.getBidResponsesForAdUnitCode";
                                    out.adUnits_with_responses = adUnits_with_responses;
                                    out.total_bid_responses = total;
                                }
                            }
                        } catch (e) {
                            out.errors.push("fallback extraction error: " + String(e));
                        }
                    }

                    // --------------------
                    // Winning bids (PBJS)
                    // --------------------
                    try {
                        if (typeof pbjs.getAllWinningBids === "function") {
                            const wins = pbjs.getAllWinningBids() || [];
                            out.winning_bids = wins.map((b) => ({
                                adUnitCode: b && b.adUnitCode,
                                bidder: b && b.bidder,
                                cpm: b && b.cpm,
                                currency: b && b.currency
                            }));
                        }
                    } catch (e) {
                        out.errors.push("getAllWinningBids error: " + String(e));
                    }

                    return out;
                }
                """
            )

            result.data["prebid_auction_activity"] = auction_data

            if self.config.get("trace"):
                dbg = auction_data.get("debug") or {}
                print(
                    "[AuctionActivityTest] execute diag:",
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