#!/usr/bin/env python3
"""Private reader; loopback by default and never serves database files."""
import argparse
import json
import mimetypes
import os
import re
import sqlite3
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "app" / "dist"
DATA_DIR = Path(os.environ.get('CG_DATA_DIR', str(ROOT / 'data' / 'generated')))
DB = DATA_DIR / "sqlite" / "cg-source-v1.sqlite"
WEB_DB = DATA_DIR / "webp" / "engwebp.sqlite"
WORD_DB = DATA_DIR / "word-study" / "strongs.sqlite"
def oshb_store_path(data_dir, configured=None):
    # Operator-selected local file; requests never control this path. Fail
    # closed if the corrected default has not been built; older intermediate
    # stores mixed alternate note readings into the main word stream.
    return Path(configured) if configured else data_dir / "word-study" / "oshb-genesis-psalms1-150-ps13-spans.sqlite"


OSHB_DB = oshb_store_path(DATA_DIR, os.environ.get('CG_OSHB_DB'))


def hebrew_passage(edition, book, chapter, verse, db=OSHB_DB):
    mappings = query('SELECT osis FROM mappings WHERE edition=? AND book=? AND chapter=? AND verse=?', (edition,book,chapter,verse), db)
    if not mappings:
        return {'available': False, 'tokens': []}
    osis = mappings[0]['osis']
    tokens = query('SELECT token_id,text,lemma,morphology FROM tokens WHERE osis=? ORDER BY position', (osis,), db)
    parts = []
    joined_target = (edition, book, chapter, verse) == ('kjv', 'bcbooks:num', 26, 1)
    if joined_target and osis != 'Num.25.19+Num.26.1':
        return {'available': False, 'tokens': []}
    if query("SELECT name FROM sqlite_master WHERE type='table' AND name='mapping_source_parts'", (), db):
        rows = query('SELECT ordinal,osis FROM mapping_source_parts WHERE edition=? AND book=? AND chapter=? AND verse=? ORDER BY ordinal', (edition,book,chapter,verse), db)
        if rows:
            # Only this reviewed local decision currently supports multipart sources.
            expected = [('Num.25.19', ['04xYD','04Y15','047YH']),
                        ('Num.26.1', ['04Scg','04VfY','043CP','04JCV','04kSK','04Dw8','04v1s','04Hhz','046Hr','04NqA'])]
            if not joined_target or osis != 'Num.25.19+Num.26.1' or [r['osis'] for r in rows] != [p[0] for p in expected]:
                return {'available': False, 'tokens': []}
            # The synthetic mapping key must not masquerade as an XML source record.
            if tokens or len(rows)<2 or [r['ordinal'] for r in rows]!=list(range(len(rows))) or len({r['osis'] for r in rows})!=len(rows):
                return {'available': False, 'tokens': []}
            for row, (_, expected_ids) in zip(rows, expected):
                source_tokens=query('SELECT position,token_id,text,lemma,morphology FROM tokens WHERE osis=? ORDER BY position', (row['osis'],), db)
                if [t['position'] for t in source_tokens] != list(range(len(expected_ids))) or [t['token_id'] for t in source_tokens] != expected_ids:
                    return {'available': False, 'tokens': []}
                parts.append({'osis':row['osis'],'tokens':[{k:v for k,v in t.items() if k != 'position'} for t in source_tokens]})
            tokens=[token for part in parts for token in part['tokens']]
            if len({token['token_id'] for token in tokens})!=len(tokens): return {'available': False, 'tokens': []}
    if joined_target and not parts:
        return {'available': False, 'tokens': []}
    response = {'available': bool(tokens), 'osis': osis, 'tokens': tokens}
    if tokens and query("SELECT name FROM sqlite_master WHERE type='table' AND name='source_segments'", (), db):
        rows = query('SELECT role,osis FROM source_segments WHERE edition=? AND book=? AND chapter=? AND verse=? ORDER BY role', (edition,book,chapter,verse), db)
        if rows:
            response['source_segments'] = [dict(row, tokens=query('SELECT token_id,text,lemma,morphology FROM tokens WHERE osis=? ORDER BY position', (row['osis'],), db)) for row in rows]
    if tokens and query("SELECT name FROM sqlite_master WHERE type='table' AND name='mapping_adjudications'", (), db):
        rows = query('SELECT decision_id FROM mapping_adjudications WHERE edition=? AND book=? AND chapter=? AND verse=?', (edition,book,chapter,verse), db)
        if rows:
            response['adjudication_id'] = rows[0]['decision_id']
    if parts:
        if response.get('adjudication_id') != 'numbers26-1-local-reference-adjudication-v1': return {'available': False, 'tokens': []}
        response['source_parts'] = parts
    return response


def lookup_words(term, db=WORD_DB):
    term = term.strip()
    if not term or len(term) > 80:
        return []
    if re.fullmatch(r'[HGhg][0-9]+', term):
        return query('SELECT number,language,lemma,transliteration,pronunciation,definition FROM entries WHERE upper(number)=upper(?) LIMIT 30', (term,), db)
    # Treat input as literal text, not SQL LIKE wildcards or FTS syntax.
    escaped = term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    like = f'%{escaped}%'
    return query("""SELECT number,language,lemma,transliteration,pronunciation,definition
        FROM entries WHERE number LIKE ? ESCAPE '\\' OR lemma LIKE ? ESCAPE '\\'
        OR transliteration LIKE ? ESCAPE '\\' OR definition LIKE ? ESCAPE '\\'
        ORDER BY CASE WHEN upper(number)=upper(?) THEN 0 ELSE 1 END,number LIMIT 30""",
        (like, like, like, like, term), db)


def valid_host(host, port, extra=()):
    return host.lower() in (f"127.0.0.1:{port}", f"localhost:{port}", *extra)


def valid_origin(origin, port, extra=()):
    return not origin or origin.lower() in (f"http://127.0.0.1:{port}", f"http://localhost:{port}", *extra)


def query(sql, args=(), db=DB):
    with closing(sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(sql, args)]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Search phrases are private; do not include request URLs in logs.
        pass

    def do_GET(self):
        if not valid_host(self.headers.get("Host", ""), self.server.server_port, getattr(self.server, 'allowed_hosts', ())):
            return self.send_error(403, "Invalid host")
        origin = self.headers.get("Origin")
        if not valid_origin(origin, self.server.server_port, getattr(self.server, 'allowed_origins', ())):
            return self.send_error(403, "Invalid origin")
        parsed = urlsplit(self.path)
        if parsed.path == '/healthz':
            try:
                if not query('SELECT id FROM books LIMIT 1'):
                    return self.send_error(503, 'Reader catalog is empty')
            except sqlite3.Error:
                return self.send_error(503, 'Reader data unavailable')
            return self.json_response({'status':'ok'})
        if parsed.path == "/api/hebrew-passage":
            params = parse_qs(parsed.query)
            try:
                edition, book = params['edition'][0], params['book'][0]
                chapter, verse = int(params['chapter'][0]), int(params['verse'][0])
                if edition not in ('kjv','webp') or len(book) > 120 or chapter < 1 or verse < 1 or chapter > 1000 or verse > 1000:
                    raise ValueError()
            except (KeyError, ValueError, IndexError):
                return self.send_error(400, 'Invalid passage')
            if not OSHB_DB.is_file():
                return self.send_error(503, 'Original-language data not installed')
            return self.json_response(hebrew_passage(edition,book,chapter,verse))
        if parsed.path == "/api/word-study":
            if not WORD_DB.is_file():
                return self.send_error(503, "Word-study data not installed")
            return self.json_response(lookup_words(parse_qs(parsed.query).get('q', [''])[0]))
        if parsed.path == "/api/catalog":
            return self.json_response(query("""SELECT b.id, b.title, v.title AS volume,
                v.slug AS volume_slug, COUNT(c.id) AS chapters FROM books b
                JOIN volumes v ON v.id=b.volume_id JOIN chapters c ON c.book_id=b.id
                GROUP BY b.id ORDER BY v.sort_order,b.sort_order"""))
        if parsed.path == "/api/chapter":
            params = parse_qs(parsed.query)
            try:
                book = params["book"][0]
                chapter = int(params["chapter"][0])
            except (KeyError, ValueError, IndexError):
                return self.send_error(400, "Invalid passage")
            if chapter < 1 or len(book) > 120:
                return self.send_error(400, "Invalid passage")
            edition = params.get("edition", ["kjv"])[0]
            if edition == "webp":
                if not WEB_DB.is_file():
                    return self.send_error(503, "WEB edition not installed")
                return self.json_response(query("SELECT verse,text FROM verses WHERE book_id=? AND chapter=? ORDER BY verse", (book, chapter), WEB_DB))
            if edition != "kjv":
                return self.send_error(400, "Unknown edition")
            return self.json_response(query("""SELECT v.verse_number AS verse,v.reference,t.text_plain AS text
                FROM verses v JOIN verse_texts t ON t.verse_id=v.id
                WHERE v.book_id=? AND v.chapter_number=? ORDER BY v.verse_number""", (book, chapter)))
        if parsed.path == "/api/search":
            term = parse_qs(parsed.query).get("q", [""])[0].strip()
            if not term or len(term) > 100:
                return self.json_response([])
            # Quote as an FTS phrase rather than interpreting user text as query syntax.
            phrase = '"' + term.replace('"', '""') + '"'
            return self.json_response(query("""SELECT v.book_id,v.chapter_number,v.verse_number,v.reference
                FROM verse_text_fts f JOIN verses v ON v.id=f.verse_id
                WHERE verse_text_fts MATCH ? LIMIT 30""", (phrase,)))
        path = "index.html" if parsed.path in ("/", "/index.html") else parsed.path.lstrip("/")
        target = (DIST / path).resolve()
        if not target.is_relative_to(DIST.resolve()) or not target.is_file():
            return self.send_error(404)
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def json_response(self, value):
        data = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=os.environ.get('PORT'), required='PORT' not in os.environ)
    parser.add_argument("--bind", default=os.environ.get('CG_BIND', '127.0.0.1'))
    args = parser.parse_args()
    if not DB.is_file() or not (DIST / "index.html").is_file():
        parser.error("Build app and generate the local source database first")
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535')
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    server.allowed_hosts = tuple(x.strip().lower() for x in os.environ.get('CG_ALLOWED_HOSTS','').split(',') if x.strip())
    server.allowed_origins = tuple(x.strip().lower() for x in os.environ.get('CG_ALLOWED_ORIGINS','').split(',') if x.strip())
    print(f"Reader listening on {args.bind}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
