#!/usr/bin/env python3
# written by So Okada so.okada@gmail.com
# a part of aoiHAL: HAL search API retriever
# https://github.com/so-okada/aoiHAL
#
#   https://api.archives-ouvertes.fr/search/
#     ?q=*:*&fq=docType_s:UNDEFINED&fq=submitType_s:file&fq=version_i:1
#     &fq=releasedDate_tdate:[<start> TO *]&fl=...&wt=json
# docs: https://api.archives-ouvertes.fr/docs/search
#
# The feed rule is applied server-side: docType UNDEFINED (HAL
# document type "Preprints, Working Papers, ..."), has a full-text
# file, version 1, released (made public) in the window.  One request
# per run; cursorMark paging, sequentially, only if a window exceeds
# `rows`.  Records are the JSON docs of the search API (halId_s,
# title_s, ...), consumed by HAL_feed_parser.retrieve.
#
# Notes:
#   * brackets and spaces in the date range must be percent-encoded
#     (%5B %5D %20); otherwise HAL's front end answers an empty 200.
#   * a 200 with numFound 0 is a valid answer (nothing released).
#   * cursorMark needs a sort ending with the unique key docid.

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from aoiHAL_variables import hal_user_agent, hal_feed_rows

hal_search = "https://api.archives-ouvertes.fr/search/"

hal_filters = [
    "docType_s:UNDEFINED",
    "submitType_s:file",
    "version_i:1",
]

hal_fields = [
    "docid",
    "halId_s",
    "version_i",
    "uri_s",
    "title_s",
    "en_title_s",
    "authFullName_s",
    "abstract_s",
    "en_abstract_s",
    "primaryDomain_s",
    "level0_domain_s",
    "domain_s",
    "language_s",
    "docType_s",
    "docSubType_s",
    "submitType_s",
    "keyword_s",
    "doiId_s",
    "arxivId_s",
    "submittedDate_tdate",
    "releasedDate_tdate",
    "modifiedDate_tdate",
    "producedDate_tdate",
]

hal_sort = "releasedDate_tdate asc,docid asc"

# safety cap on cursorMark paging
hal_max_pages = 100


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def query_url(start, rows, cursor="*"):
    """Search URL for preprints released since `start` (aware UTC)."""
    params = [
        ("q", "*:*"),
        ("fq", "releasedDate_tdate:[" + _iso(start) + " TO *]"),
    ]
    params += [("fq", f) for f in hal_filters]
    params += [
        ("fl", ",".join(hal_fields)),
        ("sort", hal_sort),
        ("rows", str(rows)),
        ("cursorMark", cursor),
        ("wt", "json"),
    ]
    return hal_search + "?" + urllib.parse.urlencode(
        params, quote_via=urllib.parse.quote
    )


def _get(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": hal_user_agent})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def parse_response(content):
    """JSON bytes -> (docs, num_found, next_cursor).  Raises on a
    malformed body (e.g. the empty 200 of a badly encoded URL)."""
    try:
        data = json.loads(content)
    except ValueError as e:
        raise ValueError("malformed HAL search response: " + str(e))
    if not isinstance(data, dict) or "response" not in data:
        err = data.get("error", {}) if isinstance(data, dict) else {}
        raise ValueError(
            "HAL search error: " + str(err.get("msg", "no response field"))
        )
    resp = data["response"]
    if not isinstance(resp, dict) or "docs" not in resp \
            or "numFound" not in resp:
        raise ValueError(
            "malformed HAL search response: missing docs or numFound"
        )
    docs, num_found = resp["docs"], resp["numFound"]
    if not isinstance(docs, list) or type(num_found) is not int \
            or num_found < 0:
        raise ValueError(
            "malformed HAL search response: invalid docs or numFound"
        )
    return docs, num_found, data.get("nextCursorMark")


def fetch(days, timeout=60, page_sleep=5, rows=None):
    """Preprints released in the last `days` days.

    Returns (docs, num_found, num_requests).  Pages sequentially with
    cursorMark, `page_sleep` seconds apart, only when numFound exceeds
    `rows`.  If paging stops early, warns and returns the available docs.
    """
    rows = hal_feed_rows if rows is None else rows
    start = datetime.now(timezone.utc) - timedelta(days=days)

    docs = []
    num_found = 0
    num_requests = 0
    cursor = "*"
    while True:
        t0 = time.time()
        content = _get(query_url(start, rows, cursor), timeout)
        num_requests += 1
        page, num_found, next_cursor = parse_response(content)
        docs.extend(page)
        print(
            "HAL search page " + str(num_requests)
            + " (" + str(round(time.time() - t0, 1)) + "s): "
            + str(len(docs)) + " of numFound " + str(num_found),
            flush=True,
        )
        if len(docs) >= num_found:
            break
        if not page or not next_cursor or next_cursor == cursor \
                or num_requests >= hal_max_pages:
            print(
                "WARNING: HAL search paging stopped early: retrieved "
                + str(len(docs)) + " of numFound " + str(num_found)
                + "; using available records.",
                flush=True,
            )
            break
        cursor = next_cursor
        time.sleep(page_sleep)

    return docs, num_found, num_requests
