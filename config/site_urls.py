# config/site_urls.py
#
# One URL per pagetype per profile.
# Pagetype keys must be meaningful labels — the framework also detects the real
# GPT pageType at runtime, so these are the *intended* page for each slot.
# Use None to skip a pagetype for a profile (no URL will be visited for it).

SITE_PROFILES = {
    # -------------------------
    # Independent (LIVE)
    # -------------------------
    "independent": {
        "site_url": "https://www.independent.co.uk",
        "urls": {
            "article":  "https://www.independent.co.uk/news/uk/home-news/major-oak-dead-robin-hood-b2998094.html",
            "liveblog": "https://www.independent.co.uk/news/world/middle-east/iran-us-war-live-trump-peace-deal-strait-of-hormuz-oil-b2998073.html",
            "index":    "https://www.independent.co.uk/sport",
            "video":    "https://www.independent.co.uk/news/uk/home-news/oxfordshire-council-england-flags-union-jack-b2998139.html",  # add a video article URL when available
        },
    },

    # -------------------------
    # Independent (UAT)
    # -------------------------
    "independent_uat": {
        "site_url": "https://uat-web.independent.co.uk",
        "urls": {
            "article":  "https://uat-web.independent.co.uk/news/born-with-teeth-ncuti-gatwa-wyndhams-review-b2823743.html",
            "liveblog": "https://uat-web.independent.co.uk/sport/football/belarus-scotland-live-stream-score-result-world-cup-qualifier-b2822194.html",
            "index":    "https://uat-web.independent.co.uk/sport",
            "video":    "https://uat-web.independent.co.uk/arts-entertainment/tv/reviews/the-paper-show-review-office-spinoff-tim-key-domhnall-gleeson-b2819773.html",
        },
    },

    # -------------------------
    # Independent (STAGING)
    # -------------------------
    "independent_staging": {
        "site_url": "https://staging-web.independent.co.uk",
        "urls": {
            "article":  "https://staging-web.independent.co.uk/life-style/fashion/asymmetric-hem-fashion-trend-2025-b2807532.html",
            "liveblog": "https://staging-web.independent.co.uk/sport/football/belarus-scotland-live-stream-score-result-world-cup-qualifier-b2822194.html",
            "index":    "https://staging-web.independent.co.uk/news/",
            "video":    None,
        },
    },

    # -------------------------
    # Standard (LIVE)
    # -------------------------
    "standard": {
        "site_url": "https://www.standard.co.uk",
        "urls": {
            "article":  "https://www.standard.co.uk/news/london/kingston-ancient-market-revival-b1276991.html",
            "liveblog": None,
            "index":    "https://www.standard.co.uk/news/",
            "video":    None,
        },
    },

    "standard_uat": {
        "site_url": "https://uat-web.standard.co.uk",
        "urls": {
            "article":  None,
            "liveblog": None,
            "index":    None,
            "video":    None,
        },
    },

    "standard_staging": {
        "site_url": "https://staging-web.standard.co.uk",
        "urls": {
            "article":  None,
            "liveblog": None,
            "index":    None,
            "video":    None,
        },
    },

    "standard_dev_master": {
        "site_url": "https://standard-web-dev.brightsites.co.uk/",
        "urls": {
            "article":  "https://standard-web-dev.brightsites.co.uk/news/london/homeless-man-battered-woman-mallet-pleads-guilty-b1244683.html",
            "liveblog": None,
            "index":    "https://standard-web-dev.brightsites.co.uk/news/",
            "video":    None,
        },
    },
}
