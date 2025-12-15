import asyncio

class ReadinessWaiter:
    """Wait until pbjs and googletag are ready before running tests."""

    def __init__(self, timeout: float = 10.0, poll_interval: float = 0.5):
        # ⬆️ Increase this to 15.0 / 20.0 etc if you want a longer overall wait
        self.timeout = timeout
        self.poll_interval = poll_interval

    async def wait_for_prebid_and_gpt(self, page):

        js_condition = """
        () => {
            const w = window;

            const pbjsReady = !!(w.pbjs && Array.isArray(w.pbjs.que));
            const gptReady =
                !!(w.googletag &&
                   w.googletag.apiReady &&
                   w.googletag.pubads &&
                   w.googletag.pubadsReady);

            const adUnitsReady =
                !!(w.pbjs && w.pbjs.adUnits && w.pbjs.adUnits.length > 0);

            const bidderSet = new Set();
            if (w.pbjs && Array.isArray(w.pbjs.adUnits)) {
              w.pbjs.adUnits.forEach(u => {
                (u.bids || []).forEach(b => {
                  if (b && b.bidder) bidderSet.add(b.bidder);
                });
              });
            }
            const bidderCount = bidderSet.size;

            // ✅ Detect whether at least one auction / bid request has fired
            let auctionStarted = false;
            try {
              if (w.pbjs) {
                if (typeof w.pbjs.getBidderRequests === "function") {
                  const br = w.pbjs.getBidderRequests() || [];
                  if (br.length > 0) auctionStarted = true;
                }
                if (!auctionStarted && Array.isArray(w.pbjs._bidsRequested)) {
                  if (w.pbjs._bidsRequested.length > 0) auctionStarted = true;
                }
                if (!auctionStarted && typeof w.pbjs.getEvents === "function") {
                  const events = w.pbjs.getEvents() || [];
                  auctionStarted = events.some(e =>
                    e &&
                    (e.eventType === "auctionInit" ||
                     e.eventType === "bidRequested" ||
                     e.eventType === "auctionEnd")
                  );
                }
              }
            } catch (e) {
              // best-effort; ignore
            }

            return { pbjsReady, gptReady, adUnitsReady, bidderCount, auctionStarted };
        }
        """

        elapsed = 0
        while elapsed < self.timeout:
            try:
                status = await page.evaluate(js_condition)
                if (
                    status.get("pbjsReady")
                    and status.get("gptReady")
                    and status.get("adUnitsReady")
                    and status.get("auctionStarted")   # 👈 new condition
                ):
                    print(
                        f"✅ pbjs & GPT ready, auction started: "
                        f"{status['bidderCount']} bidders after {elapsed:.1f}s"
                    )
                    return True
            except Exception:
                pass

            await asyncio.sleep(self.poll_interval)
            elapsed += self.poll_interval

        print(
            f"⚠️ Timeout waiting for pbjs/GPT/adUnits/auction readiness "
            f"after {self.timeout}s"
        )
        return False