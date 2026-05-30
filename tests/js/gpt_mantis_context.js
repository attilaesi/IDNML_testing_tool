() => {
  try {
    if (!window.googletag || !googletag.pubads) return null;
    const pubads = googletag.pubads();
    if (!pubads || !pubads.getTargeting) return null;
    const keys = pubads.getTargetingKeys ? pubads.getTargetingKeys() : [];
    const present = keys.includes("mantis_context");
    return {
      present,
      values: present ? (pubads.getTargeting("mantis_context") || []) : [],
    };
  } catch (e) {
    return null;
  }
}
