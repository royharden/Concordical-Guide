"""Build historical prerequisite data; output mixes note variants into main words.

Do not serve it. Finish with build_oshb_psalms1_10.py's verified correction.
"""
import hashlib
import json
import sqlite3
from contextlib import closing

from build_oshb_subset import MANIFEST, RAW, ROOT, parse_passage, validate_genesis_map, validate_unique_token_ids
from build_oshb_genesis10 import (CATALOG_RECEIPT, COUNTS, chapter_records, compare_previous,
                                  digest, publish_candidate, verify_english_catalog)

TARGET = ROOT / 'data/generated/word-study/oshb-genesis1-30-candidate.sqlite'
PREVIOUS = ROOT / 'data/generated/word-study/oshb-genesis1-10-candidate-v2.sqlite'
PREVIOUS_SHA256 = '8117c9086ce98545a50f694da8c47b1508f4168d2bb95bfb63d3d72a50d3eaf3'
CHAPTER_COUNTS = COUNTS + (32, 20, 18, 24, 21, 16, 27, 33, 38, 18,
                           34, 24, 20, 67, 34, 35, 46, 22, 35, 43)


def main():
    if TARGET.exists():
        raise SystemExit('Candidate already exists; do not overwrite it')
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    data = {}
    for name, expected in manifest['files'].items():
        data[name] = (RAW / name).read_bytes()
        if hashlib.sha256(data[name]).hexdigest() != expected:
            raise ValueError(f'Source hash mismatch: {name}')
    if digest(PREVIOUS) != PREVIOUS_SHA256:
        raise ValueError('Previously accepted Genesis 1-10 store differs from reviewed bytes')
    verify_english_catalog(json.loads(CATALOG_RECEIPT.read_text(encoding='utf-8')), CHAPTER_COUNTS)
    for chapter in range(1, len(CHAPTER_COUNTS) + 1):
        validate_genesis_map(data['VerseMap.xml'], chapter)
    passages = chapter_records(data['Gen.xml'], CHAPTER_COUNTS)
    passages.append(('kjv', 'bcbooks:ps', 3, 1, 'Ps.3.2', parse_passage(data['Ps.xml'], 'Ps.3.2', 'KJV:Ps.3.1')))
    validate_unique_token_ids(passages)

    def build_candidate(path):
        with closing(sqlite3.connect(path)) as conn, conn:
            conn.execute('CREATE TABLE mappings (edition TEXT, book TEXT, chapter INTEGER, verse INTEGER, osis TEXT, PRIMARY KEY(edition,book,chapter,verse))')
            conn.execute('CREATE TABLE tokens (osis TEXT, position INTEGER, token_id TEXT, text TEXT, lemma TEXT, morphology TEXT, PRIMARY KEY(osis,position))')
            for edition, book, chapter, verse, osis, tokens in passages:
                conn.execute('INSERT INTO mappings VALUES (?,?,?,?,?)', (edition, book, chapter, verse, osis))
                conn.executemany('INSERT INTO tokens VALUES (?,?,?,?,?,?)', [(osis, i, *token) for i, token in enumerate(tokens)])
            compare_previous(conn, PREVIOUS)
            if digest(PREVIOUS) != PREVIOUS_SHA256:
                raise ValueError('Previous store changed during comparison')
            if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Candidate integrity check failed')
    publish_candidate(TARGET, build_candidate)
    print(json.dumps({'file': str(TARGET), 'mappings': len(passages), 'tokens': sum(len(p[-1]) for p in passages),
                      'sha256': digest(TARGET), 'status': 'candidate only; no promotion'}, indent=2))


if __name__ == '__main__':
    main()
