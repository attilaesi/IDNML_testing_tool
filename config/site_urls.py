# config/site_urls.py

SITE_PROFILES = {
    "independent": {
        "site_url": "https://www.independent.co.uk",
        "live_urls": [
            "https://www.independent.co.uk/tech/cloudflare-down-twitter-not-working-outage-b2867367.html",
            "https://www.independent.co.uk/news/uk/politics/lord-edmiston-australia-uk-brexit-conservative-budget-b2861973.html",
            "https://www.independent.co.uk/news/world/europe/turkey-georgia-plane-crash-azerbaijan-soldiers-deaths-b2863408.html",
            "https://www.independent.co.uk/news/world/europe/ukraine-russia-war-trump-putin-zelensky-pokrovsk-latest-news-b2863404.html",
        ],
        "uat_urls": [
            "https://uat-web.independent.co.uk/news/test-test-test-nhl-las-vegas-marty-walsh-canada-ontario-b2823642.html",
            "https://uat-web.independent.co.uk/news/test-test-test-chagos-diego-garcia-trump-legal-case-b2823645.html",
            "https://uat-web.independent.co.uk/news/world/middle-east/qatar-explosion-israel-airstrike-hamas-doha-latest-news-b2823119.html",
            "https://uat-web.independent.co.uk/news/test-test-test-snp-kirsty-blackman-commons-mps-children-b2823608.html",
            "https://uat-web.independent.co.uk/climate-change/news/shark-teeth-ocean-acidification-co2-b2814061.html"
        ],
    },

    "standard": {
        "site_url": "https://www.standard.co.uk",
        "live_urls": [
            "https://www.standard.co.uk/showbiz/holly-ramsay-adam-peaty-feud-mother-gordon-b1257683.html",
            "https://www.standard.co.uk/news/london/crazy-golf-wall-boy-dies-b1257766.html",
            "https://www.standard.co.uk/lifestyle/celebrity/brad-pitt-ines-de-ramon-relationship-b1257724.html",
            "https://www.standard.co.uk/culture/tvfilm/waitrose-christmas-advert-2025-review-keira-knightley-b1257610.html",
        ],
        # Add UAT URLs later when ready:
        "uat_urls": [],
    },
}