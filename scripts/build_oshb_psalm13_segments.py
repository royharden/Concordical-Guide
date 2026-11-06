"""Build audited Psalm 13 partial source-word spans; leave other exceptions unavailable."""
import hashlib
import json
import sqlite3
import xml.etree.ElementTree as ET
from contextlib import closing
from build_oshb_subset import ROOT, RAW, MANIFEST, NS, validate_unique_token_ids
from build_oshb_genesis10 import CATALOG_RECEIPT, compare_previous, digest, publish_candidate, verify_english_catalog
from build_oshb_psalms31_50 import note_claims
from oshb_main_reading import primary_and_note_tokens

PREVIOUS = ROOT / 'data/generated/word-study/oshb-genesis-psalms1-150-reviewed-main.sqlite'
TARGET = ROOT / 'data/generated/word-study/oshb-genesis-psalms1-150-ps13-spans.sqlite'
PREVIOUS_SHA256 = '111e68c598d9f22f59557ccea1ffd4ec0be209f68818309434105ccef5d4bea5'
MAP_NS = {'m':'http://www.APTBibleTools.com/namespace'}
EXPECTED_IDS = ['19FQu','19rxc','19185','19ssA','19un2','194Ei','19wp8','19fZr','19qsm','19Yvd','19qo8']

def split_passages(psalms, verse_map):
    root=ET.fromstring(psalms); vm=ET.fromstring(verse_map)
    expected=[(f'Ps.13.{i+1}',f'Ps.13.{i}','full') for i in range(1,5)] + [('Ps.13.6!a','Ps.13.5','partial'),('Ps.13.6!b','Ps.13.6','partial')]
    rows=[tuple(e.get(k) for k in ('wlc','kjv','type')) for e in vm.findall('.//m:verse',MAP_NS) if any((e.get(k) or '').startswith('Ps.13.') for k in ('wlc','kjv'))]
    if sorted(rows)!=sorted(expected): raise ValueError('Psalm 13 source map differs from reviewed edges')
    claims=note_claims(root)
    if claims.get('Ps.13.5')!=['Ps.13.6'] or claims.get('Ps.13.6')!=['Ps.13.6']:
        raise ValueError('Psalm 13 source note claims changed')
    nodes=[v for v in root.findall('.//o:verse',NS) if v.get('osisID')=='Ps.13.6']
    if len(nodes)!=1: raise ValueError('Expected one source Ps.13.6')
    node=nodes[0]; primary,alternates=primary_and_note_tokens(node)
    if [t[0] for t in primary]!=EXPECTED_IDS or any(not all(t) or not t[3].startswith('H') for t in primary):
        raise ValueError('Psalm 13 primary tokens differ from reviewed source')
    active=None; groups={'Ps.13.5':[],'Ps.13.6':[]}; marks=[]
    for child in node:
        if child.tag == '{'+NS['o']+'}note' and (child.text or '').startswith('KJV:'):
            active=child.text[4:]; marks.append((active,sum(len(x) for x in groups.values())))
            if active not in groups: raise ValueError('Unexpected KJV marker')
        elif child.tag == '{'+NS['o']+'}w':
            if active is None: raise ValueError('Word before first KJV marker')
            groups[active].append(child.get('id'))
    if marks != [('Ps.13.5',0),('Ps.13.6',6)] or groups['Ps.13.5']!=EXPECTED_IDS[:6] or groups['Ps.13.6']!=EXPECTED_IDS[6:]:
        raise ValueError('Psalm 13 marker ordering or token boundary changed')
    if alternates: raise ValueError('Psalm 13 source note variants require review')
    return [('kjv','bcbooks:ps',13,5,'Ps.13.6!a',primary[:6]),('kjv','bcbooks:ps',13,6,'Ps.13.6!b',primary[6:])]

def main():
    if TARGET.exists(): raise SystemExit('Candidate exists; do not overwrite it')
    manifest=json.loads(MANIFEST.read_text(encoding='utf-8')); data={}
    for name,expected in manifest['files'].items():
        data[name]=(RAW/name).read_bytes()
        if hashlib.sha256(data[name]).hexdigest()!=expected: raise ValueError(f'Source hash mismatch: {name}')
    if digest(PREVIOUS)!=PREVIOUS_SHA256: raise ValueError('Previous store hash mismatch')
    verify_english_catalog(json.loads(CATALOG_RECEIPT.read_text(encoding='utf-8')),(6,),start=13,book_name='Psalms',book_id='bcbooks:ps')
    passages=split_passages(data['Ps.xml'],data['VerseMap.xml']); validate_unique_token_ids(passages)
    def build(path):
        with closing(sqlite3.connect(PREVIOUS.resolve().as_uri()+'?mode=ro',uri=True)) as old, closing(sqlite3.connect(path)) as conn:
            old.backup(conn)
            with conn:
                for edition,book,ch,v,osis,tokens in passages:
                    conn.execute('INSERT INTO mappings VALUES (?,?,?,?,?)',(edition,book,ch,v,osis))
                    conn.executemany('INSERT INTO tokens VALUES (?,?,?,?,?,?)',[(osis,i,*t) for i,t in enumerate(tokens)])
                compare_previous(conn,PREVIOUS)
                if digest(PREVIOUS)!=PREVIOUS_SHA256: raise ValueError('Previous store changed')
                if conn.execute('SELECT COUNT(*) FROM (SELECT token_id FROM tokens GROUP BY token_id HAVING COUNT(*)>1)').fetchone()[0]: raise ValueError('Duplicate token ID')
                if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Integrity failure')
    publish_candidate(TARGET,build)
    print(json.dumps({'file':str(TARGET),'new_mappings':len(passages),'new_tokens':sum(len(p[-1]) for p in passages),'sha256':digest(TARGET),'status':'candidate; six other exceptions unavailable'},indent=2))

if __name__=='__main__': main()
