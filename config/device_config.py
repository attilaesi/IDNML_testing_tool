# config/device_config.py
#
# Select the Playwright device profile to use for test runs.
# Playwright sets viewport, user agent, device scale factor, touch, and
# is_mobile automatically from the device name — no manual values needed.
#
# Set ACTIVE_DEVICE to any one device name from the list below.
# All others are left as comments for easy switching.
#
# Full list generated from playwright.sync_api devices dict.

ACTIVE_DEVICE = "iPhone 15 Pro Max"


# ─────────────────────────────────────────────────────────────────────────────
# DESKTOP
# ─────────────────────────────────────────────────────────────────────────────
# "Desktop Chrome"              1280x720   mobile=False
# "Desktop Chrome HiDPI"        1280x720   mobile=False
# "Desktop Edge"                1280x720   mobile=False
# "Desktop Edge HiDPI"          1280x720   mobile=False
# "Desktop Firefox"             1280x720   mobile=False
# "Desktop Firefox HiDPI"       1280x720   mobile=False
# "Desktop Safari"              1280x720   mobile=False

# ─────────────────────────────────────────────────────────────────────────────
# iPHONE
# ─────────────────────────────────────────────────────────────────────────────
# "iPhone 6"                    375x667    mobile=True
# "iPhone 6 landscape"          667x375    mobile=True
# "iPhone 6 Plus"               414x736    mobile=True
# "iPhone 6 Plus landscape"     736x414    mobile=True
# "iPhone 7"                    375x667    mobile=True
# "iPhone 7 landscape"          667x375    mobile=True
# "iPhone 7 Plus"               414x736    mobile=True
# "iPhone 7 Plus landscape"     736x414    mobile=True
# "iPhone 8"                    375x667    mobile=True
# "iPhone 8 landscape"          667x375    mobile=True
# "iPhone 8 Plus"               414x736    mobile=True
# "iPhone 8 Plus landscape"     736x414    mobile=True
# "iPhone SE"                   320x568    mobile=True
# "iPhone SE landscape"         568x320    mobile=True
# "iPhone SE (3rd gen)"         375x667    mobile=True
# "iPhone SE (3rd gen) landscape" 667x375  mobile=True
# "iPhone X"                    375x812    mobile=True
# "iPhone X landscape"          812x375    mobile=True
# "iPhone XR"                   414x896    mobile=True
# "iPhone XR landscape"         896x414    mobile=True
# "iPhone 11"                   414x715    mobile=True
# "iPhone 11 landscape"         800x364    mobile=True
# "iPhone 11 Pro"               375x635    mobile=True
# "iPhone 11 Pro landscape"     724x325    mobile=True
# "iPhone 11 Pro Max"           414x715    mobile=True
# "iPhone 11 Pro Max landscape" 808x364    mobile=True
# "iPhone 12"                   390x664    mobile=True
# "iPhone 12 landscape"         750x340    mobile=True
# "iPhone 12 Mini"              375x629    mobile=True
# "iPhone 12 Mini landscape"    712x325    mobile=True
# "iPhone 12 Pro"               390x664    mobile=True
# "iPhone 12 Pro landscape"     750x340    mobile=True
# "iPhone 12 Pro Max"           428x746    mobile=True
# "iPhone 12 Pro Max landscape" 832x378    mobile=True
# "iPhone 13"                   390x664    mobile=True
# "iPhone 13 landscape"         750x342    mobile=True
# "iPhone 13 Mini"              375x629    mobile=True
# "iPhone 13 Mini landscape"    712x327    mobile=True
# "iPhone 13 Pro"               390x664    mobile=True
# "iPhone 13 Pro landscape"     750x342    mobile=True
# "iPhone 13 Pro Max"           428x746    mobile=True
# "iPhone 13 Pro Max landscape" 832x380    mobile=True
# "iPhone 14"                   390x664    mobile=True
# "iPhone 14 landscape"         750x340    mobile=True
# "iPhone 14 Plus"              428x746    mobile=True
# "iPhone 14 Plus landscape"    832x378    mobile=True
# "iPhone 14 Pro"               393x660    mobile=True
# "iPhone 14 Pro landscape"     734x343    mobile=True
# "iPhone 14 Pro Max"           430x740    mobile=True
# "iPhone 14 Pro Max landscape" 814x380    mobile=True
# "iPhone 15"                   393x659    mobile=True
# "iPhone 15 landscape"         734x343    mobile=True
# "iPhone 15 Plus"              430x739    mobile=True
# "iPhone 15 Plus landscape"    814x380    mobile=True
# "iPhone 15 Pro"               393x659    mobile=True   ← ACTIVE
# "iPhone 15 Pro landscape"     734x343    mobile=True
# "iPhone 15 Pro Max"           430x739    mobile=True
# "iPhone 15 Pro Max landscape" 814x380    mobile=True

# ─────────────────────────────────────────────────────────────────────────────
# iPAD
# ─────────────────────────────────────────────────────────────────────────────
# "iPad Mini"                   768x1024   mobile=True
# "iPad Mini landscape"         1024x768   mobile=True
# "iPad (gen 5)"                768x1024   mobile=True
# "iPad (gen 5) landscape"      1024x768   mobile=True
# "iPad (gen 6)"                768x1024   mobile=True
# "iPad (gen 6) landscape"      1024x768   mobile=True
# "iPad (gen 7)"                810x1080   mobile=True
# "iPad (gen 7) landscape"      1080x810   mobile=True
# "iPad (gen 11)"               656x944    mobile=True
# "iPad (gen 11) landscape"     944x656    mobile=True
# "iPad Pro 11"                 834x1194   mobile=True
# "iPad Pro 11 landscape"       1194x834   mobile=True

# ─────────────────────────────────────────────────────────────────────────────
# ANDROID — SAMSUNG
# ─────────────────────────────────────────────────────────────────────────────
# "Galaxy S III"                360x640    mobile=True
# "Galaxy S III landscape"      640x360    mobile=True
# "Galaxy S5"                   360x640    mobile=True
# "Galaxy S5 landscape"         640x360    mobile=True
# "Galaxy S8"                   360x740    mobile=True
# "Galaxy S8 landscape"         740x360    mobile=True
# "Galaxy S9+"                  320x658    mobile=True
# "Galaxy S9+ landscape"        658x320    mobile=True
# "Galaxy S24"                  480x1040   mobile=True
# "Galaxy S24 landscape"        1040x480   mobile=True
# "Galaxy A55"                  480x1040   mobile=True
# "Galaxy A55 landscape"        1040x480   mobile=True
# "Galaxy Note II"              360x640    mobile=True
# "Galaxy Note II landscape"    640x360    mobile=True
# "Galaxy Note 3"               360x640    mobile=True
# "Galaxy Note 3 landscape"     640x360    mobile=True
# "Galaxy Tab S4"               712x1138   mobile=True
# "Galaxy Tab S4 landscape"     1138x712   mobile=True
# "Galaxy Tab S9"               640x1024   mobile=True
# "Galaxy Tab S9 landscape"     1024x640   mobile=True

# ─────────────────────────────────────────────────────────────────────────────
# ANDROID — GOOGLE PIXEL / NEXUS
# ─────────────────────────────────────────────────────────────────────────────
# "Pixel 2"                     411x731    mobile=True
# "Pixel 2 landscape"           731x411    mobile=True
# "Pixel 2 XL"                  411x823    mobile=True
# "Pixel 2 XL landscape"        823x411    mobile=True
# "Pixel 3"                     393x786    mobile=True
# "Pixel 3 landscape"           786x393    mobile=True
# "Pixel 4"                     353x745    mobile=True
# "Pixel 4 landscape"           745x353    mobile=True
# "Pixel 4a (5G)"               412x765    mobile=True
# "Pixel 4a (5G) landscape"     840x312    mobile=True
# "Pixel 5"                     393x727    mobile=True
# "Pixel 5 landscape"           802x293    mobile=True
# "Pixel 7"                     412x839    mobile=True
# "Pixel 7 landscape"           863x360    mobile=True
# "Nexus 4"                     384x640    mobile=True
# "Nexus 4 landscape"           640x384    mobile=True
# "Nexus 5"                     360x640    mobile=True
# "Nexus 5 landscape"           640x360    mobile=True
# "Nexus 5X"                    412x732    mobile=True
# "Nexus 5X landscape"          732x412    mobile=True
# "Nexus 6"                     412x732    mobile=True
# "Nexus 6 landscape"           732x412    mobile=True
# "Nexus 6P"                    412x732    mobile=True
# "Nexus 6P landscape"          732x412    mobile=True
# "Nexus 7"                     600x960    mobile=True
# "Nexus 7 landscape"           960x600    mobile=True
# "Nexus 10"                    800x1280   mobile=True
# "Nexus 10 landscape"          1280x800   mobile=True
# "Moto G4"                     360x640    mobile=True
# "Moto G4 landscape"           640x360    mobile=True
# "LG Optimus L70"              384x640    mobile=True
# "LG Optimus L70 landscape"    640x384    mobile=True

# ─────────────────────────────────────────────────────────────────────────────
# OTHER
# ─────────────────────────────────────────────────────────────────────────────
# "BlackBerry Z30"              360x640    mobile=True
# "BlackBerry Z30 landscape"    640x360    mobile=True
# "Blackberry PlayBook"         600x1024   mobile=True
# "Blackberry PlayBook landscape" 1024x600 mobile=True
# "Kindle Fire HDX"             800x1280   mobile=True
# "Kindle Fire HDX landscape"   1280x800   mobile=True
# "Microsoft Lumia 550"         360x640    mobile=True
# "Microsoft Lumia 550 landscape" 640x360  mobile=True
# "Microsoft Lumia 950"         360x640    mobile=True
# "Microsoft Lumia 950 landscape" 640x360  mobile=True
# "Nokia Lumia 520"             320x533    mobile=True
# "Nokia Lumia 520 landscape"   533x320    mobile=True
# "Nokia N9"                    480x854    mobile=True
# "Nokia N9 landscape"          854x480    mobile=True
