#!/usr/bin/env python3
# adapted from arXiv_feed_parser.py by So Okada so.okada@gmail.com
# a part of aoiHAL: entry builder for HAL (Hyper Articles en Ligne) records
# https://github.com/so-okada/aoiHAL
#
# Records are the JSON docs of HAL's search API fetched by
# HAL_search_parser.fetch (halId_s, title_s, ...); retrieve() below
# turns them into per-category entries.
#
# Design:
#   * one global request per run for the whole preprint stream, split
#     locally by primaryDomain_s.
#   * feed rule (applied server-side): docType UNDEFINED ("Preprints,
#     Working Papers, ..."), has a file, version 1, released (made
#     public) in the window.
#   * HAL text carries HTML entities (e.g. &#x27E8;), so text fields
#     are html.unescape'd here, once.

import html
import re

from aoiHAL_variables import post_order


_halid_re = re.compile(r"^([a-z]+-\d+)(v\d+)?$")
_domain_prefix_re = re.compile(r"^\d+\.")


def bare_halid(halid):
    """Strip a version suffix: 'hal-01234567v2' -> 'hal-01234567'."""
    m = _halid_re.match(halid or "")
    return m.group(1) if m else (halid or "")


def strip_domain_level(domain):
    """domain_s values carry the tree level as a prefix: '1.math.math-co'."""
    return _domain_prefix_re.sub("", domain or "")


def unescape(text):
    return html.unescape(text or "").strip()


def first(lst):
    return lst[0] if lst else ""


def matches_category(doc, cat):
    """cat is a primaryDomain_s prefix: 'math' matches 'math' and
    'math.math-ac'; 'math.math-ac' matches only itself.
    '', 'all' or '*' match everything (single whole-stream bot).
    """
    if cat in ("", "all", "*"):
        return True
    primary = doc.get("primaryDomain_s") or ""
    return primary == cat or primary.startswith(cat + ".")


class retrieve:
    """Entries of one category, built from globally fetched docs."""

    def __init__(self, cat, docs, num_found=None):
        self.cat = cat
        self.num_found = len(docs) if num_found is None else num_found

        entries = []
        seen = set()
        for doc in docs:
            if not matches_category(doc, cat):
                continue
            hal_id = bare_halid(doc.get("halId_s", ""))
            if not hal_id or hal_id in seen:
                continue
            seen.add(hal_id)

            version = doc.get("version_i", 1)
            try:
                version = int(version)
            except (ValueError, TypeError):
                version = 1

            entry = {
                "id": hal_id,
                "hal_url": doc.get("uri_s", "") or
                ("https://hal.science/" + hal_id),
                "title": unescape(first(doc.get("title_s", []))),
                "en_title": unescape(first(doc.get("en_title_s", []))),
                "authors": ", ".join(
                    unescape(a) for a in doc.get("authFullName_s", [])
                ),
                "abstract": unescape(first(doc.get("abstract_s", []))),
                "en_abstract": unescape(first(doc.get("en_abstract_s", []))),
                "label": "New submission" if version == 1 else "Replacement",
                "version": str(version),
                "primary_domain": doc.get("primaryDomain_s", "") or "",
                "domains": sorted({
                    strip_domain_level(d) for d in doc.get("domain_s", [])
                }),
                "language": first(doc.get("language_s", [])),
                "doc_subtype": doc.get("docSubType_s", "") or "",
                "arxiv_id": doc.get("arxivId_s", "") or "",
                "doi": doc.get("doiId_s", "") or "",
                "submitted_date": doc.get("submittedDate_tdate", ""),
                "released_date": doc.get("releasedDate_tdate", ""),
                "produced_date": doc.get("producedDate_tdate", ""),
            }
            entries.append(entry)

        # posting order: see post_order in aoiHAL_variables.py
        if post_order == "domain":
            entries.sort(key=lambda e: (
                e["primary_domain"], e["released_date"], e["id"]))
        else:
            entries.sort(key=lambda e: (e["released_date"], e["id"]))
        self.entries = entries
        self.identifiers = [e["id"] for e in entries]
        self.titles = [e["title"] for e in entries]
        self.authors = [e["authors"] for e in entries]
        self.abstracts = [e["abstract"] for e in entries]
        self.labels = [e["label"] for e in entries]
        self.versions = [e["version"] for e in entries]
        self.hal_urls = [e["hal_url"] for e in entries]
        self.domains = [e["domains"] for e in entries]
        self.submitted_dates = [e["submitted_date"] for e in entries]
        self.produced_dates = [e["produced_date"] for e in entries]
        self.total = len(entries)

        # all entries are first versions under the feed rule
        self.newsubmissions = [
            e for e in entries if e["label"] == "New submission"
        ]
        self.num_newsubmissions = len(self.newsubmissions)
