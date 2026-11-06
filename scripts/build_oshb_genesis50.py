"""Build historical prerequisite data; output mixes note variants into main words.

Do not serve it. Finish with build_oshb_psalms1_10.py's verified correction.
"""
import hashlib
import json
import sqlite3
from contextlib import closing

from build_oshb_subset import MANIFEST, RAW, ROOT, validate_genesis_map, validate_unique_token_ids
from build_oshb_genesis10 import (CATALOG_RECEIPT, chapter_records, compare_previous, digest,
                                  publish_candidate, verify_english_catalog)

TARGET = ROOT / 'data/generated/word-study/oshb-genesis1-30-33-50-candidate.sqlite'
PREVIOUS = ROOT / 'data/generated/word-study/oshb-genesis1-30-candidate.sqlite'
PREVIOUS_SHA256 = '30385a33e83087f22337af99f24b9e4b2835866498e9fa1d7b109d754b9cacb1'
COUNTS = (20, 31, 29, 43, 36, 30, 23, 23, 57, 38, 34, 34, 28, 34, 31, 22, 33, 26)


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
        raise ValueError('Previous store differs from reviewed bytes')
    verify_english_catalog(json.loads(CATALOG_RECEIPT.read_text(encoding='utf-8')), COUNTS, start=33)
    for chapter in range(33, 51):
        validate_genesis_map(data['VerseMap.xml'], chapter)
    passages = chapter_records(data['Gen.xml'], COUNTS, start=33)
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
