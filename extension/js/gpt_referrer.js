window.__adTests = window.__adTests || {};
window.__adTests["gpt_referrer"] = () => {
  const out = { gptReferrer: null, docReferrer: null, hasGpt: false };
  try {
    out.docReferrer = document.referrer || "";
  } catch (e) {}
  try {
    if (window.googletag && googletag.pubads) {
      const pubads = googletag.pubads();
      if (pubads && pubads.getTargeting) {
        out.hasGpt = true;
        const vals = pubads.getTargeting("referrer") || [];
        if (vals.length) out.gptReferrer = String(vals[0] || "");
      }
    }
  } catch (e) {}
  return out;
}
;
