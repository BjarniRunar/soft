#!/usr/bin/python3
"""
This is a Fediverse bot which helps small/solo instances "bulk up" their
federated timeline, with a focus on making specific tag searches useful.

The way it works, is it periodically polls the public timelines on a selection
of (ideally larger) servers, and if it discovers a new post it "searches" for
that post on the local intance, using the Mastodon API.

Searching by post URL will trigger the instance to go fetch the post and add to
the local federated timeline, and make the contents discoverable by local users
using normal tag searches.

Usage:

    hashtag_helper.py [--quiet] [--notoots] [--oneshot] /path/to/config.json

Arguments:

    -q, --quiet     Do not print progress reports to stdout
    -s, --silent    Do not print error messages to stdout (implies --quiet)
    -n, --notoots   Do not toot about progress made
    -1, --oneshot   Run one scraper pass and then exit (good for cron)

The configuration file should be JSON, and contain a subset of the fields
displayed in the SETTINGS dict here below.
"""

VERSION = "0.0.1"
SETTINGS = {
   # If unset, uses the same path as the config. The bot creates some files
   # to keep track of state, so this matters a lil bit.
   "workdir": None,

   # These will certainly need to be overridden in your config.
   "instance": "localhost",
   "user": "HashtagHelperBot",
   "pass": "fakefakefake",

   # This is what we report in our user-agent string, to be polite to the
   # instances we"re scraping.
   "contact_info": "Anonymous",
   "user_agent": "HashtagHelper/%s (github.com/BjarniRunar/soft; +%s)",

   # "Target run time" in seconds. This gets divided into timeslots for each
   # scrape operation. We may overrun, but we'll never be faster than this.
   "looptime": (3600 - 60),

   # Tags we are interested in and instances we scrape from.
   "tags": ["linux", "foss"],
   "sources": [
      "mastodon.social", "humblr.social", "mastodon.cloud", "mastodon.xyz"],

   # Set (name: URL) pairs, to scrape arbitrary things. Useful for grabbing
   # the entire public timeline of a small specialized instance, for example.
   "source_urls": {
      #"foss": "https://fosstodon.org/api/v1/timelines/public/?limit=50&local=true",
   },
   # If set to a higher number, each of the source_urls will be scheduled for
   # scraping multiple times per loop.
   "source_urls_freq": 1
}


##############################################################################

import datetime
import json
import os
import random
import ssl
import sys
import time
import traceback
from urllib.parse import urlencode
from urllib.request import *
from urllib.error import *
from mastodon import *


def timeline_url(server, tag, since_id=None):
   # Note: We are deliberately being dumb here and not tracking the last
   #       seen IDs or anything like that. This makes our requests
   #       cachable, which seems polite in case all the little instances
   #       start using this scraper.
   return 'https://%s/api/v1/timelines/tag/%s?limit=10' % (
      server, tag.replace('#', ''))


def simple_get_json(url, silent):
   try:
      ua = SETTINGS['user_agent'] % (VERSION, SETTINGS['contact_info'])
      return json.loads(
         urlopen(Request(url, headers={'User-Agent': ua})
            ).read().decode('utf-8'))
   except KeyboardInterrupt:
      raise
   except Exception as e:
      if not silent:
         print('urlopen(%s...): %s' % (url[:30], e))
      return []


def load_settings(configs):
   if not configs:
      configs = ['hashtag_helper_settings.json']
      _raise = False
   else:
      _raise = True
   try:
      # FIXME: This is probably overly complicated.
      config = {}
      for cfg in configs:
         config.update(json.load(open(cfg, 'r')))
      return config
   except (IOError, OSError):
      if _raise:
         raise
      return {}


if __name__ == '__main__':
   # This is a very crappy argument parser
   oneshot = ('--oneshot' in sys.argv or '-1' in sys.argv)
   toots = not ('--notoots' in sys.argv or '-n' in sys.argv)
   silent = ('--silent' in sys.argv or '-s' in sys.argv)
   quiet = (silent or '--quiet' in sys.argv or '-q' in sys.argv)
   configs = [a for a in sys.argv[1:] if not a.startswith('-')]

   SETTINGS.update(load_settings(configs))
   if SETTINGS.get('workdir'):
      os.chdir(SETTINGS.get('workdir'))
   elif configs:
      os.chdir(os.path.dirname(configs[0]))

   ccred = 'hashtag_helper_oauth-%s' % SETTINGS['instance']
   base_url = 'https://%s' % SETTINGS['instance']
   if not os.path.exists(ccred):
      Mastodon.create_app(
         'hashtag_helper', api_base_url=base_url, to_file=ccred)

   mastodon = Mastodon(client_id=ccred, api_base_url=base_url)
   mastodon.log_in(SETTINGS['user'], SETTINGS['pass'])
   if toots:
      mastodon.toot('Good morning, Fediverse!')

   seen = {}
   try:
      seen.update(json.load(open('hashtag_helper_seen.json', 'r')))
   except (IOError, OSError):
      pass

   loop = True
   while loop:
      SETTINGS.update(load_settings(configs))
      looptime = float(SETTINGS.get('looptime', 3600))

      # These are tag sources
      sources = [(t, s, timeline_url(s, t))
         for t in SETTINGS['tags'] for s in SETTINGS['sources']]

      # Add all the custom source URLs, as many times as requested
      for i in range(0, SETTINGS.get('source_urls_freq', 1)):
         sources.extend([(k, 'URL', v)
            for k, v in SETTINGS['source_urls'].items()])

      random.shuffle(sources)
      expired = [
         (k, v) for (k, v) in seen.items() if v < time.time() - (2*looptime)]
      for k in expired:
          try:
             del seen[k]
          except KeyError:
             pass

      count = 0
      try:
         for tag, src, url in sources:
            if not quiet:
               print('==== %s:%s ====' % (src, tag))
            deadline = time.time() + (looptime / len(sources))
            for post in reversed(simple_get_json(url, silent)):
               uri = post['uri']
               if uri in seen:
                  seen[uri] = int(time.time())
               else:
                  try:
                     # FIXME: Check if the post contains ignored tags,
                     #        and ignore it if so.
                     mastodon.search(q=uri, resolve=True)
                     seen[uri] = int(time.time())
                     count += 1
                     if not quiet:
                        print('new/%d: %s' % (count, uri))
                  except KeyboardInterrupt:
                     raise
                  except (MastodonBadGatewayError, MastodonInternalServerError) as e:
                     if not silent:
                        print('m.search(%s...): %s' % (uri[:30], e))
                  except:
                     traceback.print_exc()
                     time.sleep(60)
            if loop:
               time.sleep(max(0, deadline - time.time()))
            else:
               break
      except KeyboardInterrupt:
         loop = False

      with open('hashtag_helper_seen.json', 'w') as fd:
         json.dump(seen, fd)

      summary = 'Discovered %d/%d posts in %d tags, via %d instances.' % (
         count, len(seen), len(SETTINGS['tags']), len(SETTINGS['sources']))
      try:
         if not quiet:
            print(summary)
         if toots:
            mastodon.toot(summary)
      except:
         pass

      if oneshot:
         break
