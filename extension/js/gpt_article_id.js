window.__adTests = window.__adTests || {};
window.__adTests["gpt_article_id"] = () => {
  try {
    if (!window.googletag || !googletag.pubads) return null;
    const pubads = googletag.pubads();
    if (!pubads || !pubads.getTargetingKeys) return null;

    const out = {};
    const keys = pubads.getTargetingKeys() || [];
    keys.forEach(k => {
      out[k] = pubads.getTargeting(k) || [];
    });
    return out;
  } catch (e) {
    return null;
  }
}
;
