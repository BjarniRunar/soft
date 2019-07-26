# soft: Solo Fedi Tools

This is (or might become) a collection of simple tools to help with
running a small (solo) Fediverse Instance.


## Contents

   * [scripts/hashtag_helper.py](scripts/hashtag_helper.py):
     A bot which searches remote instances by hashtag, and injects
     what it finds into the local timeline.
   * ...

Consult the source of each individual tool for further documentation.


## Requirements

   * Python 3.x
   * Mastodon.py.


## Getting started

For development, I recommend using `virtualenv`:

    $ virtualenv -p $(which python3) .env
    $ . .env/bin/activate
    $ pip install Mastodon.py

    ...configure things...

    $ python ./scripts/hashtag_helper.py

If you want to install things globally:

    $ sudo pip3 install Mastodon.py
    $ cp -a scripts/*.py /usr/local/bin

I have a line like this in my crontab, to run the hashtag helper once per hour,
complemented by the `config.json` file specifying a `looptime` of 3500 seconds.

    15 * * * * /path/to/hashtag_helper.py -q -s -1 /path/to/hh_config.json


## License

Free Software: AGPLv3+
 
