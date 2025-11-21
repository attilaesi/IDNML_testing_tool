# core/readiness_waiter.py
import asyncio

class ReadinessWaiter:
    """Wait until pbjs and googletag are ready before running tests."""

    def __init__(self, timeout: float = 10.0, poll_interval: float = 0.5):
        self.timeout = timeout
        self.poll_interval = poll_interval

    async def wait_for_prebid_and_gpt(self, page):

        js_condition = """
        () => {
            const pbjsReady = !!(window.pbjs && Array.isArray(window.pbjs.que));
            const gptReady =
                !!(window.googletag &&
                   window.googletag.apiReady &&
                   window.googletag.pubads &&
                   window.googletag.pubadsReady);

            const adUnitsReady =
                !!(window.pbjs && window.pbjs.adUnits && window.pbjs.adUnits.length > 0);

            const bidderSet = new Set();
            if (window.pbjs && Array.isArray(window.pbjs.adUnits)) {
              window.pbjs.adUnits.forEach(u => {
                (u.bids || []).forEach(b => {
                  if (b && b.bidder) bidderSet.add(b.bidder);
                });
              });
            }

            const bidderCount = bidderSet.size;

            return {pbjsReady, gptReady, adUnitsReady, bidderCount};
        }
        """

        elapsed = 0
        while elapsed < self.timeout:
            try:
                status = await page.evaluate(js_condition)
                if status.get("pbjsReady") and status.get("gptReady") and status.get("adUnitsReady"):
                    print(f"✅ pbjs & GPT fully ready: {status['bidderCount']} bidders after {elapsed:.1f}s")
                    return True
            except Exception:
                pass
            await asyncio.sleep(self.poll_interval)
            elapsed += self.poll_interval

        print(f"⚠️ Timeout waiting for pbjs/GPT/adUnits readiness after {self.timeout}s")
        return False