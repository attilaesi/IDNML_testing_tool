() => {
  const out = {
    hasPbjs: false,
    locale: null,

    has_display_store: false,
    display_bidrequested_events: 0,

    floors_enabled: false,
    floors_currency: null,
    schema_fields: [],

    // [{code, short_code, has_banner}] — display (banner) ad units only
    ad_units: [],

    // {"short_code|banner": <floor_usd | null>}
    // null means no matching rule found in pbjs floors config
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
      ? window.__pbjsBidEventsDisplay
      : null;
    if (store) {
      out.has_display_store = true;
      for (let i = 0; i < store.length; i++) {
        if ((store[i] || {}).type === 'bidRequested') out.display_bidrequested_events += 1;
      }
    }
  } catch (e) {}

  // ── pbjs check ───────────────────────────────────────────────────────────────
  const pbjs = window.pbjs;
  if (!pbjs) {
    out.errors.push('window.pbjs not defined');
    return out;
  }
  out.hasPbjs = true;

  if (typeof pbjs.getConfig !== 'function') {
    out.errors.push('pbjs.getConfig not available');
    return out;
  }

  // ── Collect display (banner) ad units ────────────────────────────────────────
  try {
    const units = Array.isArray(pbjs.adUnits) ? pbjs.adUnits : [];
    for (let i = 0; i < units.length; i++) {
      const u = units[i] || {};
      const code = String(u.code || '').trim();
      if (!code) continue;
      const mt = u.mediaTypes || {};
      if (!mt.banner) continue; // display test — banner only
      // short_code: last path segment (strips /network/site/ prefix if present)
      const parts = code.split('/');
      const short_code = parts[parts.length - 1].trim() || code;
      out.ad_units.push({ code, short_code });
    }
  } catch (e) {
    out.errors.push('adUnits extraction: ' + String(e));
  }

  // ── Floors config ─────────────────────────────────────────────────────────────
  let floorsCfg = null;
  try {
    floorsCfg = pbjs.getConfig('floors') || null;
    if (!floorsCfg || !Object.keys(floorsCfg).length) {
      const full = pbjs.getConfig() || {};
      floorsCfg = full.floors || null;
    }
  } catch (e) {
    out.errors.push('getConfig floors: ' + String(e));
  }

  if (!floorsCfg) return out;

  // enabled flag
  out.floors_enabled = Object.prototype.hasOwnProperty.call(floorsCfg, 'enabled')
    ? !!floorsCfg.enabled
    : true;

  const data = floorsCfg.data || floorsCfg || {};
  out.floors_currency = (data.currency || null);

  const schema = (data.schema || {});
  out.schema_fields = Array.isArray(schema.fields) ? schema.fields.slice() : [];

  const values = data.values || null;
  if (!values || typeof values !== 'object') return out;

  // ── Floor lookup per ad unit ──────────────────────────────────────────────────
  // Tries a ranked list of key patterns, returns the first match found.
  const domain = (window.location.hostname || '').replace(/^www\./, '');

  const findFloor = (fullCode, shortCode) => {
    const mt = 'banner';

    // Ordered candidates — most specific first
    const candidates = [
      // 2-field schema: adUnitCode|mediaType
      `${fullCode}|${mt}`,
      `${shortCode}|${mt}`,
      // 2-field with wildcard mediaType
      `${fullCode}|*`,
      `${shortCode}|*`,
      // 3-field schema: domain|adUnitCode|mediaType
      `${domain}|${fullCode}|${mt}`,
      `${domain}|${shortCode}|${mt}`,
      `*|${fullCode}|${mt}`,
      `*|${shortCode}|${mt}`,
      // generic wildcard
      `*|${mt}`,
      `*|*|${mt}`,
      `*|*`,
    ];

    for (let i = 0; i < candidates.length; i++) {
      if (Object.prototype.hasOwnProperty.call(values, candidates[i])) {
        return values[candidates[i]];
      }
    }
    return null;
  };

  for (let i = 0; i < out.ad_units.length; i++) {
    const { code, short_code } = out.ad_units[i];
    const key = `${short_code}|banner`;
    out.configured_floors[key] = findFloor(code, short_code);
  }

  return out;
}
