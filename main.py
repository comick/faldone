#!/usr/bin/env python3
import argparse
import os.path
import sys
from pathlib import Path

from faldone import Faldone

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--faldone', help='Non-default faldone location')
    subparsers = parser.add_subparsers(metavar='command', dest='command')

    put_parser = subparsers.add_parser('put', help='Put documents into faldone')
    put_parser.add_argument('document', help='Path to a document', type=argparse.FileType('rb'))
    put_parser.add_argument('-t', '--title', help='Document title')
    put_parser.add_argument('-l', '--labels', help='Comma-separated list of labels (tags)', default='')

    search_parser = subparsers.add_parser('search', help='Search inside a faldone')
    search_parser.add_argument('query', nargs='?', help='Search query', default='')

    stats_parser = subparsers.add_parser('stats', help='Print faldone statistics and exit')

    list_parser = subparsers.add_parser('list', help='List all documents and exit')
    list_parser.add_argument('-l', '--labels', help='Comma-separated list of labels (tags)', default='')

    open_parser = subparsers.add_parser('open', help='Open document with preferred application')
    open_parser.add_argument('id', help='Document id', type=int)

    args = parser.parse_args()

    path = args.faldone if args.faldone else (str(Path.home()) + os.sep + '.faldone.db')
    try:
        faldone = Faldone(path)
    except:
        print('fatal: broken or invalid faldone at \'{}\''.format(path))
        sys.exit(1)

    if args.command:
        ret = getattr(faldone, args.command)(args)
        sys.exit(ret)
    else:
        parser.print_help()
        sys.exit(2)
