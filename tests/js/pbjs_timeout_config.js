() => {
    const out = {
        timeout: null,
        timeout_source: 'none',
        bidderTimeout: null,
        auctionTimeout: null,
        config_complete: false,
        errors: []
    };

    try {
        const pbjs = window.pbjs;
        if (!pbjs) {
            out.errors.push("window.pbjs is not defined");
            return out;
        }

        if (typeof pbjs.getConfig !== "function") {
            out.errors.push("pbjs.getConfig is not available");
            return out;
        }

        const cfg = pbjs.getConfig() || {};

        // Prefer bidderTimeout, then timeout, then auctionTimeout
        if (cfg.bidderTimeout != null) {
            out.timeout = cfg.bidderTimeout;
            out.timeout_source = "bidderTimeout";
            out.bidderTimeout = cfg.bidderTimeout;
        } else if (cfg.timeout != null) {
            out.timeout = cfg.timeout;
            out.timeout_source = "timeout";
        } else if (cfg.auctionTimeout != null) {
            out.timeout = cfg.auctionTimeout;
            out.timeout_source = "auctionTimeout";
            out.auctionTimeout = cfg.auctionTimeout;
        }

        // Flag whether we see any timeout-like config at all
        out.config_complete = !!(
            cfg.bidderTimeout != null ||
            cfg.timeout != null ||
            cfg.auctionTimeout != null
        );
    } catch (e) {
        out.errors.push(String(e));
    }

    return out;
}
