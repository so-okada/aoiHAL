#!/usr/bin/env python3
# written by So Okada so.okada@gmail.com
# a part of aoiHAL for HAL (Hyper Articles en Ligne) announcements
# https://github.com/so-okada/aoiHAL

# user agent sent to HAL
hal_user_agent = (
    "aoiHAL/1.0 (paper announcement bot; +https://github.com/so-okada/aoiHAL)"
)

# HAL search API timeout in seconds
hal_feed_timeout = 60

# rows per HAL search request; a run pages sequentially only if a
# window holds more preprints than this
hal_feed_rows = 1000

# pacing of HAL search requests
hal_call_limit = 1
hal_call_period = 5

# retries on HTTP/JSON errors only (an empty feed is not an error)
hal_max_trial = 2
hal_call_sleep = 5 * 60
main_thread_wait = 10

# days to look back when retrieving from HAL; overridden by --days / -d
hal_days = 3

# max post length on Bluesky
max_len = 300

# HAL URLs vary in length by subdomain:
#   https://hal.science/hal-XXXXXXXXXXX    ~35 chars
#   https://shs.hal.science/halshs-XXXXXX  ~42 chars
#   https://polytechnique.hal.science/...  ~48 chars
# use 50 as safe upper bound
url_len = 50

# one URL per post
url_margin = 1
urls_len = url_len + url_margin

# order of article posts within a run:
#   "domain":  grouped by primary HAL domain (subdomains follow their
#              top-level domain), release time within a domain
#   "release": release time only
post_order = "domain"

# domain tag appended to each article post, e.g. " [math.math-co]";
# set to "" to omit.  {domain} is the entry's primaryDomain_s.
domain_tag = " [{domain}]"
min_len_authors = 60
min_len_title = 120
newsub_spacer = 1
margin = 2

# abstract tag overhead: " [X/Y of <url>]"
# " [" (2) + counter max "10/10" (5) + " of " (4) + url (50) + "]" (1) = 62
abst_tag = 12 + (url_len + url_margin) + 1

# rate limit for each Bluesky account
# https://docs.bsky.app/docs/advanced-guides/rate-limits
an_hour = 60 * 60
post_updates = 1500

# limits independent of specific categories
bsky_createaccts_sleep = 3
overall_bsky_limit_call = 2500
overall_bsky_limit_period = 5 * 60
bsky_sleep = 1
