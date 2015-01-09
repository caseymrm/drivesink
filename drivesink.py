#!/usr/bin/env python

import argparse
import os

def main():
    parser = argparse.ArgumentParser(
        description='Amazon Cloud Drive synchronization tool')
    parser.add_argument('command', help='Commands: "sync"')
    parser.add_argument('source', help='The source directory')
    parser.add_argument('destination', help='The destination directory')
    parser.add_argument('-c', '--config', help='The config file')

    args = parser.parse_args()

    if args.command != "sync":
        parser.print_help()
        exit(1)

    config_file = args.config or os.environ.get("DRIVESINK", None)
    if not config_file:
        from os.path import expanduser
        config_file = os.path.join(expanduser("~"), ".drivesink")

    try:
        config = open(config_file, "r")
    except:
        print "Go to https://cloudsink.appspot.com/config to get your tokens"
        exit(1)


if __name__ == "__main__":
    main()
