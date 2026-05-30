window.__adTests = window.__adTests || {};
window.__adTests["pbjs_pubcid_presence_video"] = () => {
  const out = {
    hasPbjs: !!window.pbjs,
    pbjsVersion: (window.pbjs && window.pbjs.version) || null,
    pageType: null,

    store: "__pbjsBidEventsVideo",
    eventsLen: 0,
    bidRequestedEvents: 0,
    bidsScanned: 0,

    heroBidsConsidered: 0,

    biddersSeen: [],
    biddersWithPubcid: [],
    biddersMissingPubcid: [],

    perBidder: {}, // bidder -> { firstAdUnitCode, found, foundVia, examplePubcid }
  };

  const events = Array.isArray(window.__pbjsBidEventsVideo)
    ? window.__pbjsBidEventsVideo
    : [];

  out.eventsLen = events.length;

  const bidReqEvents = events.filter(e => e && e.type === "bidRequested");
  out.bidRequestedEvents = bidReqEvents.length;

  const isHeroVideoBid = (b) => {
    try {
      if (!b || typeof b !== "object") return false;
      const auc = String(b.adUnitCode || "");
      if (auc === "hero_player") return true;
      const mt = b.mediaTypes || {};
      return !!(mt && mt.video);
    } catch (e) { return false; }
  };

  const getPubcidFromUserId = (userId) => {
    try {
      if (!userId || typeof userId !== "object") return null;
      const v = userId.pubCommonId;
      if (!v) return null;
      if (typeof v === "string") return v;
      if (typeof v === "object" && v.id) return String(v.id);
      return null;
    } catch (e) { return null; }
  };

  const getPubcidFromEids = (eids) => {
    try {
      if (!Array.isArray(eids)) return null;
      for (const eid of eids) {
        if (!eid || typeof eid !== "object") continue;
        const src = String(eid.source || "").toLowerCase();
        const hint = src.includes("pubcommon") || src.includes("pubcid");
        if (!hint) continue;
        const uids = Array.isArray(eid.uids) ? eid.uids : [];
        for (const u of uids) {
          if (u && typeof u === "object" && u.id) {
            return { source: eid.source || null, id: String(u.id) };
          }
        }
      }
      return null;
    } catch (e) { return null; }
  };

  const ensureBidder = (bidder, adUnitCode) => {
    if (!bidder) return;
    if (!out.perBidder[bidder]) {
      out.perBidder[bidder] = {
        firstAdUnitCode: adUnitCode || null,
        found: false,
        foundVia: null,
        examplePubcid: null
      };
    }
  };

  for (const ev of bidReqEvents) {
    const args = ev.args || {};
    const bids = Array.isArray(args.bids) ? args.bids : [];
    for (const b of bids) {
      out.bidsScanned += 1;

      if (!isHeroVideoBid(b)) continue;
      out.heroBidsConsidered += 1;

      const bidder = b && b.bidder;
      if (!bidder) continue;

      ensureBidder(bidder, b && b.adUnitCode);

      // If we already found pubcid for this bidder, stop scanning its bids
      if (out.perBidder[bidder].found) continue;

      const v1 = getPubcidFromUserId(b && b.userId);
      if (v1) {
        out.perBidder[bidder].found = true;
        out.perBidder[bidder].foundVia = "userId.pubCommonId";
        out.perBidder[bidder].examplePubcid = v1;
        continue;
      }

      const v2 = getPubcidFromEids(b && b.userIdAsEids);
      if (v2) {
        out.perBidder[bidder].found = true;
        out.perBidder[bidder].foundVia = "userIdAsEids";
        out.perBidder[bidder].examplePubcid = v2.id;
        continue;
      }
    }
  }

  const bidders = Object.keys(out.perBidder);
  out.biddersSeen = bidders;

  for (const bidder of bidders) {
    if (out.perBidder[bidder].found) out.biddersWithPubcid.push(bidder);
    else out.biddersMissingPubcid.push(bidder);
  }

  try {
    const pubads = window.googletag && googletag.pubads ? googletag.pubads() : null;
    if (pubads) {
      const pt = pubads.getTargeting("pageType");
      if (pt && pt[0]) out.pageType = String(pt[0]).toLowerCase();
    }
  } catch (e) {}

  return out;
}
;
