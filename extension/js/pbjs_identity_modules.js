window.__adTests = window.__adTests || {};
window.__adTests["pbjs_identity_modules"] = () => {
  const out = {
    userIds: [],
    userSync: null
  };

  if (!window.pbjs || !window.pbjs.getConfig) {
    return out;
  }

  const cfg = window.pbjs.getConfig() || {};
  const us = cfg.userSync || {};
  const ids = Array.isArray(us.userIds) ? us.userIds : [];

  out.userIds = ids.map(u => u && u.name).filter(Boolean);
  out.userSync = us;
  return out;
}
;
