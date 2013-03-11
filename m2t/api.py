from bottle import route, request, response, default_app, jinja2_template as template, HTTPError
import m2t.db as database
from urlparse import urlparse
from hurry.filesize import size
from m2t.scraper import scrape

import re, socket, thread, tempfile, shutil, time, os, pprint, atexit, base64, urllib
import libtorrent as lt, logging as logger, StringIO

get_url = default_app().get_url

api_error = lambda message: {"success" : False, "message" : message }
api_success = lambda x: {"success" : True, "data" : x }

hash_pattern = re.compile("([a-fA-F0-9]{40})")
socket.setdefaulttimeout(5)

libtorrent_settings_file = os.path.abspath("./libtorrent.settings")

ses = lt.session()
ses.listen_on(6881, 6891)
ses.start_dht()

#Load DHT data
if os.path.exists(libtorrent_settings_file):
	handle = open(libtorrent_settings_file, "rb")
	logger.debug("Loading DHT state from: %s" % libtorrent_settings_file)
	ses.load_state(lt.bdecode(handle.read()))	
	handle.close()

#Save DHT data
def on_exit():
	if not ses:
		return
	state = ses.save_state(lt.save_state_flags_t(0x006)) #dht_sate is 0x002 and dht_settings is 0x004	
	logger.debug("Writing DHT state to: %s" % libtorrent_settings_file)
	handle = open(libtorrent_settings_file, "w")
	handle.write(lt.bencode(state))
	handle.close()
atexit.register(on_exit)

@route("/api")
def api_index():
	docs = {
		"/api/upload/&lt;magnet_url_or_hash&gt;" : api_upload.__doc__,
		"/api/info/&lt;hash&gt;": info.__doc__,
		"/api/metadata/&lt;hash&gt;" : metadata.__doc__,
		"/api/metadata/&lt;hash&gt;.torrent" : metadata_file.__doc__
	}
	return template("api.html", docstrings=docs)

@route("/api/upload")
@route("/api/upload/<magnet_url_or_hash:re:.*>")
def api_upload(magnet_url_or_hash=None):
	"""
	<h5>Description:</h5>
	<p>
		Adds a new torrent to the system and retrieves its data if its not already in the system.
		Note: If the torrent is added via a SHA-1 info_hash, a magnet link is constructed and we attempt to retrieve the torrent via DHT
	</p>

	<h5>Parameters:</h5>
	<ul>
		<li><strong>magnet_url_or_hash</strong> - A magnet link, a HTTP url to the .torrent file, or a SHA-1 info_hash</li>
	</ul>

	<h5>Returns:</h5>
	<p>
		If successful, a data structure like so:
<pre>
{
    "data": {
        "url": "(the contents of the url_magnet_or_hash parameter)",
        "added": true,
        "hash": "a4b93e50187930206dcf1351bceceb29f5a119ca"
    },
    "success": true
}
</pre>
		If an error occured, the following data structure will be returned:
<pre>
{
    "message": "Cannot recognise this url: foo",
    "success": false
}
</pre>
	</p>

	<h5>Examples:</h5>
	<p>
		Add based on a magnet link:<br />
		<pre>/api/upload/magnet%3A%3Fxt%3Durn%3Abtih%3Addceab34ac388ca56b0cdbc6eb726ca1844233c5%26dn%3DPioneer%2BOne%2BS01E03%2BXvid-VODO%26tr%3Dudp%253A%252F%252Ftracker.openbittorrent.com%253A80%26tr%3Dudp%253A%252F%252Ftracker.publicbt.com%253A80%26tr%3Dudp%253A%252F%252Ftracker.istole.it%253A6969%26tr%3Dudp%253A%252F%252Ftracker.ccc.de%253A80</pre>
		
		Add based on a HTTP url:<br />
		<pre>/api/upload/http%3A%2F%2Ftorrents.thepiratebay.se%2F6753216%2FPioneer_One_S01E03_Xvid-VODO.6753216.TPB.torrent</pre>
		
		Add based on a SHA-1 info_hash:<br />
		<pre>/api/upload/ddceab34ac388ca56b0cdbc6eb726ca1844233c5</pre>
	</p>
	"""
	url = magnet_url_or_hash if magnet_url_or_hash else request.query.get("magnet_url_or_hash")
	if not url:
		return api_error("No magnet, url or hash supplied")	
	item = url.strip()
	info_hash = "";
	try :
		if is_hash(item):
			info_hash = item;			
			if not is_in_database(item):
				add_to_database(item)
		elif is_magnet(item):			
			params = lt.parse_magnet_uri(item)			
			info_hash = str(params["info_hash"])
			if not info_hash.replace("0", ""):
				raise RuntimeError("The hash was all 0's, did you urlencode the magnet link properly?")
			else:
				if not is_in_database(info_hash):
					add_to_database(info_hash, item)
		elif is_url(item):
			item = urllib.unquote_plus(item)
			logger.debug("Fetching %s" % item)			
			download_to = tempfile.mkstemp(suffix=".torrent")[1]				
			urllib.urlretrieve(item, download_to)
			handle = open(download_to, "rb");
			torrent_data = handle.read()
			info = lt.torrent_info(lt.bdecode(torrent_data))
			handle.close()
			os.remove(download_to)
			info_hash = "%s" % info.info_hash()
			if not is_in_database(info_hash):
				add_to_database(info_hash, fetch_metadata=False)
				thread.start_new_thread(add_from_torrent_info, (info, torrent_data))			
		else:
			raise RuntimeError("Cannot recognise this url: %s" % item)
	except (RuntimeError, IOError) as e:
		return api_error(str(e))
	
	return api_success({ "url" : item, "hash" : info_hash, "added" : True})

@route("/api/info")
@route("/api/info/<hash:re:[a-fA-F0-9]{40}>")
def info(hash=None):
	"""
	<h5>Description:</h5>
	<p>
		Checks the information we have of a torrent that has been added.
		If the torrent metadata is still being retrieved, 'torrent.retrieving_data' will be 1.
		If the torrent metadata has been retrieved, 'torrent.download_link' will have a value
	</p>

	<h5>Parameters:</h5>
	<ul>
		<li><strong>hash</strong> - The hash returned from the /api/upload call</li>
	</ul>

	<h5>Returns:</h5>
	<p>
		On success (metadata is still downloading):
<pre>
{
    "data": {		        
        "torrent": {		            
            "retrieving_data": 1,
            "hash": "ddceab34ac388ca56b0cdbc6eb726ca1844233c6"		            
        }		        
    },
    "success": true
}
</pre>
		On success (metadata has downloaded):
<pre>
{
    "data": {
        "files": [{
                "size_bytes": 392560640,
                "full_location": "Pioneer.One.S01E03.Xvid-VODO/Pioneer.One.S01E03.Xvid-VODO.avi",
                "name": "Pioneer.One.S01E03.Xvid-VODO.avi"
        }],
        "torrent": {
            "hash": "ddceab34ac388ca56b0cdbc6eb726ca1844233c5",
            "name": "Pioneer.One.S01E03.Xvid-VODO",
            "download_link": "/api/metadata/ddceab34ac388ca56b0cdbc6eb726ca1844233c5.torrent",
            "total_size_bytes": 402477447
        },
        "trackers": [{
                "leechers": 0,
                "completed": 0,
                "seeds": 0,
                "tracker_url": "udp://tracker.openbittorrent.com:80"                
        }]
    },
    "success": true
}
</pre>
		On error:
<pre>
{
    "message": "Torrent ddceab34ac388ca56b0cdbc6eb726ca1844233c6 is not in database! Call /api/upload to add it",
    "success": false
}
</pre>
	</p>

	<h5>Example:</h5>
	<p>
		<strong>Check the info of torrent 'ddceab34ac388ca56b0cdbc6eb726ca1844233c6'</strong><br />
		/api/info/ddceab34ac388ca56b0cdbc6eb726ca1844233c6
	</p>
	"""
	if not hash or not is_hash(hash):
		return api_error("%s is not a valid hash" % hash)
	db = database.get_cursor()
	db.execute("SELECT id, hash, name, total_size_bytes, retrieving_data FROM torrent WHERE hash=%s", hash)
	torrent = db.fetchone()
	if not torrent:
		return api_error("Torrent %s is not in database! Call /api/upload to add it" % hash)
	id = torrent["id"]
	del torrent["id"]

	if torrent["retrieving_data"]:
		del torrent["total_size_bytes"]
		del torrent["name"]
		return api_success({
			"torrent" : torrent
		})
	else:
		del torrent["retrieving_data"]
		torrent["download_link"] = get_url("/api/metadata/<hash:re:[a-fA-F0-9]{40}>.torrent", hash=hash)
		torrent["nice_size"] = size(torrent["total_size_bytes"])

	db.execute("SELECT tracker_url, seeds, leechers, completed, scrape_error FROM tracker WHERE torrent_id=%s", id)
	trackers = db.fetchall()
	for tracker in trackers:
		if not tracker["scrape_error"]:
			del tracker["scrape_error"]

	db.execute("SELECT name, full_location, length_bytes as size_bytes FROM file WHERE torrent_id=%s", id)
	files = db.fetchall()
	for file in files:
		file["nice_size"] = size(file["size_bytes"])

	db.close()
	return api_success({
		"torrent" : torrent, "files" : files, "trackers" : trackers
	})

@route("/api/metadata")
@route("/api/metadata/<hash:re:[a-fA-F0-9]{40}>")
def metadata(hash=None):
	"""
	<h5>Description:</h5>
	<p>
		Returns the torrent metadata (ie, the contents of the .torrent file) as a base64-encoded string
	</p>

	<h5>Parameters:</h5>
	<ul>
		<li><strong>hash</strong> - The torrent hash, obtained from a /api/status call where torrent.download_link has a value
	</ul>

	<h5>Returns:</h5>
	<p>
		On success:
<pre>
{
    "data": {
        "base64_metadata": "ZDg6YW5ub3VuY2UzNTp1ZHA6Ly90cmFja2VyLm9wZW5...SNIP",
        "hash": "ddceab34ac388ca56b0cdbc6eb726ca1844233c5"
    },
    "success": true
}
</pre>
		On error:
<pre>
{
    "message": "The hash ddceab34ac388ca56b0cdbc6eb726ca1844233c6 isnt in the database",
    "success": false
}
</pre>
	</p>

	<h5>Example</h5>
	<p>
		Retrieve the metadata for torrent 'ddceab34ac388ca56b0cdbc6eb726ca1844233c5':
		<pre>/api/metadata/ddceab34ac388ca56b0cdbc6eb726ca1844233c5</pre>
	</p>	
	"""
	if not hash:
		return api_error("Please specify a hash" % hash)
	metadata = get_base64_metadata(hash, decode=False)
	return api_success({
		"hash" : hash,
		"base64_metadata" : metadata
	}) if metadata else api_error("The hash %s isnt in the database or the metadata hasnt been retrieved yet" % hash)

@route("/api/metadata/<hash:re:[a-fA-F0-9]{40}>.torrent")
def metadata_file(hash=None):
	"""
	<h5>Description:</h5>
	<p>
		Returns the .torrent file for the specified hash
	</p>

	<h5>Parameters:</h5>
	<ul>
		<li><strong>hash</strong> - The torrent hash, obtained from a /api/status call where torrent.download_link has a value
	</ul>

	<h5>Returns:</h5>
	<p>
		On success, a file download will be started. On error, a 404 will be triggered.
	</p>

	<h5>Example</h5>
	<p>
		Retrieve the .torrent file for hash 'ddceab34ac388ca56b0cdbc6eb726ca1844233c5':
		<pre>/api/metadata/ddceab34ac388ca56b0cdbc6eb726ca1844233c5.torrent</pre>
	</p>	
	"""	
	if not hash:
		raise HTTPError(404, "No hash specified")
	metadata = get_base64_metadata(hash, decode=True)
	response.headers["Content-Disposition"] = "attachment; filename=%s.torrent" % hash
	response.headers["Content-Type"] = "application/x-bittorrent"
	if metadata:
		return StringIO.StringIO(metadata)
	raise HTTPError(404, "No metadata exists for hash: %s" % hash)

def is_magnet(item):
	return item.startswith("magnet:")

def is_hash(item):
	return hash_pattern.match(item)

def is_url(item):
	parsed = urlparse(item)
	return parsed.scheme.lower() in ["http", "https"]

def is_in_database(hash):
	db = database.get_cursor()
	db.execute("SELECT id FROM torrent WHERE hash=%s", (hash,))
	ret = db.rowcount > 0
	db.close()
	return ret

def add_to_database(hash, full_magnet_uri=None, already_exists=False, fetch_metadata=True):
	db = database.get_cursor()
	if not already_exists:
		db.execute("INSERT INTO torrent(hash, retrieving_data) VALUES (%s, 1)", (hash))
		db.commit()
	if fetch_metadata:
		magnet_uri = full_magnet_uri if full_magnet_uri else get_magnet_uri(hash)		
		thread.start_new_thread(fetch_magnet, (magnet_uri,))
	db.close()

def add_from_torrent_info(info, torrent_metadata=None):
	db = database.get_cursor()
	torrent_hash = str(info.info_hash())	
	if is_in_database(torrent_hash):
		db.execute("DELETE FROM torrent WHERE hash=%s", (torrent_hash))	
	total_size = sum([f.size for f in info.files()])
	db.execute("INSERT INTO torrent(hash, name, total_size_bytes, retrieving_data, base64_metadata) VALUES (%s, %s, %s, 0, %s)",
		(torrent_hash, info.name(), total_size, base64.b64encode(torrent_metadata)))
	torrent_id = db.lastrowid

	for f in info.files():
		db.execute("INSERT INTO file(torrent_id, name, full_location, length_bytes) VALUES (%s, %s, %s, %s)",
			(torrent_id, os.path.basename(f.path), f.path, f.size))
	for t in info.trackers():		
		db.execute("INSERT INTO tracker(torrent_id, tracker_url) VALUES (%s, %s)",
			(torrent_id, t.url))
	db.commit()	
	db.close()
	scrape_trackers(torrent_hash, [t.url for t in info.trackers()])

def get_base64_metadata(hash, decode=False):
	db = database.get_cursor()
	db.execute("SELECT base64_metadata FROM torrent WHERE hash=%s", hash)	
	if (db.rowcount > 0):
		data = db.fetchone()
		db.close()
		metadata = data['base64_metadata']
		return base64.b64decode(metadata) if decode else metadata
	db.close()
	return None

def fetch_magnet(magnet_uri):	
	tempdir = tempfile.mkdtemp()
	logger.debug("Fetching magnet to '%s'" % tempdir)
	params = {
		"save_path" : tempdir,
		"duplicate_is_error" : True,
		"paused" : False,
		"auto_managed" : True,
		"url" : magnet_uri,
		"storage_mode" : lt.storage_mode_t(2)
	}
	handle = ses.add_torrent(params)
	def cleanup():
		ses.remove_torrent(handle)
		shutil.rmtree(tempdir)
	while not handle.has_metadata():
		try :			
			time.sleep(1)			
		except NameError as e:
			logger.debug("Exception!! %s" % str(e))
			cleanup()
			return		
	logger.debug("Magnet %s fetched!" % magnet_uri)
	torrent_data = lt.create_torrent(handle.get_torrent_info()).generate()	
	add_from_torrent_info(handle.get_torrent_info(), lt.bencode(torrent_data))
	cleanup()

def get_magnet_uri(hash):
	#use these public trackers to help find the torrent via magnet, otherwise itll never be found
	public_trackers = "tr=udp://tracker.openbittorrent.com:80&tr=udp://tracker.publicbt.com:80&tr=udp://tracker.istole.it:6969&tr=udp://tracker.ccc.de:80"
	return "magnet:?xt=urn:btih:%s&%s" % (hash, public_trackers)

def scrape_trackers(hash, tracker_list):
	db = database.get_cursor()
	for url in tracker_list:
		try:
			result = scrape(url, [hash])				
			for hash, stats in result.iteritems():				
				db.execute("""UPDATE tracker SET seeds=%s, leechers=%s, completed=%s,
					last_scrape=CURRENT_TIMESTAMP, scrape_error=NULL
					WHERE torrent_id=(SELECT id FROM torrent WHERE hash=%s) AND tracker_url=%s""",
					(stats["seeds"], stats["peers"], stats["complete"], hash, url))
			db.commit()
		except (RuntimeError, NameError, ValueError, socket.timeout) as e:			
			db.execute("""UPDATE tracker SET last_scrape=CURRENT_TIMESTAMP, scrape_error=%s
				WHERE tracker_url=%s AND torrent_id=(SELECT id FROM torrent WHERE hash=%s)""", (e, url, hash))
			db.commit()
	db.close()			

#get all torrents that were still trying to retrieve metadata and re-add them
db = database.get_cursor()
db.execute("SELECT hash FROM torrent WHERE retrieving_data = 1")
data = db.fetchall()
for item in data:
	logger.debug("Reloading '%s' since its metadata hasnt been retrieved yet" % item["hash"])
	add_to_database(item["hash"], get_magnet_uri(item["hash"]), True)
db.close()