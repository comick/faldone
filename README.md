# Faldone: a personal documents storage and search tool

Faldone wants to be a reasonable alternative to classic paper folders (faldoni).
It comes as a command line Python 3 tool, backed by SQLite for storage and indexing.

Faldone enables the following workflow:

- store documents
- search through them
- rely on a single file for all your personal documents storage needs

## Storing a document

Can be done with `put` command:

```sh
$ faldone.py put <path/to/file>
file has been added to faldone
```

A Faldone file in the default location will be created if needed. Option `-f <path>` can be used to force a non-default path.

Additional `put` parameters are:

- `-t <some title>` to explicitly add a title to the document
- `-l "comma,separated,tags"` to add labels (tags) to a document

Faldone uses `magic` to determine mime-type of incoming document and accept/reject them based on it. Supported documents are:

- pdf containing text (those are processed with poppler `pdftotext`, to extract the text to index)
- simple text (`text/*`)

## Searching

Can be done with `search` command:

```sh
$ faldone.py search <fts4 query>"
.. search results with ranking, and id
```

Search query can be anything accepted by [SQLite fts4](https://www.sqlite.org/fts3.html#full_text_index_queries). Available columns are:

- title
- labels
- text_data


## License

```
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
```