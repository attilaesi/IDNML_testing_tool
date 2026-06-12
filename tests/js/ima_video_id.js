() => {
  try {
    var req = window.__imaAdRequest;
    if (!req) return null;
    var params = req.cust_params || {};
    var val = params["videoID"];
    if (val === undefined || val === null) return [];
    var s = String(val).trim();
    return s ? [s] : [''];
  } catch (e) { return null; }
}
