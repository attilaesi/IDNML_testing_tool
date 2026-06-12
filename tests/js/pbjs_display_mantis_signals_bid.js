() => {
  const w = window;

  const diag = {
    hasPbjs: !!w.pbjs,
    totalRequests: 0,
    biddersSeen: [],
    perBidder: {},
    debug: {
      eventsLen: 0,
      eventTypes: [],
      rawEventsSample: []
    }
  };

  const events = Array.isArray(w.__pbjsBidEvents)
    ? w.__pbjsBidEvents
    : [];

  diag.debug.eventsLen = events.length;
  diag.debug.eventTypes = Array.from(
    new Set(events.map(e => e && e.type).filter(Boolean))
  );

  diag.debug.rawEventsSample = events.slice(0, 3).map(e => ({
    type: e && e.type,
    hasArgs: !!(e && e.args),
    bidderCode: e && e.args && (e.args.bidderCode || e.args.bidder || null),
    bidsLen: e && e.args && Array.isArray(e.args.bids) ? e.args.bids.length : 0
  }));

  if (!events.length) {
    return diag;
  }

  // treat each bidRequested event's args as a bidderRequest-like object
  const requests = events
    .filter(e => e && e.type === "bidRequested" && e.args)
    .map(e => e.args);

  diag.totalRequests = requests.length;

  const ensureBidder = (code) => {
    if (!diag.perBidder[code]) {
      const emptyPaths = {
        "site.ext.data.mantis": { seen: false, type: null, count: 0, sample: [] },
        "site.ext.data.mantis_context": { seen: false, type: null, count: 0, sample: [] }
      };
      diag.perBidder[code] = {
        requestCount: 0,
        paths: emptyPaths
      };
    }
    return diag.perBidder[code];
  };

  const getType = (v) => {
    if (v == null) return "null";
    if (Array.isArray(v)) return "array";
    return typeof v;
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
        if (Array.isArray(v)) {
          v.forEach(pushVal);
        } else if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
          pushVal(v);
        }
      });
    } else {
      pushVal(value);
    }

    return out.slice(0, 400);
  };

  const recordPath = (bidder, path, value) => {
    const b = ensureBidder(bidder);
    const info = b.paths[path];
    if (!info) return;

    const present = value != null;
    info.seen = present;
    info.type = present ? getType(value) : "null";

    if (Array.isArray(value)) {
      info.count = value.length;
    } else {
      info.count = 0;
    }

    if (!present) return;

    const sample = normaliseValueToSample(value);
    const existing = Array.isArray(info.sample) ? info.sample : [];
    info.sample = existing.concat(sample).slice(0, 800);
  };

  if (!requests.length) {
    return diag;
  }

  // Walk each bidRequested args -> bids[0].ortb2.site.ext.data.*
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
    const data = (siteExt && siteExt.data) ? siteExt.data : {};

    recordPath(bidder, "site.ext.data.mantis", data ? data.mantis : null);
    recordPath(bidder, "site.ext.data.mantis_context", data ? data.mantis_context : null);
  });

  diag.biddersSeen = Object.keys(diag.perBidder || {});
  return diag;
}
