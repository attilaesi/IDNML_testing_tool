window.__adTests = window.__adTests || {};
window.__adTests["gpt_testgroup"] = () => {
  try {
    if (!window.googletag || !googletag.pubads) return null;
    const pubads = googletag.pubads();
    if (!pubads || !pubads.getTargeting) return null;
    return pubads.getTargeting("testgroup") || [];
  } catch (e) {
    return null;
  }
}
;
