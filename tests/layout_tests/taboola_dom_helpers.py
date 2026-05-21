# tests/layout_tests/taboola_dom_helpers.py
#
# Shared JavaScript snippets for finding Taboola elements in the DOM.
# Imported by layout_ad_sequence_test and taboola_load_time_test.

# JS helper functions as a string fragment — embed inside a larger JS expression.
# Expects `container` to already be defined as the article container element.
TABOOLA_FINDERS_JS = r"""
    function findRecommendedBlock() {
        for (const child of container.children) {
            if (!isVisible(child)) continue;

            const label = child.querySelector("span, h2, h3, h4, [role='heading']");
            if (/^recommended$/i.test((label && label.textContent || "").trim())) {
                if (child.querySelector("ul li a")) return child;
            }

            const outer = child.matches &&
                child.matches(".trc_related_container, .tbl-trecs-container, [id^='taboola-']")
                ? child
                : child.querySelector &&
                  child.querySelector(".trc_related_container, .tbl-trecs-container, [id^='taboola-']");
            if (!outer) continue;
            const rbox = outer.querySelector(".trc_rbox");
            if (!rbox) continue;
            const layouts = [
                "alternating-thumbnails-stream-1x4",
                "alternating-thumbnails-stream-1x4-a",
                "alternating-thumbnails-d1"
            ];
            if (!layouts.some(cls => rbox.classList.contains(cls))) continue;
            const h = outer.querySelector(
                ".trc_rbox_header_span, [role='heading'], h2, h3, h4, span"
            );
            if (/^recommended$/i.test((h && h.textContent || "").trim())) return child;
        }
        return null;
    }

    function findTaboolaAd() {
        const containers = Array.from(container.querySelectorAll(
            ".trc_related_container, .tbl-trecs-container, [id^='taboola-'], .taboola"
        )).filter(isVisible);

        for (const outer of containers) {
            const rbox = outer.querySelector(
                ".trc_rbox.alternating-thumbnails-d1.trc-content-sponsored"
            );
            if (!rbox || !isVisible(rbox)) continue;
            const t = (outer.textContent || "").trim();
            if (/(promoted|sponsored|Sponsored Links|by Taboola|Promoted Links)/i.test(t)) {
                return outer;
            }
        }

        const allRboxes = Array.from(container.querySelectorAll(
            ".trc_rbox.alternating-thumbnails-d1.trc-content-sponsored"
        )).filter(isVisible);

        for (const r of allRboxes) {
            const block = r.closest(
                ".trc_related_container, .tbl-trecs-container, [id^='taboola-'], .taboola"
            ) || r;
            const t = (block.textContent || "").trim();
            if (/(promoted|sponsored|Sponsored Links|by Taboola|Promoted Links)/i.test(t)) {
                return block;
            }
        }
        return null;
    }
"""
