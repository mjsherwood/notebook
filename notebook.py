import cgi
import urllib

from google.appengine.api import users
from google.appengine.ext import ndb

import webapp2

MAIN_PAGE_FOOTER_TEMPLATE = """\
    <form action="/sign?%s" method="post">
      <div><textarea name="content" rows="3" cols="60"></textarea></div>
      <div><input type="submit" value="Leave Note"></div>
    </form>
    <hr>
    <form>Notebook name:
      <input value="%s" name="notebook_name">
      <input type="submit" value="switch">
    </form>
    <a href="%s">%s</a>
  </body>
</html>
"""

DEFAULT_NOTEBOOK_NAME = 'intro_notes'

# We set a parent key on the 'Greetings' to ensure that they are all
# in the same entity group. Queries across the single entity group
# will be consistent.  However, the write rate should be limited to
# ~1/second.

def notebook_key(notebook_name=DEFAULT_NOTEBOOK_NAME):
    """Constructs a Datastore key for a Notebook entity.

    We use notebook_name as the key.
    """
    return ndb.Key('Notebook', notebook_name)


class Author(ndb.Model):
    """Sub model for representing an author."""
    identity = ndb.StringProperty(indexed=False)
    email = ndb.StringProperty(indexed=False)


class Greeting(ndb.Model):
    """A main model for representing an individual Notebook entry."""
    author = ndb.StructuredProperty(Author)
    content = ndb.StringProperty(indexed=False)
    date = ndb.DateTimeProperty(auto_now_add=True)


class MainPage(webapp2.RequestHandler):
    def get(self):
        self.response.write('<html><body>')
        notebook_name = self.request.get('notebook_name',
                                          DEFAULT_NOTEBOOK_NAME)

        # Ancestor Queries, as shown here, are strongly consistent
        # with the High Replication Datastore. Queries that span
        # entity groups are eventually consistent. If we omitted the
        # ancestor from this query there would be a slight chance that
        # Greeting that had just been written would not show up in a
        # query.
        greetings_query = Greeting.query(
            ancestor=notebook_key(notebook_name)).order(-Greeting.date)
        greetings = greetings_query.fetch(10)

        user = users.get_current_user()
        for greeting in greetings:
            if greeting.author:
                author = greeting.author.email
                if user and user.user_id() == greeting.author.identity:
                    author += ' (You)'
                self.response.write('<b>%s</b> wrote:' % author)
            else:
                self.response.write('An anonymous person wrote:')
            self.response.write('<blockquote>%s</blockquote>' %
                                cgi.escape(greeting.content))

        if user:
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'

        # Write the submission form and the footer of the page
        sign_query_params = urllib.urlencode({'notebook_name':
                                              notebook_name})
        self.response.write(MAIN_PAGE_FOOTER_TEMPLATE %
                            (sign_query_params, cgi.escape(notebook_name),
                             url, url_linktext))

class Notebook(webapp2.RequestHandler):
    def post(self):
        # We set the same parent key on the 'Greeting' to ensure each
        # Greeting is in the same entity group. Queries across the
        # single entity group will be consistent. However, the write
        # rate to a single entity group should be limited to
        # ~1/second.
        notebook_name = self.request.get('notebook_name',
                                          DEFAULT_NOTEBOOK_NAME)
        greeting = Greeting(parent=notebook_key(notebook_name))

        if users.get_current_user():
            greeting.author = Author(
                    identity=users.get_current_user().user_id(),
                    email=users.get_current_user().email())

        greeting.content = self.request.get('content')
        greeting.put()

        query_params = {'notebook_name': notebook_name}
        self.redirect('/?' + urllib.urlencode(query_params))

app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/sign', Notebook),
], debug=True)
