import asyncio

from core.base_test import BaseTest, TestResult, TestState
from core.data_extractor import DataExtractor


class AuctionActivityTest(BaseTest):
    """
    Verifies that a Prebid auction has actually produced bids.

    Answers:
      - Did any ad unit record bid responses?
      - Are there any winning bids recorded?
      - Which bidders responded and how many bids per ad unit?

    Uses Prebid APIs:
      - pbjs.getBidResponsesForAdUnitCode(adUnitCode)
      - pbjs.getAllWinningBids()

    Assumes:
      - Framework already navigated to the URL
      - CMP has been handled
      - Prebid/GPT readiness has been waited for
    """

    name = "AuctionActivityTest"

    # How many GPT refresh cycles to trigger before inspecting bids
    REFRESH_COUNT = 2
    REFRESH_INTERVAL_SEC = 1.0  # wait between refreshes

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

    async def _trigger_gpt_refreshes(self, page):
        """
        Trigger a few GPT refreshes to ensure an auction has a chance to run.

        We refresh all slots returned by googletag.pubads().getSlots(), if available.
        """
        for i in range(self.REFRESH_COUNT):
            try:
                refreshed = await page.evaluate(
                    """
                    () => {
                        try {
                            const g = window.googletag;
                            if (!g || !g.pubads || typeof g.pubads !== "function") {
                                return "googletag.pubads not available";
                            }
                            const pubads = g.pubads();
                            if (!pubads || typeof pubads.getSlots !== "function") {
                                return "pubads.getSlots not available";
                            }
                            const slots = pubads.getSlots();
                            if (!slots || !slots.length) {
                                return "no slots to refresh";
                            }
                            pubads.refresh(slots);
                            return `refreshed ${slots.length} slot(s)`;
                        } catch (e) {
                            return `error: ${String(e)}`;
                        }
                    }
                    """
                )
                # print(f"[AuctionActivityTest] GPT refresh {i + 1}/{self.REFRESH_COUNT}: {refreshed}")
            except Exception as e:
                print(f"[AuctionActivityTest] Error triggering GPT refresh {i + 1}: {e}")

            # Give Prebid/GPT a moment to run the auction
            await asyncio.sleep(self.REFRESH_INTERVAL_SEC)

    async def execute(self, page, url: str) -> TestResult:
        """
        Trigger GPT refreshes then extract bid response and winning bid info.
        """
        result = TestResult(self.name)
        result.url = url
        result.state = TestState.PASSED
        result.data = {}

        try:
            # Optional: basic page metrics for context
            basic_data = await DataExtractor.extract_basic_data(page, url)
            result.data.update(basic_data)

            # 1) Trigger a couple of GPT refreshes to ensure an auction runs
            await self._trigger_gpt_refreshes(page)

            # 2) Inspect Prebid bid responses / winning bids
            auction_data = await page.evaluate(
                """
                () => {
                    const out = {
                        adUnits_with_responses: [],
                        total_bid_responses: 0,
                        winning_bids: [],
                        errors: []
                    };

                    try {
                        const pbjs = window.pbjs;
                        if (!pbjs) {
                            out.errors.push("window.pbjs is not defined");
                            return out;
                        }

                        if (typeof pbjs.getBidResponsesForAdUnitCode !== "function") {
                            out.errors.push("pbjs.getBidResponsesForAdUnitCode is not available");
                            return out;
                        }

                        const adUnits = Array.isArray(pbjs.adUnits) ? pbjs.adUnits : [];

                        adUnits.forEach((unit) => {
                            const code = unit.code || unit.adUnitCode;
                            if (!code) return;

                            const resp = pbjs.getBidResponsesForAdUnitCode(code) || {};
                            const bids = Array.isArray(resp.bids) ? resp.bids : [];

                            if (bids.length > 0) {
                                out.adUnits_with_responses.push({
                                    code,
                                    bidCount: bids.length,
                                    bidders: bids
                                        .map(b => b && b.bidder)
                                        .filter(Boolean)
                                });
                                out.total_bid_responses += bids.length;
                            }
                        });

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
                        out.errors.push(String(e));
                    }

                    return out;
                }
                """
            )

            result.data["prebid_auction_activity"] = auction_data

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

        # Propagate JS-side errors
        for err in data.get("errors", []):
            errors.append(f"Extraction error: {err}")

        ad_units_with_responses = data.get("adUnits_with_responses") or []
        total_bid_responses = data.get("total_bid_responses", 0) or 0
        winning_bids = data.get("winning_bids") or []

        # 1) At least one bid response somewhere
        if total_bid_responses == 0:
            errors.append("No bid responses recorded for any Prebid ad unit (after GPT refresh attempts)")

        # 2) Winning bids are highly desirable; warn if none
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
                "ad_units_with_responses_count": len(ad_units_with_responses),
                "total_bid_responses": total_bid_responses,
                "winning_bids_count": len(winning_bids),
                "bidder_response_counts": bidder_response_counts,
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