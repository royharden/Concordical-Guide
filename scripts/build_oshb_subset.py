"""Build historical prerequisite data; note variants are mixed into its output.

Do not serve this intermediate store. Run build_oshb_psalms1_10.py after the
Genesis prerequisite chain to remove note variants from the main reading.
"""
import hashlib
import json
import sqlite3
import xml.etree.ElementTree as ET
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'data/manifests/oshb-subset.json'
RAW = ROOT / 'data/downloads/oshb-v2'
TARGET = ROOT / 'data/generated/word-study/oshb-genesis1-2.sqlite'
CATALOG = ROOT / 'data/generated/sqlite/cg-source-v1.sqlite'
NS = {'o': 'http://www.bibletechnologies.net/2003/OSIS/namespace'}
# Genesis 1–2 identity is conditional on the pinned VerseMap's documented
# exception catalog, source structure and canonical KJV catalog all agreeing.
MAPPINGS = [('kjv', 'bcbooks:gen', chapter, n, 'Gen.xml', f'Gen.{chapter}.{n}', None)
            for chapter, count in ((1, 31), (2, 25)) for n in range(1, count + 1)] + [
    ('kjv', 'bcbooks:ps', 3, 1, 'Ps.xml', 'Ps.3.2', 'KJV:Ps.3.1')]


def validate_genesis_map(data, chapter):
    root = ET.fromstring(data)
    ns = {'m': 'http://www.APTBibleTools.com/namespace'}
    books = [b for b in root.findall('m:book', ns) if b.get('osisID') == 'Gen']
    if len(books) != 1:
        raise ValueError('Expected one Genesis exception list')
    # Catch incoming exceptions from any book, not just entries filed under Gen.
    for verse in root.findall('.//m:verse', ns):
        if verse.get('wlc', '').startswith(f'Gen.{chapter}.') or verse.get('kjv', '').startswith(f'Gen.{chapter}.'):
            raise ValueError(f'Genesis {chapter} contains a versification exception')


def validate_genesis_source(data, chapter, count):
    root = ET.fromstring(data)
    chapters = [c for c in root.findall('.//o:chapter', NS) if c.get('osisID') == f'Gen.{chapter}']
    if len(chapters) != 1:
        raise ValueError(f'Expected one Genesis chapter {chapter}')
    verses = chapters[0].findall('o:verse', NS)
    if [v.get('osisID') for v in verses] != [f'Gen.{chapter}.{n}' for n in range(1, count + 1)]:
        raise ValueError(f'Genesis {chapter} source coordinates are incomplete or duplicated')
    if any((note.text or '').startswith('KJV:') for v in verses for note in v.findall('o:note', NS)):
        raise ValueError(f'Genesis {chapter} has a source KJV remapping note')


def validate_unique_token_ids(passages):
    ids = [token[0] for passage in passages for token in passage[-1]]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate source token IDs across mapped passages')


def parse_passage(data, osis_id, expected_note=None):
    root = ET.fromstring(data)
    matches = [v for v in root.findall('.//o:verse', NS) if v.get('osisID') == osis_id]
    if len(matches) != 1:
        raise ValueError('Expected exactly one source verse')
    verse = matches[0]
    notes = [n.text for n in verse.findall('o:note', NS)]
    if expected_note is not None and expected_note not in notes:
        raise ValueError('Expected edition mapping note is missing')
    result = [(w.get('id'), ''.join(w.itertext()), w.get('lemma'), w.get('morph')) for w in verse.findall('.//o:w', NS)]
    if not result or any(not item[0] or not item[1] for item in result) or len({item[0] for item in result}) != len(result):
        raise ValueError('Missing or duplicate source token IDs')
    return result


def main():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    data = {}
    for name, expected in manifest['files'].items():
        content = (RAW / name).read_bytes()
        if hashlib.sha256(content).hexdigest() != expected:
            raise SystemExit(f'Source hash mismatch: {name}')
        data[name] = content
    for chapter, count in ((1,31),(2,25)):
        validate_genesis_map(data['VerseMap.xml'], chapter)
        validate_genesis_source(data['Gen.xml'], chapter, count)
    if TARGET.exists():
        raise SystemExit('Target exists; preserve it rather than overwrite it.')
    with closing(sqlite3.connect(CATALOG.resolve().as_uri() + '?mode=ro', uri=True)) as catalog:
        for edition,book,chapter,verse,_,_,_ in MAPPINGS:
            count = catalog.execute('SELECT COUNT(*) FROM verses WHERE book_id=? AND chapter_number=? AND verse_number=?', (book,chapter,verse)).fetchone()[0]
            if edition != 'kjv' or count != 1:
                raise SystemExit('Verified mapping is not unique in the canonical KJV catalog.')
    passages = [(edition,book,chapter,verse,osis,parse_passage(data[name],osis,note)) for edition,book,chapter,verse,name,osis,note in MAPPINGS]
    validate_unique_token_ids(passages)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    try:
        with closing(sqlite3.connect(TARGET)) as conn, conn:
            conn.execute('CREATE TABLE mappings (edition TEXT, book TEXT, chapter INTEGER, verse INTEGER, osis TEXT, PRIMARY KEY(edition,book,chapter,verse))')
            conn.execute('CREATE TABLE tokens (osis TEXT, position INTEGER, token_id TEXT, text TEXT, lemma TEXT, morphology TEXT, PRIMARY KEY(osis,position))')
            for edition,book,chapter,verse,osis,tokens in passages:
                conn.execute('INSERT INTO mappings VALUES (?,?,?,?,?)',(edition,book,chapter,verse,osis))
                conn.executemany('INSERT INTO tokens VALUES (?,?,?,?,?,?)',[(osis,i,*token) for i,token in enumerate(tokens)])
    except Exception:
        TARGET.unlink(missing_ok=True)
        raise
    print(f'Built {TARGET} with {len(passages)} verified KJV passage mappings.')


if __name__ == '__main__':
    main()
