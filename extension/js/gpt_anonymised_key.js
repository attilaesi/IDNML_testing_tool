window.__adTests = window.__adTests || {};
window.__adTests["gpt_anonymised_key"] = () => {
  const out = {
    hasGpt: false,
    keyUsed: null,
    values: [],
    error: null
  };

  try {
    if (!window.googletag || !googletag.pubads) {
      return out;
    }
    const pubads = googletag.pubads();
    if (!pubads || typeof pubads.getTargeting !== "function") {
      out.hasGpt = !!pubads;
      return out;
    }

    out.hasGpt = true;

    const candidateKeys = ["AnonymisedSignalLift", "anonymised"];
    for (const k of candidateKeys) {
      try {
        const v = pubads.getTargeting(k) || [];
        if (Array.isArray(v) && v.length > 0) {
          out.keyUsed = k;
          out.values = v;
          break;
        }
      } catch (e) {
        // ignore errors per key; we'll just try the next one
      }
    }
  } catch (e) {
    out.error = String(e);
  }

  return out;
}
;
