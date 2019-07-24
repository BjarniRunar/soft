#!/usr/bin/python3
#
import datetime
import json
import os
import random
import ssl
import time
import traceback
from urllib.parse import urlencode
from urllib.request import *
from urllib.error import *
from mastodon import *


# Some defaults. These should be overridden in hashtag_helper-settings.json
VERSION = '0.0.1'
SETTINGS = {
   'contact_info': 'Anonymous',  # Override to let people know who runs the bot
   'user_agent': 'HashtagHelper/%s (github.com/BjarniRunar/soft; +%s)',
   'instance': 'localhost',
   'user': 'HashtagHelperBot',
   'pass': 'fakefakefake',
   'looptime': 3600,
   'tags': ['linux', 'foss'],
   'sources': ['mastodon.social', 'humblr.social', 'mastodon.cloud', 'mastodon.xyz'],
   'source_urls': {},
   'source_urls_freq': 1}


def timeline_url(server, tag, since_id=None):
   return 'https://%s/api/v1/timelines/tag/%s?limit=10' % (
      server, tag.replace('#', ''))


def simple_get_json(url):
   try:
      ua = SETTINGS['user_agent'] % (VERSION, SETTINGS['contact_info'])
      return json.loads(
         urlopen(Request(url, headers={'User-Agent': ua})).read())
   except KeyboardInterrupt:
      raise
   except Exception as e:
      print('urlopen(%s...): %s' % (url[:30], e))
      return []


def load_settings():
   try:
      return json.load(open('hashtag_helper-settings.json', 'r'))
   except (IOError, OSError):
      return {}


if __name__ == '__main__':
   SETTINGS.update(load_settings())
   ccred = 'hashtag_helper-%s-ccred' % SETTINGS['instance']
   base_url = 'https://%s' % SETTINGS['instance']
   if not os.path.exists(ccred):
      Mastodon.create_app(
         'hashtag_helper', api_base_url=base_url, to_file=ccred)

   mastodon = Mastodon(client_id=ccred, api_base_url=base_url)
   mastodon.log_in(SETTINGS['user'], SETTINGS['pass'])
   mastodon.toot('Good morning, Fediverse!')

   seen = {}
   try:
      seen.update(json.load(open('hashtag_helper-seen.json', 'r')))
   except (IOError, OSError):
      pass

   loop = True
   while loop:
      SETTINGS.update(load_settings())
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
            print('==== %s:%s ====' % (src, tag))
            deadline = time.time() + (looptime / len(sources))
            for post in reversed(simple_get_json(url)):
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
                     print('new/%d: %s' % (count, uri))
                  except KeyboardInterrupt:
                     raise
                  except (MastodonBadGatewayError, MastodonInternalServerError) as e:
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

      with open('hashtag_helper-seen.json', 'w') as fd:
         json.dump(seen, fd)

      summary = 'Discovered %d/%d posts in %d tags, via %d instances.' % (
         count, len(seen), len(SETTINGS['tags']), len(SETTINGS['sources']))
      try:
         print(summary)
         mastodon.toot(summary)
      except:
         pass
