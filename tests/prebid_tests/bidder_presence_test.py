# tests/prebid_tests/bidder_presence_test.py

from typing import Dict, Any, List, Set
from core.base_test import BaseTest, TestResult, TestState

class BidderPresenceTest(BaseTest):
    """
    WHAT THIS TEST CHECKS
    ---------------------
    Ensures that bidders which are EXPECTED for the active site/geo AND are CONFIGURED
    on this specific page (via pbjs.adUnits) actually PARTICIPATE in the auction
    (visible in pbjs.getBidderRequests() after 'auctionEnd').

    TEST CONDITIONS
    ---------------
    - Prebid must be present (window.pbjs).
    - We wait until 'auctionEnd' (or a timeout) to ensure all adapters had a chance to run.
    - We discover 'configured' bidders from pbjs.getAdUnits()/pbjs.adUnits.
    - We discover 'seen' bidders from pbjs.getBidderRequests().

    PASS / FAIL CRITERIA
    --------------------
    PASS  => (expected ∩ configured) ⊆ seen
    FAIL  => Any bidder in (expected ∩ configured) is NOT found in 'seen'.
             The failure lists which bidders were missing and the key counts.
    """

    # --- abstract methods (implemented but minimal) -----------------
    async def setup(self, page, url: str) -> bool:
        # Nothing special to set up; framework already waited for pbjs/GPT readiness.
        return True

    async def execute(self, page, url: str) -> TestResult:
        result = TestResult(self.name)
        result.url = url

        # 1) Pull expected bidders from config by geo
        geo = (self.config.get("geo_mode") or "UK").upper()
        expected_global: Set[str] = set((self.config.get("expected_bidders") or {}).get(geo, []))

        # Normalization helper: lower, strip "BidAdapter", map common aliases to canonical keys
        def norm(name: str) -> str:
            n = (name or "").strip().lower()
            if n.endswith("bidadapter"):
                n = n[:-10]
            alias_map = {
                "rubiconproject": "rubicon",
                "indexexchange": "ix",
                "xandr": "appnexus",
                "tradedesk": "ttd",
                "thetradedesk": "ttd",
                "apsnexus": "appnexus",
                # keep others as-is
            }
            return alias_map.get(n, n)

        expected_norm = {norm(b) for b in expected_global}

        # 2) Run the robust browser-side snippet: find pbjs (even in child frames),
        #    wait for auction end, then return configured + seen arrays.
        js = r"""
        () => new Promise(resolveOuter => {
          function findPbjs(win) {
            try {
              if (win.pbjs && typeof win.pbjs === 'object') return win;
              for (let i = 0; i < win.frames.length; i++) {
                const r = findPbjs(win.frames[i]);
                if (r) return r;
              }
            } catch (e) {}
            return null;
          }
          const w = findPbjs(window) || window;

          function biddersFromAdUnits() {
            try {
              const adUnits = (w.pbjs && w.pbjs.getAdUnits && w.pbjs.getAdUnits()) || (w.pbjs && w.pbjs.adUnits) || [];
              const all = [].concat(...adUnits.map(u => (u.bids || []).map(b => (b.bidder || b.bidderCode || '').toLowerCase())));
              return Array.from(new Set(all.filter(Boolean)));
            } catch(e) {
              return [];
            }
          }

          async function waitForPbjs() {
            if (!w || !w.pbjs) {
              await new Promise(r => setTimeout(r, 50));
              let tries = 0;
              while ((!w || !w.pbjs) && tries < 100) {
                await new Promise(r => setTimeout(r, 50));
                tries++;
              }
            }
          }

          async function waitForAuctionEnd() {
            return new Promise(resolve => {
              try {
                let resolved = false;
                const done = () => { if (!resolved) { resolved = true; resolve(); } };
                if (w && w.pbjs && w.pbjs.onEvent) {
                  w.pbjs.onEvent('auctionEnd', done);
                }
                setTimeout(done, 4000); // safety
              } catch(e) { resolve(); }
            });
          }

          (async () => {
            await waitForPbjs();
            const configured = biddersFromAdUnits();
            await waitForAuctionEnd();

            let seen = [];
            try {
              const reqs = (w.pbjs && w.pbjs.getBidderRequests && w.pbjs.getBidderRequests()) || [];
              const codes = reqs.map(r => (r && (r.bidderCode || r.bidder) || '').toLowerCase()).filter(Boolean);
              seen = Array.from(new Set(codes));
            } catch(e) {
              seen = [];
            }

            resolveOuter({ configured, seen, hasPbjs: !!(w && w.pbjs) });
          })();
        })
        """
        data = await page.evaluate(js)
        configured = {norm(b) for b in (data.get("configured") or [])}
        seen = {norm(b) for b in (data.get("seen") or [])}

        # 3) ONLY require bidders that are both expected (site/geo) AND configured on this page
        expected_subset = expected_norm & configured

        # 4) Work out missing
        missing = sorted(expected_subset - seen)

        # 5) Fill diagnostics
        diag = {
            "geo": geo,
            "expected_global": sorted(expected_global),
            "expected_normalized": sorted(expected_norm),
            "configured": sorted(configured),
            "seen": sorted(seen),
            "expected_subset": sorted(expected_subset),
            "missing": missing,
        }
        result.data = diag

        # 6) State + messages
        if not data.get("hasPbjs"):
            result.state = TestState.ERROR
            result.errors.append("pbjs not found in any frame")
            return result

        if missing:
            result.state = TestState.FAILED
            result.errors.append(f"Missing bidders (expected∩configured but not seen): {', '.join(missing)}")
        else:
            result.state = TestState.PASSED

        return result

    async def validate(self, result: TestResult) -> TestResult:
        # Nothing extra; execute() already sets result.state and details.
        return result

    async def cleanup(self, page, result: TestResult) -> None:
        # No-op; add screenshots or traces here if needed.
        return