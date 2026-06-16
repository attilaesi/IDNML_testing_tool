window.__adTests = window.__adTests || {};
window.__adTests["pbjs_video_hero_player_placement"] = () => {
  const w = window;

  // Read pageType early — drives expected plcmt value.
  let pageType = null;
  try {
    const pubads = w.googletag && googletag.pubads ? googletag.pubads() : null;
    if (pubads) {
      const pt = pubads.getTargeting("pageType");
      if (pt && pt[0]) pageType = String(pt[0]).toLowerCase();
    }
  } catch (e) {}

  // placement is always 1.
  // plcmt: tv_hub pages = 1 (instream); video / liveblog pages = 2 (accompanying content).
  const expectedPlacement = 1;
  const expectedPlcmt = (pageType === "tv_hub") ? 1 : 2;

  const diag = {
    hasPbjs: !!w.pbjs,
    pageType,
    expectedPlacement,
    expectedPlcmt,
    source: null,
    eventsLen: 0,
    bidRequestedEvents: 0,
    heroBidsTotal: 0,

    // perBidder[bidder] = {
    //   bids, placement_values, placement_paths, plcmt_values, plcmt_paths,
    //   missingPlacement, missingPlcmt, invalidPlacement, invalidPlcmt
    // }
    perBidder: {},

    debug: { firstHeroBidSample: null }
  };

  if (!diag.hasPbjs) return diag;

  const eventsVideo  = Array.isArray(w.__pbjsBidEventsVideo) ? w.__pbjsBidEventsVideo : null;
  const eventsLegacy = Array.isArray(w.__pbjsBidEvents)      ? w.__pbjsBidEvents      : null;

  const events =
    (eventsVideo && eventsVideo.length ? eventsVideo : null) ||
    (eventsLegacy && eventsLegacy.length ? eventsLegacy : []);

  diag.source =
    events === eventsVideo  ? "__pbjsBidEventsVideo" :
    events === eventsLegacy ? "__pbjsBidEvents"      : "none";

  diag.eventsLen = events.length;
  if (!events.length) return diag;

  const ensureBidder = (code) => {
    if (!diag.perBidder[code]) {
      diag.perBidder[code] = {
        bids: 0,
        placement_values: [], placement_paths: [],
        plcmt_values: [],     plcmt_paths: [],
        missingPlacement: 0, missingPlcmt: 0,
        invalidPlacement: 0, invalidPlcmt: 0,
      };
    }
    return diag.perBidder[code];
  };

  const toIntOrNull = (v) => {
    if (typeof v === "number" && Number.isFinite(v)) return v;
    if (typeof v === "string") { const n = parseInt(v, 10); if (!Number.isNaN(n)) return n; }
    return null;
  };

  const getPlacementWithPath = (bid) => {
    try {
      const video = bid?.mediaTypes?.video;
      if (video && Object.prototype.hasOwnProperty.call(video, "placement"))
        return { value: video.placement, path: "bid.mediaTypes.video.placement" };
      const impVideo = bid?.ortb2Imp?.video;
      if (impVideo && Object.prototype.hasOwnProperty.call(impVideo, "placement"))
        return { value: impVideo.placement, path: "bid.ortb2Imp.video.placement" };
      if (bid?.params && Object.prototype.hasOwnProperty.call(bid.params, "placement"))
        return { value: bid.params.placement, path: "bid.params.placement" };
    } catch (e) {}
    return { value: null, path: "missing" };
  };

  const getPlcmtWithPath = (bid) => {
    try {
      const video = bid?.mediaTypes?.video;
      if (video && Object.prototype.hasOwnProperty.call(video, "plcmt"))
        return { value: video.plcmt, path: "bid.mediaTypes.video.plcmt" };
      if (bid?.params && Object.prototype.hasOwnProperty.call(bid.params, "plcmt"))
        return { value: bid.params.plcmt, path: "bid.params.plcmt" };
    } catch (e) {}
    return { value: null, path: "missing" };
  };

  const bidRequested = events.filter(e => e && e.type === "bidRequested" && e.args);
  diag.bidRequestedEvents = bidRequested.length;

  const HERO = "hero_player".toLowerCase();

  bidRequested.forEach(ev => {
    const bidsArr = Array.isArray(ev.args?.bids) ? ev.args.bids : [];
    bidsArr.forEach(bid => {
      if (!bid) return;
      if ((bid.adUnitCode ?? "").toString().toLowerCase() !== HERO) return;

      diag.heroBidsTotal += 1;

      const bidder =
        (bid.bidder      && String(bid.bidder))      ||
        (ev.args.bidderCode && String(ev.args.bidderCode)) ||
        (ev.args.bidder  && String(ev.args.bidder))  ||
        "unknown";

      const b = ensureBidder(bidder);
      b.bids += 1;

      const placementObj = getPlacementWithPath(bid);
      const plcmtObj     = getPlcmtWithPath(bid);

      b.placement_values.push(placementObj.value);
      b.placement_paths.push(placementObj.path);
      b.plcmt_values.push(plcmtObj.value);
      b.plcmt_paths.push(plcmtObj.path);

      const placementInt = toIntOrNull(placementObj.value);
      const plcmtInt     = toIntOrNull(plcmtObj.value);

      if (placementObj.value == null)           b.missingPlacement += 1;
      else if (placementInt !== expectedPlacement) b.invalidPlacement += 1;

      if (plcmtObj.value == null)               b.missingPlcmt += 1;
      else if (plcmtInt !== expectedPlcmt)       b.invalidPlcmt += 1;

      if (!diag.debug.firstHeroBidSample) {
        const video = bid?.mediaTypes?.video ?? {};
        diag.debug.firstHeroBidSample = {
          bidder, adUnitCode: bid.adUnitCode,
          placement: placementObj.value, placementPath: placementObj.path,
          plcmt: plcmtObj.value, plcmtPath: plcmtObj.path,
          videoPreview: {
            placement: video.placement,
            plcmt:     video.plcmt,
          }
        };
      }
    });
  });

  return diag;
}
;
