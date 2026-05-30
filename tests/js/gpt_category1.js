() => {
  try {
    if (!window.googletag || !googletag.pubads) return null;
    const pubads = googletag.pubads();
    if (!pubads || !pubads.getTargeting) return null;

    return {
      pageType: pubads.getTargeting("pageType") || [],
      category1: pubads.getTargeting("category1") || []
    };
  } catch (e) {
    return null;
  }
}
