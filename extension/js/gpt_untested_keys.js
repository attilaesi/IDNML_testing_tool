window.__adTests = window.__adTests || {};
window.__adTests["gpt_untested_keys"] = () => {
  try {
    if (!window.googletag || !googletag.pubads) return null;
    const pubads = googletag.pubads();
    if (!pubads || !pubads.getTargetingKeys) return null;
    return pubads.getTargetingKeys() || [];
  } catch (e) {
    return null;
  }
}
;
