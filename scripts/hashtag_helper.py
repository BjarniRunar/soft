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

    hashtag_helper.py [options] /path/to/config.json

Options:

    -v, --verbose   Verbose output, useful when debugging and experimenting
    -q, --quiet     Do not print progress reports to stdout
    -s, --silent    Do not print error messages to stdout (implies --quiet)
    -n, --notoots   Do not toot about progress made
    -1, --oneshot   Run one scraper pass and then exit (good for cron)
        --nosleep   Never sleep between scrapes (Do Not Use: implies --verbose)

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

   # Content we would like to ignore. Can be #tags, @users or regular
   # expressions matched against the de-HTML'ed & lowercase'd content.
   "ignore": [
      # "#nsfw", "#boobs",
      # "@bjarni@bre.klaki.net",
      # "(fuck|trump)"
   ],
   "ignore_many_tags": 0,  # Ignore posts with more tags than this
#  "ignore_many_links": 0, # FIXME: Ignore posts with more links than this

   # Tags we are interested in and instances we scrape from.
   "tags": ["linux", "foss"],
   "sources": [
      "mastodon.social", "humblr.social", "mastodon.cloud", "mastodon.xyz"
   ],

   # Instances whose local timelines we'd like to track
   "local_timelines": [
      #"fosstodon.org"
   ],

   # Set (name: URL) pairs, to scrape arbitrary things. Useful for grabbing
   # the entire public timeline of a small specialized instance, for example.
   "source_urls": {
      #"foss": "https://fosstodon.org/api/v1/timelines/public/?limit=50&local=true",
   },
   # If set to a higher number, each of the source_urls will be scheduled for
   # scraping multiple times per loop. This also affects the tracking of local
   # timelines.
   "source_urls_freq": 1
}


##############################################################################

import datetime
import json
import os
import random
import re
import ssl
import sys
import time
import traceback
from urllib.parse import urlencode
from urllib.request import *
from urllib.error import *
from mastodon import *


def local_timeline_url(server):
   return 'https://%s/api/v1/timelines/public/?local=true' % server


def tag_timeline_url(server, tag, since_id=None):
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

def should_ignore(post, verbose):
   post_tags = list(t['name'].lower() for t in post.get('tags', []))
   post_content = re.sub('<[^>]+>', ' ', post['content']).lower()
   if len(post_tags) > (SETTINGS.get('ignore_many_tags') or len(post_tags)):
      if verbose:
         print('Too many tags (%s) in post, ignoring' % len(post_tags))
      return True
   for word in SETTINGS['ignore']:
      if word.startswith('#'):
         if word[1:].lower() in post_tags:
            if verbose:
               print('Found %s in post tags, ignoring' % word)
            return True
      elif word.startswith('@'):
          print('FIXME: igoring users is not implemented yet')
      elif re.search(word, post_content):
          print('Found %s in post content, ignoring' % word)
          return True
   return False


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
   nosleep = ('--nosleep' in sys.argv)
   verbose = (nosleep or '--verbose' in sys.argv or '-v' in sys.argv)
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
      sources = [(t, s, tag_timeline_url(s, t))
         for t in SETTINGS['tags'] for s in SETTINGS['sources']]

      # Add local timelines and custom source, as many times as requested
      for i in range(0, SETTINGS.get('source_urls_freq', 1)):
         sources.extend([(k, 'URL', v)
            for k, v in (SETTINGS.get('source_urls') or {}).items()])
         sources.extend([(s, 'LOCAL', local_timeline_url(s))
            for s in (SETTINGS.get('local_timelines') or [])])

      random.shuffle(sources)
      expired = [
         (k, v) for (k, v) in seen.items() if v < time.time() - (2*looptime)]
      for k in expired:
          try:
             del seen[k]
          except KeyError:
             pass
      if verbose:
         print('Expired %d from seen list' % len(expired))
         print('Polling plan:\n\t%s' % '\n\t'.join(t[2] for t in sources))

      count = 0
      starttime = time.time()
      endtime = starttime + looptime
      try:
         for i, (tag, src, url) in enumerate(sources):
            now = int(time.time())
            deadline = min(endtime, now + ((endtime - now) / (len(sources)-i)))
            if not quiet:
               print('==== %s:%s (%ds) ====' % (src, tag, deadline - time.time()))

            posts = simple_get_json(url, silent)
            if verbose and posts:
               print('Found %d posts at %s' % (len(posts), url))
            for post in reversed(posts):
               uri = post['uri']
               if uri in seen:
                  if verbose:
                     print('old: %s' % uri)
               elif not should_ignore(post, verbose):
                  try:
                     if verbose:
                        print('Submitting new post: %s' % json.dumps(post, indent=1))
                     mastodon.search(q=uri, resolve=True)
                     count += 1
                     if not quiet:
                        print('new/%d: %s' % (count, uri))
                  except KeyboardInterrupt:
                     raise
                  except (MastodonBadGatewayError, MastodonInternalServerError) as e:
                     if not silent:
                        print('m.search(%s...): %s' % (uri[:30], e))
                  except:
                     if not silent:
                        traceback.print_exc()
                     if not nosleep:
                        time.sleep(60)
               seen[uri] = now

            with open('hashtag_helper_seen.json', 'w') as fd:
                json.dump(seen, fd)

            if loop:
               sleeptime = int(max(0, deadline - time.time()))
               if verbose and sleeptime:
                  print('Sleeping for %ds' % sleeptime)
               if not nosleep:
                  time.sleep(sleeptime)
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
