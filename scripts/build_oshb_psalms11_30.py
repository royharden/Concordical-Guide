"""Build Psalms 11-30 main readings, excluding the unresolved Psalm 13 split."""
import hashlib
import json
import sqlite3
import xml.etree.ElementTree as ET
from contextlib import closing
from build_oshb_subset import MANIFEST, RAW, ROOT, NS, validate_unique_token_ids
from build_oshb_genesis10 import CATALOG_RECEIPT, compare_previous, digest, publish_candidate, verify_english_catalog
from oshb_main_reading import primary_and_note_tokens

TARGET = ROOT / 'data/generated/word-study/oshb-genesis-psalms1-30-except13-5-6-main.sqlite'
PREVIOUS = ROOT / 'data/generated/word-study/oshb-genesis-psalms1-10-main-reading.sqlite'
PREVIOUS_SHA256 = '7ce35e2177b00e9c8f9b6ec4f850f356093bd78093334a777f18a3264090237e'
COUNTS = (7, 8, 6, 7, 5, 11, 15, 50, 14, 9, 13, 31, 6, 10, 22, 12, 14, 9, 11, 12)
SHIFTED = {12, 13, 18, 19, 20, 21, 22, 30}
MAP_NS = {'m': 'http://www.APTBibleTools.com/namespace'}


def psalm_candidates(psalms, verse_map, counts=COUNTS, start=11):
    root = ET.fromstring(psalms)
    vm = ET.fromstring(verse_map)
    chapters = set(range(start, start + len(counts)))
    expected = []
    for ch, count in enumerate(counts, start):
        if ch in SHIFTED:
            expected.extend((f'Ps.{ch}.{v+1}', f'Ps.{ch}.{v}', 'full')
                            for v in range(1, (4 if ch == 13 else count) + 1))
        if ch == 13:
            expected.extend([('Ps.13.6!a','Ps.13.5','partial'), ('Ps.13.6!b','Ps.13.6','partial')])
    relevant = []
    for e in vm.findall('.//m:verse', MAP_NS):
        row = tuple(e.get(k) for k in ('wlc','kjv','type'))
        if any(any((ref or '').startswith(f'Ps.{ch}.') for ch in chapters) for ref in row[:2]):
            relevant.append(row)
    if sorted(relevant) != sorted(expected):
        raise ValueError('Unexpected Psalms reference exception or partial mapping')
    passages = []
    for ch, count in enumerate(counts, start):
        shifted = ch in SHIFTED
        chapters_found = [c for c in root.findall('.//o:chapter', NS) if c.get('osisID') == f'Ps.{ch}']
        if len(chapters_found) != 1:
            raise ValueError(f'Expected exactly one Psalm {ch}')
        verses = chapters_found[0].findall('o:verse', NS)
        source_count = count + int(shifted and ch != 13)
        if [v.get('osisID') for v in verses] != [f'Ps.{ch}.{n}' for n in range(1, source_count+1)]:
            raise ValueError(f'Unexpected source coordinates for Psalm {ch}')
        for verse in range(1, count+1):
            if ch == 13 and verse in (5,6):
                continue  # Source does not provide defensible partial-token bounds.
            target = f'Ps.{ch}.{verse}'
            osis = f'Ps.{ch}.{verse+int(shifted)}'
            node = verses[verse-1+int(shifted)]
            notes = [(n.text or '')[4:] for n in node.findall('o:note', NS) if (n.text or '').startswith('KJV:')]
            if (shifted and notes != [target]) or (not shifted and notes not in ([], [target])):
                raise ValueError(f'Conflicting source note for {target}')
            tokens, _note_tokens = primary_and_note_tokens(node)
            if not tokens or any(not tid or not text or not lemma or not morph or not morph.startswith('H')
                                 for tid,text,lemma,morph in tokens):
                raise ValueError(f'Missing source metadata or unsupported language: {osis}')
            passages.append(('kjv','bcbooks:ps',ch,verse,osis,tokens))
    return passages


def main():
    if TARGET.exists():
        raise SystemExit('Candidate exists; do not overwrite it')
    manifest=json.loads(MANIFEST.read_text(encoding='utf-8'))
    data={}
    for name, expected_hash in manifest['files'].items():
        data[name]=(RAW/name).read_bytes()
        if hashlib.sha256(data[name]).hexdigest() != expected_hash:
            raise ValueError(f'Source hash mismatch: {name}')
    if digest(PREVIOUS) != PREVIOUS_SHA256:
        raise ValueError('Previous corrected store hash mismatch')
    verify_english_catalog(json.loads(CATALOG_RECEIPT.read_text(encoding='utf-8')), COUNTS,
                           start=11, book_name='Psalms', book_id='bcbooks:ps')
    passages=psalm_candidates(data['Ps.xml'],data['VerseMap.xml'])
    validate_unique_token_ids(passages)
    def build(path):
        with closing(sqlite3.connect(PREVIOUS.resolve().as_uri()+'?mode=ro',uri=True)) as old:
            with closing(sqlite3.connect(path)) as conn:
                old.backup(conn)
                with conn:
                    for edition,book,chapter,verse,osis,tokens in passages:
                        conn.execute('INSERT INTO mappings VALUES (?,?,?,?,?)',(edition,book,chapter,verse,osis))
                        conn.executemany('INSERT INTO tokens VALUES (?,?,?,?,?,?)',[(osis,i,*t) for i,t in enumerate(tokens)])
                    compare_previous(conn, PREVIOUS)
                    if digest(PREVIOUS) != PREVIOUS_SHA256:
                        raise ValueError('Previous store changed during build')
                    if conn.execute('SELECT COUNT(*) FROM (SELECT token_id FROM tokens GROUP BY token_id HAVING COUNT(*) > 1)').fetchone()[0]:
                        raise ValueError('Source token ID duplicated across batches')
                    if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise ValueError('Candidate integrity check failed')
    publish_candidate(TARGET,build)
    print(json.dumps({'file':str(TARGET),'new_mappings':len(passages),'new_tokens':sum(len(p[-1]) for p in passages),
                      'sha256':digest(TARGET),'status':'candidate only; Psalm 13:5-6 unavailable'},indent=2))


if __name__ == '__main__':
    main()
