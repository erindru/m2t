#!/usr/bin/python
from m2t.db import db
from m2t.scraper import scrape

def main():
	db.execute("SELECT torrent_id, tracker_id, hash, tracker_url, last_scrape FROM vw_scrape")	
	all_trackers = {}
	all_torrents = {}
	for x in range(0, db.rowcount):
		row = db.fetchone()
		turl = row["tracker_url"]
		hash = row["hash"]
		if turl in all_trackers.iterkeys():
			if hash not in all_trackers[turl]:
				all_trackers[turl].append(hash)
		else:
			all_trackers[turl] = [hash]
		if not hash in all_torrents:
			all_torrents[hash] = { "torrent_id" : row["torrent_id"] }

	for tracker, hashes in all_trackers.iteritems():
		try:
			result = scrape(tracker, hashes)	
			if result:
				for hash, stats in result.iteritems():
					tid = all_torrents[hash]["torrent_id"]					
					db.execute("""UPDATE tracker SET seeds=%s, leechers=%s, completed=%s,
						last_scrape=CURRENT_TIMESTAMP, scrape_error=NULL
						WHERE torrent_id=%s AND tracker_url=%s""",
						(stats["seeds"], stats["peers"], stats["complete"], tid, tracker))
				db.commit()
		except (RuntimeError, NameError, ValueError, socket.timeout) as e:
			print "Error: %s" % e
			db.execute("""UPDATE tracker SET last_scrape=CURRENT_TIMESTAMP, scrape_error=%s
				WHERE tracker_url=%s""", (e, tracker))
			db.commit()

if __name__ == "__main__":
	main()