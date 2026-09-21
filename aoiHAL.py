#!/usr/bin/env python3
# written by So Okada so.okada@gmail.com
# a main interface of aoiHAL
# HAL (Hyper Articles en Ligne) preprint announcements on Bluesky
# https://github.com/so-okada/aoiHAL

import json
import argparse
import traceback
from aoiHAL_variables import *
import aoiHAL_post as aHp

parser = argparse.ArgumentParser(
    description=(
        "HAL new preprints/working papers by posts "
        "and abstracts by replies."
    )
)
parser.add_argument(
    "--switches_keys", "-s",
    required=True,
    default="",
    help="output switches and api keys in json",
)
parser.add_argument(
    "--logfiles", "-l",
    default="",
    help="log file names in json",
)
parser.add_argument(
    "--captions", "-c",
    default="",
    help="captions of HAL categories in json",
)
parser.add_argument(
    "--days", "-d",
    type=int,
    default=None,
    help="number of past days to harvest from HAL "
         "(default: hal_days in aoiHAL_variables.py)",
)
parser.add_argument(
    "--mode", "-m",
    choices=[0, 1],
    type=int,
    default=0,
    help="1 for bsky posting and 0 for stdout only",
)

args = parser.parse_args()
switches = args.switches_keys
logfiles = args.logfiles
captions = args.captions
pt_days = args.days
pt_mode = args.mode

try:
    f = open(switches)
except Exception:
    traceback.print_exc()
    raise Exception("cannot obtain output switches and api keys")
switches = json.load(f)

if logfiles:
    try:
        f = open(logfiles)
    except Exception:
        traceback.print_exc()
        raise Exception("cannot obtain log filenames")
    logfiles = json.load(f)

if captions:
    try:
        f = open(captions)
    except Exception:
        traceback.print_exc()
        raise Exception("cannot obtain captions of HAL categories")
    captions = json.load(f)
else:
    captions = {}

aHp.main(switches, logfiles, captions, pt_days, pt_mode)
