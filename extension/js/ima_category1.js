window.__adTests = window.__adTests || {};
window.__adTests["ima_category1"] = () => {
  try {
    var req = window.__imaAdRequest;
    if (!req) return null;
    var params = req.cust_params || {};
    var val = params["category1"];
    if (val === undefined || val === null) return [];
    var s = String(val).trim();
    return s ? [s] : [''];
  } catch (e) { return null; }
}
;
