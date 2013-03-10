import MySQLdb
from MySQLdb.cursors import DictCursor
from m2t import config

full_db = MySQLdb.connect(
	host = config.database_host,
	user = config.database_username,
	passwd = config.database_password,
	db = config.database_name,
	port = config.database_port	
)

db = full_db.cursor(DictCursor)
db.commit = lambda: full_db.commit()