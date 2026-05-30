window.__adTests = window.__adTests || {};
window.__adTests["gpt_mantis"] = () => {
  try {
    if (!window.googletag || !googletag.pubads) return null;
    const pubads = googletag.pubads();
    if (!pubads || !pubads.getTargeting) return null;
    return pubads.getTargeting("mantis") || [];
  } catch (e) {
    return null;
  }
}
;
