window.__adTests = window.__adTests || {};
window.__adTests["gpt_gdpr_key"] = () => {
  const out = {
    hasGpt: false,
    gdprValues: [],
    errors: []
  };

  try {
    const g = window.googletag;
    if (!g || !g.pubads || typeof g.pubads !== "function") {
      out.errors.push("googletag.pubads() not available");
      return out;
    }
    const pubads = g.pubads();
    if (!pubads || typeof pubads.getTargeting !== "function") {
      out.errors.push("pubads.getTargeting() not available");
      return out;
    }
    out.hasGpt = true;

    try {
      const vals = pubads.getTargeting("gdpr") || [];
      if (Array.isArray(vals)) {
        out.gdprValues = vals.map(v => String(v));
      }
    } catch (e) {
      out.errors.push("Error reading gdpr targeting: " + String(e));
    }
  } catch (e) {
    out.errors.push(String(e));
  }

  return out;
}
;
