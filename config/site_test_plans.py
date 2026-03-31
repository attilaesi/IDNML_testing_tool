# config/site_test_plans.py
# -------------------------------------------------------------------
# Master test list + per-site exclusions.
# Effective tests per page:
#   allowed = ALL_TESTS
#            - SITE_TEST_PLANS[site].get("exclude", [])
#            - SITE_TEST_PLANS[site].get("exclude_by_page_type", {}).get(pageType, [])
#
# Test names use snake_case matching the test filenames.
# -------------------------------------------------------------------


SITE_TEST_PLANS = {
    "independent": {
        "exclude": [
            "gpt_untested_keys_test",
            "gpt_testgroup_test",
            "gpt_anonymised_key_test",
            "gpt_cmp_active_test",
            "gpt_longread_test",
            "gpt_referrer_test",
            "gpt_autorefresh_test",
            "gpt_commercial_test",
            "gpt_liveblog_test",
        ],
        "exclude_by_page_type": {
            "image": [],
            "index": ["layout_ad_sequence_test"],
            "video": [],
            "gallery": [],
            "liveblog": ["layout_ad_sequence_test"],
        },
    },

    "standard": {
        "exclude": [
            "gpt_untested_keys_test",
            "gpt_testgroup_test",
            "gpt_anonymised_key_test",
            "gpt_cmp_active_test",
            "gpt_longread_test",
            "gpt_referrer_test",
            "gpt_autorefresh_test",
            "gpt_commercial_test",
            "gpt_liveblog_test",
        ],
        "exclude_by_page_type": {
            "index": ["layout_ad_sequence_test"],
            "liveblog": ["layout_ad_sequence_test"],
            "image": [
                "pbjs_adunit_configuration_test",
                "pbjs_auction_activity_test",
                "pbjs_display_bidder_presence_test",
                "pbjs_video_bidder_presence_test",
                "pbjs_consent_integration_test",
                "pbjs_identity_modules_test",
                "pbjs_prebid_environment_test",
                "pbjs_prebid_timeout_config_test",
                "pbjs_price_floors_display_test",
                "pbjs_price_floors_video_test",
            ],
        },
    },
}
