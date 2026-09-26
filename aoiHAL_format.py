#!/usr/bin/env python3
# written by So Okada so.okada@gmail.com
# a part of aoiHAL for formatting HAL metadata
# https://github.com/so-okada/aoiHAL

import re
from nameparser import HumanName
from aoiHAL_variables import *


# format all new submissions
def format(entries):
    return [format_each(one) for one in entries]


def tag(entry):
    """Domain tag for an article post, e.g. ' [math.math-co]'."""
    if not domain_tag or not entry.get("primary_domain"):
        return ""
    return domain_tag.format(domain=entry["primary_domain"])


def format_each(orig_entry):
    entry = orig_entry.copy()
    entry["tag"] = tag(entry)
    # one URL per post, plus the domain tag; reserve the actual URL
    # length when it exceeds url_len
    entry_urls_len = max(urls_len, len(list(entry["hal_url"])) + url_margin)
    fixed_length = (
        entry_urls_len + newsub_spacer + margin + len(list(entry["tag"]))
    )
    orig_title = entry["title"]

    authors_title = entry["authors"] + entry["title"]
    current_len = len(list(authors_title)) + fixed_length

    # first, trim title
    if current_len > max_len:
        difference = current_len - max_len
        current_len_title = len(list(entry["title"]))
        lim = max(min_len_title, current_len_title - difference)
        entry["title"] = simple(entry["title"], lim)

    authors_title = entry["authors"] + entry["title"]
    current_len = len(list(authors_title)) + fixed_length

    # second, trim authors
    if current_len > max_len:
        difference = current_len - max_len
        current_len_authors = len(list(entry["authors"]))
        lim = max(min_len_authors, current_len_authors - difference)
        entry["authors"] = authors(entry["authors"], lim)

    # third, restore full title now that authors may be shorter
    entry["title"] = orig_title
    authors_title = entry["authors"] + entry["title"]
    current_len = len(list(authors_title)) + fixed_length

    if current_len > max_len:
        difference = current_len - max_len
        current_len_title = len(list(entry["title"]))
        lim = max(min_len_title, current_len_title - difference)
        entry["title"] = simple(entry["title"], lim)

    entry["separated_abstract"] = separate_abstract(
        entry["abstract"], entry["id"], entry["hal_url"],
        max_len - (abst_tag - urls_len + entry_urls_len) - margin
    )
    return entry


# a simple text cut
def simple(orig, lim):
    orig = orig.strip()
    wlen = len(list(orig))
    if wlen <= lim:
        return orig
    while wlen > lim:
        orig = orig[:-1]
        wlen = len(list(orig))
    return orig[:-3] + "..."


# formatting authors' names
def authors(orig, lim):
    if lim < 1:
        return ""
    if len(list(orig)) <= lim:
        return orig

    collab = collaboration(orig)
    if collab != orig:
        if len(list(collab)) <= lim:
            return collab
        else:
            return ""

    no_paren = noparen(orig)
    if len(list(no_paren)) <= lim:
        return no_paren

    sr_names = surnames(no_paren)
    if len(list(sr_names)) <= lim:
        return sr_names

    et_al = etal(no_paren)
    if len(list(et_al)) <= lim:
        return et_al

    return ""


def collaboration(orig):
    collab = re.match(r"^[^:]+collaboration:", orig, re.IGNORECASE)
    if collab:
        return re.sub(":$", "", collab.group())
    else:
        return orig


def noparen(test_str):
    ret = ""
    skip = 0
    for i in test_str:
        if i == "(":
            skip += 1
        elif i == ")":
            skip -= 1
        elif skip == 0:
            ret += i
    ret = re.sub("[ ]+,", ",", ret)
    ret = re.sub("[ ]+$", "", ret)
    return ret


def surnames(orig):
    names = orig.split(",")
    sr_names = [
        HumanName(one).last or one.strip() for one in names
    ]
    return ", ".join(sr_names)


def etal(orig):
    names = orig.split(",")
    first_author = names[0].strip()
    return first_author + ", et al."


# separate an abstract with a counter and HAL URL tag
def separate_abstract(orig, hal_id, hal_url, lim):
    sep_abstract = separate(orig, lim)
    num = len(list(sep_abstract))
    result = []
    for i, each in enumerate(sep_abstract):
        ptext = (
            each
            + " ["
            + str(i + 1)
            + "/"
            + str(num)
            + " of "
            + hal_url
            + "]"
        )
        result.append(ptext)
    return result


# separate a text into chunks of weighted length <= lim
def separate(orig, lim):
    sep_text = []
    orig = orig.strip()

    # guard against unsplittable tokens
    if any(len(list(t)) > lim for t in orig.split(" ")):
        print(
            "\n**cannot separate**"
            "\nmax weighted length: " + str(lim) +
            "\ninput: " + orig
        )
        return sep_text

    while orig:
        partial_text = orig
        wlen = len(list(partial_text))
        while wlen > lim:
            partial_text = partial_text.rsplit(" ", 1)[0]
            wlen = len(list(partial_text))
        sep_text.append(partial_text.strip())
        orig = orig[len(list(partial_text)):].strip()
    return sep_text
