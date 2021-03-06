#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import webapp2
import jinja2
import os
import cgi
import datetime
import time
import logging

from operator import itemgetter

from google.appengine.ext import db
from google.appengine.api import memcache
from google.appengine.api import channel

# set up a directory for jinja html templates
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)

# use this to change our event in case we want to test
# at different events and sort our data
EVENT = "MVP party 4-7"
TRACK_KEY = "track"
QUEUE = "queue"
VOTE = "vote"

vote_songs = {}
queue = []

# hex code for purple #672199 old = #5e5e5e

def escape_html(s):
	s = s.replace("&", "&amp;")
	return cgi.escape(s, quote = True)

# shortcut function for rendering jinja templates
def render_str(template, **params):
	t = jinja_env.get_template(template)
	return t.render(params)

# cache the current song
def cache(track_name):
    memcache.set(TRACK_KEY, track_name)

# timezone class for MST
# for some reason it isn't working and we are
# still getting UTC time
class MST(datetime.tzinfo):
    def utcoffset(self, dt):
    	return datetime.timedelta(hours=-6)

    def dst(self, dt):
        return datetime.timedelta(0)

def transform_time(dt, tz):
	return dt.replace(tzinfo = tz)


# app engine datastore class
# basically like a SQL table
class Input(db.Model):
	user_input = db.StringProperty(required = True)
	event = db.StringProperty()
	created = db.DateTimeProperty(auto_now_add = True)

	# this function is called in dataview.html for each entry
	def render_input(self):
		self._render_text = self.user_input.replace('\n', '<br>')
		co_time = MST()
		t = transform_time(self.created, co_time)
		return render_str("input_view.html", time = t, content = self.user_input)

# used to track number of hits our page gets
class Tracking(db.Model):
	hits = db.IntegerProperty()
	name = db.StringProperty()

"""
class Song(db.Model):
    name = db.StringProperty()
    artist = db.StringProperty()
    genre = db.StringProperty()
    played = db.TextProperty() # comma separated timestamps
    plays = db.IntegerProperty()
    requests = db.TextProperty() # comma separated timestamps
"""


# A parent class for all handlers with some useful methods
# just call self.render( <template name>, <arguments> ) to
# render a page from any handler
class MainHandler(webapp2.RequestHandler):
	def render(self, template, **kw):
		self.response.out.write(render_str(template, **kw))

# class for the user input form
class FormHandler(MainHandler):
    def get(self):
        track = memcache.get(TRACK_KEY)
        if track and track != "":
            now_playing = "Now Playing: %s" % track
            self.render("buttons.html", now_playing = now_playing)
        else:
            self.render("buttons.html")

        cursor = db.GqlQuery("SELECT * FROM Tracking WHERE key_name = 'hits_at_tylers'")
        if not cursor.get():
        	a = Tracking(key_name='hits_at_tylers', hits=1)
        	a.put()

        else:
        	myKey = db.Key.from_path('Tracking', 'hits_at_tylers')
        	rec = db.get(myKey)
        	if rec:
        		rec.hits += 1
        		rec.put()

    def post(self):
    	user_input = self.request.get("user_input")
        button = self.request.get("button_pressed")
        track = memcache.get(TRACK_KEY)

        if track and track != "":
            now_playing = "Now Playing: %s" % track
        else:
            now_playing = None
            #"<span class=\"track\">Now Playing: %s</span><br>" % track

        if button:
            a = Input(user_input = button, event = EVENT)
            a.put()
            if button == "more chill":
                message = "Chill music coming up!"
            if button == "more bangin":
                message = "Bangin music coming up!"
            if button == "louder":
                message = "We\'ll turn it up"
            if button == "softer":
                message = "Softer music on the way"
            if button == "skip":
                message = "Skipping track..."

        elif user_input != "":
        	a = Input(user_input = user_input, event = EVENT)
        	a.put()
    		message = "Got it! We'll get that playing next"

        else:
            message = ""

        if now_playing:
            self.render("buttons.html", message = message, now_playing = now_playing)
        else:
            self.render("buttons.html", message = message)

class VoteHandler(MainHandler):
    def get(self):
        songs = memcache.get(VOTE)
        if not songs:
            songs = [["Thrift Shop - Macklemore", 0],
                     ["Thriller - Michael Jackson", 0],
                     ["Mirrors - Justin Timberlake", 0]]
            memcache.set(VOTE, songs)
        self.render('vote.html', songs = songs)

    def post(self):
        vote = self.request.get('vote')
        from_queue = self.request.get('from_queue')
        songs = memcache.get(VOTE)
        for song in songs:
            if song[0] == vote:
                song[1] += 1
                break
        memcache.set(VOTE, songs)
        if from_queue:
            self.redirect('/queue')
        else:
            self.redirect('/thanks')

class ThanksHandler(MainHandler):
    def get(self):
        songs = memcache.get(VOTE)
        self.render('thanks.html', songs = songs)

class QueueHandler(MainHandler):
    def get(self):
        queue = memcache.get(QUEUE)
        vote_songs = memcache.get(VOTE)
        if not queue:
            queue = ["Thrift Shop - Macklemore",
                     "Thriller - Michael Jackson",
                     "Mirrors - Justin Timberlake"]
            memcache.set(QUEUE, queue)
        if not vote_songs:
            vote_songs = []
        self.render('queue.html', songs = queue, vote_songs = vote_songs)

    def post(self):
        queue = memcache.get(QUEUE)
        vote_songs = memcache.get(VOTE)
        if not queue:
            queue = []
        if not vote_songs:
            vote_songs = []
        remove = self.request.get('remove')
        if remove:
            queue.remove(remove)
            memcache.set(QUEUE, queue)
            self.render('queue.html', songs = queue, vote_songs = vote_songs)



        name = self.request.get('name')
        artist = self.request.get('artist')
        genre = self.request.get('genre')
        position = self.request.get('position')
        if position.isdigit():
            position = int(position) + 1
        else:
            position = 0

        if name:
            #n = Song(name = name, artist = artist, genre = genre)
            #n.put()
            if artist:
                song = [name, artist]
                queue.insert(position, ' - '.join(song))
            else:
                queue.insert(position, name)
            memcache.set(QUEUE, queue)
            self.render('queue.html', songs = queue, vote_songs = vote_songs)

class NextHandler(MainHandler):
    def post(self):
        songs = memcache.get(QUEUE)
        songs = songs[:3]
        vote = [[song, 0] for song in songs]
        memcache.set(VOTE, vote)
        self.redirect('/queue')


# class for us to view the data
class DataViewHandler(MainHandler):
    def get(self):
        content = db.GqlQuery("SELECT * FROM Input WHERE event ='" + EVENT + "' ORDER BY created DESC")    
        track = self.request.get("song")
        if track == "":
            memcache.set(TRACK_KEY, "")
        elif track:
            memcache.set(TRACK_KEY, track)

        now_playing = memcache.get(TRACK_KEY)
        if now_playing:
            self.render("dataview.html", content = content, track = now_playing)
        else:
            self.render("dataview.html", content = content)


# add new pages here
app = webapp2.WSGIApplication([
    ('/', VoteHandler),
    ('/dataview', DataViewHandler),
    ('/vote', VoteHandler),
    ('/queue', QueueHandler),
    ('/thanks', ThanksHandler),
    ('/next', NextHandler)
], debug=True)