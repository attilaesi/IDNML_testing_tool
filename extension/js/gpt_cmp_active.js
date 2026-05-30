window.__adTests = window.__adTests || {};
window.__adTests["gpt_cmp_active"] = () => {
  try {
    if (!window.googletag || !googletag.pubads) return null;
    const pubads = googletag.pubads();
    if (!pubads || !pubads.getTargeting) return null;
    return pubads.getTargeting("cmpActive") || [];
  } catch (e) {
    return null;
  }
}
;
