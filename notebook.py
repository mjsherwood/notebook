import os
import urllib
import urllib2
from xml.dom import minidom

from google.appengine.api import users
from google.appengine.ext import ndb

import jinja2
import webapp2


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

DEFAULT_NOTEBOOK_NAME = 'intro_notes'

# We set a parent key on the 'Notes' to ensure that they are all
# in the same entity group. Queries across the single entity group
# will be consistent.  However, the write rate should be limited to
# ~1/second.

def notebook_key(notebook_name=DEFAULT_NOTEBOOK_NAME):
    """Constructs a Datastore key for a Notebook entity.

    We use notebook_name as the key.
    """
    return ndb.Key('Notebook', notebook_name)


GMAPS_URL = "http://maps.googleapis.com/maps/api/staticmap?size=380x263&sensor=false&"
def gmaps_img(points):
    markers = '&'.join('markers=%s,%s' % (p.lat, p.lon) for p in points)
    return GMAPS_URL + markers

IP_URL = "http://api.hostip.info/?ip="
def get_coords(ip):
    url = IP_URL + "4.4.2.2"
    content = None
    content = urllib2.urlopen(url).read()
    try:
        content = urllib2.urlopen(url).read()
    except urllib2.URLError:
        return

    if content:
        #parse the xml and find the coordinates
        d = minidom.parseString(content)
        coords = d.getElementsByTagName("gml:coordinates")
        if coords and coords[0].childNodes[0].nodeValue:
            lon, lat = coords[0].childNodes[0].nodeValue.split(',')
            return ndb.GeoPt(lat, lon)



class Author(ndb.Model):
    """Sub model for representing an author."""
    identity = ndb.StringProperty(indexed=False)
    email = ndb.StringProperty(indexed=False)


class Note(ndb.Model):
#This is where we define the variables we want to input into the database
    """A main model for representing an individual Notebook entry."""
    author = ndb.StructuredProperty(Author)
    unit = ndb.StringProperty(indexed=True)
    title = ndb.StringProperty(indexed=False)
    description = ndb.StringProperty(indexed=False)
    date = ndb.DateTimeProperty(auto_now_add=True)
    coords = ndb.GeoPtProperty()


class MainPage(webapp2.RequestHandler):
#This is the class for the homepage. it retrieves the data to be rendered
    def get(self):
        notebook_name = self.request.get('notebook_name',
                                          DEFAULT_NOTEBOOK_NAME)
        #This is the number of notes that will be shown on the notebook.
        number_of_notes = 30
        notes_query = Note.query(
            ancestor=notebook_key(notebook_name)).order(Note.unit)
        notes = notes_query.fetch(number_of_notes)
        #Get user info of the person who entered the note if logged in.
        user = users.get_current_user()
        if user:
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'

        #Find which notes have coordinates.
        points = filter(None, (note.coords for note in notes))

        #If we have any note coordinatess, makes an image url
        img_url = None
        if points:
            img_url = gmaps_img(points)

        template_values = {
            'user': user,
            'notes': notes,
            'notebook_name': urllib.quote_plus(notebook_name),
            'url': url,
            'url_linktext': url_linktext,
            'img_url': img_url,
        }

        template = JINJA_ENVIRONMENT.get_template('home.html')
        self.response.write(template.render(template_values))

class Notebook(webapp2.RequestHandler):
#Here we are sending all the data from our form to the database.
    def post(self):
        # We set the same parent key on the 'Note' to ensure each
        # Note is in the same entity group. Queries across the
        # single entity group will be consistent. However, the write
        # rate to a single entity group should be limited to
        # ~1/second.
        notebook_name = self.request.get('notebook_name',
                                          DEFAULT_NOTEBOOK_NAME)
        note = Note(parent=notebook_key(notebook_name))

        if users.get_current_user():
            note.author = Author(
                    identity=users.get_current_user().user_id(),
                    email=users.get_current_user().email())

        note.description = self.request.get('description').strip()
        note.title = self.request.get('title').strip()
        note.unit = self.request.get('unit').strip()
        query_params = {'notebook_name': notebook_name}

        if not(note.unit and note.title and note.description):
            self.redirect('/error')
        else:
            note.coords = get_coords(self.request.remote_addr)

            note.put()
            self.redirect('/?' + urllib.urlencode(query_params))


class Error(webapp2.RequestHandler):
#We use this class to define our error page for
#incorrectly entered or missing data
    def get(self):
        template = JINJA_ENVIRONMENT.get_template('error.html')
        template_values = {}
        self.response.write(template.render(template_values))

app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/sign', Notebook),
    ('/error', Error),
], debug=True)
