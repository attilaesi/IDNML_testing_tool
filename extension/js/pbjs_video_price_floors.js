window.__adTests = window.__adTests || {};
window.__adTests["pbjs_video_price_floors"] = () => {
  const out = {
    hasPbjs: false,
    pageType: null,

    has_video_store: false,
    video_bidrequested_events: 0,

    floors_currency: null,

    // [{code, short_code}] — video ad units only
    ad_units: [],

    // {"short_code|video": <floor_usd | null>}
    // null means adUnit.floors is missing or has no video value
    configured_floors: {},

    errors: [],
  };

  // ── Video activity ───────────────────────────────────────────────────────────
  try {
    const store = Array.isArray(window.__pbjsBidEventsVideo)
      ? window.__pbjsBidEventsVideo : null;
    if (store) {
      out.has_video_store = true;
      for (let i = 0; i < store.length; i++) {
        if ((store[i] || {}).type === 'bidRequested') out.video_bidrequested_events += 1;
      }
    }
  } catch (e) {}

  // ── pageType ──────────────────────────────────────────────────────────────────
  try {
    const pubads = window.googletag && googletag.pubads ? googletag.pubads() : null;
    if (pubads) {
      const pt = pubads.getTargeting('pageType');
      if (pt && pt[0]) out.pageType = String(pt[0]).toLowerCase();
    }
  } catch (e) {}

  // ── pbjs ──────────────────────────────────────────────────────────────────────
  const pbjs = window.pbjs;
  if (!pbjs) { out.errors.push('window.pbjs not defined'); return out; }
  out.hasPbjs = true;

  // ── Per-unit floors ───────────────────────────────────────────────────────────
  // Floors are configured per ad unit on adUnit.floors, not in the global config.
  // Schema is single-field [mediaType], so the values key is just 'video'.
  try {
    const units = Array.isArray(pbjs.adUnits) ? pbjs.adUnits : [];
    for (let i = 0; i < units.length; i++) {
      const u = units[i] || {};
      const code = String(u.code || '').trim();
      if (!code) continue;
      if (!(u.mediaTypes || {}).video) continue;

      const parts = code.split('/');
      const short_code = parts[parts.length - 1].trim() || code;
      out.ad_units.push({ code, short_code });

      let floor = null;
      try {
        const f = u.floors;
        if (f && f.values && typeof f.values === 'object') {
          floor = f.values['video'] ?? f.values['*'] ?? null;
          if (out.floors_currency === null && f.currency) {
            out.floors_currency = f.currency;
          }
        }
      } catch (e) {}

      out.configured_floors[`${short_code}|video`] = floor;
    }
  } catch (e) {
    out.errors.push('adUnits extraction: ' + String(e));
  }

  return out;
}
;
