window.__adTests = window.__adTests || {};
window.__adTests["ima_mantis_context"] = () => {
  try {
    var req = window.__imaAdRequest;
    if (!req) return null;
    var params = req.cust_params || {};
    var val = params["mantis_context"];
    if (val === undefined || val === null) return [];
    var s = String(val).trim();
    return s ? [s] : [''];
  } catch (e) { return null; }
}
;
