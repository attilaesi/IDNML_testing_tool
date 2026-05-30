window.__adTests = window.__adTests || {};
window.__adTests["gpt_permutive_composite"] = () => {
  try {
    if (!window.googletag || !googletag.pubads) return null;
    const pubads = googletag.pubads();
    if (!pubads || !pubads.getTargeting) return null;
    return pubads.getTargeting("permutive") || [];
  } catch (e) {
    return null;
  }
}
;
