#!/usr/bin/env python

import datetime
import json
import logging
import urllib
import urllib2
import webapp2

import credentials

class SinkHandler(webapp2.RequestHandler):
    def _set_cookie(self, key, value, days_expires=None):
        kwargs = {
            "domain": self.request.host,
            "httponly": True,
            "secure": self.request.scheme == "https",
        }
        if "localhost" in kwargs["domain"]:
            del kwargs["domain"]
        if days_expires:
            kwargs["expires"] = datetime.datetime.now() + datetime.timedelta(
                days_expires)
        self.response.set_cookie(key, value, **kwargs)

    def _all_tokens(self):
        token = self.request.cookies.get("token")
        if not token:
            raise NeedAuthException(self.request.url)
        return json.loads(token)

    def _token(self):
        return self._all_tokens()["access_token"]

    def _fetch(self, url, data=None):
        headers = {"Authorization": "Bearer %s" % self._token()}
        req = urllib2.Request(url, data, headers)
        return urllib2.urlopen(req).read()

    def _endpoints(self):
        endpoints = self.request.cookies.get("endpoints")
        if not endpoints or True:
            # TODO: record fetched time
            endpoints = self._fetch(
                "https://drive.amazonaws.com/drive/v1/account/endpoint")
            self._set_cookie("endpoints", endpoints, 5)
        return json.loads(endpoints)

    def _metadata(self):
        return self._endpoints()["metadataUrl"]

    def _content(self):
        return self._endpoints()["contentUrl"]

    def handle_exception(self, exception, debug):
        if isinstance(exception, NeedAuthException):
            # TODO: redirect back to exception.url afterwards
            self.redirect("/auth")
        else:
            super(SinkHandler, self).handle_exception(exception, debug)


class NeedAuthException(Exception):
    def __init__(self, url):
        self.url = url


class MainHandler(SinkHandler):
    def get(self):
        self.response.write('Want to <a href="/auth">auth</a>?')


class AuthHandler(SinkHandler):
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
        self._set_cookie("token", response, 365)
        self.response.write(json.loads(response))


class RefreshHandler(SinkHandler):
    def post(self):
        refresh_token = self.request.get("refresh_token")
        data = urllib.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": credentials.CLIENT_ID,
            "client_secret": credentials.SECRET,
        })
        req = urllib2.Request("https://api.amazon.com/auth/o2/token", data)
        response = urllib2.urlopen(req).read()
        self._set_cookie("token", response, 365)
        self.response.write(response)


class NodesHandler(SinkHandler):
    def get(self):
        nodes = self._fetch("%s/nodes?filters=kind:FILE" % self._metadata())
        self.response.write(nodes)


class ConfigHandler(SinkHandler):
    def get(self):
        token = self._all_tokens()
        token.update(self._endpoints())
        self.response.write(
            "<pre>\n%s\n</pre>" % json.dumps(token, sort_keys=True, indent=4))


app = webapp2.WSGIApplication([
    ('/', MainHandler),
    ('/config', ConfigHandler),
    ('/auth', AuthHandler),
    ('/refresh', RefreshHandler),
    ('/nodes', NodesHandler),
], debug=True)
