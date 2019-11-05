import locale
import mimetypes
import os.path
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile

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


class Faldone:

    def __init__(self, path):
        existed = not os.path.exists(path)
        self.conn = sqlite3.connect(path)
        self.cursor = self.conn.cursor()
        if existed:
            print('Creating faldone at \'{}\''.format(path))
            for s in init_sql:
                self.cursor.execute(s)
            self.conn.commit()

        self.cursor.execute('PRAGMA application_id')
        if (self.cursor.fetchone()[0] != int(APPLICATION_ID, 16)): raise ValueError()

    def list(self, args):
        search_sql = "SELECT id, title, mime, labels " \
                     "FROM documents " \
                     "ORDER BY id"
        for res in self.cursor.execute(search_sql):
            print('{}\t{} [{}]: {{}}'.format(res[0], res[1], res[2], res[3]))
        return 0


    def put(self, args):
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
            if (shutil.which('pdftotext')):
                doc_text = subprocess.run(['pdftotext', doc.name, '-'], stdout=subprocess.PIPE).stdout
            else:
                print('Cannot put PDF file, please make sure `pdftotext` is in your path.')
                return 1
        elif mime_type.startswith('image/'):
            tools = pyocr.get_available_tools()
            if len(tools) == 0:
                print('Cannot put image file, could not find any OCR tool.')
                return 1
            tool = tools[0]
            print('Using `{}` for OCR'.format(tool.get_name()))
            doc_text = tool.image_to_string(
                Image.open(doc),
                builder=pyocr.builders.TextBuilder()
            )
        elif mime_type.startswith('text/'):
            doc_text = doc_blob
        else:
            print('Unsupported mime type "{}"'.format(mime_type))
            return 1

        put_sql = 'INSERT INTO documents(title, labels, mime, text_data, raw_data) VALUES (?, ?, ?, ?, ?)'
        self.cursor.execute(put_sql, (title, labels, mime_type, doc_text, doc_blob))
        self.conn.commit()
        print('{} has been added to faldone'.format(title))

    def drop(self):
        pass

    @staticmethod
    def __sql_rank(matchinfo):

        # https://gist.github.com/saaj/fdc8e6351d07fbb1a511
        def parseMatchInfo(buf):
            '''see http://sqlite.org/fts3.html#matchinfo'''
            bufsize = len(buf)  # length in bytes
            return [struct.unpack('@I', buf[i:i + 4])[0] for i in range(0, bufsize, 4)]

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

    def search(self, args):
        self.conn.create_function('rank', 1, self.__sql_rank)
        search_sql = "SELECT docid, title, snippet(documents_idx, ' \033[1m ', ' \033[0m ', '\u2026', -1, 20), rank(matchinfo(documents_idx)) AS rank " \
                     "FROM documents_idx " \
                     "WHERE documents_idx MATCH ? " \
                     "ORDER BY rank DESC LIMIT 10 OFFSET 0"
        for res in self.cursor.execute(search_sql, (args.query,)):
            print('\033[92m{}. {} (relevancy {:.2f})\033[0m:'.format(res[0], res[1], res[3]))
            print('\t' + '\t'.join(res[2].splitlines(True)))
        return 0

    def stats(self):
        self.cursor.execute('SELECT COUNT(*) FROM documents')
        print('Documents: {}'.format(self.cursor.fetchone()[0]))

    def open(self, args):
        self.cursor.execute("SELECT title, raw_data, mime FROM documents WHERE id = ?", (args.id,))
        doc = self.cursor.fetchone()
        if doc is None:
            print('Document does not exist')
            return 1
        ext = mimetypes.guess_extension(doc[2])
        try:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as output_file:
                output_file.write(doc[1])
            subprocess.check_call(['xdg-open', output_file.name])
            print("Document `{}` opened".format(doc[0]))
        except:
            print("Could not open document `{}` externally".format(output_file.name))

    def __open_file(file_path):
        if sys.platform.startswith('darwin'):
            subprocess.check_call(('open', file_path))
        elif os.name == 'nt':
            os.startfile(file_path)
        elif os.name == 'posix':
            subprocess.check_call(('xdg-open', file_path))

    def close(self):
        self.cursor.close()
        self.conn.close()
