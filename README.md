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

I recommend using `virtualenv`:

    $ virtualenv -p $(which python3) .env

    $ . .env/bin/activate

    $ pip install Mastodon.py

    ... configure things ...

    $ python ./scripts/hashtag_helper.py


## License

Free Software: AGPLv3+
 
