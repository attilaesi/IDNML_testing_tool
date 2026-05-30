() => {
  try {
    const cookies = document.cookie ? document.cookie.split(/;\s*/) : [];
    for (const c of cookies) {
      const idx = c.indexOf("=");
      if (idx === -1) continue;
      const name = c.slice(0, idx).trim();
      if (name === "is_mobile_or_tablet") {
        return c.slice(idx + 1).trim() || null;
      }
    }
    return null;
  } catch (e) {
    return null;
  }
}
