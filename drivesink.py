#!/usr/bin/env python

import argparse
import hashlib
import json
import logging
import os
import requests
import requests_toolbelt
import uuid


class CloudNode(object):
    def __init__(self, node):
        self.node = node
        self._children_fetched = False

    def children(self):
        if not self._children_fetched:
            nodes = DriveSink.instance().request_metadata(
                "%%snodes/%s/children" % self.node["id"])
            self._children = {n["name"]: CloudNode(n) for n in nodes["data"]}
            self._children_fetched = True
        return self._children

    def child(self, name, create=False):
        node = self.children().get(name)
        if not node and create:
            node = self._make_child_folder(name)
        return node

    def upload_child_file(self, name, local_path, existing_node=None):
        logging.info("Uploading %s in %r", local_path, self.node["name"])
        m = requests_toolbelt.MultipartEncoder([
            ("metadata", json.dumps({
                "name": name,
                "kind": "FILE",
                "parents": [self.node["id"]],
            })),
            ("content", (name, open(local_path, 'rb')))])
        if existing_node:
            """
            # TODO: this is under-documented and currently 500s on Amazon's side
            node = CloudNode(DriveSink.instance().request_content(
                "%%snodes/%s/content" % existing_node.node["id"],
                method="put", data=m, headers={'Content-Type': m.content_type}))
            """
            old_info = DriveSink.instance().request_metadata(
                "%%s/trash/%s" % existing_node.node["id"], method="put")
        node = CloudNode(DriveSink.instance().request_content(
            "%snodes", method="post", data=m,
            headers={'Content-Type': m.content_type}))
        self._children[name] = node

    def _make_child_folder(self, name):
        logging.info(
            "Creating remote folder %s in %s", name, self.node["name"])
        node = CloudNode(
            DriveSink.instance().request_metadata("%snodes", {
                "kind": "FOLDER",
                "name": name,
                "parents": [self.node["id"]]}))
        self._children[name] = node
        return node


class DriveSink(object):
    def __init__(self, args):
        if not args:
            logging.error("Never initialized")
            exit(1)
        self.args = args
        self.config = None

    @classmethod
    def instance(cls, args=None):
        if not hasattr(cls, "_instance"):
            cls._instance = cls(args)
        return cls._instance

    def sync(self, source, destination):
        remote_node = self.node_at_path(
            self.get_root(), destination, create_missing=True)
        for dirpath, dirnames, filenames in os.walk(source):
            relative = dirpath[len(source):]
            current_dir = self.node_at_path(
                remote_node, relative, create_missing=True)
            if not current_dir:
                logging.error("Could not create missing node")
                exit(1)
            for dirname in dirnames:
                current_dir.child(dirname, create=True)
            for filename in filenames:
                local_path = os.path.join(dirpath, filename)
                node = current_dir.child(filename)
                if (not node or node.node["contentProperties"]["size"]
                    != os.path.getsize(local_path) or
                    node.node["contentProperties"]["md5"] !=
                    self.md5sum(local_path)) and self.filter_file(filename):
                    current_dir.upload_child_file(filename, local_path, node)

    def filter_file(self, filename):
        extension = filename.split(".")[-1]
        allowed = self.args.extensions
        if not allowed:
            # Not all tested to be free
            allowed = (
                'apng,arw,bmp,cr2,crw,dng,emf,gif,jfif,jpe,jpeg,jpg,mef,nef,' +
                'orf,pcx,png,psd,raf,ras,srw,swf,tga,tif,tiff,wmf')
        return extension in allowed.split(",")

    def get_root(self):
        nodes = self.request_metadata("%snodes?filters=isRoot:True")
        if nodes["count"] != 1:
            logging.error("Could not find root")
            exit(1)
        return CloudNode(nodes["data"][0])

    def node_at_path(self, root, path, create_missing=False):
        parts = filter(None, path.split("/"))
        node = root
        while len(parts):
            node = node.child(parts.pop(0), create=create_missing)
            if not node:
                return None
        return node

    def _config_file(self):
        config_filename = self.args.config or os.environ.get(
            "DRIVESINK", None)
        if not config_filename:
            config_filename = os.path.join(
                os.path.expanduser("~"), ".drivesink")
        return config_filename

    def _config(self):
        if not self.config:
            config_filename = self._config_file()
            try:
                self.config = json.loads(open(config_filename, "r").read())
            except:
                print "%s/config to get your tokens" % self.args.drivesink
                exit(1)
        return self.config

    def request_metadata(self, path, json_data=None, **kwargs):
        args = {}
        if json_data:
            args["method"] = "post"
            args["data"] = json.dumps(json_data)
        else:
            args["method"] = "get"

        args.update(kwargs)

        return self._request(
            path % self._config()["metadataUrl"], **args)

    def request_content(self, path, **kwargs):
        return self._request(
            path % self._config()["contentUrl"], **kwargs)

    def _request(self, url, refresh=True, **kwargs):
        headers = {
            "Authorization": "Bearer %s" % self._config()["access_token"],
        }
        headers.update(kwargs.pop("headers", {}))
        req = requests.request(url=url, headers=headers, **kwargs)
        if req.status_code == 401 and refresh:
            # Have to proxy to get the client id and secret
            req = requests.post("%s/refresh" % self.args.drivesink, data={
                "refresh_token": self._config()["refresh_token"],
            })
            req.raise_for_status()
            new_config = req.json()
            self.config.update(new_config)
            with open(self._config_file(), 'w') as f:
                f.write(json.dumps(self.config, sort_keys=True, indent=4))
            return self._request(url, refresh=False, **kwargs)
        req.raise_for_status()
        return req.json()

    def md5sum(self, filename, blocksize=65536):
        md5 = hashlib.md5()
        with open(filename, "r+b") as f:
            for block in iter(lambda: f.read(blocksize), ""):
                md5.update(block)
        return md5.hexdigest()


def main():
    parser = argparse.ArgumentParser(
        description='Amazon Cloud Drive synchronization tool')
    parser.add_argument('command', help='Commands: "sync"')
    parser.add_argument('source', help='The source directory')
    parser.add_argument('destination', help='The destination directory')
    parser.add_argument('-e', '--extensions',
                        help='File extensions to upload, images by default')
    parser.add_argument('-c', '--config', help='The config file')
    parser.add_argument('-d', '--drivesink', help='Drivesink URL',
                        # TODO: https://cloudsink.appspot.com
                        default='http://localhost:14080')

    args = parser.parse_args()

    if args.command != "sync":
        parser.print_help()
        exit(1)

    drivesink = DriveSink.instance(args)

    drivesink.sync(args.source, args.destination)

logging.basicConfig(
    format = "%(levelname) -10s %(module)s:%(lineno)s %(funcName)s %(message)s",
    level = logging.DEBUG
)
logging.getLogger("requests").setLevel(logging.WARNING)

if __name__ == "__main__":
    main()
