() => {
    const out = {
        ad_units: [],
        errors: []
    };

    try {
        const pbjs = window.pbjs;
        if (!pbjs || !Array.isArray(pbjs.adUnits)) {
            out.errors.push("pbjs.adUnits is not an array");
            return out;
        }

        out.ad_units = pbjs.adUnits.map((unit) => {
            const bids = Array.isArray(unit.bids) ? unit.bids : [];
            const bidderCodes = bids
                .map(b => b && b.bidder)
                .filter(Boolean);

            const sizes =
                unit.sizes
                || (unit.mediaTypes && unit.mediaTypes.banner && unit.mediaTypes.banner.sizes)
                || [];

            return {
                code: unit.code || unit.adUnitCode || null,
                bidders: bidderCodes,
                sizes: sizes,
                mediaTypes: unit.mediaTypes || {},
            };
        });
    } catch (e) {
        out.errors.push(String(e));
    }

    return out;
}
