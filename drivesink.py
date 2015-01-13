#!/usr/bin/env python

import argparse
import json
import logging
import os
import urllib
import urllib2


class DriveSink(object):
    def __init__(self, args):
        self.args = args
        self.config = None
        self.drivesink = args.drivesink

    def get_local_files(self, path):
        # TODO: symlinks, handle trailing slash
        local_files = {}
        for dirpath, dirnames, filenames in os.walk(path):
            relative = dirpath[len(path):]
            for filename in filenames:
                local_path = os.path.join(dirpath, filename)
                local_files["%s/%s" % (relative, filename)] = {
                    "path": local_path,
                    "size": os.path.getsize(local_path),
                }
        return local_files

    def get_remote_files(self, path):
        remote_files = {}
        # TODO: handle trailing slash, endpoint refresh
        folder_nodes = json.loads(self._fetch(
            "%s/nodes?filters=kind:FOLDER" % self._config()["metadataUrl"]))
        # TODO: fetch just the ones that start with the path
        for node in folder_nodes["data"]:
            logging.error(node)

    def _config_file(self):
        config_filename = self.args.config or os.environ.get(
            "DRIVESINK", None)
        if not config_filename:
            from os.path import expanduser
            config_filename = os.path.join(expanduser("~"), ".drivesink")
        return config_filename

    def _config(self):
        if not self.config:
            config_filename = self._config_file()
            try:
                self.config = json.loads(open(config_filename, "r").read())
            except:
                print "%s/config to get your tokens" % self.drivesink
                exit(1)
        return self.config

    def _fetch(self, url, data=None):
        # TODO: refresh token
        try:
            headers = {
                "Authorization": "Bearer %s" % self._config()["access_token"],
            }
            req = urllib2.Request(url, data, headers)
            return urllib2.urlopen(req).read()
        except urllib2.HTTPError, e:
            if e.code == 401:
                # Have to proxy to get the client id and secret
                data = urllib.urlencode({
                    "refresh_token": self._config()["refresh_token"],
                })
                req = urllib2.Request("%s/refresh" % self.drivesink, data)
                new_config = json.loads(urllib2.urlopen(req).read())
                self.config.update(new_config)
                with open(self._config_file(), 'w') as f:
                    f.write(json.dumps(self.config, sort_keys=True, indent=4))
                return self._fetch(url, data)
            else:
                print e.read()
                raise

def main():
    parser = argparse.ArgumentParser(
        description='Amazon Cloud Drive synchronization tool')
    parser.add_argument('command', help='Commands: "sync"')
    parser.add_argument('source', help='The source directory')
    parser.add_argument('destination', help='The destination directory')
    parser.add_argument('-c', '--config', help='The config file')
    parser.add_argument('-d', '--drivesink', help='Drivesink URL',
                        # TODO: https://cloudsink.appspot.com
                        default='http://localhost:14080')

    args = parser.parse_args()

    if args.command != "sync":
        parser.print_help()
        exit(1)

    drivesink = DriveSink(args)
    local_files = drivesink.get_local_files(args.source)
    remote_files = drivesink.get_remote_files(args.destination)
    logging.error(local_files)
    logging.error(remote_files)


if __name__ == "__main__":
    main()
