#!/usr/bin/env python

import argparse
import json
import logging
import os
import urllib
import urllib2
import uuid


class DriveSink(object):
    def __init__(self, args):
        self.args = args
        self.config = None
        self.drivesink = args.drivesink

    def get_local_files(self, path):
        # TODO: symlinks, handle trailing slash
        local_files = {
            "kind": "FOLDER",
            "children": {},
        }
        for dirpath, dirnames, filenames in os.walk(path):
            relative = dirpath[len(path):]
            current_dir = local_files
            for dirname in relative.split("/"):
                if dirname:
                    current_dir = current_dir["children"][dirname]
            for dirname in dirnames:
                current_dir["children"][dirname] = {
                    "kind": "FOLDER",
                    "children": {},
                }
            for filename in filenames:
                local_path = os.path.join(dirpath, filename)
                current_dir["children"][filename] = {
                    "kind": "FILE",
                    "path": local_path,
                    "size": os.path.getsize(local_path),
                }
        return local_files

    def get_remote_files(self, path, create_missing=False):
        # TODO: handle trailing slash, endpoint refresh
        folder_nodes = self._fetch(
            "%s/nodes?filters=kind:FOLDER" % self._config()["metadataUrl"])
        # TODO: fetch just the ones that start with the path
        root = None
        children = {}
        for node in folder_nodes["data"]:
            if node.get("isRoot", False):
                root = node
            for parent in node["parents"]:
                children.setdefault(parent, []).append(node)
        parts = filter(None, path.split("/"))
        node = root
        while len(parts):
            for child in children.get(node["id"], []):
                if child["name"].lower() == parts[0].lower():
                    node = child
                    parts.pop(0)
                    break
            else:
                break
        # create a folder for each item left in parts, starting at node
        if create_missing:
            for part in parts:
                node = self._fetch("%s/nodes" % self._config()["metadataUrl"],
                                   {
                                       "kind": "FOLDER",
                                       "name": part,
                                       "parents": [node["id"]],
                                   })
        elif parts:
            return None
        remote_files = {
            "node": node,
            "children": {}
        }
        child_nodes = self._fetch("%s/nodes/%s/children" % (
            self._config()["metadataUrl"], node["id"]))
        for child in child_nodes["data"]:
            logging.info(child)
        return remote_files

    def upload_node(self, local_node, remote_node):
        if local_node["kind"] == "FILE":
            # TODO: handle single file case
            pass
        elif local_node["kind"] == "FOLDER":
            for local_file, local_info in local_node["children"].iteritems():
                if local_file not in remote_node["children"]:
                    logging.info("upload %r %r", local_file, local_info)

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

    def _fetch(self, url, data=None, refresh=True):
        try:
            headers = {
                "Authorization": "Bearer %s" % self._config()["access_token"],
            }
            if data:
                req_data = json.dumps(data)
            else:
                req_data = None
            req = urllib2.Request(url, req_data, headers)
            return json.loads(urllib2.urlopen(req).read())
        except urllib2.HTTPError, e:
            if e.code == 401 and refresh:
                # Have to proxy to get the client id and secret
                data = urllib.urlencode({
                    "refresh_token": self._config()["refresh_token"],
                })
                req = urllib2.Request("%s/refresh" % self.drivesink, data)
                new_config = json.loads(urllib2.urlopen(req).read())
                self.config.update(new_config)
                with open(self._config_file(), 'w') as f:
                    f.write(json.dumps(self.config, sort_keys=True, indent=4))
                return self._fetch(url, data, refresh=False)
            else:
                logging.error(e.read())
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
    remote_files = drivesink.get_remote_files(args.destination, True)
    logging.info(local_files)
    logging.info(remote_files)
    drivesink.upload_node(local_files, remote_files)

logging.basicConfig(
    format = "%(levelname) -10s %(module)s:%(lineno)s %(funcName)s %(message)s",
    level = logging.DEBUG
)

if __name__ == "__main__":
    main()
