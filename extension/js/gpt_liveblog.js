window.__adTests = window.__adTests || {};
window.__adTests["gpt_liveblog"] = () => {
  try {
    if (!window.googletag || !googletag.pubads) return null;
    const pubads = googletag.pubads();
    if (!pubads || !pubads.getTargeting) return null;
    return pubads.getTargeting("liveblog") || [];
  } catch (e) {
    return null;
  }
}
;
