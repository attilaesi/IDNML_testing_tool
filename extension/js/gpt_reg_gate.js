window.__adTests = window.__adTests || {};
window.__adTests["gpt_reg_gate"] = () => {
  try {
    if (!window.googletag || !googletag.pubads) return null;
    const pubads = googletag.pubads();
    if (!pubads || !pubads.getTargeting) return null;
    return pubads.getTargeting("reg_gate") || [];
  } catch (e) {
    return null;
  }
}
;
