window.__adTests = window.__adTests || {};
window.__adTests["pbjs_environment"] = () => {
    const out = {
        pbjs_loaded: false,
        queue_ready: false,
        version: null,
        installed_modules: [],
        errors: []
    };

    try {
        const pbjs = window.pbjs;

        if (!pbjs) {
            return out;
        }

        out.pbjs_loaded = true;
        out.queue_ready = Array.isArray(pbjs.que);
        out.version = pbjs.version || null;

        if (Array.isArray(pbjs.installedModules)) {
            out.installed_modules = pbjs.installedModules.slice();
        }
    } catch (e) {
        out.errors.push(String(e));
    }

    return out;
}
;
