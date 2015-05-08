# -*- coding: utf-8 -*-

"""
Reco
~~~~~~
A simple proof-of-concept for doing artist/band recommendations using
only user-submitted information.

version 0.03

"""

import os, sys
import json
import sqlite3, MySQLdb
from flask import Flask, render_template, g, request, flash, redirect, url_for
from forms import FavoritesForm,ArtistSearchForm
import requests
import config
import numpy as np
from recommender import ArtistRecommender
import json
import itertools
import random

app = Flask(__name__)

"""
DB-related
"""

sys.setrecursionlimit(10000)

# Load/override default config
app.config.update(dict(
	DATABASE=os.path.join(app.root_path, 'reco.db'),
	DEBUG=config.DEBUG,
	SECRET_KEY=config.SECRET_KEY,
	MYSQL_HOST=config.MYSQL_HOST,
	MYSQL_PORT=config.MYSQL_PORT,
	MYSQL_DATABASE=config.MYSQL_DATABASE,
	MYSQL_USER=config.MYSQL_USER,
	MYSQL_PASSWORD=config.MYSQL_PASSWORD
))

cache = {} # a place to store API responses so we can avoid asking the same question twice

"""
SQLite
"""

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
MYSQL
"""

def mysql_connect_db():
	""" connect to the specific database """
	c = MySQLdb.connect(host=app.config['MYSQL_HOST'],port=app.config['MYSQL_PORT'],db=app.config['MYSQL_DATABASE'],user=app.config['MYSQL_USER'],passwd=app.config['MYSQL_PASSWORD'],use_unicode=True,charset='utf8', init_command='SET NAMES UTF8')
	return c

def mysql_get_db():
	"""	open a new database connection if there is none yet for the current application context """
	if not hasattr(g, 'mysql_db'):
		g.mysql_db = mysql_connect_db()
	return g.mysql_db

@app.teardown_appcontext
def mysql_close_db(error):
	""" close the database connection """
	if hasattr(g, 'mysql_db'):
		g.mysql_db.close()

"""
General recommendation database setting, use table SubTables
"""

def mysql_connect_subdb():
	""" connect to the specific database """
	c = MySQLdb.connect(host=app.config['MYSQL_HOST'],port=app.config['MYSQL_PORT'],db='SubTables',user=app.config['MYSQL_USER'],passwd=app.config['MYSQL_PASSWORD'],use_unicode=True,charset='utf8', init_command='SET NAMES UTF8')
	return c

def mysql_get_subdb():
	"""	open a new database connection if there is none yet for the current application context """
	if not hasattr(g, 'mysql_subdb'):
		g.mysql_subdb = mysql_connect_subdb()
	return g.mysql_subdb

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
	result = try_get_album_cover_urls_for_artist(a,N)

	if len(result)<1:
		aliases = artist_aliases_lookup(a,by='name')
		for al in aliases:
			result = try_get_album_cover_urls_for_artist(al,N)
			if len(result)>0:
				break
	return result
		
			

def try_get_album_cover_urls_for_artist(a,N=3):
	"""
	Grab the first N (default is 3) album cover urls from the Discogs search results for an artist
	"""
	
	d = discogs_search_artist(a)
	
	thumbs = []
	
	N=int(N)
	
	try:
		if 'results' in d:
			for i in d['results']:
				if i['thumb'] != '':
					thumbs.append(i['thumb'])
			return thumbs[:N]
	except:
		print "Unexpected error:", sys.exc_info()[0]
	return []
	

def get_genres_list():
	db = mysql_get_db()
	
	q="select distinct name from (select name from Genres where level=1 and name!='Unknown genre' limit 2000) as t;"
		
	cur = db.cursor()
	
	cur.execute(q)
	
	dbresults = [i[0] for i in cur.fetchall()]
	
	return dbresults

def artist_name_lookup(id):
	db = mysql_get_db()
	cur = db.cursor()
	cur.execute("select artistName from Artists where artistId='"+str(id)+"' limit 1;")
	name = cur.fetchone()
	if name is not None:
		return name[0]
	else:
		return None

def artist_name_popularity_lookup(id):
	db = mysql_get_db()
	cur = db.cursor()
	cur.execute("select artistName, artistPopularityAll from Artists where artistId='"+id+"' limit 1;")
	data = cur.fetchone()
	return data

def artist_id_lookup(name):
	db = mysql_get_db()
	cur = db.cursor()
	cur.execute("select artistId from Artists where lower(artistName) like lower('"+name+"') limit 1;")
	name = cur.fetchone()
	return str(name[0])

def artist_id_lookup_soundslike(name):
	
	db = mysql_get_db()
	cur = db.cursor()
	cur.execute("select concat('%',splitname('"+name+"'),'%') limit 1;")
	soundex = cur.fetchone()[0]
	
	cur = db.cursor()
	cur.execute("select artistId from Artists where soundName like '"+soundex+"' order by artistPopularityAll desc limit 1;")
	artist_id = cur.fetchone()
	if artist_id is not None:
		return str(artist_id[0])
	else:
		return None

def artist_id_search_soundslike(name,N=20):
	
	db = mysql_get_db()
	cur = db.cursor()
	cur.execute("select concat('%',splitname('"+name+"'),'%') limit 1;")
	soundex = cur.fetchone()[0]
	
	cur = db.cursor()
	cur.execute("select distinct artistId from Artists where soundName like '"+soundex+"' order by artistPopularityAll desc limit "+str(N)+";")
	artist_ids = cur.fetchall()
	
	return [str(i[0]) for i in artist_ids][:N]

def distinctify(seq):
    seen = set()
    seen_add = seen.add
    return [ x for x in seq if not (x in seen or seen_add(x))]

def artist_aliases_lookup(x,by='id'):

	db = mysql_get_db()
	

	if(by!='id'): # then assume searching by name
		x = artist_id_lookup(x)
	
	cur = db.cursor()
	cur.execute("select distinct artistAlias from ArtistAlias where artistId='"+str(x)+"';")
	aliases = cur.fetchall()
	
	aliases = [i[0] for i in aliases]		
	return aliases

def artist_id_search_cached(name,N=20,feelinglucky=False):
	q=name+str(N)+str(feelinglucky)
	
	if( q in cache ):
		return cache[q]
	else:
		return artist_id_search(name,N,feelinglucky)

def artist_id_search(name,N=20,feelinglucky=False):
	

	# first search for an exact match
	db = mysql_get_db()
	cur = db.cursor()
	cur.execute("SELECT distinct ArtistId from ArtistAlias where replace(artistAlias,' ','') = '"+name.replace(' ','')+"' limit "+str(N)+";")
	exact = cur.fetchall()
	
	exact_match = distinctify([str(i[0]) for i in exact])
	
	if(feelinglucky):
		if(len(exact_match)>0):
			return exact_match[0]
	
	if(len(exact_match)>=N):
		return exact_match[:N]
	
	# now search for soundex in ArtistAlias table
	cur = db.cursor()
	cur.execute("select concat('%',splitname('"+name+"'),'%') limit 1;")
	soundex = cur.fetchone()[0]
	soundex = soundex.replace(' ','')
	
	cur = db.cursor()
	cur.execute("SELECT distinct ArtistId from ArtistAlias where replace(AliasSound,' ','') like '"+soundex+"' limit "+str(N)+";")
	
	approx = cur.fetchall()
	
	approx_match = [str(i[0]) for i in approx]
	
	if(feelinglucky):
		if(len(approx_match)>0):
			return approx_match[0]
	
	results = distinctify( exact_match+approx_match )[:N]
	
	return distinctify( exact_match+approx_match )[:N]
	
def lookup_songs_of_artist(id,N=10):

	db = mysql_get_db()
	cur = db.cursor()
	cur.execute("select youtubeId,songName,url from Songs where artistId='"+id+"' order by viewCount desc limit "+str(N)+";")
	songs = cur.fetchall()
	
	return songs

def get_trending_status(id):
	
	db = mysql_get_db()
	cur = db.cursor()
	cur.execute("select artistPopularityRecent,artistPopularityAll from Artists where artistId='"+id+"' limit 1;")
	[recent,theall] = cur.fetchone()

	mu = get_mean_popularity_ratio()

	return int(recent - (theall*mu))
	
def get_mean_popularity_ratio():
	"""	get the ratio of mean popularity (recent / all) """
	if not hasattr(g, 'mean_popularity_ratio'):
		
		db = mysql_get_db()
		cur = db.cursor()
		cur.execute("select avg(artistPopularityRecent)/avg(artistPopularityAll) from Artists limit 1;")
		mu = cur.fetchone()[0]
		
		g.mean_popularity_ratio = mu
	return g.mean_popularity_ratio

"""
KDTree / SVD stuff
"""

def get_recommender():
	"""	returns the artist recommender object """
	if not hasattr(g, 'recommender'):
		g.recommender = ArtistRecommender()
	return g.recommender

"""
View functions
"""

@app.route("/")
def index():
	form = ArtistSearchForm()
	
	""" Display the general recommendation """
	db = mysql_get_subdb()	
	cur = db.cursor()
	
	Nlim = 8 # number of items to show
		
	#Trending Songs
	q = "select youtubeId,songName,url from trenSong order by viewCount desc limit 30;"
	cur.execute(q)
	songs_t = cur.fetchall()
	songs_list = [i for i in songs_t]
	slen = len(songs_list)
	w = [1.2 * slen - i for i in range(slen)]
	sum_w = sum(w)
	weight = [float(i)/sum_w for i in w]
	
	song_ind = np.random.choice([i for i in range(slen)], Nlim, replace = False, p = weight)	
	songs = [songs_list[i] for i in song_ind]	
		
	tren_song = []
	for song in songs:
		tren_song.append({'youtubeId':song[0],'songName':song[1],'url':song[2]})
	
	
	#Trending Artists
	q = "select distinct artistName, artistId from recArtist order by artistPopularityRecent Desc limit 50;"
	cur.execute(q)	
	dbresults_t = cur.fetchall()

	artist_list = [i for i in dbresults_t]
	alen = len(artist_list)
	w = [1.2 * alen - i for i in range(alen)]
	sum_w = sum(w)
	weight = [float(i)/sum_w for i in w]
	
	artist_ind = np.random.choice([i for i in range(alen)], Nlim, replace = False, p = weight)	
	dbresults = [artist_list[i] for i in artist_ind ]

	tren_artist = [ {'name':n,'id':i} for (n,i) in dbresults]
	
	#popular Songs
	q = "select youtubeId,songName,url from popuSong order by viewCount desc limit 30;"
	cur.execute(q)
	songs_t = cur.fetchall()

	songs_list = [i for i in songs_t]
	slen = len(songs_list)
	w = [1.2 * slen - i for i in range(slen)]
	sum_w = sum(w)
	weight = [float(i)/sum_w for i in w]
	
	song_ind = np.random.choice([i for i in range(slen)], Nlim, replace = False, p = weight)	
	songs = [songs_list[i] for i in song_ind]
	
	popu_song = []
	for song in songs:
		popu_song.append({'youtubeId':song[0],'songName':song[1],'url':song[2]})
	
	#Popular Artists
	q = "select distinct artistName, artistId from popuArtist group by artistName order by artistPopularityAll Desc limit 50;"
	cur.execute(q)	
	dbresults_t = cur.fetchall()
	
	artist_list = [i for i in dbresults_t]
	alen = len(artist_list)
	w = [1.2 * alen - i for i in range(alen)]
	sum_w = sum(w)
	weight = [float(i)/sum_w for i in w]
	
	artist_ind = np.random.choice([i for i in range(alen)], Nlim, replace = False, p = weight)	
	dbresults = [artist_list[i] for i in artist_ind]	

	popu_artist = [ {'name':n,'id':i} for (n,i) in dbresults]	
	
	return render_template('index.html', form=form, popu_artist=popu_artist,popu_song=popu_song, tren_artist=tren_artist, tren_song = tren_song)
	
@app.route('/favorites', methods=['GET'])
def askfavorites():
	""" show the favorites entry form """
	form = FavoritesForm()
	return render_template('favorites.html',form=form)

@app.route('/recommend/<artist_name>')
def recommend(artist_name):
	artist_id=artist_id_lookup(artist_name)
	[dist,ids,points]=get_recommender().recommend(artist_id,k=10)
	names = [artist_name_lookup(i) for i in ids]
	return render_template('recommend.html',artist_name=artist_name_lookup(artist_id),names=names,dist=dist)

@app.route('/json/location/id',methods=['POST'])
def get_location_from_id_json():
	artist_id = request.form['aid']
	
	x=get_recommender().getlocationof(artist_id)
	
	return json.dumps(x.tolist())

@app.route('/json/recommend/id',methods=['POST'])
def recommend_json():
	artist_id = request.form['aid']
	
	[dist,ids,points]=get_recommender().recommend(artist_id,k=20)
	names = [artist_name_lookup(i) for i in ids]
	
	dist = (dist/np.max(dist)) # return relative normalize distance (scale of 0-1)
	
	data = [ (p[0],p[1],p[2],p[3],p[4],n,d,i) for p,n,d,i in itertools.izip(points.tolist(),names,dist.tolist(),ids.tolist())]
	
	return json.dumps(data)
	
@app.route('/json/recommend/searchnear',methods=['POST'])
def recommend_searchnear_json():
	xs = [float(request.form[x]) for x in ['x0','x1','x2','x3','x4']]

	[dist,ids,points]=get_recommender().searchnear(xs,k=20)

	names = [artist_name_lookup(i) for i in ids]
	
	dist = (dist/np.max(dist)) # return relative normalize distance (scale of 0-1)
	
	data = [ (p[0],p[1],p[2],p[3],p[4],n,d,i) for p,n,d,i in itertools.izip(points.tolist(),names,dist.tolist(),ids.tolist())]
	
	return json.dumps(data)	

@app.route('/json/artistid/soundslike',methods=['POST'])
def search_artist_id_lookup_soundslike():
	
	search = request.form['search_term']
	
	artistId = artist_id_search_cached(search,N=1,feelinglucky=True)
	
	if artistId is not None:
		return json.dumps({'id':artistId,'status':'success'})
	else:
		return json.dumps({'id':'0','status':'error'})
	
	

@app.route("/artists")	
def artists():
	""" list known artists """
	db = get_db()
	cur = db.execute('select aid, display from a order by aid')
	artists = cur.fetchall()
	return render_template('artists.html',artists=artists)

@app.route("/artist")
@app.route("/artist/<id>")
def artist_page(id=None):
	""" artist page """
	
	if id is None:
		id = artist_id_lookup('Rihanna')
	
	artist_name = artist_name_lookup(id)
	
	# find similar artists
	[dist,ids,points] = get_recommender().recommend(id,k=11)
	names = [artist_name_lookup(i) for i in ids]
	
	order=np.argsort(dist)
	names = np.array(names)[order].tolist()
	ids = np.array(ids)[order].tolist()
	
	trending_status = np.round(get_trending_status(id))
		
	similar_artists = [ {'name':n,'id':i} for n,i in itertools.izip(names,ids)]
	
	# find songs
	songdata = []
	for song in lookup_songs_of_artist(id,N=12):
		songdata.append({'youtubeId':song[0],'songName':song[1],'url':song[2]})
	
	return render_template('artist_page.html',artist_id=id,artist_name=artist_name,similar_artists=similar_artists,songdata=songdata,trending_status=trending_status)

@app.route("/artistsearch/",methods=['POST'])
def artist_search_page():
	search_term = request.form['searchbox']
		
	artist_ids = artist_id_search_cached(search_term,N=15,feelinglucky=False)
	artist_names = [artist_name_lookup(str(i)) for i in artist_ids]
	return render_template('artist_search.html',search_term=search_term,artists=itertools.izip(artist_ids,artist_names))

@app.route("/albumcovers/<by>/<artist>/<N>")
@app.route("/albumcovers/<by>/<artist>")
def json_get_album_cover_urls_for_artist(by,artist,N=1):
	if by=='id':
		artist_name=artist_name_lookup(artist)
	else:
		artist_name=artist
	
	results = get_album_cover_urls_for_artist(artist_name,N=N)
		
	return json.dumps(results)

@app.route("/genres")	
def genres():
	""" list genres """
	return render_template('genres.html',genres=get_genres_list())
	
@app.route("/gvision")
@app.route("/gvision/<by>/<x>")
def genrevision(by=None,x=None):
	""" genrevision """
	if by=='id':
		searchpoint = get_recommender().getlocationof(x)
	elif by=='name':
		searchpoint = get_recommender().getlocationof(artist_id_lookup(x))
	else:
		searchpoint = get_recommender().getlocationof(artist_id_lookup('Rihanna'))
	
	return render_template('genre_vision.html',initial_point=searchpoint,dimlabels=config.dimlabels)

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
