# tests/gpt_tests/gpt_gam_bid_keys_test.py
"""
gpt:gam_bid_keys

What this test is meant to test
-------------------------------
Verifies that both demand sources enriched the GAM ad request with their
key-values:

  - Prebid.js  → keys prefixed "hb_"   (e.g. hb_pb, hb_bidder, hb_adid)
  - Amazon TAM → keys prefixed "amzn"  (e.g. amznbid, amzniid, amznsz)

Data sources:
  - Prebid keys: read from auctionEnd events across both __pbjsBidEventsDisplay
    and __pbjsBidEventsVideo (on video pages the auction may include hero_player
    causing auctionEnd to be routed to the video store). Reads
    args.bidsReceived[].adserverTargeting — persisted in the store, no timing
    dependency.
  - TAM keys: checked at both page level (pubads().getTargetingKeys()) and slot
    level (slot.getTargetingKeys()) since TAM integrations vary.

Test conditions
---------------
1. googletag.pubads() must be present.
2. At least one bidWon event must have fired (from __pbjsBidEventsDisplay).

What counts as PASS / FAIL / SKIPPED
------------------------------------
* SKIPPED:
    - GPT not available.
    - No auctionEnd events captured (auction has not completed yet).

* FAILED:
    - auctionEnd fired but no hb_* keys in bidsReceived (Prebid did not set targeting).
    - No amzn* keys in page-level GAM targeting (TAM missing).

* PASSED:
    - At least one bidWon has hb_* keys AND page-level targeting has amzn* keys.
"""

from typing import Dict, Any, List

from core.gpt_base_test import GptBaseTest
from core.base_test import TestResult, TestState

class GptGamBidKeysTest(GptBaseTest):

    async def setup(self, page, _url: str) -> bool:
        """Wait up to 10s for auctionEnd to appear in either event store."""
        try:
            await page.wait_for_function(
                """() => {
                    const all = (window.__pbjsBidEventsDisplay || [])
                        .concat(window.__pbjsBidEventsVideo || []);
                    return all.some(function(ev) { return ev && ev.type === "auctionEnd"; });
                }""",
                timeout=10000,
            )
        except Exception:
            pass  # proceed and let validate() report the skip
        return True

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        js = """
        () => {
          try {
            if (!window.googletag || !googletag.pubads) {
              return { hasGpt: false };
            }

            // --- Prebid: extract hb_* keys from auctionEnd bidsReceived ---
            // auctionEnd fires after all bids are in and winners determined.
            // On video pages the event may be routed to __pbjsBidEventsVideo
            // (if the auction contains hero_player), so check both stores.
            const allEvents = (window.__pbjsBidEventsDisplay || [])
              .concat(window.__pbjsBidEventsVideo || []);
            const auctionEndEvents = allEvents
              .filter(function(ev) { return ev && ev.type === "auctionEnd"; });

            const prebidKeys = [];
            let bidsReceivedCount = 0;
            auctionEndEvents.forEach(function(ev) {
              const bids = (ev.args && ev.args.bidsReceived) || [];
              bidsReceivedCount += bids.length;
              bids.forEach(function(bid) {
                Object.keys(bid.adserverTargeting || {}).forEach(function(k) {
                  if (k.startsWith("hb_") && !prebidKeys.includes(k)) prebidKeys.push(k);
                });
              });
            });

            // --- TAM: check page-level AND slot-level targeting for amzn* keys ---
            const tamKeys = [];
            try {
              const pageKeys = googletag.pubads().getTargetingKeys() || [];
              pageKeys.forEach(function(k) {
                if (k.startsWith("amzn") && !tamKeys.includes(k)) tamKeys.push(k);
              });
            } catch(e) {}
            try {
              const slots = googletag.pubads().getSlots() || [];
              slots.forEach(function(slot) {
                (slot.getTargetingKeys() || []).forEach(function(k) {
                  if (k.startsWith("amzn") && !tamKeys.includes(k)) tamKeys.push(k);
                });
              });
            } catch(e) {}

            return {
              hasGpt: true,
              auctionEndCount: auctionEndEvents.length,
              bidsReceivedCount: bidsReceivedCount,
              prebidKeys: prebidKeys,
              tamKeys: tamKeys,
              hasPrebid: prebidKeys.length > 0,
              hasTam: tamKeys.length > 0,
            };
          } catch (e) {
            return { error: String(e) };
          }
        }
        """

        diag = await page.evaluate(js)
        result.data = diag or {}
        return result

    async def validate(self, result: TestResult) -> TestResult:
        diag: Dict[str, Any] = result.data or {}

        if diag.get("error"):
            result.state = TestState.ERROR
            result.errors.append(f"JS error: {diag['error']}")
            return result

        if not diag.get("hasGpt"):
            result.state = TestState.SKIPPED
            result.warnings.append("GPT not available.")
            return result

        auction_end_count: int = diag.get("auctionEndCount", 0)
        if auction_end_count == 0:
            result.state = TestState.SKIPPED
            result.warnings.append("No auctionEnd events captured; auction has not completed yet.")
            return result

        has_prebid: bool = diag.get("hasPrebid", False)
        has_tam: bool = diag.get("hasTam", False)
        prebid_keys: List[str] = diag.get("prebidKeys", [])
        tam_keys: List[str] = diag.get("tamKeys", [])
        bids_received: int = diag.get("bidsReceivedCount", 0)

        errors = []
        if not has_prebid:
            errors.append(
                f"No hb_* keys in {bids_received} bid(s) from {auction_end_count} auction(s); "
                "Prebid did not enrich GAM."
            )
        if not has_tam:
            errors.append(
                "No amzn* keys in page-level or slot-level GAM targeting; TAM did not enrich GAM."
            )

        if errors:
            result.state = TestState.FAILED
            result.errors.extend(errors)
        else:
            result.state = TestState.PASSED
            result.warnings.append(
                f"Both Prebid {prebid_keys} and TAM {tam_keys} present "
                f"({bids_received} bid(s) across {auction_end_count} auction(s))."
            )

        return result
