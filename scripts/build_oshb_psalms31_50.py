"""Build Psalms 31-50 main readings, excluding contradictory note claims."""
import hashlib
import json
import sqlite3
import xml.etree.ElementTree as ET
from collections import defaultdict
from contextlib import closing
from build_oshb_subset import MANIFEST, RAW, ROOT, NS, validate_unique_token_ids
from build_oshb_genesis10 import CATALOG_RECEIPT, compare_previous, digest, publish_candidate, verify_english_catalog
from oshb_main_reading import primary_and_note_tokens

TARGET = ROOT / 'data/generated/word-study/oshb-genesis-psalms1-50-reviewed-main.sqlite'
PREVIOUS = ROOT / 'data/generated/word-study/oshb-genesis-psalms1-30-except13-5-6-main.sqlite'
PREVIOUS_SHA256 = '920962eeef2a7ecd5246987ec4f31f071cb7d30a7783b9f0f4e401289972603b'
COUNTS = (24,11,22,22,28,12,40,22,13,17,13,11,5,26,17,11,9,14,20,23)
SHIFTED = {31,34,36,38,39,40,41,42,44,45,46,47,48,49}
EXCLUDED = {(42,1),(44,1)}
MAP_NS = {'m': 'http://www.APTBibleTools.com/namespace'}


def note_claims(root):
    claims = defaultdict(list)
    for verse in root.findall('.//o:verse', NS):
        for note in verse.findall('o:note', NS):
            if (note.text or '').startswith('KJV:'):
                claims[note.text[4:]].append(verse.get('osisID'))
    return claims


def ensure_no_foreign_claim(claims, target, expected_source):
    if any(source != expected_source for source in claims.get(target, [])):
        raise ValueError(f'Conflicting incoming source note for {target}')


def psalm_candidates(psalms, verse_map, counts=COUNTS, start=31):
    root = ET.fromstring(psalms)
    vm = ET.fromstring(verse_map)
    chapters = set(range(start, start + len(counts)))
    expected = [(f'Ps.{ch}.{v+1}', f'Ps.{ch}.{v}', 'full')
                for ch,count in enumerate(counts,start) if ch in SHIFTED for v in range(1,count+1)]
    relevant = []
    for entry in vm.findall('.//m:verse', MAP_NS):
        row = tuple(entry.get(k) for k in ('wlc','kjv','type'))
        if any(any((ref or '').startswith(f'Ps.{ch}.') for ch in chapters) for ref in row[:2]):
            relevant.append(row)
    if sorted(relevant) != sorted(expected):
        raise ValueError('Unexpected Psalms reference exception')
    claims = note_claims(root)
    # The two targets are intentionally excluded until this pinned conflict is adjudicated.
    if 42 in chapters and 44 in chapters and sorted(claims.get('Ps.42.1', [])) != ['Ps.42.2','Ps.44.2']:
        raise ValueError('Psalm 42/44 source-note conflict changed; re-review required')
    passages = []
    for ch,count in enumerate(counts,start):
        shifted = ch in SHIFTED
        nodes = [c for c in root.findall('.//o:chapter', NS) if c.get('osisID') == f'Ps.{ch}']
        if len(nodes) != 1:
            raise ValueError(f'Expected exactly one Psalm {ch}')
        verses = nodes[0].findall('o:verse', NS)
        if [v.get('osisID') for v in verses] != [f'Ps.{ch}.{n}' for n in range(1,count+1+int(shifted))]:
            raise ValueError(f'Unexpected source coordinates for Psalm {ch}')
        for verse in range(1,count+1):
            if (ch,verse) in EXCLUDED:
                continue
            target = f'Ps.{ch}.{verse}'
            osis = f'Ps.{ch}.{verse+int(shifted)}'
            node = verses[verse-1+int(shifted)]
            notes = [(n.text or '')[4:] for n in node.findall('o:note', NS) if (n.text or '').startswith('KJV:')]
            if (shifted and notes != [target]) or (not shifted and notes not in ([],[target])):
                raise ValueError(f'Conflicting source note for {target}')
            ensure_no_foreign_claim(claims,target,osis)
            tokens,_note_tokens = primary_and_note_tokens(node)
            if not tokens or any(not tid or not text or not lemma or not morph or not morph.startswith('H')
                                 for tid,text,lemma,morph in tokens):
                raise ValueError(f'Missing source metadata or unsupported language: {osis}')
            passages.append(('kjv','bcbooks:ps',ch,verse,osis,tokens))
    return passages


def main():
    if TARGET.exists():
        raise SystemExit('Candidate exists; do not overwrite it')
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    data = {}
    for name,expected_hash in manifest['files'].items():
        data[name] = (RAW/name).read_bytes()
        if hashlib.sha256(data[name]).hexdigest() != expected_hash:
            raise ValueError(f'Source hash mismatch: {name}')
    if digest(PREVIOUS) != PREVIOUS_SHA256:
        raise ValueError('Previous corrected store hash mismatch')
    verify_english_catalog(json.loads(CATALOG_RECEIPT.read_text(encoding='utf-8')), COUNTS,
                           start=31,book_name='Psalms',book_id='bcbooks:ps')
    passages = psalm_candidates(data['Ps.xml'],data['VerseMap.xml'])
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
                      'sha256':digest(TARGET),'status':'candidate only; Psalm 42:1 and 44:1 unavailable'},indent=2))


if __name__ == '__main__':
    main()
