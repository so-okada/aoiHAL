#!/usr/bin/env python3
# written by So Okada so.okada@gmail.com
# a part of aoiHAL for retrieval of HAL feeds
# https://github.com/so-okada/aoiHAL
#
# One global HAL search request per run, shared by all category
# threads (cached under a lock); each category then filters locally.

import time
import threading
from datetime import datetime, timezone
from ratelimit import limits, sleep_and_retry

from aoiHAL_variables import *
import HAL_feed_parser as hfpa
import HAL_search_parser as hspa


_cache = {"days": None, "docs": None, "num_found": 0}
_cache_lock = threading.Lock()


def days_to_fetch():
    """Number of past days to retrieve: hal_days, or hal_days_monday
    on Mondays."""
    weekday = datetime.now(timezone.utc).weekday()
    if weekday == 0:  # Monday
        return hal_days_monday
    return hal_days


@sleep_and_retry
@limits(calls=hal_call_limit, period=hal_call_period)
def hal_fetch(days):
    return hspa.fetch(
        days,
        timeout=hal_feed_timeout,
        page_sleep=hal_call_period,
    )


def hal_docs(days):
    """All HAL preprints of the last `days` days, retrieved once per run.

    Retries only on exceptions (HTTP/JSON errors); an empty result is
    a valid answer and is cached like any other.  Raises after
    hal_max_trial failures.
    """
    with _cache_lock:
        if _cache["days"] == days and _cache["docs"] is not None:
            return _cache["docs"], _cache["num_found"]

        trial_num = 0
        while True:
            try:
                docs, num_found, num_requests = hal_fetch(days)
                print(
                    "HAL preprints of the last " + str(days) + " day(s): "
                    + str(len(docs)) + " (numFound " + str(num_found)
                    + ", " + str(num_requests) + " request(s))"
                )
                _cache["days"] = days
                _cache["docs"] = docs
                _cache["num_found"] = num_found
                return docs, num_found
            except Exception as e:
                trial_num += 1
                print(
                    str(trial_num) + "th HAL feed error: " + str(e)
                )
                if trial_num >= hal_max_trial:
                    raise Exception("fatal HAL feed error")
                print("sleep and retry for HAL")
                time.sleep(hal_call_sleep)


def hal_entries(cat, days=None):
    """HAL_feed_parser.retrieve object of one category for the last
    `days` days (days_to_fetch() if None)."""
    if days is None:
        days = days_to_fetch()
    docs, num_found = hal_docs(days)
    return hfpa.retrieve(cat, docs, num_found)
