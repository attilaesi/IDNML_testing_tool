window.__adTests = window.__adTests || {};
window.__adTests["pbjs_display_permutive_signals_bid"] = () => {
  const w = window;

  const REQUIRED = ["ix", "rubicon", "msft", "pubmatic"];

  const diag = {
    hasPbjs: !!w.pbjs,
    totalRequests: 0,

    // useful for downstream reporting clarity
    requiredBidders: REQUIRED,
    biddersSeen: [],
    ignoredBidders: [],

    // we still capture all bidders for debugging
    perBidder: {},

    // convenience filtered view: only required bidders
    perBidderRequired: {},

    debug: {
      eventsLen: 0,
      eventTypes: [],
      rawEventsSample: []
    }
  };

  const events = Array.isArray(w.__pbjsBidEvents) ? w.__pbjsBidEvents : [];

  diag.debug.eventsLen = events.length;
  diag.debug.eventTypes = Array.from(new Set(events.map(e => e && e.type).filter(Boolean)));

  diag.debug.rawEventsSample = events.slice(0, 3).map(e => ({
    type: e && e.type,
    hasArgs: !!(e && e.args),
    bidderCode: e && e.args && (e.args.bidderCode || e.args.bidder || null),
    bidsLen: e && e.args && Array.isArray(e.args.bids) ? e.args.bids.length : 0
  }));

  if (!events.length) return diag;

  const requests = events
    .filter(e => e && e.type === "bidRequested" && e.args)
    .map(e => e.args);

  diag.totalRequests = requests.length;

  const ensureBidder = (code) => {
    if (!diag.perBidder[code]) {
      const emptyPaths = {
        "site.ext.permutive": { seen: false, sample: [] },
        "site.ext.permutive.p_standard": { seen: false, sample: [] },
        "user.ext.data.p_standard": { seen: false, sample: [] },
        "user.ext.data.permutive": { seen: false, sample: [] },
        "user.data[0].name": { seen: false, sample: [] },
        "user.data[1].name": { seen: false, sample: [] },
        "user.keywords": { seen: false, sample: [] }
      };
      diag.perBidder[code] = {
        requestCount: 0,
        paths: emptyPaths
      };
    }
    return diag.perBidder[code];
  };

  const normaliseValueToSample = (value) => {
    if (value == null) return [];
    const out = [];
    const pushVal = (v) => {
      if (v == null) return;
      try { out.push(String(v)); } catch (e) {}
    };

    if (Array.isArray(value)) {
      value.forEach(pushVal);
    } else if (typeof value === "object") {
      Object.values(value).forEach(v => {
        if (typeof v === "string" || typeof v === "number") pushVal(v);
      });
    } else {
      pushVal(value);
    }

    return out.slice(0, 200);
  };

  const recordPath = (bidder, path, value) => {
    const b = ensureBidder(bidder);
    if (!value) return;
    const sample = normaliseValueToSample(value);
    if (!sample.length) return;

    const info = b.paths[path];
    if (!info) return;

    info.seen = true;
    const existing = Array.isArray(info.sample) ? info.sample : [];
    info.sample = existing.concat(sample).slice(0, 400);
  };

  requests.forEach(req => {
    const bidder = req.bidderCode || req.bidder || "unknown";
    const b = ensureBidder(bidder);
    b.requestCount += 1;

    const bidsArr = Array.isArray(req.bids) ? req.bids : [];
    let ortb2 = {};
    if (bidsArr.length && bidsArr[0] && bidsArr[0].ortb2) {
      ortb2 = bidsArr[0].ortb2 || {};
    } else {
      ortb2 = req.ortb2 || {};
    }

    const site = ortb2.site || {};
    const siteExt = site.ext || {};
    const sitePerm = siteExt.permutive;

    const user = ortb2.user || {};
    const userExt = user.ext || {};
    const extData = userExt.data || {};
    const userData = Array.isArray(user.data) ? user.data : [];
    const userKeywordsRaw = user.keywords;

    if (sitePerm) {
      recordPath(bidder, "site.ext.permutive", sitePerm);
      if (sitePerm && sitePerm.p_standard) {
        recordPath(bidder, "site.ext.permutive.p_standard", sitePerm.p_standard);
      }
    }

    // p_standard is the canonical key; pstandard (no underscore) is a known
    // mis-casing seen in some Permutive adapter versions — accept both.
    if (Array.isArray(extData.p_standard) || Array.isArray(extData.pstandard)) {
      const ps = Array.isArray(extData.p_standard) ? extData.p_standard : extData.pstandard;
      recordPath(bidder, "user.ext.data.p_standard", ps);
    }

    if (extData.permutive) {
      recordPath(bidder, "user.ext.data.permutive", extData.permutive);
    }

    if (userData[0] && userData[0].name) recordPath(bidder, "user.data[0].name", userData[0].name);
    if (userData[1] && userData[1].name) recordPath(bidder, "user.data[1].name", userData[1].name);

    if (Array.isArray(userKeywordsRaw)) {
      recordPath(bidder, "user.keywords", userKeywordsRaw);
    } else if (typeof userKeywordsRaw === "string") {
      const split = userKeywordsRaw.split(/[\s,]+/).filter(Boolean);
      recordPath(bidder, "user.keywords", split);
    }
  });

  diag.biddersSeen = Object.keys(diag.perBidder || {});
  diag.ignoredBidders = diag.biddersSeen.filter(b => !REQUIRED.includes(b));

  // build filtered view
  REQUIRED.forEach(b => {
    if (diag.perBidder[b]) diag.perBidderRequired[b] = diag.perBidder[b];
  });

  return diag;
}
;
