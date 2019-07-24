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

from mastodon import Mastodon


SETTINGS = {
   'instance': 'localhost',
   'user': 'searchHelperBot',
   'pass': 'fakefakefake',
   'tags': ['linux', 'foss'],
   'sources': [
      'mastodon.social', 'infosec.exchange', 'fosstodon.org',
      'mastodon.technology', 'chaos.social'],
}


def timeline_url(server, tag, since_id=None):
   return 'https://%s/api/v1/timelines/tag/%s?limit=10' % (server, tag)


def simple_get_json(url):
   try:
      return json.loads(urlopen(timeline_url(src, tag)).read())
   except KeyboardInterrupt:
      return []
   except Exception as e:
      print('Error: %s' % e)
      return []


if __name__ == '__main__':
   try:
      SETTINGS.update(json.load(open('search_helper-settings.json', 'r')))
   except (IOError, OSError):
      pass

   ccred = 'search_helper-%s-ccred' % SETTINGS['instance']
   base_url = 'https://%s' % SETTINGS['instance']
   if not os.path.exists(ccred):
      Mastodon.create_app(
         'search_helper', api_base_url=base_url, to_file=ccred)

   mastodon = Mastodon(client_id=ccred, api_base_url=base_url)
   mastodon.log_in(SETTINGS['user'], SETTINGS['pass'])
   mastodon.toot('Good morning, Fediverse!')

   seen = {}
   try:
      seen.update(json.load(open('search_helper-seen.json', 'r')))
   except (IOError, OSError):
      pass

   pairs = [(t, s) for t in SETTINGS['tags'] for s in SETTINGS['sources']]
   loop = True
   while loop:
      count = 0
      random.shuffle(pairs)
      for k in [(k, v) for (k, v) in seen.items() if v < time.time() - 7200]:
         del seen[k]
      for tag, src in pairs:
         deadline = time.time() + (3600.0 / len(pairs))
         for post in simple_get_json(timeline_url(src, tag)):
            uri = post['uri']
            if uri not in seen:
               try:
                  mastodon.search(q=uri, resolve=True)
                  seen[uri] = int(time.time())
                  count += 1
                  print('%d: %s/%s: %s' % (count, src, tag, uri))
               except KeyboardInterrupt:
                  loop = False
                  break
               except:
                  traceback.print_exc()
                  time.sleep(120)
         if loop:
             time.sleep(max(0, deadline - time.time()))
         else:
             break

      mastodon.toot('Slurped up %d new posts' % count)
      with open('search_helper-seen.json', 'w') as fd:
         json.dump(seen, fd)
