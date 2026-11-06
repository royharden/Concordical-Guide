"""Build historical prerequisite data; output mixes note variants into main words.

Do not serve it. Finish with build_oshb_psalms1_10.py's verified correction.
"""
import hashlib
import json
import sqlite3
import xml.etree.ElementTree as ET
from contextlib import closing

from build_oshb_subset import MANIFEST, RAW, ROOT, NS, validate_unique_token_ids
from build_oshb_genesis10 import (CATALOG_RECEIPT, compare_previous, digest, publish_candidate,
                                  verify_english_catalog)

TARGET = ROOT / 'data/generated/word-study/oshb-genesis-complete-candidate.sqlite'
PREVIOUS = ROOT / 'data/generated/word-study/oshb-genesis1-30-33-50-candidate.sqlite'
PREVIOUS_SHA256 = 'aefc3aad20f83b66c21056f1293ec17c71ab7bcaa67d10534208bf26f6f78856'
MAP_NS = {'m': 'http://www.APTBibleTools.com/namespace'}


def boundary_passages(genesis, verse_map):
    root = ET.fromstring(genesis)
    vm = ET.fromstring(verse_map)
    expected = [(f'Gen.32.{n}', 'Gen.31.55' if n == 1 else f'Gen.32.{n-1}', 'full') for n in range(1, 34)]
    relevant = []
    for entry in vm.findall('.//m:verse', MAP_NS):
        wlc, kjv, kind = (entry.get(k) for k in ('wlc', 'kjv', 'type'))
        if any((ref or '').startswith(f'Gen.{ch}.') for ref in (wlc, kjv) for ch in (31, 32)):
            relevant.append((wlc, kjv, kind))
    if sorted(relevant) != sorted(expected):
        raise ValueError('Unexpected Genesis 31-32 WLC/KJV exception map')
    source = {}
    for ch, count in ((31, 54), (32, 33)):
        chapters = [c for c in root.findall('.//o:chapter', NS) if c.get('osisID') == f'Gen.{ch}']
        if len(chapters) != 1:
            raise ValueError(f'Expected one Genesis chapter {ch}')
        verses = chapters[0].findall('o:verse', NS)
        if [v.get('osisID') for v in verses] != [f'Gen.{ch}.{i}' for i in range(1, count + 1)]:
            raise ValueError(f'Unexpected source references in Genesis {ch}')
        source.update({v.get('osisID'): v for v in verses})
    result = []
    for ch, count in ((31, 55), (32, 32)):
        for verse in range(1, count + 1):
            target = f'Gen.{ch}.{verse}'
            osis = target if ch == 31 and verse < 55 else f'Gen.32.{1 if ch == 31 else verse + 1}'
            node = source[osis]
            notes = [(n.text or '')[4:] for n in node.findall('o:note', NS) if (n.text or '').startswith('KJV:')]
            if notes != ([] if osis == target else [target]):
                raise ValueError(f'Source note mismatch for {target} -> {osis}')
            tokens = [(w.get('id'), ''.join(w.itertext()), w.get('lemma'), w.get('morph'))
                      for w in node.findall('.//o:w', NS)]
            if not tokens or any(not tid or not text or not lemma or not morph or morph[0] not in ('H', 'A')
                                 for tid, text, lemma, morph in tokens):
                raise ValueError(f'Missing token metadata or unsupported language at {osis}')
            result.append(('kjv', 'bcbooks:gen', ch, verse, osis, tokens))
    return result


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
    verify_english_catalog(json.loads(CATALOG_RECEIPT.read_text(encoding='utf-8')), (55, 32), start=31)
    passages = boundary_passages(data['Gen.xml'], data['VerseMap.xml'])
    validate_unique_token_ids(passages)
    def build_candidate(path):
        with closing(sqlite3.connect(PREVIOUS.resolve().as_uri() + '?mode=ro', uri=True)) as old:
            with closing(sqlite3.connect(path)) as conn:
                old.backup(conn)
                with conn:
                    for edition, book, chapter, verse, osis, tokens in passages:
                        conn.execute('INSERT INTO mappings VALUES (?,?,?,?,?)', (edition, book, chapter, verse, osis))
                        conn.executemany('INSERT INTO tokens VALUES (?,?,?,?,?,?)', [(osis, i, *token) for i, token in enumerate(tokens)])
                    compare_previous(conn, PREVIOUS)
                    if digest(PREVIOUS) != PREVIOUS_SHA256:
                        raise ValueError('Previous store changed during build')
                    if conn.execute('SELECT COUNT(*) FROM (SELECT token_id FROM tokens GROUP BY token_id HAVING COUNT(*) > 1)').fetchone()[0]:
                        raise ValueError('Source token ID duplicated across batches')
                    if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise ValueError('Candidate integrity check failed')
    publish_candidate(TARGET, build_candidate)
    print(json.dumps({'file': str(TARGET), 'new_mappings': len(passages), 'new_tokens': sum(len(p[-1]) for p in passages),
                      'sha256': digest(TARGET), 'status': 'candidate only; no promotion'}, indent=2))


if __name__ == '__main__':
    main()
