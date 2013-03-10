#!/usr/bin/python
from bottle import route, run, static_file, default_app, SimpleTemplate
import m2t, bottle
from m2t import config

bottle.TEMPLATE_PATH.append("./m2t/views")

@route("/public/<filename:path>")
def static(filename):
	return static_file(filename, root="./m2t/public")

SimpleTemplate.defaults["get_url"] = default_app().get_url
SimpleTemplate.defaults["static_url"] = lambda x: default_app().get_url("/public/<filename:path>", filename=x)

run(port=config.bottle_port, debug=config.bottle_debug, reloader=config.bottle_reload, server=config.bottle_server)

