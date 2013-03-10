from bottle import route, jinja2_template as template
from m2t.db import db

@route("/")
def index():
	db.execute("SELECT hash, name, total_size_bytes FROM torrent ORDER BY create_date DESC LIMIT 10")
	lastten = db.fetchall()
	return template("index.html", lastten = lastten)	