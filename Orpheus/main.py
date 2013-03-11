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

from google.appengine.ext import db

# set up a directory for jinja html templates
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)

# use this to change our event in case we want to test
# at different events and sort our data
EVENT = "test"

def escape_html(s):
	s = s.replace("&", "&amp;")
	return cgi.escape(s, quote = True)

# shortcut function for rendering jinja templates
def render_str(template, **params):
	t = jinja_env.get_template(template)
	return t.render(params)

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


# A parent class for all handlers with some useful methods
# just call self.render( <template name>, <arguments> ) to
# render a page from any handler
class MainHandler(webapp2.RequestHandler):
	def render(self, template, **kw):
		self.response.out.write(render_str(template, **kw))

# class for the user input form
class FormHandler(MainHandler):
    def get(self):
        self.render("input.html")

    def post(self):
    	user_input = self.request.get("user_input")
    	if user_input != "":
    		a = Input(user_input = user_input, event = EVENT)
    		a.put()
    		message = "Thanks for your submission, we hope you enjoy the music!"
    		self.render("input.html", message = message)

# class for us to view the data
class DataViewHandler(MainHandler):
	def get(self):
		content = db.GqlQuery("SELECT * FROM Input WHERE event ='" + EVENT + "' ORDER BY created DESC LIMIT 10")
		self.render("dataview.html", content = content)


# add new pages here
app = webapp2.WSGIApplication([
    ('/', FormHandler),
    ('/dataview', DataViewHandler)
], debug=True)
