() => {
    const out = {
        paragraphs: 0,
        images: 0,
        ad_slots: 0,
        slots: [],
        targeting: {}
    };

    try {
        out.paragraphs = document.querySelectorAll('#main p').length;
    } catch {}

    try {
        out.images = document.querySelectorAll('#main img').length;
    } catch {}

    try {
        const pub = googletag.pubads();
        ['category1','category2','pageType','liveblog'].forEach(k => {
            const v = pub.getTargeting(k);
            if (v?.length) out.targeting[k] = v;
        });

        const slots = pub.getSlots();
        out.ad_slots = slots.length;
        out.slots = slots.map(s => s.getAdUnitPath().split('/').pop());
    } catch (e) {
        // googletag not available or no slots
    }

    return out;
}
