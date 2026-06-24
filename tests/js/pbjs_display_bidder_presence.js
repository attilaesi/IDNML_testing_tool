() => {
  const out = {
    hasPbjs: !!window.pbjs,
    locale: null,
    pageType: null,
    liveblog: null,
    source: null,
    biddersFromRequests: [],
    eventsLen: 0,
    bidRequestedEvents: 0
  };

  const w = window;
  if (!w.pbjs) return out;

  // Locale cookie
  try {
    const m = document.cookie.match(/(?:^|;\s*)Locale=([^;]+)/i);
    if (m && m[1]) out.locale = decodeURIComponent(m[1]).toUpperCase();
  } catch (e) {}

  // GPT targeting
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

  const isHeroCode = (code) => {
    const s = String(code || '').trim().toLowerCase();
    return s === 'hero_player' || s.endsWith('/hero_player');
  };

  // Primary: captured display event store
  let store = Array.isArray(w.__pbjsBidEventsDisplay) ? w.__pbjsBidEventsDisplay : [];
  let bidReq = store.filter(e => e && e.type === "bidRequested" && e.args);

  // Fallback: pbjs.getEvents() — Prebid's own internal event log (timing-safe)
  if (!bidReq.length && typeof w.pbjs.getEvents === "function") {
    try {
      const native = w.pbjs.getEvents() || [];
      bidReq = native
        .filter(e => {
          if (!e || e.eventType !== "bidRequested" || !e.args) return false;
          const bids = Array.isArray(e.args.bids) ? e.args.bids : [];
          return !bids.some(b => isHeroCode((b || {}).adUnitCode));
        })
        .map(e => ({ type: "bidRequested", args: e.args, stream: "display", ts: 0 }));
      if (bidReq.length) out.source = "pbjs.getEvents";
    } catch (e) {}
  } else if (bidReq.length) {
    out.source = "__pbjsBidEventsDisplay";
  }

  out.eventsLen = bidReq.length;
  out.bidRequestedEvents = bidReq.length;

  const reqSet = new Set();
  const addBidder = (code) => {
    if (typeof code === "string") {
      const t = code.trim();
      if (t) reqSet.add(t);
    }
  };

  try {
    bidReq.forEach(ev => {
      const req = ev.args || {};
      if (req.bidderCode) addBidder(req.bidderCode);
      else if (req.bidder) addBidder(req.bidder);
    });
  } catch (e) {}

  out.biddersFromRequests = Array.from(reqSet);
  return out;
}
