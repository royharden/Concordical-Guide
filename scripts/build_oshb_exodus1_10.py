"""Build an isolated, unpromoted OSHB Exodus 1–10 word-study candidate."""
import hashlib,json,sqlite3,xml.etree.ElementTree as ET
from contextlib import closing
from build_oshb_subset import ROOT,RAW,MANIFEST,NS,validate_unique_token_ids
from build_oshb_genesis10 import CATALOG_RECEIPT,compare_previous,digest,publish_candidate,verify_english_catalog
from build_oshb_psalms31_50 import note_claims
from audit_exodus1_10_map import COUNTS,candidates
from oshb_main_reading import primary_and_note_tokens

PREVIOUS=ROOT/'data/generated/word-study/oshb-genesis-psalms1-150-ps13-spans.sqlite'
TARGET=ROOT/'data/generated/word-study/oshb-exodus1-10-candidate.sqlite'
EXOD_MANIFEST=ROOT/'data/manifests/oshb-exodus.json'
PREVIOUS_SHA256='97923d6c5ff339855215b5b047a8daf2e65bca73753632780182ec81b3a548f7'
SOURCE_COUNTS=(22,25,22,31,23,30,29,28,35,29)

def exodus_passages(exod,verse_map,genesis,psalms):
    root=ET.fromstring(exod); candidates_by_target=candidates(verse_map)
    osis=root.find('o:osisText',NS)
    if osis is None or osis.get('osisIDWork')!='OSHB': raise ValueError('Unexpected source identity')
    for ch,count in enumerate(SOURCE_COUNTS,1):
        chapters=[n for n in root.findall('.//o:chapter',NS) if n.get('osisID')==f'Exod.{ch}']
        if len(chapters)!=1 or [v.get('osisID') for v in chapters[0].findall('o:verse',NS)] != [f'Exod.{ch}.{v}' for v in range(1,count+1)]: raise ValueError(f'Unexpected Exodus source coordinates: {ch}')
    nodes={}
    for node in root.findall('.//o:verse',NS):
        ref=node.get('osisID')
        if not ref or ref in nodes: raise ValueError('Missing or duplicate source reference')
        nodes[ref]=node
    claims={}
    for data in (exod,genesis,psalms):
        for target,sources in note_claims(ET.fromstring(data)).items(): claims.setdefault(target,[]).extend(sources)
    passages=[];variant_refs=[]
    for item in candidates_by_target:
        target,osis=item['target'],item['source']; node=nodes.get(osis)
        if node is None: raise ValueError(f'Missing source record: {osis}')
        notes=[(n.text or '')[4:] for n in node.findall('o:note',NS) if (n.text or '').startswith('KJV:')]
        if notes != ([target] if item['kind']=='explicit_full' else []) and not (item['kind']=='identity_candidate' and notes==[target]): raise ValueError(f'Source note conflict: {target}')
        if any(source!=osis for source in claims.get(target,[])): raise ValueError(f'Foreign source claim: {target}')
        tokens,variants=primary_and_note_tokens(node)
        if not tokens or any(not all(t) or not t[3].startswith('H') for t in tokens): raise ValueError(f'Invalid source token: {osis}')
        if variants: variant_refs.append((osis,len(variants)))
        _,ch,v=target.split('.');passages.append(('kjv','bcbooks:ex',int(ch),int(v),osis,tokens))
    if variant_refs != [('Exod.4.2',2)]: raise ValueError('Unexpected note-contained alternate words')
    return passages

def main():
    if TARGET.exists(): raise SystemExit('Candidate exists; do not overwrite')
    base=json.loads(MANIFEST.read_text(encoding='utf8')); additional=json.loads(EXOD_MANIFEST.read_text(encoding='utf-8-sig'))
    if additional['revision']!=base['revision']: raise ValueError('Source revision mismatch')
    data={}
    for name,expected in base['files'].items():
        data[name]=(RAW/name).read_bytes()
        if hashlib.sha256(data[name]).hexdigest()!=expected: raise ValueError(f'Source hash mismatch: {name}')
    data['Exod.xml']=(RAW/'Exod.xml').read_bytes()
    if hashlib.sha256(data['Exod.xml']).hexdigest()!=additional['sha256'] or hashlib.sha256(data['LICENSE.md']).hexdigest()!=additional['license_sha256']: raise ValueError('Exodus source or license mismatch')
    if digest(PREVIOUS)!=PREVIOUS_SHA256: raise ValueError('Previous store hash mismatch')
    verify_english_catalog(json.loads(CATALOG_RECEIPT.read_text(encoding='utf8')),COUNTS,start=1,book_name='Exodus',book_id='bcbooks:ex')
    passages=exodus_passages(data['Exod.xml'],data['VerseMap.xml'],data['Gen.xml'],data['Ps.xml']);validate_unique_token_ids(passages)
    if len(passages)!=274 or sum(len(p[-1]) for p in passages)!=4008: raise ValueError('Unexpected candidate coverage')
    def build(path):
        with closing(sqlite3.connect(PREVIOUS.resolve().as_uri()+'?mode=ro',uri=True)) as old,closing(sqlite3.connect(path)) as conn:
            old.backup(conn)
            with conn:
                for edition,book,ch,v,osis,tokens in passages:
                    conn.execute('INSERT INTO mappings VALUES (?,?,?,?,?)',(edition,book,ch,v,osis))
                    conn.executemany('INSERT INTO tokens VALUES (?,?,?,?,?,?)',[(osis,i,*t) for i,t in enumerate(tokens)])
                compare_previous(conn,PREVIOUS)
                if digest(PREVIOUS)!=PREVIOUS_SHA256: raise ValueError('Previous store changed')
                if conn.execute('SELECT COUNT(*) FROM (SELECT token_id FROM tokens GROUP BY token_id HAVING COUNT(*)>1)').fetchone()[0]: raise ValueError('Duplicate token ID')
                if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Candidate integrity failure')
    publish_candidate(TARGET,build)
    print(json.dumps({'file':str(TARGET),'new_mappings':len(passages),'new_tokens':sum(len(p[-1]) for p in passages),'sha256':digest(TARGET),'status':'isolated candidate only; pending Psalm heading candidate is not included'},indent=2))

if __name__=='__main__': main()
