window.__adTests = window.__adTests || {};
window.__adTests["pbjs_price_floors_display"] = () => {
  const out = {
    // observed activity
    has_display_store: false,
    display_events_total: 0,
    display_bidrequested_events: 0,
    display_auctioninit_events: 0,
    display_auctionend_events: 0,

    // floors snapshot
    has_pbjs: false,
    has_getConfig: false,
    module_present: false,
    installed_modules: null,

    has_floors_config: false,
    enabled: false,
    provider: null,
    rules_count: 0,
    display_applicable_rules_count: 0,

    raw_config: null,
    errors: []
  };

  const safeObjKeys = (o) => {
    try { return o && typeof o === 'object' ? Object.keys(o) : []; }
    catch (e) { return []; }
  };

  const getFloorsCfg = (pbjs) => {
    let floorsCfg = null;
    try {
      floorsCfg = pbjs.getConfig ? pbjs.getConfig('floors') : null;
    } catch (e) {}

    // Some stacks nest under full config
    try {
      if (!floorsCfg || (typeof floorsCfg === 'object' && safeObjKeys(floorsCfg).length === 0)) {
        const fullCfg = pbjs.getConfig ? (pbjs.getConfig() || {}) : {};
        if (fullCfg && fullCfg.floors) floorsCfg = fullCfg.floors;
      }
    } catch (e) {}

    return floorsCfg || null;
  };

  const getValuesObj = (floorsCfg) => {
    try {
      return (floorsCfg && floorsCfg.data && floorsCfg.data.values) ||
             (floorsCfg && floorsCfg.values) ||
             null;
    } catch (e) {
      return null;
    }
  };

  const looksBannerApplicable = (ruleObj) => {
    // Heuristic:
    // - if rule has explicit mediaType/mediaTypes and includes banner -> banner-applicable
    // - if no mediaType/mediaTypes -> assume generic (applies-to-all) -> banner-applicable
    try {
      if (!ruleObj || typeof ruleObj !== 'object') return true;

      const mt = ruleObj.mediaType;
      if (typeof mt === 'string') {
        return mt.toLowerCase() === 'banner';
      }

      const mts = ruleObj.mediaTypes;
      if (Array.isArray(mts)) {
        return mts.map(x => String(x || '').toLowerCase()).includes('banner');
      }

      // Some configs use "type"
      const t = ruleObj.type;
      if (typeof t === 'string') {
        const tl = t.toLowerCase();
        if (tl === 'banner' || tl === 'display') return true;
      }

      // No explicit media type => treat as generic
      return true;
    } catch (e) {
      return true;
    }
  };

  // ------------------------------------------------------------
  // 1) DISPLAY STORE OBSERVATION
  // ------------------------------------------------------------
  try {
    const store = Array.isArray(window.__pbjsBidEventsDisplay) ? window.__pbjsBidEventsDisplay : null;
    if (store) {
      out.has_display_store = true;
      out.display_events_total = store.length;

      // count key event types
      for (let i = 0; i < store.length; i++) {
        const ev = store[i] || {};
        const type = (ev.type || '').toString();
        if (type === 'bidRequested') out.display_bidrequested_events += 1;
        if (type === 'auctionInit') out.display_auctioninit_events += 1;
        if (type === 'auctionEnd') out.display_auctionend_events += 1;
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

    // installedModules – presence of priceFloors module
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
      out.raw_config = null;
      out.has_floors_config = false;
      return out;
    }

    out.raw_config = floorsCfg;
    out.has_floors_config = true;

    // Enabled flag
    if (Object.prototype.hasOwnProperty.call(floorsCfg, 'enabled')) {
      out.enabled = !!floorsCfg.enabled;
    } else {
      // default TRUE when config present
      out.enabled = true;
    }

    // Provider (optional)
    if (floorsCfg.data && floorsCfg.data.provider) out.provider = floorsCfg.data.provider;
    else if (floorsCfg.provider) out.provider = floorsCfg.provider;

    const valuesObj = getValuesObj(floorsCfg);
    if (valuesObj && typeof valuesObj === 'object') {
      const keys = Object.keys(valuesObj);
      out.rules_count = keys.length;

      // display-applicable count
      let dcount = 0;
      for (let i = 0; i < keys.length; i++) {
        const k = keys[i];
        const rule = valuesObj[k];
        if (looksBannerApplicable(rule)) dcount += 1;
      }
      out.display_applicable_rules_count = dcount;
    } else {
      out.rules_count = 0;
      out.display_applicable_rules_count = 0;
    }

    // Fallback: if config exists, treat module_present as true
    if (!out.module_present && out.has_floors_config) out.module_present = true;

  } catch (e) {
    out.errors.push(String(e));
  }

  return out;
}
;
