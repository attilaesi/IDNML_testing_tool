window.__adTests = window.__adTests || {};
window.__adTests["gpt_consent_tcf"] = () => {
  const out = {
    hasGpt: false,
    gdprKey: null,
    tcString: null,
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
      const gdprVals = pubads.getTargeting("gdpr") || [];
      if (Array.isArray(gdprVals) && gdprVals.length) {
        out.gdprKey = String(gdprVals[0]);
      }
    } catch (e) {
      out.errors.push("Error reading gdpr targeting: " + String(e));
    }

    try {
      const cookies = document.cookie ? document.cookie.split(/;\s*/) : [];
      const tcCookie = cookies.find(c => c.startsWith("euconsent-v2="));
      if (tcCookie) {
        const parts = tcCookie.split("=");
        out.tcString = parts.slice(1).join("=") || null;
      }
    } catch (e) {
      out.errors.push("Error reading euconsent-v2 cookie: " + String(e));
    }

  } catch (e) {
    out.errors.push(String(e));
  }

  return out;
}
;
