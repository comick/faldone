#!/usr/bin/env python3
import argparse
import locale
import os.path
import sqlite3
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
import mimetypes
import magic
import pyocr
import pyocr.builders
from PIL import Image

APPLICATION_ID = '0x66616c64'

init_sql = ['''
CREATE TABLE documents (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  title     TEXT,
  labels    TEXT,
  mime      TEXT,
  text_data TEXT,
  raw_data  BLOB
);''', '''
CREATE VIRTUAL TABLE documents_idx USING fts4(title, labels, text_data, content="documents");
''', '''
CREATE TRIGGER documents_after_insert AFTER INSERT ON documents BEGIN
  INSERT INTO documents_idx (docid, title, labels, text_data) VALUES (new.id, new.title, new.labels, new.text_data);
END;
''', '''
CREATE TRIGGER documents_before_delete BEFORE DELETE ON documents BEGIN
  DELETE FROM documents_idx WHERE docid = old.id;
END;''', '''
PRAGMA application_id = {};
'''.format(APPLICATION_ID)]


def init(filepath):
    create_schema = not os.path.exists(filepath)
    conn = sqlite3.connect(dbname)
    cursor = conn.cursor()
    if create_schema:
        print('Creating faldone at \'{}\''.format(filepath))
        for s in init_sql:
            cursor.execute(s)
        conn.commit()

    try:
        cursor.execute('PRAGMA application_id')
        if (cursor.fetchone()[0] != int(APPLICATION_ID, 16)): raise ValueError()
    except:
        print('fatal: \'{}\' is not a valid faldone file'.format(dbname))

    return (conn, cursor)


def put(conn, cursor, args):
    doc = args.document
    title = args.title if args.title else os.path.basename(doc.name)
    labels = args.labels
    doc_raw = doc.read()
    mime_type = magic.from_buffer(doc_raw, mime=True)

    if (type(doc_raw) is str):
        # This is the case for stdin
        doc_blob = sqlite3.Binary(bytearray(doc_raw, locale.getdefaultlocale()[1]))
    else:
        doc_blob = sqlite3.Binary(doc_raw)

    if mime_type == 'application/pdf':
        doc_text = subprocess.run(['pdftotext', doc.name, '-'], stdout=subprocess.PIPE).stdout
    elif mime_type.startswith('image/'):
        tools = pyocr.get_available_tools()
        if (len(tools) == 0):
            print('OCR tool not found, cannot put image.')
            return 1
        tool = tools[0]
        print('Using `{}` for OCR'.format(tool.get_name()))
        doc_text = tool.image_to_string(
                Image.open(doc),
                builder=pyocr.builders.TextBuilder()
        )
        print(doc_text)
    elif mime_type.startswith('text/'):
        doc_text = doc_blob
    else:
        print('Unsupported mime type "{}"'.format(mime_type))
        return 1

    put_sql = 'INSERT INTO documents(title, labels, mime, text_data, raw_data) VALUES (?, ?, ?, ?, ?)'
    cursor.execute(put_sql, (title, labels, mime_type, doc_text, doc_blob))
    conn.commit()
    print('{} has been added to faldone'.format(title))


def drop():
    pass


def search(conn, cursor, args):
    # https://gist.github.com/saaj/fdc8e6351d07fbb1a511
    def parseMatchInfo(buf):
        '''see http://sqlite.org/fts3.html#matchinfo'''
        bufsize = len(buf)  # length in bytes
        return [struct.unpack('@I', buf[i:i + 4])[0] for i in range(0, bufsize, 4)]

    def _sql_rank(matchinfo):
        '''
        handle match_info called w/default args 'pcx' - based on the example rank
        function http://sqlite.org/fts3.html#appendix_a
        '''
        match_info = parseMatchInfo(matchinfo)
        score = 0.0
        p, c = match_info[:2]
        for phrase_num in range(p):
            phrase_info_idx = 2 + (phrase_num * c * 3)
            for col_num in range(c):
                col_idx = phrase_info_idx + (col_num * 3)
                x1, x2 = match_info[col_idx:col_idx + 2]
                if x1 > 0:
                    score += float(x1) / x2
        return score

    conn.create_function('rank', 1, _sql_rank)
    search_sql = "SELECT docid, title, snippet(documents_idx, '\033[1m', '\033[0m', '\u2026', -1, 20), rank(matchinfo(documents_idx)) AS rank " \
                 "FROM documents_idx " \
                 "WHERE documents_idx MATCH ? " \
                 "ORDER BY rank DESC LIMIT 10 OFFSET 0"
    for res in cursor.execute(search_sql, (args.query,)):
        print('\033[92m{}. {} (relevancy {:.2f})\033[0m:'.format(res[0], res[1], res[3]))
        print('\t' + '\t'.join(res[2].splitlines(True)))
    return 0


def stats(conn, cursor, args):
    cursor.execute('SELECT COUNT(*) FROM documents')
    print('Documents: {}'.format(cursor.fetchone()[0]))


def openX(conn, cursor, args):
    cursor.execute("SELECT raw_data, mime FROM documents WHERE id = ?", (args.id,))
    doc = cursor.fetchone()
    if doc == None:
        print('Document does not exist')
        return 1
    ext = mimetypes.guess_extension(doc[1])
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as output_file:
        output_file.write(doc[0])
    subprocess.run(['xdg-open', output_file.name])


ops = {
    'put': put,
    'search': search,
    'stats': stats,
    'open': openX
}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--faldone', help='Non-default faldone location')
    subparsers = parser.add_subparsers(metavar='command', dest='command')

    put_parser = subparsers.add_parser('put', help='Put documents into faldone')
    put_parser.add_argument('document', help='Path to a document',
                            type=argparse.FileType('rb'))
    put_parser.add_argument('-t', '--title', help='Document title')
    put_parser.add_argument('-l', '--labels', help='Comma-separated list of labels (tags)', default='')

    search_parser = subparsers.add_parser('search', help='Search through your faldone documents')
    search_parser.add_argument('query', nargs='?', help='Search query', default='')

    stats_parser = subparsers.add_parser('stats', help='Print faldone statistics and exit')

    open_parser = subparsers.add_parser('open', help='Open document with xdg-open')
    open_parser.add_argument('id', help='Document id', type=int)

    args = parser.parse_args()

    dbname = args.faldone if args.faldone else (str(Path.home()) + os.sep + '.faldone.db')
    (conn, cursor) = init(dbname)

    if (args.command):
        ret = ops[args.command](conn, cursor, args)
        sys.exit(ret)
    else:
        parser.print_help()
        sys.exit(2)
