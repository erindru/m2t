#!/usr/bin/python
from bottle import route, run, static_file, SimpleTemplate, default_app
import m2t, bottle
from m2t import config
from hurry.filesize import size
import m2t.api
import m2t.main

import logging
logging.basicConfig(level=logging.DEBUG)

bottle.TEMPLATE_PATH.append("./m2t/views")
#Default bottle settings
app = default_app()
SimpleTemplate.defaults["get_url"] = app.get_url
SimpleTemplate.defaults["static_url"] = lambda x: app.get_url("/public/<filename:path>", filename=x)
SimpleTemplate.defaults["size"] = size

run(port=config.bottle_port, debug=config.bottle_debug, reloader=config.bottle_reload, server=config.bottle_server)