#!/usr/bin/env python

import base64
import datetime
import hashlib
import json
import logging
import urllib
import urllib2
import urlparse
import webapp2

from google.appengine.api import memcache
from webapp2_extras import jinja2

import credentials

class SinkHandler(webapp2.RequestHandler):
    @webapp2.cached_property
    def _jinja2(self):
        return jinja2.get_jinja2(app=self.app)

    def _render_template(self, filename, **template_args):
        self.response.write(self._jinja2.render_template(
            filename, **template_args))

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
        if not hasattr(self, "_access_token"):
            self._access_token = self._all_tokens()["access_token"]
        return self._access_token

    def _fetch(self, url, data=None, refresh=True):
        try:
            headers = {"Authorization": "Bearer %s" % self._token()}
            if data:
                data = json.dumps(data)
            req = urllib2.Request(url, data, headers)
            return urllib2.urlopen(req).read()
        except urllib2.HTTPError, e:
            if e.code == 401 and refresh:
                self._refresh(self._all_tokens()["refresh_token"])
                return self._fetch(url, data, refresh=False)
            else:
                logging.error(e.read())
                raise

    def _refresh(self, token):
        data = urllib.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": token,
            "client_id": credentials.CLIENT_ID,
            "client_secret": credentials.SECRET,
        })
        req = urllib2.Request("https://api.amazon.com/auth/o2/token", data)
        response = urllib2.urlopen(req).read()
        self._set_cookie("token", response, 365)
        self._access_token = json.loads(response)["access_token"]

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
            self.redirect("/auth?next=%s" % exception.url)
        else:
            super(SinkHandler, self).handle_exception(exception, debug)


class NeedAuthException(Exception):
    def __init__(self, url):
        self.url = url


class MainHandler(SinkHandler):
    def get(self):
        self._render_template("index.html")


class AuthHandler(SinkHandler):
    def get(self):
        code = self.request.get("code")
        if not code:
            # Need spaces to be encoded as %20 so can't use urllib.urlencode
            url = "https://www.amazon.com/ap/oa?%s" % "&".join(
                ["=".join((urllib.quote(k), urllib.quote(v))) for k,v in{
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
        self.redirect(self.request.get("next", "/config"))


class RefreshHandler(SinkHandler):
    def post(self):
        refresh_token = self.request.get("refresh_token")
        self.response.write(self._refresh(refresh_token))


class NodesHandler(SinkHandler):
    def get(self):
        logging.error("%s/nodes%s" % (self._metadata(), self.request.query_string))
        nodes = self._fetch(
            "%snodes?%s" % (self._metadata(), self.request.query_string))
        self.response.write("<pre>%s</pre>" % json.dumps(
            json.loads(nodes), sort_keys=True, indent=4))


class ConfigHandler(SinkHandler):
    def get(self):
        if self.request.get("c"):
            config = memcache.get("code:%s" % self.request.get("c"))
            self.response.write(config)
            return
        token = self._all_tokens()
        token.update(self._endpoints())
        config = json.dumps(token, sort_keys=True, indent=4)
        code = base64.b64encode(hashlib.sha256(config).digest(), "cm")[:30]
        memcache.set("code:%s" % code, config, time=900)
        self._render_template("config.html", config=config,
                              code="%s?c=%s" % (self.request.url, code))


class UsageHandler(SinkHandler):
    def get(self):
        usage = self._fetch("%saccount/usage" % self._metadata())
        self.response.write("<pre>%s</pre>" % json.dumps(
            json.loads(usage), sort_keys=True, indent=4))


app = webapp2.WSGIApplication([
    ("/", MainHandler),
    ("/config", ConfigHandler),
    ("/auth", AuthHandler),
    ("/refresh", RefreshHandler),
    ("/nodes", NodesHandler),
    ("/usage", UsageHandler),
], debug=True)
