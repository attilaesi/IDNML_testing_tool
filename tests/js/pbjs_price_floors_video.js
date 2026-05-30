() => {
  const out = {
    pageType: null,

    // observed activity
    has_video_store: false,
    video_events_total: 0,
    video_bidrequested_events: 0,
    video_auctioninit_events: 0,
    video_auctionend_events: 0,

    // floors snapshot
    has_pbjs: false,
    has_getConfig: false,
    module_present: false,
    installed_modules: null,

    has_floors_config: false,
    enabled: false,
    provider: null,
    rules_count: 0,
    video_applicable_rules_count: 0,

    raw_config: null,
    errors: []
  };

  const safeKeys = (o) => {
    try { return o && typeof o === 'object' ? Object.keys(o) : []; }
    catch (e) { return []; }
  };

  const getFloorsCfg = (pbjs) => {
    let cfg = null;
    try { cfg = pbjs.getConfig ? pbjs.getConfig('floors') : null; } catch (e) {}
    try {
      if (!cfg || safeKeys(cfg).length === 0) {
        const full = pbjs.getConfig ? (pbjs.getConfig() || {}) : {};
        if (full && full.floors) cfg = full.floors;
      }
    } catch (e) {}
    return cfg || null;
  };

  const getValuesObj = (cfg) => {
    try {
      return (cfg && cfg.data && cfg.data.values) ||
             (cfg && cfg.values) ||
             null;
    } catch (e) { return null; }
  };

  const looksVideoApplicable = (rule) => {
    try {
      if (!rule || typeof rule !== 'object') return true;

      const mt = rule.mediaType;
      if (typeof mt === 'string') {
        return mt.toLowerCase() === 'video';
      }

      const mts = rule.mediaTypes;
      if (Array.isArray(mts)) {
        return mts.map(x => String(x || '').toLowerCase()).includes('video');
      }

      const t = rule.type;
      if (typeof t === 'string') {
        return t.toLowerCase() === 'video';
      }

      // No media type specified => global => applies to video
      return true;
    } catch (e) {
      return true;
    }
  };

  // ------------------------------------------------------------
  // 1) VIDEO STORE OBSERVATION
  // ------------------------------------------------------------
  try {
    const store = Array.isArray(window.__pbjsBidEventsVideo)
      ? window.__pbjsBidEventsVideo
      : null;

    if (store) {
      out.has_video_store = true;
      out.video_events_total = store.length;

      for (let i = 0; i < store.length; i++) {
        const ev = store[i] || {};
        const type = String(ev.type || '');
        if (type === 'bidRequested') out.video_bidrequested_events += 1;
        if (type === 'auctionInit') out.video_auctioninit_events += 1;
        if (type === 'auctionEnd') out.video_auctionend_events += 1;
      }
    }
  } catch (e) {}

  // ------------------------------------------------------------
  // 2) FLOORS CONFIG EXTRACTION
  // ------------------------------------------------------------
  try {
    const pbjs = window.pbjs;
    if (!pbjs) {
      out.errors.push('window.pbjs is not defined');
      return out;
    }
    out.has_pbjs = true;

    if (Array.isArray(pbjs.installedModules)) {
      out.installed_modules = pbjs.installedModules.slice();
      out.module_present = pbjs.installedModules.includes('priceFloors');
    }

    if (typeof pbjs.getConfig !== 'function') {
      out.errors.push('pbjs.getConfig is not available');
      return out;
    }
    out.has_getConfig = true;

    const floorsCfg = getFloorsCfg(pbjs);
    if (!floorsCfg) {
      out.has_floors_config = false;
      return out;
    }

    out.raw_config = floorsCfg;
    out.has_floors_config = true;

    if (Object.prototype.hasOwnProperty.call(floorsCfg, 'enabled')) {
      out.enabled = !!floorsCfg.enabled;
    } else {
      out.enabled = true;
    }

    if (floorsCfg.data && floorsCfg.data.provider) out.provider = floorsCfg.data.provider;
    else if (floorsCfg.provider) out.provider = floorsCfg.provider;

    const valuesObj = getValuesObj(floorsCfg);
    if (valuesObj && typeof valuesObj === 'object') {
      const keys = Object.keys(valuesObj);
      out.rules_count = keys.length;

      let vcount = 0;
      for (let i = 0; i < keys.length; i++) {
        if (looksVideoApplicable(valuesObj[keys[i]])) vcount += 1;
      }
      out.video_applicable_rules_count = vcount;
    }

    if (!out.module_present && out.has_floors_config) out.module_present = true;

  } catch (e) {
    out.errors.push(String(e));
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
