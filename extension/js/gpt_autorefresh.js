window.__adTests = window.__adTests || {};
window.__adTests["gpt_autorefresh"] = () => {
  try {
    if (!window.googletag || !googletag.pubads) return null;
    const pubads = googletag.pubads();
    if (!pubads || !pubads.getTargeting) return null;
    return pubads.getTargeting("autorefresh") || [];
  } catch (e) {
    return null;
  }
}
;
