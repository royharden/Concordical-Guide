"""Build a historical prerequisite; output mixes note variants into main words.

Do not serve it. Finish with build_oshb_psalms1_10.py's verified correction.
"""
import hashlib
import json
import os
import sqlite3
import tempfile
import xml.etree.ElementTree as ET
from contextlib import closing

from build_oshb_subset import (CATALOG, MANIFEST, NS, RAW, ROOT, parse_passage,
                               validate_genesis_map, validate_genesis_source,
                               validate_unique_token_ids)

TARGET = ROOT / 'data/generated/word-study/oshb-genesis1-10-candidate-v2.sqlite'
PREVIOUS = ROOT / 'data/generated/word-study/oshb-genesis1-2.sqlite'
CATALOG_RECEIPT = ROOT / 'data/generated/sqlite/cg-source-v1.manifest.json'
RAW_ENGLISH = ROOT / 'data/downloads/lds-scriptures-json/old-testament.json'
COUNTS = (31, 25, 24, 26, 32, 22, 24, 22, 29, 32)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def chapter_records(content, counts=COUNTS, start=1):
    """Preserve source surfaces, raw lemma/morphology, and stable IDs unchanged."""
    root = ET.fromstring(content)
    passages = []
    for chapter, count in enumerate(counts, start):
        validate_genesis_source(content, chapter, count)
        for verse in range(1, count + 1):
            osis = f'Gen.{chapter}.{verse}'
            nodes = [v for v in root.findall('.//o:verse', NS) if v.get('osisID') == osis]
            if len(nodes) != 1:
                raise ValueError(f'Expected one {osis}')
            tokens = [(w.get('id'), ''.join(w.itertext()), w.get('lemma'), w.get('morph'))
                      for w in nodes[0].findall('.//o:w', NS)]
            if not tokens or any(not tid or not text or not lemma or not morph or not morph.startswith('H')
                                 for tid, text, lemma, morph in tokens):
                raise ValueError(f'Missing token metadata or unsupported language at {osis}')
            passages.append(('kjv', 'bcbooks:gen', chapter, verse, osis, tokens))
    return passages


def verify_english_catalog(receipt, counts=COUNTS, start=1, book_name='Genesis', book_id='bcbooks:gen'):
    raw_entry = next(e for e in receipt['source_files'] if e['path'].endswith('/old-testament.json'))
    raw = RAW_ENGLISH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != raw_entry['sha256']:
        raise ValueError('Local KJV source or derived catalog differs from its import receipt')
    bible = json.loads(raw.decode('utf-8'))
    book = next(b for b in bible['books'] if b['book'] == book_name)
    raw_coordinates = {(ch['chapter'], v['verse']) for ch in book['chapters'] for v in ch['verses']}
    expected = {(chapter, verse) for chapter, count in enumerate(counts, start) for verse in range(1, count + 1)}
    with closing(sqlite3.connect(CATALOG.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        if conn.execute('PRAGMA journal_mode').fetchone()[0].lower() != 'delete':
            raise ValueError('Catalog journal mode must be delete for a verifiable file hash')
        conn.execute('BEGIN')
        conn.execute('SELECT COUNT(*) FROM verses').fetchone()  # Hold the read lock during both hashes.
        if digest(CATALOG) != receipt['db_sha256']:
            raise ValueError('Local KJV catalog differs from its import receipt')
        catalog = conn.execute('SELECT chapter_number, verse_number, source_id FROM verses WHERE book_id=? AND chapter_number BETWEEN ? AND ?',
                               (book_id, start, start + len(counts) - 1)).fetchall()
        if digest(CATALOG) != receipt['db_sha256']:
            raise ValueError('Local KJV catalog changed during verification')
    if (not expected.issubset(raw_coordinates) or len(catalog) != len(expected)
            or {(c, v) for c, v, _ in catalog} != expected
            or {s for _, _, s in catalog} != {'bcbooks-scriptures-json'}):
        raise ValueError('KJV raw file, catalog and expected chapter coordinates disagree')


def compare_previous(conn, previous=None):
    """Every old mapping and token must survive exactly, in both directions for its passages."""
    previous = PREVIOUS if previous is None else previous
    with closing(sqlite3.connect(previous.resolve().as_uri() + '?mode=ro', uri=True)) as old:
        mappings = old.execute('SELECT edition,book,chapter,verse,osis FROM mappings').fetchall()
        for mapping in mappings:
            row = conn.execute('SELECT edition,book,chapter,verse,osis FROM mappings WHERE edition=? AND book=? AND chapter=? AND verse=?', mapping[:4]).fetchone()
            if row != mapping:
                raise ValueError(f'Previous mapping changed: {mapping[:4]}')
            sql = 'SELECT osis,position,token_id,text,lemma,morphology FROM tokens WHERE osis=? ORDER BY position'
            if old.execute(sql, (mapping[4],)).fetchall() != conn.execute(sql, (mapping[4],)).fetchall():
                raise ValueError(f'Previous source tokens changed: {mapping[4]}')


def publish_candidate(target, build):
    """Build privately, then atomically install without replacing any existing path."""
    fd, temp_name = tempfile.mkstemp(prefix='.oshb-candidate-', suffix='.sqlite', dir=target.parent)
    os.close(fd)
    try:
        build(temp_name)
        os.link(temp_name, target)  # Atomic and fails if target exists.
    finally:
        os.unlink(temp_name)


def main():
    if TARGET.exists():
        raise SystemExit('Candidate already exists; do not overwrite it')
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    data = {}
    for name, expected in manifest['files'].items():
        data[name] = (RAW / name).read_bytes()
        if hashlib.sha256(data[name]).hexdigest() != expected:
            raise ValueError(f'Source hash mismatch: {name}')
    verify_english_catalog(json.loads(CATALOG_RECEIPT.read_text(encoding='utf-8')))
    for chapter in range(1, len(COUNTS) + 1):
        validate_genesis_map(data['VerseMap.xml'], chapter)
    passages = chapter_records(data['Gen.xml'])
    passages.append(('kjv', 'bcbooks:ps', 3, 1, 'Ps.3.2', parse_passage(data['Ps.xml'], 'Ps.3.2', 'KJV:Ps.3.1')))
    validate_unique_token_ids(passages)
    def build_candidate(path):
        with closing(sqlite3.connect(path)) as conn, conn:
            conn.execute('CREATE TABLE mappings (edition TEXT, book TEXT, chapter INTEGER, verse INTEGER, osis TEXT, PRIMARY KEY(edition,book,chapter,verse))')
            conn.execute('CREATE TABLE tokens (osis TEXT, position INTEGER, token_id TEXT, text TEXT, lemma TEXT, morphology TEXT, PRIMARY KEY(osis,position))')
            for edition, book, chapter, verse, osis, tokens in passages:
                conn.execute('INSERT INTO mappings VALUES (?,?,?,?,?)', (edition, book, chapter, verse, osis))
                conn.executemany('INSERT INTO tokens VALUES (?,?,?,?,?,?)', [(osis, i, *token) for i, token in enumerate(tokens)])
            compare_previous(conn)
            if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Candidate integrity check failed')
    publish_candidate(TARGET, build_candidate)
    print(json.dumps({'file': str(TARGET), 'mappings': len(passages), 'tokens': sum(len(p[-1]) for p in passages),
                      'sha256': digest(TARGET), 'status': 'candidate only; no promotion'}, indent=2))


if __name__ == '__main__':
    main()
