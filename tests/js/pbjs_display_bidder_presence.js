() => {
  const out = {
    hasPbjs: !!window.pbjs,
    locale: null,
    pageType: null,
    liveblog: null,
    source: "__pbjsBidEventsDisplay",
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

  const events = Array.isArray(w.__pbjsBidEventsDisplay) ? w.__pbjsBidEventsDisplay : [];
  out.eventsLen = events.length;

  const reqSet = new Set();
  const addBidder = (code) => {
    if (typeof code === "string") {
      const t = code.trim();
      if (t) reqSet.add(t);
    }
  };

  try {
    const bidReq = events.filter(e => e && e.type === "bidRequested" && e.args);
    out.bidRequestedEvents = bidReq.length;

    bidReq.forEach(ev => {
      const req = ev.args || {};
      if (req.bidderCode) addBidder(req.bidderCode);
      else if (req.bidder) addBidder(req.bidder);
    });
  } catch (e) {}

  out.biddersFromRequests = Array.from(reqSet);
  return out;
}
