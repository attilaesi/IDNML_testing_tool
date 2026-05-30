window.__adTests = window.__adTests || {};
window.__adTests["gpt_slot_dump_probe"] = () => {
  try {
    if (!window.googletag || !googletag.pubads) return null;
    const pubads = googletag.pubads();
    if (!pubads || !pubads.getSlots) return null;
    const slots = pubads.getSlots() || [];
    const out = [];
    slots.forEach(s => {
      const id = s.getSlotElementId && s.getSlotElementId();
      const adUnit = s.getAdUnitPath && s.getAdUnitPath();
      const keys = s.getTargetingKeys ? s.getTargetingKeys() : [];
      const kv = {};
      keys.forEach(k => {
        kv[k] = s.getTargeting(k) || [];
      });
      out.push({ id, adUnit, targeting: kv });
    });
    return out;
  } catch (e) {
    return null;
  }
}
;
