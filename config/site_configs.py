# Site-specific configurations 

INDEPENDENT_CONFIG = {
    "site_url": "https://www.independent.co.uk",
    "sitemap_url": "https://www.independent.co.uk/sitemaps/sitemap-recent.xml",
    "cmp_selectors": {
        "css": "#notice > div.message-component.message-row.main-container > div:nth-child(2)",
        "xpath": '//*[@id="notice"]/div,[object Object],/div,[object Object],/div,[object Object],/button,[object Object],'
    }
}

# User agents 
USER_AGENTS = {
    "desktop": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/115 Safari/537.36",
    "mobile":  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
               "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15A372 Safari/604.1",
}

SITE_CONFIGS = {
    "independent": INDEPENDENT_CONFIG,
}

EVENING_STANDARD_CONFIG = {
    "site_url": "https://www.standard.co.uk",
    "sitemap_url": "https://www.standard.co.uk/sitemaps/sitemap-recent.xml",
    "cmp_selectors": {
        "css": "#notice > div.message-component.message-row.cmp-row > div.message-component.message-row.row-contentpass > div > button",
        "xpath": '//*[@id="notice"]//div[contains(@class,"row-contentpass")]//button'
    }
}

SITE_CONFIGS = {
    "independent": INDEPENDENT_CONFIG,
    "standard": EVENING_STANDARD_CONFIG,
}
