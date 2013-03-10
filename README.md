m2t - Magnet to Torrent converter

Overview
--------
m2t is a simple service for converting magnets to torrents. It is written in Python/MySQL and uses the bottle web framework and libtorrent bindings.
A reference installation of the service can be found at: [http://m2t.openseedbox.com](http://m2t.openseedbox.com)

Installation
------------
Prerequisites:

1. Python 2.7 / bottle web framework (`pip install bottle`)
2. libtorrent-rasterbar >= 0.16.8 + python bindings (I had to compile my own because Ubuntu was bundled with an old version and I needed the add_magnet_uri() function)
3. MySQL server

Basically, what you need to do is create the database structure (defined in `m2t/db/schema.sql`), and then rename `m2t/config.py.default` to `m2t/config.py` and update the settings in that file as appropriate. You can then start the server using `./start.py`

Why
---
Basically, I wanted a magnet to torrent converter that could be used <i>as a service</i> (hence its completely API-based) for [openseedbox](http://openseedbox.com) so metadata about torrents (mainly, the total size) could be known in advance <i>before</i> its added to the backend. This is to prevent things like users exceeding their space limits, because if you dont know the size of the torrent in advance, you dont know if the user will exceed their space limits.