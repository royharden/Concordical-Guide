"""Build Psalms 126-150 audited primary readings."""
import hashlib
import json
import sqlite3
import xml.etree.ElementTree as ET
from contextlib import closing
from build_oshb_subset import MANIFEST, RAW, ROOT, NS, validate_unique_token_ids
from build_oshb_genesis10 import CATALOG_RECEIPT, compare_previous, digest, publish_candidate, verify_english_catalog
from build_oshb_psalms31_50 import note_claims, ensure_no_foreign_claim
from oshb_main_reading import primary_and_note_tokens

TARGET = ROOT / 'data/generated/word-study/oshb-genesis-psalms1-150-reviewed-main.sqlite'
PREVIOUS = ROOT / 'data/generated/word-study/oshb-genesis-psalms1-125-reviewed-main.sqlite'
PREVIOUS_SHA256 = '7abf1cdb890204f595ac7939fad022238817f3be28fd509e0d3fab0b4a042813'
COUNTS = (6,5,6,8,8,3,18,3,3,21,26,9,8,24,13,10,7,12,15,21,10,20,14,9,6)
SHIFTED = {140,142}
MULTIPLE = set()
MAP_NS = {'m': 'http://www.APTBibleTools.com/namespace'}


def psalm_candidates(psalms, verse_map, counts=COUNTS, start=126):
    root = ET.fromstring(psalms)
    vm = ET.fromstring(verse_map)
    chapters = set(range(start,start+len(counts)))
    expected = []
    for ch,count in enumerate(counts,start):
        if ch in MULTIPLE:
            expected.extend([(f'Ps.{ch}.2',f'Ps.{ch}.1','full'),(f'Ps.{ch}.3',f'Ps.{ch}.1','full')])
            expected.extend((f'Ps.{ch}.{v+2}',f'Ps.{ch}.{v}','full') for v in range(2,count+1))
        elif ch in SHIFTED:
            expected.extend((f'Ps.{ch}.{v+1}',f'Ps.{ch}.{v}','full') for v in range(1,count+1))
    relevant = []
    for entry in vm.findall('.//m:verse',MAP_NS):
        row = tuple(entry.get(k) for k in ('wlc','kjv','type'))
        if any(any((ref or '').startswith(f'Ps.{ch}.') for ch in chapters) for ref in row[:2]):
            relevant.append(row)
    if sorted(relevant) != sorted(expected):
        raise ValueError('Unexpected Psalms reference exception or multiple-source mapping')
    claims = note_claims(root)
    passages = []
    for ch,count in enumerate(counts,start):
        offset = 2 if ch in MULTIPLE else 1 if ch in SHIFTED else 0
        nodes = [c for c in root.findall('.//o:chapter',NS) if c.get('osisID')==f'Ps.{ch}']
        if len(nodes)!=1:
            raise ValueError(f'Expected exactly one Psalm {ch}')
        verses = nodes[0].findall('o:verse',NS)
        if [v.get('osisID') for v in verses] != [f'Ps.{ch}.{n}' for n in range(1,count+offset+1)]:
            raise ValueError(f'Unexpected source coordinates for Psalm {ch}')
        for verse in range(1,count+1):
            if ch in MULTIPLE and verse==1:
                continue  # Multiple source verses cannot be represented by this API.
            target=f'Ps.{ch}.{verse}'
            osis=f'Ps.{ch}.{verse+offset}'
            node=verses[verse-1+offset]
            notes=[(n.text or '')[4:] for n in node.findall('o:note',NS) if (n.text or '').startswith('KJV:')]
            if (offset and notes != [target]) or (not offset and notes not in ([],[target])):
                raise ValueError(f'Conflicting source note for {target}')
            ensure_no_foreign_claim(claims,target,osis)
            tokens,_note_tokens=primary_and_note_tokens(node)
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
    for name,expected_hash in manifest['files'].items():
        data[name]=(RAW/name).read_bytes()
        if hashlib.sha256(data[name]).hexdigest()!=expected_hash:
            raise ValueError(f'Source hash mismatch: {name}')
    if digest(PREVIOUS)!=PREVIOUS_SHA256:
        raise ValueError('Previous corrected store hash mismatch')
    verify_english_catalog(json.loads(CATALOG_RECEIPT.read_text(encoding='utf-8')),COUNTS,
                           start=126,book_name='Psalms',book_id='bcbooks:ps')
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
                    compare_previous(conn,PREVIOUS)
                    if digest(PREVIOUS)!=PREVIOUS_SHA256:
                        raise ValueError('Previous store changed during build')
                    if conn.execute('SELECT COUNT(*) FROM (SELECT token_id FROM tokens GROUP BY token_id HAVING COUNT(*) > 1)').fetchone()[0]:
                        raise ValueError('Source token ID duplicated across batches')
                    if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                        raise ValueError('Candidate integrity check failed')
    publish_candidate(TARGET,build)
    print(json.dumps({'file':str(TARGET),'new_mappings':len(passages),'new_tokens':sum(len(p[-1]) for p in passages),
                      'sha256':digest(TARGET),'status':'candidate only; multiple-source targets unavailable'},indent=2))


if __name__=='__main__':
    main()
