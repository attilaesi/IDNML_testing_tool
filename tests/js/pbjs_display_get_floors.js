() => {
  const out = {
    hasPbjs: false,
    locale: null,

    has_display_store: false,
    display_bidrequested_events: 0,

    module_present: false,

    // true if at least one bid object had bid.getFloor as a callable function
    get_floors_available: false,

    // {"short_code": {floor: 0.20, currency: "USD", worked: true, error: null}}
    results_per_unit: {},

    units_with_floor: [],
    units_without_floor: [],

    errors: [],
  };

  // ── Locale ───────────────────────────────────────────────────────────────────
  try {
    const m = document.cookie.match(/(?:^|;\s*)Locale=([^;]+)/i);
    if (m && m[1]) out.locale = decodeURIComponent(m[1]).toUpperCase();
  } catch (e) {}

  // ── pbjs ──────────────────────────────────────────────────────────────────────
  const pbjs = window.pbjs;
  if (!pbjs) { out.errors.push('window.pbjs not defined'); return out; }
  out.hasPbjs = true;

  if (Array.isArray(pbjs.installedModules)) {
    out.module_present = pbjs.installedModules.includes('priceFloors');
  }

  const isHeroCode = (code) => {
    const s = String(code || '').trim().toLowerCase();
    return s === 'hero_player' || s.endsWith('/hero_player');
  };

  // ── Get display bidRequested events (with fallback) ──────────────────────────
  let bidReqEvents = [];

  // Primary: captured display event store
  const capturedStore = Array.isArray(window.__pbjsBidEventsDisplay)
    ? window.__pbjsBidEventsDisplay : [];
  const fromStore = capturedStore.filter(e => e && e.type === 'bidRequested' && e.args);

  if (fromStore.length) {
    bidReqEvents = fromStore;
    out.has_display_store = true;
    out.display_bidrequested_events = fromStore.length;
  } else {
    // Fallback: pbjs.getEvents() — Prebid's own internal event log (timing-safe)
    if (typeof pbjs.getEvents === 'function') {
      try {
        const native = pbjs.getEvents() || [];
        const displayReqs = native.filter(e => {
          if (!e || e.eventType !== 'bidRequested' || !e.args) return false;
          const bids = Array.isArray(e.args.bids) ? e.args.bids : [];
          return !bids.some(b => isHeroCode((b || {}).adUnitCode));
        });
        if (displayReqs.length) {
          bidReqEvents = displayReqs.map(e => ({ type: 'bidRequested', args: e.args, stream: 'display', ts: 0 }));
          out.has_display_store = true;
          out.display_bidrequested_events = displayReqs.length;
        }
      } catch (_) {}
    }
  }

  // ── Call bid.getFloor() on display bid objects ────────────────────────────────
  const tested = new Set();

  for (let i = 0; i < bidReqEvents.length; i++) {
    const ev = bidReqEvents[i] || {};
    if (ev.type !== 'bidRequested') continue;
    const bids = ((ev.args || {}).bids) || [];

    for (let j = 0; j < bids.length; j++) {
      const bid = bids[j];
      if (!bid || !bid.adUnitCode) continue;

      const parts = String(bid.adUnitCode).split('/');
      const short_code = (parts[parts.length - 1] || '').trim() || bid.adUnitCode;

      if (tested.has(short_code)) continue;
      tested.add(short_code);

      if (typeof bid.getFloor !== 'function') {
        out.results_per_unit[short_code] = {
          floor: null, currency: null,
          worked: false, error: 'bid.getFloor is not a function',
        };
        out.units_without_floor.push(short_code);
        continue;
      }

      out.get_floors_available = true;

      try {
        const res = bid.getFloor({ mediaType: 'banner' });
        if (res && typeof res.floor === 'number' && res.floor > 0) {
          out.results_per_unit[short_code] = {
            floor: res.floor,
            currency: res.currency || 'USD',
            worked: true,
            error: null,
          };
          out.units_with_floor.push(short_code);
        } else {
          out.results_per_unit[short_code] = {
            floor: res ? res.floor : null,
            currency: res ? (res.currency || null) : null,
            worked: false,
            error: res
              ? ('floor value: ' + JSON.stringify(res.floor))
              : 'getFloors returned null/undefined',
          };
          out.units_without_floor.push(short_code);
        }
      } catch (e) {
        out.results_per_unit[short_code] = {
          floor: null, currency: null,
          worked: false, error: String(e),
        };
        out.units_without_floor.push(short_code);
      }
    }
  }

  return out;
}
