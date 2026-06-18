window.__adTests = window.__adTests || {};
window.__adTests["pbjs_msft_keywords"] = () => {
  const out = {
    hasPbjs: false,

    // Whether msft appeared in the display bid events
    msft_bid_observed: false,

    // Raw keyword strings as found (null = not present)
    user_keywords: null,
    site_keywords: null,

    // user.keywords checks
    user_has_p_standard:  false,
    user_has_permutive:   false,
    user_spaces_found:    false,

    // site.keywords checks
    site_has_mantis:         false,
    site_has_mantis_context: false,
    site_spaces_found:       false,

    errors: [],
  };

  const pbjs = window.pbjs;
  if (!pbjs) { out.errors.push('window.pbjs not defined'); return out; }
  out.hasPbjs = true;

  // Read keywords from bid.ortb2 on the first msft bid in the display event store.
  // Path: __pbjsBidEventsDisplay[].args.bids[].ortb2.user.keywords
  //                                              .ortb2.site.keywords
  let userKw = null, siteKw = null;

  try {
    const events = Array.isArray(window.__pbjsBidEventsDisplay)
      ? window.__pbjsBidEventsDisplay : [];

    for (let i = 0; i < events.length; i++) {
      const ev = events[i] || {};
      if (ev.type !== 'bidRequested') continue;
      const bids = ((ev.args || {}).bids) || [];

      for (let j = 0; j < bids.length; j++) {
        const bid = bids[j] || {};
        const code = String(bid.bidder || bid.bidderCode || '').toLowerCase();
        if (code !== 'msft') continue;

        out.msft_bid_observed = true;
        const ortb2 = bid.ortb2 || {};
        if (userKw === null && (ortb2.user || {}).keywords != null)
          userKw = ortb2.user.keywords;
        if (siteKw === null && (ortb2.site || {}).keywords != null)
          siteKw = ortb2.site.keywords;

        if (userKw !== null && siteKw !== null) break;
      }
      if (userKw !== null && siteKw !== null) break;
    }
  } catch (e) {
    out.errors.push('bid event read error: ' + String(e));
  }

  // Normalize: keywords may arrive as a string or array of strings
  const normalize = (kw) => {
    if (kw == null) return null;
    if (Array.isArray(kw)) return kw.join(',');
    return String(kw);
  };

  const userStr = normalize(userKw);
  const siteStr = normalize(siteKw);

  out.user_keywords = userStr;
  out.site_keywords = siteStr;

  // Spaces around commas: matches "word , word" or "word ,word" or "word, word"
  const SPACE_RE = /\s,|,\s/;

  if (userStr !== null) {
    out.user_has_p_standard = userStr.includes('p_standard=');
    out.user_has_permutive  = userStr.includes('permutive=');
    out.user_spaces_found   = SPACE_RE.test(userStr);
  }

  if (siteStr !== null) {
    out.site_has_mantis         = siteStr.includes('mantis=');
    out.site_has_mantis_context = siteStr.includes('mantis_context=');
    out.site_spaces_found       = SPACE_RE.test(siteStr);
  }

  return out;
}
;
