window.__adTests = window.__adTests || {};
window.__adTests["gpt_content_sources"] = () => {
  try {
    if (!window.googletag || !googletag.pubads) return null;
    const pubads = googletag.pubads();
    if (!pubads || !pubads.getTargeting) return null;
    return pubads.getTargeting("contentSources") || [];
  } catch (e) {
    return null;
  }
}
;
