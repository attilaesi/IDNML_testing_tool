window.__adTests = window.__adTests || {};
window.__adTests["pbjs_hero_player_placement"] = () => {
  const w = window;

  const diag = {
    hasPbjs: !!w.pbjs,
    pageType: null,
    expectedPlacement: 1,
    source: null,
    eventsLen: 0,
    bidRequestedEvents: 0,
    heroBidsTotal: 0,

    // perBidder[bidder] = {
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
    // }
    perBidder: {},

    debug: {
      firstHeroBidSample: null
    }
  };

  if (!diag.hasPbjs) {
    return diag;
  }

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

  if (!events.length) {
    return diag;
  }

  const ensureBidder = (code) => {
    if (!diag.perBidder[code]) {
      diag.perBidder[code] = {
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
      };
    }
    return diag.perBidder[code];
  };

  const toIntOrNull = (v) => {
    if (typeof v === "number" && Number.isFinite(v)) return v;
    if (typeof v === "string") {
      const n = parseInt(v, 10);
      if (!Number.isNaN(n)) return n;
    }
    return null;
  };

  const isValidExpected = (v) => {
    const n = toIntOrNull(v);
    return n !== null && n === diag.expectedPlacement;
  };

  const getPlacementWithPath = (bid) => {
    // placement (preferred) + fallbacks
    try {
      const mt = (bid && bid.mediaTypes && typeof bid.mediaTypes === "object") ? bid.mediaTypes : null;
      const video = (mt && mt.video && typeof mt.video === "object") ? mt.video : null;

      if (video && Object.prototype.hasOwnProperty.call(video, "placement")) {
        return { value: video.placement, path: "bid.mediaTypes.video.placement" };
      }

      const ortb2Imp = (bid && bid.ortb2Imp && typeof bid.ortb2Imp === "object") ? bid.ortb2Imp : null;
      const impVideo = (ortb2Imp && ortb2Imp.video && typeof ortb2Imp.video === "object") ? ortb2Imp.video : null;
      if (impVideo && Object.prototype.hasOwnProperty.call(impVideo, "placement")) {
        return { value: impVideo.placement, path: "bid.ortb2Imp.video.placement" };
      }

      const params = (bid && bid.params && typeof bid.params === "object") ? bid.params : null;
      if (params && Object.prototype.hasOwnProperty.call(params, "placement")) {
        return { value: params.placement, path: "bid.params.placement" };
      }
    } catch (e) {}

    return { value: null, path: "missing" };
  };

  const getPlcmtWithPath = (bid) => {
    // plcmt (preferred in your stack) + fallbacks
    try {
      const mt = (bid && bid.mediaTypes && typeof bid.mediaTypes === "object") ? bid.mediaTypes : null;
      const video = (mt && mt.video && typeof mt.video === "object") ? mt.video : null;

      if (video && Object.prototype.hasOwnProperty.call(video, "plcmt")) {
        return { value: video.plcmt, path: "bid.mediaTypes.video.plcmt" };
      }

      const params = (bid && bid.params && typeof bid.params === "object") ? bid.params : null;
      if (params && Object.prototype.hasOwnProperty.call(params, "plcmt")) {
        return { value: params.plcmt, path: "bid.params.plcmt" };
      }
    } catch (e) {}

    return { value: null, path: "missing" };
  };

  const bidRequested = events.filter(e => e && e.type === "bidRequested" && e.args);
  diag.bidRequestedEvents = bidRequested.length;

  const HERO = "hero_player".toLowerCase();

  bidRequested.forEach(ev => {
    const req = ev.args || {};
    const bidsArr = Array.isArray(req.bids) ? req.bids : [];
    if (!bidsArr.length) return;

    bidsArr.forEach(bid => {
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

      if (placement == null) {
        b.missingPlacement += 1;
      } else if (!isValidExpected(placement)) {
        b.invalidPlacement += 1;
      }

      if (plcmt == null) {
        b.missingPlcmt += 1;
      } else if (!isValidExpected(plcmt)) {
        b.invalidPlcmt += 1;
      }

      // mismatch check only when both present + parseable
      if (placementInt !== null && plcmtInt !== null && placementInt !== plcmtInt) {
        b.mismatch += 1;
      }

      if (!diag.debug.firstHeroBidSample) {
        const mt = (bid.mediaTypes && typeof bid.mediaTypes === "object") ? bid.mediaTypes : {};
        const video = (mt.video && typeof mt.video === "object") ? mt.video : {};

        diag.debug.firstHeroBidSample = {
          bidder,
          adUnitCode,
          placement,
          placementPath: placementObj.path,
          plcmt,
          plcmtPath: plcmtObj.path,
          videoPreview: {
            placement: Object.prototype.hasOwnProperty.call(video, "placement") ? video.placement : undefined,
            plcmt: Object.prototype.hasOwnProperty.call(video, "plcmt") ? video.plcmt : undefined,
          }
        };
      }
    });
  });

  try {
    const pubads = window.googletag && googletag.pubads ? googletag.pubads() : null;
    if (pubads) {
      const pt = pubads.getTargeting("pageType");
      if (pt && pt[0]) diag.pageType = String(pt[0]).toLowerCase();
    }
  } catch (e) {}

  return diag;
}
;
