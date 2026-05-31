window.__adTests = window.__adTests || {};
window.__adTests["layout_ad_sequence"] = () => {
  const MIN_CHARS = 100;
  const MAX_WAIT_MS = 2500;
  const SETTLE_MS = 400;

  const container = document.getElementById("main");
  if (!container) return { error: "no #main" };

  function getCookie(name) {
    const m = document.cookie.match(
      new RegExp("(?:^|;\\s*)" + name + "=([^;]*)")
    );
    return m ? decodeURIComponent(m[1]) : null;
  }

  const featUseLightAdRules =
    (getCookie("feat__use_light_ad_rules") || "").toLowerCase() === "true";
  const mobileCookieRaw = getCookie("is_mobile_or_tablet");
  const isMobileOrTablet = (mobileCookieRaw || "").toLowerCase() === "true";

  function isVisible(el) {
    if (!el) return false;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  function isImageBlock(el) {
    if (!el) return false;
    if (el.matches && el.matches("figure, picture")) return true;
    return !!(el.querySelector && el.querySelector("figure img, picture img, img"));
  }

  function findSlotByName(name) {
    if (!name) return null;
    let el = document.getElementById(name);
    if (el) return el;

    const base = name.replace(/-m$/, "");
    el = container.querySelector(
      '[data-tile-name="' + name + '"], [data-tile-name="' + base + '"]'
    );
    if (el) return el;

    el = container.querySelector('iframe[id*="' + name + '"]');
    if (el) {
      return el.closest("div[id], .third-party-ad, .sc-r9kkgp-2, .sc-r9kkgp-0") || el;
    }

    try {
      el = container.querySelector('[id$="' + CSS.escape(name) + '"]');
      if (el) return el;
    } catch(e) {}

    return null;
  }

  function findRecommended() {
    return document.getElementById("taboola-mid-article-thumbnails-ii") || null;
  }

  function findTaboolaAd() {
    return document.getElementById("taboola-carousel-thumbnails") || null;
  }

  function collectAllSlotNames() {
    const names = new Set();
    container.querySelectorAll("[data-tile-name]").forEach(function(el) {
      const n = el.getAttribute("data-tile-name");
      if (n) names.add(n);
    });
    container.querySelectorAll("[id]").forEach(function(el) {
      if (/^mpu\d+(?:-m)?$/.test(el.id)) names.add(el.id);
    });
    return Array.from(names);
  }

  // --- Build rule set ---
  const allSlotNames = collectAllSlotNames();
  let ruleSetName, mustHaveKeys, targets;

  if (featUseLightAdRules && isMobileOrTablet) {
    ruleSetName = "light-mobile";
    mustHaveKeys = ["mpu1-m", "taboola-mid-article-thumbnails-ii", "taboola-carousel-thumbnails"];
    targets = [
      { key:"mpu1-m",                              expectedAfter:3,  finder:function(){ return findSlotByName("mpu1-m"); } },
      { key:"taboola-mid-article-thumbnails-ii",   expectedAfter:5,  finder:findRecommended },
      { key:"taboola-carousel-thumbnails",         expectedAfter:7,  finder:findTaboolaAd },
      { key:"mpu2-m",      expectedAfter:9,  finder:function(){ return findSlotByName("mpu2-m"); } },
      { key:"mpu3-m",      expectedAfter:13, finder:function(){ return findSlotByName("mpu3-m"); } },
      { key:"mpu4-m",      expectedAfter:18, finder:function(){ return findSlotByName("mpu4-m"); } },
      { key:"mpu5-m",      expectedAfter:25, finder:function(){ return findSlotByName("mpu5-m"); } },
      { key:"mpu6-m",      expectedAfter:30, finder:function(){ return findSlotByName("mpu6-m"); } },
    ];
  } else if (isMobileOrTablet) {
    ruleSetName = "heavy-mobile";
    mustHaveKeys = ["mpu1-m", "taboola-carousel-thumbnails"];
    targets = [
      { key:"mpu1-m",                      expectedAfter:2,  finder:function(){ return findSlotByName("mpu1-m"); } },
      { key:"mpu2-m",                      expectedAfter:4,  finder:function(){ return findSlotByName("mpu2-m"); } },
      { key:"taboola-carousel-thumbnails", expectedAfter:6,  finder:findTaboolaAd },
      { key:"mpu3-m",     expectedAfter:8,  finder:function(){ return findSlotByName("mpu3-m"); } },
      { key:"mpu4-m",     expectedAfter:10, finder:function(){ return findSlotByName("mpu4-m"); } },
    ];
    const mobileMpus = allSlotNames
      .map(function(n) {
        const m = n.match(/^mpu(\d+)-m$/);
        return m ? Number(m[1]) : null;
      })
      .filter(function(n) { return n != null && n >= 5; });
    const maxN = mobileMpus.length ? Math.max.apply(null, mobileMpus) : 4;
    for (let n = 5; n <= maxN; n++) {
      (function(num) {
        targets.push({
          key: "mpu" + num + "-m",
          expectedAfter: 12 + (num - 5) * 4,
          finder: function() { return findSlotByName("mpu" + num + "-m"); }
        });
      })(n);
    }
  } else {
    ruleSetName = "heavy-desktop";
    mustHaveKeys = ["mpu1", "taboola-carousel-thumbnails"];
    targets = [
      { key:"mpu1",                        expectedAfter:3, finder:function(){ return findSlotByName("mpu1"); } },
      { key:"taboola-carousel-thumbnails", expectedAfter:6, finder:findTaboolaAd },
      { key:"mpu2",       expectedAfter:8, finder:function(){ return findSlotByName("mpu2"); } },
      { key:"mpu3",       expectedAfter:10, finder:function(){ return findSlotByName("mpu3"); } },
    ];
  }

  // --- Resolve slots ---
  const found = {};
  targets.forEach(function(t) {
    try { const el = t.finder(); if (el) found[t.key] = true; }
    catch(e) {}
  });

  const mustHavePresent = mustHaveKeys.some(function(k) { return found[k]; });
  if (!mustHavePresent) {
    return {
      ruleSetName: ruleSetName,
      skipped: true,
      reason: "None of the must-have slots found: " + mustHaveKeys.join(", "),
    };
  }

  // --- Walk DOM and count paragraphs ---
  let pCount = 0;
  let charBucket = 0;
  const firstSeen = {};
  const pCountBefore = [];
  const children = Array.from(container.children);

  // First pass: resolve slot → DOM element
  const resolvedEls = {};
  targets.forEach(function(t) {
    try { const el = t.finder(); if (el) resolvedEls[t.key] = el; }
    catch(e) {}
  });

  for (let i = 0; i < children.length; i++) {
    const child = children[i];
    if (!isVisible(child)) { pCountBefore[i] = pCount; continue; }

    targets.forEach(function(t) {
      if (firstSeen[t.key] != null) return;
      const el = resolvedEls[t.key];
      if (!el) return;
      if (child === el || child.contains(el)) firstSeen[t.key] = pCount;
    });

    pCountBefore[i] = pCount;

    if (child.tagName === "P" && child.parentElement === container) {
      const txt = (child.textContent || "").replace(/\s+/g, " ").trim();
      if (txt) {
        charBucket += txt.length;
        if (charBucket >= MIN_CHARS) { pCount++; charBucket = 0; }
      }
    }
  }

  // --- Build row results ---
  function passesImageGrace(t, seenAfter) {
    if (seenAfter !== t.expectedAfter + 1) return false;
    for (let i = 0; i < pCountBefore.length; i++) {
      if (pCountBefore[i] === t.expectedAfter) {
        const el = children[i];
        return el ? isImageBlock(el) : false;
      }
    }
    return false;
  }

  const rows = targets.map(function(t) {
    const el = resolvedEls[t.key];
    const seenAfter = firstSeen[t.key];
    let status;

    // Article too short — slot not expected at this length.
    if (pCount <= t.expectedAfter) {
      status = "SKIPPED (article too short: " + pCount + " paragraphs, needs >" + t.expectedAfter + ")";
    // Article long enough — slot was expected but not found.
    } else if (!el) {
      status = "FAIL (missing — expected after paragraph " + t.expectedAfter + ")";
    } else if (seenAfter == null) {
      status = "FAIL (anchor exists but not found inside #main)";
    } else if (seenAfter === t.expectedAfter) {
      status = "PASS";
    } else if (passesImageGrace(t, seenAfter)) {
      status = "PASS (image shift to " + seenAfter + ")";
    } else if (Math.abs(seenAfter - t.expectedAfter) === 1) {
      status = "WARN (seen after " + seenAfter + ", expected " + t.expectedAfter + ")";
    } else {
      status = "FAIL (misplaced — seen after " + seenAfter + ", expected " + t.expectedAfter + ")";
    }

    return {
      unit: t.key,
      expectedAfter: t.expectedAfter,
      seenAfter: (el && seenAfter != null) ? seenAfter : null,
      status: status,
    };
  });

  // --- DOM slots found on the page ---
  const domSlots = collectAllSlotNames().sort();

  // --- GPT slot ad unit paths ---
  const gptSlots = [];
  try {
    if (window.googletag && googletag.pubads) {
      (googletag.pubads().getSlots() || []).forEach(function(s) {
        const path = s.getAdUnitPath ? s.getAdUnitPath() : null;
        const id = s.getSlotElementId ? s.getSlotElementId() : null;
        if (path || id) gptSlots.push(id || path);
      });
    }
  } catch(e) {}

  // --- Slot number continuity check ---
  // Extract mpu numbers from resolved slots and verify no gaps in sequence.
  const mpuSuffix = isMobileOrTablet ? "-m" : "";
  const mpuRe = isMobileOrTablet ? /^mpu(\d+)-m$/ : /^mpu(\d+)$/;
  const mpuNums = Object.keys(resolvedEls)
    .map(function(k) { const m = k.match(mpuRe); return m ? Number(m[1]) : null; })
    .filter(function(n) { return n != null; })
    .sort(function(a, b) { return a - b; });

  let continuityFail = null;
  if (mpuNums.length >= 2) {
    for (let i = 1; i < mpuNums.length; i++) {
      if (mpuNums[i] !== mpuNums[i - 1] + 1) {
        continuityFail = "mpu" + mpuNums[i - 1] + mpuSuffix
          + " → mpu" + mpuNums[i] + mpuSuffix
          + " (gap: missing mpu" + (mpuNums[i - 1] + 1) + mpuSuffix + ")";
        break;
      }
    }
  }

  return {
    ruleSetName: ruleSetName,
    isMobileOrTablet: isMobileOrTablet,
    mobileCookieRaw: mobileCookieRaw,
    featUseLightAdRules: featUseLightAdRules,
    totalParagraphs: pCount,
    domSlots: domSlots,
    gptSlots: gptSlots,
    mpuSequence: mpuNums,
    continuityFail: continuityFail,
    rows: rows,
  };
}
;
