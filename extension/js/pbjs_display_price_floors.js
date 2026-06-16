window.__adTests = window.__adTests || {};
window.__adTests["pbjs_display_price_floors"] = () => {
  const out = {
    hasPbjs: false,
    locale: null,

    has_display_store: false,
    display_bidrequested_events: 0,

    floors_currency: null,

    // [{code, short_code}] — banner ad units only
    ad_units: [],

    // {"short_code|banner": <floor_usd | null>}
    // null means adUnit.floors is missing or has no banner value
    configured_floors: {},

    errors: [],
  };

  // ── Locale ──────────────────────────────────────────────────────────────────
  try {
    const m = document.cookie.match(/(?:^|;\s*)Locale=([^;]+)/i);
    if (m && m[1]) out.locale = decodeURIComponent(m[1]).toUpperCase();
  } catch (e) {}

  // ── Display activity ─────────────────────────────────────────────────────────
  try {
    const store = Array.isArray(window.__pbjsBidEventsDisplay)
      ? window.__pbjsBidEventsDisplay : null;
    if (store) {
      out.has_display_store = true;
      for (let i = 0; i < store.length; i++) {
        if ((store[i] || {}).type === 'bidRequested') out.display_bidrequested_events += 1;
      }
    }
  } catch (e) {}

  // ── pbjs ──────────────────────────────────────────────────────────────────────
  const pbjs = window.pbjs;
  if (!pbjs) { out.errors.push('window.pbjs not defined'); return out; }
  out.hasPbjs = true;

  // ── Per-unit floors ───────────────────────────────────────────────────────────
  // Floors are configured per ad unit on adUnit.floors, not in the global config.
  // Schema is single-field [mediaType], so the values key is just 'banner'.
  try {
    const units = Array.isArray(pbjs.adUnits) ? pbjs.adUnits : [];
    for (let i = 0; i < units.length; i++) {
      const u = units[i] || {};
      const code = String(u.code || '').trim();
      if (!code) continue;
      if (!(u.mediaTypes || {}).banner) continue;

      const parts = code.split('/');
      const short_code = parts[parts.length - 1].trim() || code;
      out.ad_units.push({ code, short_code });

      let floor = null;
      try {
        const f = u.floors;
        if (f && f.values && typeof f.values === 'object') {
          // Single-field schema: key is just the mediaType value ('banner' or '*')
          floor = f.values['banner'] ?? f.values['*'] ?? null;
          if (out.floors_currency === null && f.currency) {
            out.floors_currency = f.currency;
          }
        }
      } catch (e) {}

      out.configured_floors[`${short_code}|banner`] = floor;
    }
  } catch (e) {
    out.errors.push('adUnits extraction: ' + String(e));
  }

  return out;
}
;
