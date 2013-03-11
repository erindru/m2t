from bottle import route, jinja2_template as template, static_file
import m2t.db as database

@route("/")
def index():
	db = database.get_cursor()
	db.execute("SELECT hash, name, total_size_bytes FROM torrent WHERE retrieving_data=0 ORDER BY create_date DESC LIMIT 10")
	lastten = db.fetchall()
	db.close()
	return template("index.html", lastten = lastten)

@route("/public/<filename:path>")
def static(filename):
	return static_file(filename, root="./m2t/public")	