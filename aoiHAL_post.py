#!/usr/bin/env python3
# written by So Okada so.okada@gmail.com
# a part of aoiHAL for posting to Bluesky and stdout
# https://github.com/so-okada/aoiHAL

import re
import os
import time
import traceback
from atproto import Client
import pandas as pd
from threading import Thread
from datetime import datetime, timedelta, timezone
from ratelimit import limits, sleep_and_retry, rate_limited
from aoiHAL_variables import *
import aoiHAL_format as aHf
import aoiHAL_feed as aHd


def main(switches, logfiles, captions, pt_days, pt_mode):
    starting_time = datetime.now(timezone.utc).replace(microsecond=0)
    print("**process started at " + str(starting_time) + " (UTC)")

    client_dict = {}
    update_dict = {}
    entries_dict = {}
    webreplacements_dict = {}
    caption_dict = {}

    newsubmission_mode = {}
    abstract_mode = {}
    quote_replacement_mode = {}
    repost_replacement_mode = {}

    for cat in switches:
        # no Bluesky login in stdout mode
        client_dict[cat] = (
            atproto_client(switches[cat]) if pt_mode else None
        )
        update_dict[cat] = sleep_and_retry(
            rate_limited(post_updates, an_hour)(update)
        )
        newsubmission_mode[cat] = int(switches[cat]["newsubmissions"])
        abstract_mode[cat] = int(switches[cat]["abstracts"])
        quote_replacement_mode[cat] = int(
            switches[cat]["quote_replacements"]
        )
        repost_replacement_mode[cat] = int(
            switches[cat]["repost_replacements"]
        )
        caption_dict[cat] = captions.get(cat, "")

    # retrieval / new submissions / abstracts
    threads = []
    for i, cat in enumerate(switches):
        th = Thread(
            name=cat,
            target=newentries,
            args=(
                logfiles,
                cat,
                caption_dict[cat],
                client_dict[cat],
                update_dict[cat],
                entries_dict,
                newsubmission_mode[cat],
                abstract_mode[cat],
                pt_days,
                pt_mode,
            ),
        )
        threads.append(th)
        print(
            "starting thread of retrieval/new submissions/abstracts for "
            + th.name
        )
        th.start()
        if i != len(switches) - 1:
            print("waiting for next thread")
            time.sleep(main_thread_wait)

    print("joining threads of retrieval/new submissions/abstracts")
    [th.join() for th in threads]

    if not logfiles:
        ending_time = datetime.now(timezone.utc).replace(microsecond=0)
        print(
            "\n**process ended at " + str(ending_time) + " (UTC)"
            + "\n**elapsed time from the start: "
            + str(ending_time - starting_time)
        )
        return None

    # replacements
    replacement_time = datetime.now(timezone.utc).replace(microsecond=0)
    print(
        "\n**replacement process started at "
        + str(replacement_time) + " (UTC)"
        + "\n**elapsed time from the start: "
        + str(replacement_time - starting_time)
    )

    print("\n**quote-replacement starts")
    for cat in switches:
        webreplacements_dict[cat] = []
        if entries_dict.get(cat):
            for each in entries_dict[cat].replacements:
                # only post replacements up to version 5
                try:
                    ver = int(each["version"])
                except (ValueError, TypeError):
                    ver = 0
                if 1 < ver <= 5:
                    webreplacements_dict[cat].append(each)

    threads = []
    for i, cat in enumerate(switches):
        if webreplacements_dict[cat] and quote_replacement_mode[cat]:
            th = Thread(
                name=cat,
                target=quote_replacement,
                args=(
                    logfiles,
                    cat,
                    client_dict[cat],
                    update_dict[cat],
                    webreplacements_dict[cat],
                    pt_mode,
                ),
            )
            threads.append(th)
            print("starting quote-replacement thread for " + th.name)
            th.start()
            if i != len(switches) - 1:
                print("waiting for next quote-replacement thread")
                time.sleep(main_thread_wait)

    if threads:
        print("joining quote-replacement threads")
        [th.join() for th in threads]

    print("\n**repost-replacement starts")
    threads = []
    for i, cat in enumerate(switches):
        if webreplacements_dict[cat] and repost_replacement_mode[cat]:
            th = Thread(
                name=cat,
                target=repost_replacement,
                args=(
                    logfiles,
                    cat,
                    client_dict[cat],
                    update_dict[cat],
                    webreplacements_dict[cat],
                    pt_mode,
                ),
            )
            threads.append(th)
            print("starting repost-replacement thread for " + th.name)
            th.start()
            if i != len(switches) - 1:
                print("waiting for next repost-replacement thread")
                time.sleep(main_thread_wait)

    if threads:
        print("joining repost-replacement threads")
        [th.join() for th in threads]

    ending_time = datetime.now(timezone.utc).replace(microsecond=0)
    print(
        "\n**process ended at " + str(ending_time) + " (UTC)"
        + "\n**elapsed time from the start: "
        + str(ending_time - starting_time)
        + "\n**elapsed time from the replacement start: "
        + str(ending_time - replacement_time)
    )


# post/repost/unrepost/reply/quote with overall limit
@sleep_and_retry
@limits(calls=overall_bsky_limit_call, period=overall_bsky_limit_period)
def update(
    logfiles,
    cat,
    client,
    total,
    hal_id,
    text,
    post_uri,
    post_cid,
    root_uri,
    root_cid,
    parent_uri,
    parent_cid,
    pt_method,
    pt_mode,
):
    result = 0

    if not pt_mode:
        update_print(
            cat, hal_id, text, post_uri, post_cid,
            root_uri, root_cid, parent_uri, parent_cid,
            pt_method, pt_mode,
        )
        return result

    if not client:
        update_print(
            cat, hal_id,
            "\n**error: client not available:\n\n" + text,
            post_uri, post_cid, root_uri, root_cid,
            parent_uri, parent_cid, pt_method, pt_mode,
        )
        return result

    error_text = (
        "\nthread HAL category: " + cat
        + "\nclient_handle: " + client.me.handle
        + "\nclient_did: " + client.me.did
        + "\nHAL id: " + hal_id
        + "\ntext: " + text
        + "\nuri: " + post_uri
        + "\ncid: " + post_cid
        + "\nurl: " + atproto_uri_to_url(post_uri)
        + "\npt_method: " + pt_method + "\n"
    )

    if pt_method == "post":
        try:
            result = client.send_post(
                text=text,
                facets=generate_facets_for_urls(text)
            )
            update_print(
                cat, hal_id, text, result.uri, result.cid,
                root_uri, root_cid, parent_uri, parent_cid,
                pt_method, pt_mode,
            )
        except Exception:
            time_now = datetime.now(timezone.utc).replace(microsecond=0)
            print(
                "\n**error to post**\nutc: " + str(time_now)
                + error_text
            )
            traceback.print_exc()

    elif pt_method in ("repost_replacement",):
        try:
            result = client.repost(post_uri, post_cid)
            update_print(
                cat, hal_id, text, result.uri, result.cid,
                "", "", "", "", pt_method, pt_mode,
            )
        except Exception:
            time_now = datetime.now(timezone.utc).replace(microsecond=0)
            print(
                "\n**error to repost**\nutc: " + str(time_now)
                + error_text
            )
            traceback.print_exc()

    elif pt_method == "unrepost":
        try:
            result = client.delete_repost(post_uri)
            update_print(
                cat, hal_id, text, "", "", "", "",
                "", "", pt_method, pt_mode,
            )
        except Exception:
            time_now = datetime.now(timezone.utc).replace(microsecond=0)
            print(
                "\n**error to unrepost**\nutc: " + str(time_now)
                + error_text
            )
            traceback.print_exc()

    elif pt_method == "reply":
        try:
            reply_ref = {
                "root": {"uri": root_uri, "cid": root_cid},
                "parent": {"uri": parent_uri, "cid": parent_cid},
            }
            result = client.send_post(
                text=text,
                reply_to=reply_ref,
                facets=generate_facets_for_urls(text),
            )
            update_print(
                cat, hal_id, text, result.uri, result.cid,
                root_uri, root_cid, parent_uri, parent_cid,
                pt_method, pt_mode,
            )
        except Exception:
            time_now = datetime.now(timezone.utc).replace(microsecond=0)
            print(
                "\n**error to reply**\nutc: " + str(time_now)
                + error_text
            )
            traceback.print_exc()

    elif pt_method == "quote":
        try:
            result = client.send_post(
                text=text,
                facets=generate_facets_for_urls(text),
                embed={
                    "$type": "app.bsky.embed.record",
                    "record": {"uri": post_uri, "cid": post_cid},
                },
            )
            update_print(
                cat, hal_id, text, result.uri, result.cid,
                root_uri, root_cid, parent_uri, parent_cid,
                pt_method, pt_mode,
            )
        except Exception:
            time_now = datetime.now(timezone.utc).replace(microsecond=0)
            print(
                "\n**error to quote**\nutc: " + str(time_now)
                + error_text
            )
            traceback.print_exc()

    update_log(logfiles, cat, total, hal_id, result, pt_method, pt_mode)
    time.sleep(bsky_sleep)
    return result


def update_print(
    cat, hal_id, text, result_uri, result_cid,
    root_uri, root_cid, parent_uri, parent_cid,
    pt_method, pt_mode,
):
    time_now = datetime.now(timezone.utc).replace(microsecond=0)
    print(
        "\nutc: " + str(time_now)
        + "\nthread HAL category: " + cat
        + "\nHAL id: " + hal_id
        + "\nroot url: " + atproto_uri_to_url(root_uri)
        + "\npost method: " + pt_method
        + "\npost mode: " + str(pt_mode)
        + "\nresult url: " + atproto_uri_to_url(result_uri)
        + "\ntext: " + text + "\n"
    )


def update_log(logfiles, cat, total, hal_id, result, pt_method, pt_mode):
    if not result or not pt_mode or not logfiles:
        return None

    time_now = datetime.now(timezone.utc).replace(microsecond=0)

    if not hal_id and pt_method == "post":
        filename = logfiles[cat]["post_summary_log"]
        log_text = [
            [time_now, total, logfiles[cat]["username"],
             result.uri, result.cid]
        ]
        df = pd.DataFrame(
            log_text,
            columns=["utc", "total", "username", "uri", "cid"]
        )
    elif pt_method == "unrepost":
        log_text = [
            [time_now, hal_id, logfiles[cat]["username"], "", ""]
        ]
        df = pd.DataFrame(
            log_text,
            columns=["utc", "hal_id", "username", "uri", "cid"]
        )
        filename = logfiles[cat][pt_method + "_log"]
    else:
        log_text = [
            [time_now, hal_id, logfiles[cat]["username"],
             result.uri, result.cid]
        ]
        df = pd.DataFrame(
            log_text,
            columns=["utc", "hal_id", "username", "uri", "cid"]
        )
        filename = logfiles[cat][pt_method + "_log"]

    if not filename:
        return None
    if os.path.exists(filename):
        df.to_csv(filename, mode="a", header=None, index=None)
    else:
        df.to_csv(filename, mode="w", index=None)


def newentries(
    logfiles,
    cat,
    caption,
    client,
    update_limited,
    entries_dict,
    newsubmission_mode,
    abstract_mode,
    pt_days,
    pt_mode,
):
    print("getting HAL entries for " + cat)
    try:
        entries_dict[cat] = aHd.hal_entries(cat, days=pt_days)
    except Exception:
        # on a retrieval error, post nothing
        entries_dict[cat] = {}
        print("\n**error for retrieval**\nthread HAL category: " + cat)
        traceback.print_exc()
        return None

    if newsubmission_mode:
        print("new submissions for " + cat)
        if entries_dict.get(cat):
            already = logged_ids(cat, "post_log", logfiles)
            fresh = [
                e for e in entries_dict[cat].newsubmissions
                if e["id"] not in already
            ]
            if len(fresh) < entries_dict[cat].num_newsubmissions:
                print(
                    str(entries_dict[cat].num_newsubmissions - len(fresh))
                    + " already posted entries skipped for " + cat
                )
            newsub_entries = aHf.format(fresh)
            if not check_log_dates(cat, "post_log", logfiles) and \
                    not check_log_dates(cat, "post_summary_log", logfiles):
                newsubmissions(
                    logfiles, cat, caption, client, update_limited,
                    newsub_entries, abstract_mode, pt_mode,
                )
            else:
                print(cat + " already posted for today")


def intro(given_time, num, cat, caption):
    """Introductory post text, e.g.:
    [2026-03-16 Mon (UTC), 4 new articles found for HAL math.math-co]
    """
    ptext = "[" + given_time.strftime("%Y-%m-%d %a") + " (UTC), "
    if num == 0:
        ptext += "no new articles found for "
    elif num == 1:
        ptext += str(num) + " new article found for "
    else:
        ptext += str(num) + " new articles found for "

    # display category name without dots; a whole-stream bot
    # (category "all") just says "HAL"
    if cat in ("", "all", "*"):
        ptext += "HAL"
    else:
        ptext += "HAL " + re.sub(r"\.", "", cat)

    if caption:
        ptext += " " + caption

    if num > post_updates - 1:
        ptext += (
            ", but only first "
            + str(post_updates - 1)
            + " articles to post.]"
        )
    else:
        ptext += "]"
    return ptext


def newsubmissions(
    logfiles, cat, caption, client, update_limited,
    entries, abstract_mode, pt_mode,
):
    time_now = datetime.now(timezone.utc).replace(microsecond=0)
    ptext = intro(time_now, len(entries), cat, caption)
    update_limited(
        logfiles, cat, client, str(len(entries)), "",
        ptext, "", "", "", "", "", "", "post", pt_mode,
    )
    post_counter = 1

    for each in entries:
        if post_counter >= post_updates:
            break

        hal_id = each["id"]
        authors_prefix = (
            each["authors"] + ": " if each["authors"] else ""
        )
        article_text = (
            authors_prefix
            + each["title"]
            + " "
            + each["hal_url"]
            + each.get("tag", "")
        )

        result = update_limited(
            logfiles, cat, client, "", hal_id, article_text,
            "", "", "", "", "", "", "post", pt_mode,
        )
        post_counter += 1

        if abstract_mode and result:
            sep_abst = each["separated_abstract"]
            for i, partial_abst in enumerate(sep_abst):
                if i == 0:
                    abst_result = update_limited(
                        logfiles, cat, client, "", hal_id,
                        partial_abst, "", "",
                        result.uri, result.cid,
                        result.uri, result.cid,
                        "reply", pt_mode,
                    )
                else:
                    abst_result = update_limited(
                        logfiles, cat, client, "", hal_id,
                        partial_abst, "", "",
                        result.uri, result.cid,
                        abst_result.uri, abst_result.cid,
                        "reply", pt_mode,
                    )
                if abst_result == 0:
                    break


def quote_replacement(logfiles, cat, client, update_limited, entries, pt_mode):
    post_filename = logfiles[cat]["post_log"]
    if not os.path.exists(post_filename):
        print("no post log file for " + cat)
        return None

    try:
        post_df = pd.read_csv(post_filename, dtype=object)
    except Exception:
        time_now = datetime.now(timezone.utc).replace(microsecond=0)
        print(
            "\n**error for post log**"
            "\nutc: " + str(time_now)
            + "\npost_filename: " + post_filename
        )
        traceback.print_exc()
        return False

    quote_filename = logfiles[cat]["quote_log"]
    if not os.path.exists(quote_filename) and pt_mode:
        print("posting mode without quote log file for " + cat)
        return None

    try:
        quote_df = pd.read_csv(quote_filename, dtype=object)
    except Exception:
        time_now = datetime.now(timezone.utc).replace(microsecond=0)
        print(
            "\n**error for quote log**"
            "\nutc: " + str(time_now)
            + "\nquote_filename: " + quote_filename
        )
        traceback.print_exc()
        return False

    # avoid duplicate quote-replacements today
    time_now = datetime.now(timezone.utc).replace(microsecond=0)
    if pt_mode and any(
        check_dates(time_now, datetime.fromisoformat(t))
        for t in quote_df.utc.values
    ):
        print("already made quote-replacements today for " + cat)
        return None

    for each in entries:
        hal_id = each["id"]
        hal_url = each["hal_url"]
        ver = each["version"]

        # only quote-replace if not already done
        already_quoted = any(
            hal_id == row["hal_id"]
            for _, row in quote_df.iterrows()
        )
        if already_quoted:
            continue

        for _, post_row in post_df.iterrows():
            if hal_id == post_row["hal_id"]:
                post_uri = post_row["uri"]
                post_cid = post_row["cid"]
                ptext = (
                    hal_url
                    + " has been replaced (v" + str(ver) + "). "
                    + atproto_uri_to_url(post_uri)
                )
                update_limited(
                    logfiles, cat, client, "", hal_id,
                    ptext, post_uri, post_cid,
                    "", "", "", "", "quote", pt_mode,
                )


def repost_replacement(
    logfiles, cat, client, update_limited, entries, pt_mode
):
    repost_filename = logfiles[cat]["repost_replacement_log"]
    if not os.path.exists(repost_filename):
        print("no repost replacement log file for " + cat)
        return False

    try:
        repost_df = pd.read_csv(repost_filename, dtype=object)
    except Exception:
        time_now = datetime.now(timezone.utc).replace(microsecond=0)
        print(
            "\n**error for repost replacement log**"
            "\nutc: " + str(time_now)
            + "\nrepost_filename: " + repost_filename
        )
        traceback.print_exc()
        return False

    quote_filename = logfiles[cat]["quote_log"]
    if not os.path.exists(quote_filename):
        print("no quote log file for " + cat)
        return False

    try:
        quote_df = pd.read_csv(quote_filename, dtype=object)
    except Exception:
        time_now = datetime.now(timezone.utc).replace(microsecond=0)
        print(
            "\n**error for quote log**"
            "\nutc: " + str(time_now)
            + "\nquote_filename: " + quote_filename
        )
        traceback.print_exc()
        return False

    for each in entries:
        hal_id = each["id"]
        time_now = datetime.now(timezone.utc).replace(microsecond=0)

        for _, quote_row in quote_df.iterrows():
            if hal_id == quote_row["hal_id"]:
                log_time = datetime.fromisoformat(quote_row["utc"])
                if not check_dates(time_now, log_time):
                    # unrepost old, repost new quote
                    for _, repost_row in repost_df.iterrows():
                        if hal_id == repost_row["hal_id"]:
                            update_limited(
                                logfiles, cat, client, "", hal_id,
                                "", repost_row["uri"], repost_row["cid"],
                                "", "", "", "", "unrepost", pt_mode,
                            )
                    update_limited(
                        logfiles, cat, client, "", hal_id,
                        "", quote_row["uri"], quote_row["cid"],
                        "", "", "", "", "repost_replacement", pt_mode,
                    )


def logged_ids(cat, logname, logfiles):
    """Set of HAL ids already recorded in a log."""
    if not logfiles or cat not in logfiles or logname not in logfiles[cat]:
        return set()
    filename = logfiles[cat][logname]
    if not filename or not os.path.exists(filename):
        return set()
    try:
        df = pd.read_csv(filename, dtype=object)
    except Exception:
        print("\n**error for log file**\nfilename: " + filename)
        traceback.print_exc()
        return set()
    if "hal_id" not in df.columns:
        return set()
    return set(df["hal_id"].dropna().values)


def check_log_dates(cat, logname, logfiles):
    if not logfiles:
        print("no log files")
        return False

    if cat not in logfiles or logname not in logfiles[cat]:
        return False

    filename = logfiles[cat][logname]
    if not os.path.exists(filename):
        print("log file does not exist: " + filename)
        return False

    time_now = datetime.now(timezone.utc).replace(microsecond=0)
    try:
        df = pd.read_csv(filename, dtype=object)
    except Exception:
        print(
            "\n**error for log file**"
            "\nutc: " + str(time_now)
            + "\nfilename: " + filename
        )
        traceback.print_exc()
        return False

    for _, row in df.iterrows():
        log_time = datetime.fromisoformat(row["utc"])
        if (
            check_dates(log_time, time_now)
            and row["username"] == logfiles[cat]["username"]
        ):
            return True
    return False


def check_dates(time1, time2):
    """True if time1 and time2 fall on the same calendar date (UTC).

    Unlike bXiv, HAL has no weekend gap, so no weekend extension needed.
    """
    return time1.date() == time2.date()


def atproto_client(keys):
    client = Client()
    try:
        time.sleep(bsky_createaccts_sleep)
        client.login(keys["username"], keys["password"])
    except Exception:
        print("\n**error: " + keys["username"] + " failed to login.")
        traceback.print_exc()
        return None
    return client


def atproto_uri_to_url(uri):
    if not uri:
        return ""
    path = uri[5:]
    parts = path.split("/", 1)
    did = parts[0]
    resource = parts[1]
    post_id = resource.split("/")[-1]
    return f"https://bsky.app/profile/{did}/post/{post_id}"


def generate_facets_for_urls(text):
    url_pattern = re.compile(r"https?://[^\s\[\]]+")
    facets = []
    for match in url_pattern.finditer(text):
        # convert character offsets to UTF-8 byte offsets
        byte_start = len(text[:match.start()].encode("utf-8"))
        byte_end = len(text[:match.end()].encode("utf-8"))
        url = match.group()
        facets.append({
            "index": {
                "byteStart": byte_start,
                "byteEnd": byte_end,
            },
            "features": [{
                "$type": "app.bsky.richtext.facet#link",
                "uri": url,
            }],
        })
    return facets
