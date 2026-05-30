window.__adTests = window.__adTests || {};
window.__adTests["pbjs_consent_integration"] = () => {
  const w = window;
  const out = {
    hasPbjs: !!w.pbjs,
    hasGetConfig: false,
    consentManagement: null,
    gdpr: null,
    usp: null,
    gpp: null,
    error: null
  };

  if (!w.pbjs || typeof w.pbjs.getConfig !== "function") {
    out.hasGetConfig = !!(w.pbjs && typeof w.pbjs.getConfig === "function");
    return out;
  }

  out.hasGetConfig = true;

  try {
    const cfg = w.pbjs.getConfig() || {};
    const cm = cfg.consentManagement || {};
    out.consentManagement = cm || null;
    out.gdpr = cm.gdpr || null;
    out.usp  = cm.usp  || null;
    out.gpp  = cm.gpp  || null;
  } catch (e) {
    out.error = String(e && e.message ? e.message : e);
  }

  return out;
}
;
