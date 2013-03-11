import MySQLdb
from MySQLdb.cursors import DictCursor
from m2t import config

def get_connection():
	return MySQLdb.connect(
		host = config.database_host,
		user = config.database_username,
		passwd = config.database_password,
		db = config.database_name,
		port = config.database_port	
	)

def get_cursor(connection=None):
	if not connection:
		connection = get_connection()
	cursor = connection.cursor(DictCursor)

	cursor.commit = lambda: connection.commit()

	def close():
		if connection.open:
			connection.close()
			
	cursor.close = close
	return cursor