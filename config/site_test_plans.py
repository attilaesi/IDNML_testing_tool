# config/site_test_plans.py
# -------------------------------------------------------------------
# Master test list + per-site exclusions.
# Effective tests per page:
#   allowed = ALL_TESTS
#            - SITE_TEST_PLANS[site].get("exclude", [])
#            - SITE_TEST_PLANS[site].get("exclude_by_page_type", {}).get(pageType, [])
# -------------------------------------------------------------------


#Run all test by default for each site. Here you can configure the ones not wanting to run for a site: 
SITE_TEST_PLANS = {
    "independent": {
        "exclude": [

            "UntestedKeysTest",
            "TestgroupTest",
            "AnonymisedKeyTest",
            "CmpActiveTest",
            "LongreadTest",
            "ReferrerTest",
            "AutorefreshTest",
            "CommercialTest",
            "LiveblogTest"


        ],
        "exclude_by_page_type": {

            "image": [],
            "index": [],
             "video": [],
             "gallery": [],
        },
    },

    "standard": {
        "exclude": [
            # (example) nothing globally excluded right now
        ],
        "exclude_by_page_type": {
            # Example parity with Independent
            "image": [
                "AdUnitConfigurationTest",
                "AuctionActivityTest",
                "BidderPresenceTest",
                "ConsentIntegrationTest",
                "IdentityModulesTest",
                "PrebidEnvironmentTest",
                "PrebidTimeoutConfigTest",
                "PriceFloorsTest",
            ],
        },
    },
}