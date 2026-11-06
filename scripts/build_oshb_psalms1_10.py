"""Build KJV Psalms 1-10 alongside the accepted Genesis source-word store."""
import hashlib
import json
import sqlite3
import xml.etree.ElementTree as ET
from contextlib import closing

from build_oshb_subset import MANIFEST, RAW, ROOT, NS, validate_unique_token_ids
from build_oshb_genesis10 import (CATALOG_RECEIPT, digest, publish_candidate,
                                  verify_english_catalog)
from oshb_main_reading import primary_and_note_tokens

TARGET = ROOT / 'data/generated/word-study/oshb-genesis-psalms1-10-main-reading.sqlite'
PREVIOUS = ROOT / 'data/generated/word-study/oshb-genesis-complete-candidate.sqlite'
PREVIOUS_SHA256 = '703cb3510b143d204c2bc01990465bacfaabaeeacea98244512b8b6542dce0f4'
COUNTS = (6, 12, 8, 8, 12, 10, 17, 9, 20, 18)
MAP_NS = {'m': 'http://www.APTBibleTools.com/namespace'}


def psalm_passages(psalms, verse_map, counts=COUNTS, start=1):
    root = ET.fromstring(psalms)
    vm = ET.fromstring(verse_map)
    chapters = set(range(start, start + len(counts)))
    expected = [(f'Ps.{ch}.{v+1}', f'Ps.{ch}.{v}', 'full')
                for ch, count in enumerate(counts, start) if 3 <= ch <= 9 for v in range(1, count+1)]
    relevant = []
    for e in vm.findall('.//m:verse', MAP_NS):
        row = tuple(e.get(k) for k in ('wlc', 'kjv', 'type'))
        if any(any((ref or '').startswith(f'Ps.{ch}.') for ch in chapters) for ref in row[:2]):
            relevant.append(row)
    if sorted(relevant) != sorted(expected):
        raise ValueError('Unexpected Psalms reference exception or heading mapping')
    passages = []
    for ch, count in enumerate(counts, start):
        shifted = 3 <= ch <= 9
        nodes = [c for c in root.findall('.//o:chapter', NS) if c.get('osisID') == f'Ps.{ch}']
        if len(nodes) != 1:
            raise ValueError(f'Expected exactly one Psalm {ch}')
        verses = nodes[0].findall('o:verse', NS)
        expected_source = [f'Ps.{ch}.{n}' for n in range(1, count + 1 + int(shifted))]
        if [v.get('osisID') for v in verses] != expected_source:
            raise ValueError(f'Unexpected source coordinates for Psalm {ch}')
        for v in range(1, count+1):
            osis = f'Ps.{ch}.{v + int(shifted)}'
            node = verses[v - 1 + int(shifted)]
            notes = [(n.text or '')[4:] for n in node.findall('o:note', NS) if (n.text or '').startswith('KJV:')]
            if notes != ([f'Ps.{ch}.{v}'] if shifted else []):
                raise ValueError(f'Source note mismatch for Psalm {ch}:{v}')
            tokens, _note_tokens = primary_and_note_tokens(node)
            if not tokens or any(not tid or not text or not lemma or not morph or not morph.startswith('H')
                                 for tid, text, lemma, morph in tokens):
                raise ValueError(f'Missing token metadata or unsupported language: {osis}')
            passages.append(('kjv', 'bcbooks:ps', ch, v, osis, tokens))
    return passages


def main():
    if TARGET.exists():
        raise SystemExit('Candidate already exists; do not overwrite it')
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    data = {}
    for name, expected_hash in manifest['files'].items():
        data[name] = (RAW / name).read_bytes()
        if hashlib.sha256(data[name]).hexdigest() != expected_hash:
            raise ValueError(f'Source hash mismatch: {name}')
    if digest(PREVIOUS) != PREVIOUS_SHA256:
        raise ValueError('Previous store differs from reviewed bytes')
    verify_english_catalog(json.loads(CATALOG_RECEIPT.read_text(encoding='utf-8')), COUNTS,
                           book_name='Psalms', book_id='bcbooks:ps')
    passages = psalm_passages(data['Ps.xml'], data['VerseMap.xml'])
    validate_unique_token_ids(passages)
    roots = {name: ET.fromstring(data[name]) for name in ('Gen.xml', 'Ps.xml')}
    source = {v.get('osisID'): v for root in roots.values() for v in root.findall('.//o:verse', NS)}
    repair = {'references': [], 'removed_note_tokens': 0}
    def build_candidate(path):
        with closing(sqlite3.connect(PREVIOUS.resolve().as_uri() + '?mode=ro', uri=True)) as old:
            with closing(sqlite3.connect(path)) as conn:
                old.backup(conn)
                with conn:
                    # Reconcile each previous mapping against the original source.
                    # The former builder accidentally included note/rdg words in
                    # the main stream; correct only those verified differences.
                    old_rows = old.execute('SELECT edition,book,chapter,verse,osis FROM mappings').fetchall()
                    for edition, book, chapter, verse, osis in old_rows:
                        node = source.get(osis)
                        if node is None:
                            raise ValueError(f'Missing prior source verse: {osis}')
                        primary, note_words = primary_and_note_tokens(node)
                        original = [(w.get('id'), ''.join(w.itertext()), w.get('lemma'), w.get('morph'))
                                    for w in node.findall('.//o:w', NS)]
                        actual = old.execute('SELECT token_id,text,lemma,morphology FROM tokens WHERE osis=? ORDER BY position', (osis,)).fetchall()
                        if actual != original:
                            raise ValueError(f'Prior store differs from pinned source: {osis}')
                        if note_words:
                            if book != 'bcbooks:gen' or not primary:
                                raise ValueError(f'Unexpected prior note variants at {osis}')
                            conn.execute('DELETE FROM tokens WHERE osis=?', (osis,))
                            conn.executemany('INSERT INTO tokens VALUES (?,?,?,?,?,?)', [(osis, i, *token) for i, token in enumerate(primary)])
                            repair['references'].append(f'{chapter}:{verse}')
                            repair['removed_note_tokens'] += len(note_words)
                        now = conn.execute('SELECT token_id,text,lemma,morphology FROM tokens WHERE osis=? ORDER BY position', (osis,)).fetchall()
                        if now != primary:
                            raise ValueError(f'Primary source verification failed: {osis}')
                    if len(repair['references']) != 15 or repair['removed_note_tokens'] != 17:
                        raise ValueError('Unexpected number of prior Genesis corrections')
                    for edition, book, chapter, verse, osis, tokens in passages:
                        if (chapter, verse) == (3, 1):
                            continue  # Existing row is verified below, not overwritten.
                        conn.execute('INSERT INTO mappings VALUES (?,?,?,?,?)', (edition, book, chapter, verse, osis))
                        conn.executemany('INSERT INTO tokens VALUES (?,?,?,?,?,?)', [(osis, i, *token) for i, token in enumerate(tokens)])
                    if conn.execute('SELECT COUNT(*) FROM mappings').fetchone()[0] != len(old_rows) + len(passages) - 1:
                        raise ValueError('Unexpected number of mappings')
                    if digest(PREVIOUS) != PREVIOUS_SHA256:
                        raise ValueError('Previous store changed during build')
                    if conn.execute('SELECT COUNT(*) FROM (SELECT token_id FROM tokens GROUP BY token_id HAVING COUNT(*) > 1)').fetchone()[0]:
                        raise ValueError('Source token ID duplicated across batches')
                    if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise ValueError('Candidate integrity check failed')
    publish_candidate(TARGET, build_candidate)
    print(json.dumps({'file': str(TARGET), 'new_mappings': len(passages)-1,
                      'new_tokens': sum(len(p[-1]) for p in passages if (p[2], p[3]) != (3, 1)),
                      'corrected_genesis_refs': repair['references'], 'removed_note_tokens': repair['removed_note_tokens'],
                      'sha256': digest(TARGET), 'status': 'candidate only; no promotion'}, indent=2))


if __name__ == '__main__':
    main()
