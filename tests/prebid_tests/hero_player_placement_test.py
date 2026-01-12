"""
prebid: HeroPlayerPlacementTest (VIDEO)

What this test checks
---------------------
For the video ad unit "hero_player", find Prebid bidRequested events from the
VIDEO event store and inspect each bid object.

For each bidder that submitted a bid for hero_player, verify:
  - BOTH placement and plcmt exist
  - BOTH are valid (expected 1 by default)
  - BOTH match (placement == plcmt)

Primary data source
-------------------
Prefer:
  - window.__pbjsBidEventsVideo   (new split store)

Fallbacks (backwards compatibility):
  - window.__pbjsBidEvents        (legacy single store)

Pass / Fail / Skipped semantics
-------------------------------
* SKIPPED:
    - window.pbjs missing, or
    - event store missing/empty, or
    - no hero_player bids found in bidRequested events

* FAILED:
    - at least one bidder has a hero_player bid where placement/plcmt is missing,
      invalid, or mismatched

* PASSED:
    - all bidders with hero_player bids have placement + plcmt present, valid, and equal
"""

from typing import Any, Dict, List

from core.base_test import BaseTest, TestResult, TestState


class HeroPlayerPlacementTest(BaseTest):
    name = "HeroPlayerPlacementTest"

    HERO_ADUNIT_CODE = "hero_player"
    EXPECTED_PLACEMENT = 1

    async def setup(self, page, url: str) -> bool:
        try:
            await page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass

        has_pbjs = await page.evaluate("() => !!window.pbjs")
        return bool(has_pbjs)

    async def execute(self, page, url: str) -> TestResult:
        if self.config.get("trace"):
            print("🔥 HeroPlayerPlacementTest EXECUTING 🔥")

        result = TestResult(self.name)
        result.url = url

        expected_placement = int(
            self.config.get("hero_player_expected_placement", self.EXPECTED_PLACEMENT)
        )

        js = f"""
        () => {{
          const w = window;

          const diag = {{
            hasPbjs: !!w.pbjs,
            expectedPlacement: {expected_placement},
            source: null,
            eventsLen: 0,
            bidRequestedEvents: 0,
            heroBidsTotal: 0,

            // perBidder[bidder] = {{
            //   bids: number,
            //   placement_values: any[],
            //   placement_paths: string[],
            //   plcmt_values: any[],
            //   plcmt_paths: string[],
            //   missingPlacement: number,
            //   missingPlcmt: number,
            //   invalidPlacement: number,
            //   invalidPlcmt: number,
            //   mismatch: number,
            // }}
            perBidder: {{}},

            debug: {{
              firstHeroBidSample: null
            }}
          }};

          if (!diag.hasPbjs) {{
            return diag;
          }}

          // Prefer split VIDEO store; fallback to legacy store
          const eventsVideo = Array.isArray(w.__pbjsBidEventsVideo) ? w.__pbjsBidEventsVideo : null;
          const eventsLegacy = Array.isArray(w.__pbjsBidEvents) ? w.__pbjsBidEvents : null;

          const events =
            (eventsVideo && eventsVideo.length ? eventsVideo : null) ||
            (eventsLegacy && eventsLegacy.length ? eventsLegacy : []) ;

          diag.source =
            (events === eventsVideo) ? "__pbjsBidEventsVideo" :
            (events === eventsLegacy) ? "__pbjsBidEvents" :
            "none";

          diag.eventsLen = events.length;

          if (!events.length) {{
            return diag;
          }}

          const ensureBidder = (code) => {{
            if (!diag.perBidder[code]) {{
              diag.perBidder[code] = {{
                bids: 0,

                placement_values: [],
                placement_paths: [],
                plcmt_values: [],
                plcmt_paths: [],

                missingPlacement: 0,
                missingPlcmt: 0,
                invalidPlacement: 0,
                invalidPlcmt: 0,
                mismatch: 0,
              }};
            }}
            return diag.perBidder[code];
          }};

          const toIntOrNull = (v) => {{
            if (typeof v === "number" && Number.isFinite(v)) return v;
            if (typeof v === "string") {{
              const n = parseInt(v, 10);
              if (!Number.isNaN(n)) return n;
            }}
            return null;
          }};

          const isValidExpected = (v) => {{
            const n = toIntOrNull(v);
            return n !== null && n === diag.expectedPlacement;
          }};

          const getPlacementWithPath = (bid) => {{
            // placement (preferred) + fallbacks
            try {{
              const mt = (bid && bid.mediaTypes && typeof bid.mediaTypes === "object") ? bid.mediaTypes : null;
              const video = (mt && mt.video && typeof mt.video === "object") ? mt.video : null;

              if (video && Object.prototype.hasOwnProperty.call(video, "placement")) {{
                return {{ value: video.placement, path: "bid.mediaTypes.video.placement" }};
              }}

              const ortb2Imp = (bid && bid.ortb2Imp && typeof bid.ortb2Imp === "object") ? bid.ortb2Imp : null;
              const impVideo = (ortb2Imp && ortb2Imp.video && typeof ortb2Imp.video === "object") ? ortb2Imp.video : null;
              if (impVideo && Object.prototype.hasOwnProperty.call(impVideo, "placement")) {{
                return {{ value: impVideo.placement, path: "bid.ortb2Imp.video.placement" }};
              }}

              const params = (bid && bid.params && typeof bid.params === "object") ? bid.params : null;
              if (params && Object.prototype.hasOwnProperty.call(params, "placement")) {{
                return {{ value: params.placement, path: "bid.params.placement" }};
              }}
            }} catch (e) {{}}

            return {{ value: null, path: "missing" }};
          }};

          const getPlcmtWithPath = (bid) => {{
            // plcmt (preferred in your stack) + fallbacks
            try {{
              const mt = (bid && bid.mediaTypes && typeof bid.mediaTypes === "object") ? bid.mediaTypes : null;
              const video = (mt && mt.video && typeof mt.video === "object") ? mt.video : null;

              if (video && Object.prototype.hasOwnProperty.call(video, "plcmt")) {{
                return {{ value: video.plcmt, path: "bid.mediaTypes.video.plcmt" }};
              }}

              const params = (bid && bid.params && typeof bid.params === "object") ? bid.params : null;
              if (params && Object.prototype.hasOwnProperty.call(params, "plcmt")) {{
                return {{ value: params.plcmt, path: "bid.params.plcmt" }};
              }}
            }} catch (e) {{}}

            return {{ value: null, path: "missing" }};
          }};

          const bidRequested = events.filter(e => e && e.type === "bidRequested" && e.args);
          diag.bidRequestedEvents = bidRequested.length;

          const HERO = "{self.HERO_ADUNIT_CODE}".toLowerCase();

          bidRequested.forEach(ev => {{
            const req = ev.args || {{}};
            const bidsArr = Array.isArray(req.bids) ? req.bids : [];
            if (!bidsArr.length) return;

            bidsArr.forEach(bid => {{
              if (!bid) return;

              const adUnitCode = bid.adUnitCode != null ? String(bid.adUnitCode) : "";
              if (adUnitCode.toLowerCase() !== HERO) return;

              diag.heroBidsTotal += 1;

              const bidder =
                (bid.bidder && String(bid.bidder)) ||
                (req.bidderCode && String(req.bidderCode)) ||
                (req.bidder && String(req.bidder)) ||
                "unknown";

              const b = ensureBidder(bidder);
              b.bids += 1;

              const placementObj = getPlacementWithPath(bid);
              const plcmtObj = getPlcmtWithPath(bid);

              const placement = placementObj.value;
              const plcmt = plcmtObj.value;

              b.placement_values.push(placement);
              b.placement_paths.push(placementObj.path);

              b.plcmt_values.push(plcmt);
              b.plcmt_paths.push(plcmtObj.path);

              const placementInt = toIntOrNull(placement);
              const plcmtInt = toIntOrNull(plcmt);

              if (placement == null) {{
                b.missingPlacement += 1;
              }} else if (!isValidExpected(placement)) {{
                b.invalidPlacement += 1;
              }}

              if (plcmt == null) {{
                b.missingPlcmt += 1;
              }} else if (!isValidExpected(plcmt)) {{
                b.invalidPlcmt += 1;
              }}

              // mismatch check only when both present + parseable
              if (placementInt !== null && plcmtInt !== null && placementInt !== plcmtInt) {{
                b.mismatch += 1;
              }}

              if (!diag.debug.firstHeroBidSample) {{
                const mt = (bid.mediaTypes && typeof bid.mediaTypes === "object") ? bid.mediaTypes : {{}};
                const video = (mt.video && typeof mt.video === "object") ? mt.video : {{}};

                diag.debug.firstHeroBidSample = {{
                  bidder,
                  adUnitCode,
                  placement,
                  placementPath: placementObj.path,
                  plcmt,
                  plcmtPath: plcmtObj.path,
                  videoPreview: {{
                    placement: Object.prototype.hasOwnProperty.call(video, "placement") ? video.placement : undefined,
                    plcmt: Object.prototype.hasOwnProperty.call(video, "plcmt") ? video.plcmt : undefined,
                  }}
                }};
              }}
            }});
          }});

          return diag;
        }}
        """

        diag = await page.evaluate(js)
        result.data = diag or {}

        if self.config.get("trace"):
            d = result.data or {}
            print(
                f"[HeroPlayerPlacementTest] diag: source={d.get('source')}, hasPbjs={bool(d.get('hasPbjs'))}, "
                f"eventsLen={d.get('eventsLen', 0)}, bidRequestedEvents={d.get('bidRequestedEvents', 0)}, "
                f"heroBidsTotal={d.get('heroBidsTotal', 0)}, expectedPlacement={d.get('expectedPlacement')}"
            )
            per = (d.get("perBidder") or {})
            for bidder, info in per.items():
                print(
                    f"[HeroPlayerPlacementTest] bidder={bidder} bids={info.get('bids', 0)} "
                    f"missingPlacement={info.get('missingPlacement', 0)} invalidPlacement={info.get('invalidPlacement', 0)} "
                    f"missingPlcmt={info.get('missingPlcmt', 0)} invalidPlcmt={info.get('invalidPlcmt', 0)} "
                    f"mismatch={info.get('mismatch', 0)}"
                )
            sample = (d.get("debug") or {}).get("firstHeroBidSample")
            if sample:
                print("[HeroPlayerPlacementTest] firstHeroBidSample:", sample)

        return result

    async def validate(self, result: TestResult) -> TestResult:
        diag: Dict[str, Any] = result.data or {}

        if not diag.get("hasPbjs"):
            result.state = TestState.SKIPPED
            result.warnings.append("window.pbjs not present; cannot inspect hero_player bids.")
            return result

        events_len = int(diag.get("eventsLen", 0) or 0)
        if events_len == 0:
            result.state = TestState.SKIPPED
            src = diag.get("source") or "event store"
            result.warnings.append(f"{src} is empty; no Prebid events captured.")
            return result

        hero_bids_total = int(diag.get("heroBidsTotal", 0) or 0)
        if hero_bids_total == 0:
            result.state = TestState.SKIPPED
            result.warnings.append("No bids found for adUnitCode 'hero_player' in bidRequested events.")
            return result

        per_bidder: Dict[str, Dict[str, Any]] = diag.get("perBidder", {}) or {}

        any_fail = False
        lines: List[str] = []

        for bidder in sorted(per_bidder.keys()):
            info = per_bidder.get(bidder) or {}

            bids = int(info.get("bids", 0) or 0)

            miss_p = int(info.get("missingPlacement", 0) or 0)
            inv_p = int(info.get("invalidPlacement", 0) or 0)
            miss_c = int(info.get("missingPlcmt", 0) or 0)
            inv_c = int(info.get("invalidPlcmt", 0) or 0)
            mismatch = int(info.get("mismatch", 0) or 0)

            placement_vals = info.get("placement_values") or []
            placement_paths = info.get("placement_paths") or []
            plcmt_vals = info.get("plcmt_values") or []
            plcmt_paths = info.get("plcmt_paths") or []

            if miss_p == 0 and inv_p == 0 and miss_c == 0 and inv_c == 0 and mismatch == 0:
                lines.append(f"{bidder}: PASS ({bids} hero_player bids)")
                continue

            any_fail = True
            reasons = []
            if miss_p:
                reasons.append(f"missing placement={miss_p}")
            if inv_p:
                reasons.append(f"invalid placement={inv_p}")
            if miss_c:
                reasons.append(f"missing plcmt={miss_c}")
            if inv_c:
                reasons.append(f"invalid plcmt={inv_c}")
            if mismatch:
                reasons.append(f"placement/plcmt mismatch={mismatch}")

            p_vals = ", ".join(str(x) for x in placement_vals[:10])
            p_paths = ", ".join(str(x) for x in placement_paths[:10])
            c_vals = ", ".join(str(x) for x in plcmt_vals[:10])
            c_paths = ", ".join(str(x) for x in plcmt_paths[:10])

            lines.append(
                f"{bidder}: FAIL ({bids} bids; {', '.join(reasons)}; "
                f"placement_vals=[{p_vals}] placement_paths=[{p_paths}]; "
                f"plcmt_vals=[{c_vals}] plcmt_paths=[{c_paths}])"
            )

        if any_fail:
            result.state = TestState.FAILED
            result.errors.append("FAILED\n" + "\n".join(lines))
        else:
            result.state = TestState.PASSED
            result.warnings.append("PASSED\n" + "\n".join(lines))

        result.metadata.update(
            {
                "hero_adunit": self.HERO_ADUNIT_CODE,
                "expected_placement": diag.get("expectedPlacement"),
                "hero_bids_total": hero_bids_total,
                "bidders_checked": sorted(per_bidder.keys()),
                "source": diag.get("source"),
            }
        )

        return result

    async def cleanup(self, page, result: TestResult) -> None:
        return