() => {
  const HERO = "hero_player";

  const out = {
    hasPbjs: !!window.pbjs,
    locale: null,
    pageType: null,
    liveblog: null,

    source: "__pbjsBidEventsVideo",

    // raw store counts
    eventsLen: 0,
    bidRequestedEvents: 0,

    // hero_player-focused counts
    heroBidRequestedEvents: 0,     // number of bidRequested events that include >=1 hero_player bid
    heroBidsTotal: 0,              // total number of bids in req.bids[] that match hero_player (or mediaTypes.video)
    biddersFromHeroRequests: [],   // DISTINCT bidder codes that actually bid on hero_player

    // diagnostics (optional)
    heroBidSamples: [],            // up to N sample bid objects for debugging
  };

  const w = window;
  if (!w.pbjs) return out;

  // Locale cookie
  try {
    const m = document.cookie.match(/(?:^|;\s*)Locale=([^;]+)/i);
    if (m && m[1]) out.locale = decodeURIComponent(m[1]).toUpperCase();
  } catch (e) {}

  // GPT targeting (pageType + liveblog)
  try {
    if (w.googletag && w.googletag.pubads) {
      const pubads = w.googletag.pubads();
      if (pubads && typeof pubads.getTargeting === "function") {
        const pt = pubads.getTargeting("pageType");
        if (pt && pt[0]) out.pageType = String(pt[0]).toLowerCase();
        const lb = pubads.getTargeting("liveblog");
        if (lb && lb[0]) out.liveblog = String(lb[0]).toLowerCase();
      }
    }
  } catch (e) {}

  const events = Array.isArray(w.__pbjsBidEventsVideo) ? w.__pbjsBidEventsVideo : [];
  out.eventsLen = events.length;

  const heroBidderSet = new Set();
  const heroSamples = [];
  const MAX_SAMPLES = 3;

  const norm = (v) => (typeof v === "string" ? v.trim() : "");

  // Treat a bid as hero-video if:
  //  1) adUnitCode === "hero_player"
  //  OR
  //  2) mediaTypes.video exists (best-effort fallback)
  const isHeroVideoBid = (bid) => {
    if (!bid || typeof bid !== "object") return false;

    const auc = norm(bid.adUnitCode);
    if (auc === HERO) return true;

    try {
      const mt = bid.mediaTypes || bid.mediaType || null;
      if (mt && typeof mt === "object") {
        if (mt.video && typeof mt.video === "object") return true;
      }
    } catch (e) {}

    return false;
  };

  try {
    const bidReqEvents = events.filter(e => e && e.type === "bidRequested" && e.args);
    out.bidRequestedEvents = bidReqEvents.length;

    bidReqEvents.forEach(ev => {
      const req = ev.args || {};
      const bidder = norm(req.bidderCode || req.bidder);

      const bids = Array.isArray(req.bids) ? req.bids : [];
      let matchedThisReq = false;

      for (const b of bids) {
        if (isHeroVideoBid(b)) {
          matchedThisReq = true;
          out.heroBidsTotal += 1;

          if (bidder) heroBidderSet.add(bidder);

          if (heroSamples.length < MAX_SAMPLES) {
            heroSamples.push({
              bidder: bidder || null,
              adUnitCode: b && b.adUnitCode ? String(b.adUnitCode) : null,
              hasMediaTypesVideo: !!(b && b.mediaTypes && b.mediaTypes.video),
              mediaTypesKeys: b && b.mediaTypes ? Object.keys(b.mediaTypes) : [],
            });
          }
        }
      }

      if (matchedThisReq) {
        out.heroBidRequestedEvents += 1;
      }
    });
  } catch (e) {}

  out.biddersFromHeroRequests = Array.from(heroBidderSet);
  out.heroBidSamples = heroSamples;

  return out;
}
