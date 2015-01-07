#!/usr/bin/env python

import datetime
import json
import logging
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
                    "redirect_uri": self.request.host_url + "/auth",
                }.iteritems()])
            self.redirect(url)
            return
        data = urllib.urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "client_id": credentials.CLIENT_ID,
            "client_secret": credentials.SECRET,
            "redirect_uri": self.request.host_url + "/auth",
        })
        req = urllib2.Request("https://api.amazon.com/auth/o2/token", data)
        response = urllib2.urlopen(req).read()
        domain = self.request.host
        if "localhost" in domain:
            domain = None
        self.response.set_cookie(
            "token", response, domain=domain, httponly=True,
            secure=self.request.scheme=="https")
        self.response.write(json.loads(response))

class NodesHandler(webapp2.RequestHandler):
    def get(self):
        token = json.loads(self.request.cookies.get("token"))
        headers = {"Authorization": "Bearer %s" % token["access_token"]}

        req = urllib2.Request(
            "https://drive.amazonaws.com/drive/v1/account/endpoint",
            None,
            headers)
        response = urllib2.urlopen(req).read()
        self.response.write(response)

app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/auth', AuthHandler),
    ('/nodes', NodesHandler),
], debug=True)
