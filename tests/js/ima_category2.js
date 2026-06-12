() => {
  try {
    var req = window.__imaAdRequest;
    if (!req) return null;
    var params = req.cust_params || {};
    function getVal(key) {
      var val = params[key];
      if (val === undefined || val === null) return [];
      var s = String(val).trim();
      return s ? [s] : [''];
    }
    return { category1: getVal("category1"), category2: getVal("category2") };
  } catch (e) { return null; }
}
