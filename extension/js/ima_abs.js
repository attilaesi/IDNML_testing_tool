window.__adTests = window.__adTests || {};
window.__adTests["ima_abs"] = () => {
  try {
    var req = window.__imaAdRequest;
    if (!req) return null;
    var params = req.cust_params || {};
    var val = params["ABS"];
    if (val === undefined || val === null) return [];
    var s = String(val).trim();
    return s ? [s] : [''];
  } catch (e) { return null; }
}
;
