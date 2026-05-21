# config/site_urls.py

SITE_PROFILES = {
    # -------------------------
    # Independent (LIVE)
    # -------------------------
    "independent": {
        "site_url": "https://www.independent.co.uk",
        "urls": [
            "https://www.independent.co.uk/sport/winter-olympics/lindsey-vonn-winter-olympics-crans-montana-crash-b2910786.html",
            "https://www.independent.co.uk/news/uk/home-news/golden-eagle-england-rsbp-b2809376.html",
            "https://www.independent.co.uk/news/world/middle-east/qatar-explosion-israel-airstrike-hamas-doha-latest-news-b2823119.html",
            "https://www.independent.co.uk/news/uk/home-news/london-bus-theft-mark-hehir-b2910974.html?test_group=lighteradlayout",
            "https://www.independent.co.uk/climate-change/news/shark-teeth-ocean-acidification-co2-b2814061.html",
            "https://www.independent.co.uk/news/uk/home-news/food-hunger-crisis-britain-trussell-report-poverty-b2822926.html",
        ],
    },

    # -------------------------
    # Independent (UAT)
    # -------------------------
    "independent_uat": {
        "site_url": "https://uat-web.independent.co.uk",
        "urls": [
            "https://uat-web.independent.co.uk/sport/football/belarus-scotland-live-stream-score-result-world-cup-qualifier-b2822194.html",
            "https://uat-web.independent.co.uk/news/uk/home-news/golden-eagle-england-rsbp-b2809376.html",
            "https://uat-web.independent.co.uk/climate-change/news/shark-teeth-ocean-acidification-co2-b2814061.html",
            "https://uat-web.independent.co.uk/news/uk/home-news/food-hunger-crisis-britain-trussell-report-poverty-b2822926.html",
        ],
    },

    # -------------------------
    # Independent (STAGING)
    # -------------------------
    "independent_staging": {
        "site_url": "https://staging-web.independent.co.uk",
        "urls": [
            "https://staging-web.independent.co.uk/life-style/fashion",
            "https://staging-web.independent.co.uk/life-style/fashion/asymmetric-hem-fashion-trend-2025-b2807532.html",
            "https://staging-web.independent.co.uk/life-style/fashion/topshop-cara-delevingne-sadiq-khan-adwoa-aboah-london-b2808903.html",
            "https://staging-web.independent.co.uk/sport/football/belarus-scotland-live-stream-score-result-world-cup-qualifier-b2822194.html",
            "https://staging-web.independent.co.uk/tv/lifestyle/summer-holiday-escapes-b2787278.html",
        ],
    },

    # -------------------------
    # Standard (LIVE)
    # -------------------------
    "standard": {
        "site_url": "https://www.standard.co.uk",
        "urls": [
            "https://www.standard.co.uk/news/london/kingston-ancient-market-revival-b1276991.html",
            "https://www.standard.co.uk/showbiz/holly-ramsay-adam-peaty-feud-mother-gordon-b1257683.html",
            "https://www.standard.co.uk/news/london/crazy-golf-wall-boy-dies-b1257766.html",
            "https://www.standard.co.uk/lifestyle/celebrity/brad-pitt-ines-de-ramon-relationship-b1257724.html",
            "https://www.standard.co.uk/culture/tvfilm/waitrose-christmas-advert-2025-review-keira-knightley-b1257610.html",
        ],
    },

    # Optional placeholders (enable when you have URLs)
    "standard_uat": {
        "site_url": "https://uat-web.standard.co.uk",
        "urls": [],
    },
    "standard_staging": {
        "site_url": "https://staging-web.standard.co.uk",
        "urls": [],
    },
    "standard_dev_master": {
        "site_url": "https://standard-web-dev.brightsites.co.uk/",
        "urls": [
        "https://standard-web-dev.brightsites.co.uk/news/london/homeless-man-battered-woman-mallet-pleads-guilty-b1244683.html",
        "https://standard-web-dev.brightsites.co.uk/showbiz/emmerdale-mack-boyd-death-scene-ofcom-complaints-b1244730.html",
        "https://standard-web-dev.brightsites.co.uk/sport/football/transfer-news-live-arsenal-fc-chelsea-liverpool-man-utd-hincapie-garnacho-isak-b1244334.html",
        "https://standard-web-dev.brightsites.co.uk/news/seven-athome-beauty-gadgets-that-are-really-worth-investing-in-b1244864.html",
        ],
    },
}