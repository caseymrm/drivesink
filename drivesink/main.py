#!/usr/bin/env python

import json
import urllib
import urllib2
import webapp2

import credentials

class MainHandler(webapp2.RequestHandler):
    def get(self):
        self.response.write('Ready to <a href="/auth">auth</a>?')

class AuthHandler(webapp2.RequestHandler):
    def get(self):
        code = self.request.get("code")
        if not code:
            # Need spaces to be encoded as %20 so can't use urllib.urlencode
            url = "https://www.amazon.com/ap/oa?%s" % '&'.join(
                ['='.join((urllib.quote(k), urllib.quote(v))) for k,v in{
                    "client_id": credentials.CLIENT_ID,
                    "scope": "clouddrive:read clouddrive:write",
                    "response_type": "code",
                    "redirect_uri": "http://localhost:14080/auth",
                }.iteritems()])
            self.redirect(url)
            return
        data = urllib.urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "client_id": credentials.CLIENT_ID,
            "client_secret": credentials.SECRET,
            "redirect_uri": "http://localhost:14080/auth",
        })
        req = urllib2.Request("https://api.amazon.com/auth/o2/token", data)
        response = json.loads(urllib2.urlopen(req).read())
        self.response.write(response)

app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/auth', AuthHandler),
], debug=True)
