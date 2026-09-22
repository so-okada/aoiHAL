# Application Info

aoiHAL delivers new submissions of preprints/working papers on HAL
(Hyper Articles en Ligne) as Bluesky posts. aoi means blue 
(青い/あおい) in Japanese. We use python3 scripts with atproto. 
aoiHAL is not affiliated with HAL or the CCSD.


## Setup

* Install atproto, pandas, ratelimit, and nameparser.

	```
	% pip3 install atproto pandas ratelimit nameparser
	```

* Make aoiHAL.py executable.

	```
	% chmod +x aoiHAL.py
	```

* Put the following python scripts in the same directory.

	- aoiHAL.py
	- aoiHAL_post.py
	- aoiHAL_format.py
	- aoiHAL_feed.py
	- aoiHAL_variables.py
	- HAL_feed_parser.py
	- HAL_search_parser.py

* Configure switches.json and logfiles.json for your settings.

	- switches.json specifies Bluesky access keys and whether to use
	new submissions/abstracts by aoiHAL.  Each key is a HAL primary
	domain code (`math`, `math.math-co`, `shs`, ...) or `all` for the
	whole HAL preprint/working papers. captions.json tells aoiHAL
	to display captions for HAL category names.

	- logfiles.json indicates log file locations for post summaries,
	posts, and replies.  aoiHAL uses the post log to skip entries
	already posted in earlier runs.

* Configure aoiHAL_variables.py for your settings.

	- aoiHAL_variables.py assigns format parameters for aoiHAL posts,
	the number of days to retrieve, access frequencies for HAL and
	Bluesky, the domain tag of each post, and the posting order.

## Notes

* aoiHAL retrieves HAL records by the [HAL search
  API](https://api.archives-ouvertes.fr/docs/search) with
  HAL_search_parser.py for `docType_s:UNDEFINED`, which is HAL's
  document type labeled "Preprints, Working Papers, ..." («
  Pré-publication, Document de travail »), in their `json` format.
  aoiHAL uses lists of first versions with a full-text file released
  in the query period (`releasedDate_tdate`).  HAL_feed_parser.py
  splits them into categories by their primary HAL domains.  We use
  these via aoiHAL_feed.py to regularly obtain data.

* aoiHAL retrieves from HAL sequentially, without parallel requests:
  one search request per run, shared by all categories, with further
  pages (only if a period holds more than `hal_feed_rows` preprints)
  followed one at a time (`hal_call_period` seconds apart).

* Unlike arXiv, HAL is a continuous repository with no fixed daily
  announcement cycle.  aoiHAL retrieves the last N days on each run
  (`hal_days` in aoiHAL_variables.py or `-d`), and the post log skips
  entries already posted.

* On the use of HAL metadata: HAL's own documentation states that
  metadata are under a [CC0
  license](https://about.hal.science/en/publishing-workflow/); the
  metadata set (title, authors, etc.) is the one defined by the HAL
  [deposit form](https://doc.hal.science/en/deposit_new/). The [COAR
  Directory of Open Access Preprint
  Repositories](https://doapr.coar-repositories.org/repositories/hal/)
  entry for HAL states: "The HAL open archive and its portals are
  harvestable via the OAI-PMH protocol + API are free to use." HAL's
  legal page [Questions
  juridiques](https://doc.hal.science/questions-juridiques/) states: «
  Les métadonnées de HAL peuvent être consultées de façon totale ou
  partielle par moissonnage dans le respect du code de la propriété
  intellectuelle. Elles sont distribuées [sous licence
  CC0](https://creativecommons.org/publicdomain/zero/1.0/). Obligation
  de citer la source (exemple : hal.science/hal-00000001). »


## Usage

```
% ./aoiHAL.py -h
usage: aoiHAL.py [-h] --switches_keys SWITCHES_KEYS [--logfiles LOGFILES]
                 [--captions CAPTIONS] [--days DAYS] [--mode {0,1}]

HAL new preprints/working papers by posts and abstracts by replies.

options:
  -h, --help            show this help message and exit
  --switches_keys SWITCHES_KEYS, -s SWITCHES_KEYS
                        output switches and api keys in json
  --logfiles LOGFILES, -l LOGFILES
                        log file names in json
  --captions CAPTIONS, -c CAPTIONS
                        captions of HAL categories in json
  --days DAYS, -d DAYS  number of past days to retrieve from HAL (default
                        values in aoiHAL_variables.py)
  --mode {0,1}, -m {0,1}
                        1 for bsky posting and 0 for stdout only
```

## Sample stdouts

* New submissions of all HAL preprints/working papers of the last
  3 days with no log files:

	```
	% ./aoiHAL.py -s tests/switches.json -c tests/captions.json -m 1 -d 3
	**process started at xxxx-xx-xx xx:xx:xx (UTC)
	starting thread of retrieval/new submissions/abstracts for all
	getting HAL entries for all
	joining threads of retrieval/new submissions/abstracts
	HAL preprints of the last 3 day(s): 84 (numFound 84, 1 request(s))
	new submissions for all
	no log files
	no log files

	utc: xxxx-xx-xx xx:xx:xx
	thread HAL category: all
	HAL id:
	root url: https://bsky.app/profile/
	post method: post
	post mode: 1
	result url: https://bsky.app/profile/xxxxxxxxxxxxxxxxxxxxxxxx
	text: [xxxx-xx-xx Sun (UTC), 84 new articles found for HAL preprints and working papers]

	utc: xxxx-xx-xx xx:xx:xx
	thread HAL category: all
	HAL id: hal-xxxxxxxx
	root url: https://bsky.app/profile/
	post method: post
	post mode: 1
	result url: https://bsky.app/profile/xxxxxxxxxxxxxxxxxxxxxxxx
	text: Xxxx, Yyyy: Title of the paper https://hal.science/hal-xxxxxxxxv1 [chim]

	....

	utc: xxxx-xx-xx xx:xx:xx
	thread HAL category: all
	HAL id: hal-xxxxxxxx
	root url: https://bsky.app/profile/
	post method: post
	post mode: 1
	result url: https://bsky.app/profile/xxxxxxxxxxxxxxxxxxxxxxxx
	text: Xxxx, Yyyy: Title of the paper https://hal.science/hal-xxxxxxxxv1 [math.math-co]

	....

	**process ended at xxxx-xx-xx xx:xx:xx (UTC)
	**elapsed time from the start: xx:xx:xx
	```

* New submissions and abstracts with log files; entries already in
  the post log are skipped:

	```
	% ./aoiHAL.py -s tests/switches.json -l tests/logfiles.json -c tests/captions.json -m 1 -d 3
	**process started at xxxx-xx-xx xx:xx:xx (UTC)
	starting thread of retrieval/new submissions/abstracts for all
	getting HAL entries for all
	joining threads of retrieval/new submissions/abstracts
	HAL preprints of the last 3 day(s): 84 (numFound 84, 1 request(s))
	new submissions for all
	79 already posted entries skipped for all

	utc: xxxx-xx-xx xx:xx:xx
	thread HAL category: all
	HAL id:
	root url: https://bsky.app/profile/
	post method: post
	post mode: 1
	result url: https://bsky.app/profile/xxxxxxxxxxxxxxxxxxxxxxxxx
	text: [xxxx-xx-xx Sun (UTC), 5 new articles found for HAL preprints and working papers]

	utc: xxxx-xx-xx xx:xx:xx
	thread HAL category: all
	HAL id: hal-xxxxxxxx
	root url: https://bsky.app/profile/
	post method: post
	post mode: 1
	result url: https://bsky.app/profile/xxxxxxxxxxxxxxxxxxxxxxxxx
	text: Xxxx, Yyyy: Title of the paper https://hal.science/hal-xxxxxxxxv1 [math.math-ap]

	utc: xxxx-xx-xx xx:xx:xx
	thread HAL category: all
	HAL id: hal-xxxxxxxx
	root url: https://bsky.app/profile/xxxxxxxxxxxxxxxxxxxx
	post method: reply
	post mode: 1
	result url: https://bsky.app/profile/xxxxxxxxxxxxxxxxxxxx
	text: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx [1/3 of https://hal.science/hal-xxxxxxxxv1]

	.....

	**process ended at xxxx-xx-xx xx:xx:xx (UTC)
	**elapsed time from the start: xx:xx:xx
	```

* Without the option `-c tests/captions.json` above, you get

	```
	text: [xxxx-xx-xx Sun (UTC), 5 new articles found for HAL]
	```

	instead of

	```
	text: [xxxx-xx-xx Sun (UTC), 5 new articles found for HAL preprints and working papers]
	```


## Versions

* 0.0.1, initial release, 2026-05-17.
* 0.0.2, public release, 2026-09-21.
* 0.0.3, HAL search API instead of OAI-PMH, 2026-09-22.


## List of Bots

* [https://bsky.app/profile/aoihal-ppbot.bsky.social](https://bsky.app/profile/aoihal-ppbot.bsky.social) 
HAL Preprints/Working Paper announcement bot (unofficial) 

## Author
So Okada, so.okada@gmail.com, https://so-okada.github.io/

## Motivation

This is an open-science practice (see
https://github.com/so-okada/twXiv#motivation).  Since 2013-04, the
author has been running Twitter bots for all
[arXiv](https://arxiv.org) math categories with
[twXiv](https://github.com/so-okada/twXiv).  Since 2023-01, the author
has been running Mastodon bots for all arXiv categories with
[toXiv](https://github.com/so-okada/toXiv).  Since 2025-02, the author
has been running Bluesky bots for all arXiv categories with
[bXiv](https://github.com/so-okada/bXiv).  Since 2026-07, the author
has been running a Bluesky bot for [SciELO
Preprints](https://preprints.scielo.org/index.php/scielo) with
[aozoraSciELO](https://github.com/so-okada/aozoraSciELO). Since
2026-09, the author has been running a Bluesky bot for
[HAL](https://hal.science/) preprints/working papers with
[aoiHAL](https://github.com/so-okada/aoiHAL).


## License
[AGPLv3](https://www.gnu.org/licenses/agpl-3.0.en.html)
