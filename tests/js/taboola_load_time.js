([loaderUrl, timeoutMs, placements]) => new Promise(function(resolve) {
    const resources = performance.getEntriesByType("resource");

    const loaderEntry = resources.find(function(e) {
        return e.name.indexOf(loaderUrl) !== -1;
    });
    if (!loaderEntry) {
        return resolve({ loaderPresent: false });
    }

    const tScriptStart = loaderEntry.startTime;
    const tScript = loaderEntry.responseEnd;

    // A placement is "rendered" when Taboola has injected
    // .trc_rbox_container inside the anchor div.
    function isRendered(containerId) {
        const el = document.getElementById(containerId);
        if (!el) return false;
        return !!el.querySelector(".trc_rbox_container");
    }

    // Track timing per placement: null = not yet found
    const times = {};
    placements.forEach(function(p) { times[p[0]] = null; });

    const startedAt = performance.now();

    const interval = setInterval(function() {
        const elapsed = performance.now() - startedAt;

        placements.forEach(function(p) {
            const key = p[0], cid = p[1];
            if (times[key] === null && isRendered(cid)) {
                times[key] = Math.round(performance.now());
            }
        });

        const allFound = placements.every(function(p) { return times[p[0]] !== null; });
        if (!allFound && elapsed < timeoutMs) return;

        clearInterval(interval);

        const deltas = {};
        placements.forEach(function(p) {
            const key = p[0];
            deltas[key] = times[key] !== null
                ? Math.round(times[key] - tScript)
                : null;
        });

        resolve({
            loaderPresent:   true,
            tScriptStart:    Math.round(tScriptStart),
            tScript:         Math.round(tScript),
            deltas:          deltas,
            timedOutAfterMs: Math.round(elapsed),
        });
    }, 200);
})
