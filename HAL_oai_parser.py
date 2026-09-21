#!/usr/bin/env python3
# written by So Okada so.okada@gmail.com
# a part of aoiHAL: OAI-PMH (xml-tei) harvester for HAL
# https://github.com/so-okada/aoiHAL
#
#   https://api.archives-ouvertes.fr/oai/hal/
#     ?verb=ListRecords&metadataPrefix=xml-tei&set=type:UNDEFINED&from=...
# The set type:UNDEFINED (HAL document type "Preprints, Working
# Papers, ...") selects server-side; "has a file", "version 1" and
# "released in the window" are checked here from the AOfr TEI record
# (schema: https://api.archives-ouvertes.fr/documents/aofr.xsd).
# Records are returned as dicts keyed like HAL's search API fields
# (halId_s, title_s, ...), consumed by HAL_feed_parser.retrieve.
#
# OAI-PMH caveats:
#   * `from` selects on the OAI datestamp (last modification, day
#     granularity), so old records that were edited reappear; we keep
#     only those whose whenReleased (the date the deposit became
#     public, which can be later than whenSubmitted) falls in the
#     window, and the post log dedups.
#   * a record lists every version as an <edition>; the one with
#     type="current" is the live version.
#   * errors come as <error code="..."> inside an HTTP 200;
#     noRecordsMatch is the normal "nothing today" and is not an error.
#   * one set per request; paging via resumptionToken.

import html
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from aoiHAL_variables import hal_user_agent

hal_oai = "https://api.archives-ouvertes.fr/oai/hal/"
hal_oai_set = "type:UNDEFINED"
hal_oai_prefix = "xml-tei"

NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "tei": "http://www.tei-c.org/ns/1.0",
}
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

_version_re = re.compile(r"v(\d+)$")


def _text(el):
    if el is None:
        return ""
    return html.unescape("".join(el.itertext())).strip()


def _parse_date(s):
    """HAL TEI dates: '2026-09-12 10:00:00' or '2026-09-12T10:00:00Z' or
    '2026-09-12'.  Returns an aware UTC datetime or None."""
    s = (s or "").strip()
    if not s:
        return None
    s = s.replace("T", " ").replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else ""


def record_to_doc(record):
    """One <record> -> dict in search-API field names, or None if the
    record is deleted or malformed."""
    header = record.find("oai:header", NS)
    if header is None or header.get("status") == "deleted":
        return None
    oai_id = _text(header.find("oai:identifier", NS))
    bibl = record.find(".//tei:biblFull", NS)
    if bibl is None:
        return None

    # identifiers
    hal_id = ""
    hal_uri = ""
    for idno in bibl.findall("tei:publicationStmt/tei:idno", NS):
        if idno.get("type") == "halId":
            hal_id = _text(idno)
        elif idno.get("type") == "halUri":
            hal_uri = _text(idno)
    if not hal_id:
        hal_id = oai_id.rsplit(":", 1)[-1]
        hal_id = _version_re.sub("", hal_id)

    # version, dates, files: the type="current" edition (else the last)
    version = 1
    submitted = released = modified = produced = None
    has_file = False
    editions = bibl.findall("tei:editionStmt/tei:edition", NS)
    current = [e for e in editions if e.get("type") == "current"]
    edition = current[0] if current else (editions[-1] if editions else None)
    if edition is not None:
        m = _version_re.search(edition.get("n", "") or "")
        if m:
            version = int(m.group(1))
        for d in edition.findall("tei:date", NS):
            t = d.get("type")
            if t == "whenSubmitted":
                submitted = _parse_date(_text(d))
            elif t == "whenReleased":
                released = _parse_date(_text(d))
            elif t == "whenModified":
                modified = _parse_date(_text(d))
            elif t == "whenProduced":
                produced = _parse_date(_text(d))
        has_file = any(
            r.get("type") == "file" for r in edition.findall("tei:ref", NS)
        )
    if not hal_uri:
        hal_uri = "https://hal.science/" + hal_id
    uri_versioned = hal_uri.rstrip("/") + "v" + str(version)

    # titles / abstracts by language
    titles, en_titles = [], []
    for t in bibl.findall("tei:titleStmt/tei:title", NS):
        s = _text(t)
        if not s:
            continue
        titles.append(s)
        if t.get(XML_LANG) == "en":
            en_titles.append(s)
    abstracts, en_abstracts = [], []
    for a in bibl.findall("tei:profileDesc/tei:abstract", NS):
        s = _text(a)
        if not s:
            continue
        abstracts.append(s)
        if a.get(XML_LANG) == "en":
            en_abstracts.append(s)

    # authors
    authors = []
    for au in bibl.findall("tei:titleStmt/tei:author", NS):
        pn = au.find("tei:persName", NS)
        if pn is None:
            continue
        fore = " ".join(_text(f) for f in pn.findall("tei:forename", NS))
        sur = _text(pn.find("tei:surname", NS))
        name = (fore + " " + sur).strip()
        if name:
            authors.append(name)

    # classification
    domains, doc_type = [], ""
    for cc in bibl.findall("tei:profileDesc/tei:textClass/tei:classCode", NS):
        scheme = cc.get("scheme")
        if scheme == "halDomain" and cc.get("n"):
            domains.append(cc.get("n"))
        elif scheme == "halTypology":
            doc_type = cc.get("n", "") or ""
    primary = domains[0] if domains else ""

    lang = bibl.find("tei:profileDesc/tei:langUsage/tei:language", NS)
    language = lang.get("ident", "") if lang is not None else ""

    arxiv = doi = ""
    for idno in bibl.findall("tei:sourceDesc/tei:biblStruct/tei:idno", NS):
        if idno.get("type") == "arxiv":
            arxiv = _text(idno)
        elif idno.get("type") == "doi":
            doi = _text(idno)

    keywords = [
        _text(t) for t in bibl.findall(
            "tei:profileDesc/tei:textClass/tei:keywords/tei:term", NS)
    ]

    return {
        "halId_s": hal_id,
        "version_i": version,
        "uri_s": uri_versioned,
        "title_s": titles,
        "en_title_s": en_titles,
        "authFullName_s": authors,
        "abstract_s": abstracts,
        "en_abstract_s": en_abstracts,
        "primaryDomain_s": primary,
        "level0_domain_s": sorted({d.split(".")[0] for d in domains}),
        # search API style: level-prefixed paths
        "domain_s": [str(d.count(".")) + "." + d for d in domains],
        "language_s": [language] if language else [],
        "docType_s": doc_type,
        "submitType_s": "file" if has_file else "notice",
        "keyword_s": keywords,
        "doiId_s": doi,
        "arxivId_s": arxiv,
        "submittedDate_tdate": _iso(submitted),
        "releasedDate_tdate": _iso(released or submitted),
        "modifiedDate_tdate": _iso(modified),
        "producedDate_tdate": _iso(produced),
    }


def _get(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": hal_user_agent})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch(days, timeout=60, page_sleep=5):
    """ListRecords over the last `days` days of the type:UNDEFINED set.

    Returns (docs, num_found, num_requests).  Applies the feed rule
    client-side: docType UNDEFINED, has a file, version 1,
    whenReleased in window.  `from` is sent one day earlier than the
    window because the OAI datestamp is day-granular and can lag the
    release.  The OAI page size is server-chosen (100 for HAL); pages
    are followed via resumptionToken with `page_sleep` between.
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    params = {
        "verb": "ListRecords",
        "metadataPrefix": hal_oai_prefix,
        "set": hal_oai_set,
        "from": (start - timedelta(days=1)).strftime("%Y-%m-%d"),
    }
    url = hal_oai + "?" + urllib.parse.urlencode(params)

    docs = []
    num_requests = 0
    complete_size = None
    while True:
        content = _get(url, timeout)
        num_requests += 1
        root = ET.fromstring(content)
        err = root.find("oai:error", NS)
        if err is not None:
            if err.get("code") == "noRecordsMatch":
                break
            raise ValueError(
                "OAI-PMH error " + str(err.get("code")) + ": " + _text(err)
            )
        lr = root.find("oai:ListRecords", NS)
        if lr is None:
            raise ValueError("malformed OAI-PMH response (no ListRecords)")
        for record in lr.findall("oai:record", NS):
            doc = record_to_doc(record)
            if doc is None:
                continue
            if doc["docType_s"] and doc["docType_s"] != "UNDEFINED":
                continue
            if doc["submitType_s"] != "file" or doc["version_i"] != 1:
                continue
            rel = _parse_date(doc["releasedDate_tdate"])
            if rel is None or rel < start:
                continue  # edited old record re-emitted by the datestamp
            docs.append(doc)
        token = lr.find("oai:resumptionToken", NS)
        if token is not None and token.get("completeListSize"):
            complete_size = int(token.get("completeListSize"))
        if token is None or not (token.text or "").strip():
            break
        url = hal_oai + "?" + urllib.parse.urlencode(
            {"verb": "ListRecords", "resumptionToken": token.text.strip()}
        )
        time.sleep(page_sleep)

    # deposit order
    docs.sort(key=lambda d: (d["releasedDate_tdate"], d["halId_s"]))
    num_found = complete_size if complete_size is not None else len(docs)
    return docs, num_found, num_requests
