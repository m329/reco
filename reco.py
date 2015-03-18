# -*- coding: utf-8 -*-

"""
Reco
~~~~~~
A simple proof-of-concept for doing artist/band recommendations using
only user-submitted information.

version 0.02

"""

import os, sys
import json, sqlite3
from flask import Flask, render_template, g, request, flash, redirect, url_for
from forms import FavoritesForm
import requests
import config

app = Flask(__name__)

"""
DB-related
"""

# Load/override default config
app.config.update(dict(
	DATABASE=os.path.join(app.root_path, 'reco.db'),
	DEBUG=config.DEBUG,
	SECRET_KEY=config.SECRET_KEY
))

cache = {} # a place to store API responses so we can avoid asking the same question twice

def connect_db():
	""" connect to the specific database """
	rv = sqlite3.connect(app.config['DATABASE'])
	rv.row_factory = sqlite3.Row
	return rv

def get_db():
	"""	open a new database connection if there is none yet for the current application context """
	if not hasattr(g, 'sqlite_db'):
		g.sqlite_db = connect_db()
	return g.sqlite_db

def init_db():
	""" initialize the database """
	with app.app_context():
		db = get_db()
		with app.open_resource('schema.sql', mode='r') as f:
			db.cursor().executescript(f.read())
		db.commit()

@app.teardown_appcontext
def close_db(error):
	""" close the database connection """
	if hasattr(g, 'sqlite_db'):
		g.sqlite_db.close()

"""
Helper functions
"""

def arthash(a):
	""" conveniently normalize artist name """
	return a.lower().replace(' ','')

def cached_request(url,headers=None):
	"""	keep API responses in a dict and only make requests for new information	"""
	
	if url in cache:
		return cache[url]
	else:
		r = requests.get(url,headers=headers)
	
		if r.status_code==200:
			cache[url] = r
	
		return r

def discogs_search_artist(a):
	"""
	Make a request to the Discogs API search endpoint for information about a particular artist

	Note: Discogs does not cooperate unless you pass an arbitrary user-agent!
	"""
	
	request_url = 'https://api.discogs.com/database/search?artist='+a+'&key='+config.DISCOGS_CONSUMER_KEY+'&secret='+config.DISCOGS_CONSUMER_SECRET

	try:	
		r = cached_request(request_url,headers = {'user-agent': config.DISCOGS_APP_USER_AGENT})
		return r.json()
		
	except Exception as e:
		print "Unexpected error:", sys.exc_info()[0]
		return None

def get_album_cover_urls_for_artist(a,N=3):
	"""
	Grab the first N (default is 3) album cover urls from the Discogs search results for an artist
	"""
	
	d = discogs_search_artist(a)
	
	try:
		return [i['thumb'] for i in d['results']][:N]
	except:
		print "Unexpected error:", sys.exc_info()[0]
		return []

"""
View functions
"""

@app.route("/")
@app.route('/favorites', methods=['GET'])
def askfavorites():
	""" show the favorites entry form """
	form = FavoritesForm()
	return render_template('favorites.html',form=form)

@app.route("/artists")	
def artists():
	""" list known artists """
	db = get_db()
	cur = db.execute('select aid, display from a order by aid')
	artists = cur.fetchall()
	return render_template('artists.html',artists=artists)

@app.route('/favorites', methods=['POST'])
def postfavorites():
	""" process the user's favorites list """
	db = get_db()
	arts = [request.form['a1'],request.form['a2'],request.form['a3']]
	
	if all(a is not u'' for a in arts):	# make sure that none of the fields were left empty
	
		arts.sort()
		
		ahs = [arthash(a) for a in arts]
		
		# assimulate new data
		
		"""
			Add 1 to the weighting between each pair of artists selected
			by the user. If the link did not already exist, add it.
		"""
		
		q="insert or replace into a2a values (?, ?,coalesce( (SELECT w FROM a2a WHERE aid1=? AND aid2=?), 0) + 1);"
		
		db.execute(q,[ahs[0],ahs[1],ahs[0],ahs[1]])
		db.execute(q,[ahs[1],ahs[2],ahs[1],ahs[2]])
		db.execute(q,[ahs[0],ahs[2],ahs[0],ahs[2]])
		
		# add these artists to the list of known artists (if any were previously unknown)
		
		q="insert or ignore into a (aid, display) values (?, ?);"
		
		db.execute(q,[ahs[0],arts[0]])
		db.execute(q,[ahs[1],arts[1]])
		db.execute(q,[ahs[2],arts[2]])
		db.commit()
		
		"""
			Return the top 5 artists with the strongest connection to the
			artists selected by the user.
		"""
		
		cur = db.execute('select B.display, sum(w) as s from (select aid2 as aidA, aid1 as aidB, w from a2a where aid1 = ? or aid1=? or aid1=? union select aid1 as aidA, aid2 as aidB, w from a2a where aid2 = ? or aid2=? or aid2=? ) as A join a as B on A.aidA = B.aid where A.aidA != ? and A.aidA != ? and A.aidA != ? group by aidA order by s desc limit 5;', [ahs[0],ahs[1],ahs[2], ahs[0],ahs[1],ahs[2], ahs[0],ahs[1],ahs[2]])
		
		dbresults = cur.fetchall()
		
		"""
			If there weren't any known artists connected to those
			selected by the user, return the top 5 most popular artists in the database.
		"""
		
		if(len(dbresults)<1):
			cur = db.execute('select B.display,sum(w) as s from (select aid2 as aidA, aid1 as aidB, w from a2a union select aid1 as aidA, aid2 as aidB, w from a2a) as A join a as B on A.aidA = B.aid where A.aidA != ? and A.aidA != ? and A.aidA != ? group by aidA order by s desc limit 5;',[ahs[0],ahs[1],ahs[2]])
			dbresults = cur.fetchall()
	
		results = []
		for dbr in dbresults:
			results.append({'display':dbr['display'],'album_covers':get_album_cover_urls_for_artist(dbr['display'])})
			
		return render_template('results.html',results=results)

	else:	# if some fields were left empty, redirect back to the form
		return redirect(url_for('askfavorites'))

# if this module is called directly, run the app
if __name__ == "__main__":
	app.run()
