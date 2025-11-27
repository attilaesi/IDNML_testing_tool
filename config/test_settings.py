# tests/prebid_tests/test_settings.py

"""
Geo-specific Prebid expectations.

This file keeps all UK/US config in one place so tests can:
  1. Detect geo from cookies.
  2. Look up expected bidders/modules/identity modules here.
"""

GEO_UK = "UK"
GEO_US = "US"

# --- UK config ---

UK_BIDDERS = [
    "amx",
    "appnexus",
    "connatix",
    "conversant",
    "criteo",
    "gumgum",
    "invibes",
    "ix",
    "mobkoi",
    "ozone",
    "pubmatic",
    "richaudience",
    "rubicon",
    "seedtag",
    "teads",
    "ttd",
    "taboola"
]

UK_MODULES = [
    "adpod",
    "atsAnalyticsAdapter",
    "consentManagementTcf",
    "currency",
    "gamAdServerVideo",
    "dfpAdServerVideo",
    "gptPreAuction",
    "id5AnalyticsAdapter",
    "id5IdSystem",
    "identityLinkIdSystem",
    "jwplayerRtdProvider",
    "nodalsAiRtdProvider",
    "paapi",
    "paapiForGpt",
    "pairIdSystem",
    "permutiveRtdProvider",
    "priceFloors",
    "pubxaiAnalyticsAdapter",
    "pubxaiRtdProvider",
    "rtdModule",
    "sharedIdSystem",
    "sizeMappingV2",
    "tcfControl",
    "teadsIdSystem",
    "userId",
]

UK_IDENTITY_MODULES = [
    "teadsId",
    "identityLink",
    "pairId",
    "id5Id",
]

# --- US / non-UK config ---

US_BIDDERS = [
    "adagio",
    "amx",
    "appnexus",
    "connatix",
    "criteo",
    "gumgum",
    "grid",
    "invibes",
    "ix",
    "kargo",
    "mobkoi",
    "nextMillennium",
    "ozone",
    "pubmatic",
    "rise",
    "richaudience",
    "rubicon",
    "seedtag",
    "teads",
    "ttd",
    "unifiedIdSystem",  # appears as module in some configs
    "vidazoo",
]

US_MODULES = [
    "adpod",
    "allowActivities",
    "atsAnalyticsAdapter",
    "consentManagementGpp",
    "consentManagementTcf",
    "consentManagementUsp",
    "currency",
    "gamAdServerVideo",
    "dfpAdServerVideo",
    "gppControl_usnat",
    "gptPreAuction",
    "id5AnalyticsAdapter",
    "id5IdSystem",
    "identityLinkIdSystem",
    "jwplayerRtdProvider",
    "paapi",
    "paapiForGpt",
    "pairIdSystem",
    "permutiveRtdProvider",
    "priceFloors",
    "pubProvidedIdSystem",
    "pubxaiAnalyticsAdapter",
    "rtdModule",
    "sharedIdSystem",
    "sizeMappingV2",
    "tcfControl",
    "userId",
]

US_IDENTITY_MODULES = [
    "identityLink",
    "pairId",
    "id5Id",
    "unifiedId",  # depending on how it appears in config
]

# --- Geo config map ---

GEO_CONFIG = {
    GEO_UK: {
        "bidders": UK_BIDDERS,
        "modules": UK_MODULES,
        "identity_modules": UK_IDENTITY_MODULES,
    },
    GEO_US: {
        "bidders": US_BIDDERS,
        "modules": US_MODULES,
        "identity_modules": US_IDENTITY_MODULES,
    },
}

DEFAULT_GEO = GEO_UK


def get_geo_config(geo: str) -> dict:
    """Return config dict for a given geo code."""
    return GEO_CONFIG.get(geo.upper(), GEO_CONFIG[DEFAULT_GEO])