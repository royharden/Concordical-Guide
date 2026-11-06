"""Build a fail-closed, labeled local adjudication for Psalm 42:1 and 44:1."""
import hashlib,json,sqlite3,xml.etree.ElementTree as ET
from contextlib import closing
from build_oshb_subset import ROOT,RAW,MANIFEST,NS,validate_unique_token_ids
from build_oshb_genesis10 import CATALOG_RECEIPT,RAW_ENGLISH,compare_previous,digest,publish_candidate,verify_english_catalog
from build_oshb_psalms31_50 import note_claims
from oshb_main_reading import primary_and_note_tokens

PREVIOUS=ROOT/'data/generated/word-study/oshb-psalm-headings-exodus1-40-candidate.sqlite'
TARGET=ROOT/'data/generated/word-study/oshb-psalm42-44-adjudicated-candidate.sqlite'
DECISION=ROOT/'data/manifests/psalm42-44-adjudication.json'
EXOD_MANIFEST=ROOT/'data/manifests/oshb-exodus.json'
PREVIOUS_SHA256='937913fb3768ee4a45a894998de38a1d0d8657a8a965a87aad9af1851acac071'
MAP_NS={'m':'http://www.APTBibleTools.com/namespace'}
IDS={42:['19rR7','195jH','195us','19Kgs','19Zij','19VE6','19iDE','19dza','19FBM','19RBD'],44:['19nt7','19Pk3','19sGy','19g9J','19ZYF','19mjh','19ugU','19XTu','19aA5','196n5','19bTj']}

def adjudicated_passages(psalms,verse_map,genesis,exodus):
    root=ET.fromstring(psalms);vm=ET.fromstring(verse_map)
    expected=[('Ps.42.2','Ps.42.1','full'),('Ps.44.2','Ps.44.1','full')]
    edges=[tuple(e.get(k) for k in ('wlc','kjv','type')) for e in vm.findall('.//m:verse',MAP_NS) if e.get('wlc') in ('Ps.42.2','Ps.44.2') or e.get('kjv') in ('Ps.42.1','Ps.44.1')]
    if sorted(edges)!=sorted(expected): raise ValueError('Adjudicated map edges changed')
    claims={}
    for data in (psalms,genesis,exodus):
        for target,sources in note_claims(ET.fromstring(data)).items(): claims.setdefault(target,[]).extend(sources)
    if sorted(claims.get('Ps.42.1',[]))!=['Ps.42.2','Ps.44.2'] or claims.get('Ps.44.1',[])!=[]: raise ValueError('Pinned conflicting claims changed; re-review required')
    out=[]
    for ch in (42,44):
        osis=f'Ps.{ch}.2';nodes=[n for n in root.findall('.//o:verse',NS) if n.get('osisID')==osis]
        if len(nodes)!=1: raise ValueError(f'Unexpected source record: {osis}')
        notes=[(n.text or '') for n in nodes[0].findall('o:note',NS) if (n.text or '').startswith('KJV:')]
        if notes!=['KJV:Ps.42.1']: raise ValueError(f'Pinned note changed: {osis}')
        tokens,variants=primary_and_note_tokens(nodes[0])
        if variants or [t[0] for t in tokens]!=IDS[ch] or any(not all(t) or not t[3].startswith('H') for t in tokens): raise ValueError(f'Source tokens changed: {osis}')
        out.append(('kjv','bcbooks:ps',ch,1,osis,tokens))
    return out

def main():
    if TARGET.exists(): raise SystemExit('Candidate exists; do not overwrite')
    manifest=json.loads(MANIFEST.read_text(encoding='utf8'));extra=json.loads(EXOD_MANIFEST.read_text(encoding='utf-8-sig'));decision=json.loads(DECISION.read_text(encoding='utf-8-sig'));data={}
    if decision['id']!='psalm-42-44-local-reference-adjudication-v1' or decision['source_revision']!=manifest['revision'] or extra['revision']!=manifest['revision']: raise ValueError('Adjudication or source revision mismatch')
    if decision['ps_xml_sha256']!=manifest['files']['Ps.xml'] or decision['verse_map_sha256']!=manifest['files']['VerseMap.xml']: raise ValueError('Decision provenance mismatch')
    expected_cases=[{'target':'Ps.42.1','source':'Ps.42.2','source_note':'KJV:Ps.42.1','competing_source_note':'Ps.44.2:KJV:Ps.42.1'},{'target':'Ps.44.1','source':'Ps.44.2','source_note':'KJV:Ps.42.1','competing_source_note':'Ps.42.2:KJV:Ps.42.1'}]
    if decision['cases']!=expected_cases: raise ValueError('Decision scope changed')
    for name,expected in manifest['files'].items():
        data[name]=(RAW/name).read_bytes()
        if hashlib.sha256(data[name]).hexdigest()!=expected: raise ValueError(f'Source hash mismatch: {name}')
    data['Exod.xml']=(RAW/'Exod.xml').read_bytes()
    if hashlib.sha256(data['Exod.xml']).hexdigest()!=extra['sha256']: raise ValueError('Exodus source hash mismatch')
    receipt=json.loads(CATALOG_RECEIPT.read_text(encoding='utf8')); raw=RAW_ENGLISH.read_bytes(); entry=next(e for e in receipt['source_files'] if e['path'].endswith('/old-testament.json'))
    if receipt['db_sha256']!=decision['local_kjv_catalog_sha256'] or entry['sha256']!=decision['local_kjv_source_sha256'] or hashlib.sha256(raw).hexdigest()!=entry['sha256']: raise ValueError('Adjudication KJV receipt mismatch')
    for ch,count in ((42,11),(44,26)): verify_english_catalog(receipt,(count,),start=ch,book_name='Psalms',book_id='bcbooks:ps')
    if digest(PREVIOUS)!=PREVIOUS_SHA256: raise ValueError('Previous checkpoint hash mismatch')
    passages=adjudicated_passages(data['Ps.xml'],data['VerseMap.xml'],data['Gen.xml'],data['Exod.xml']);validate_unique_token_ids(passages)
    def build(path):
        with closing(sqlite3.connect(PREVIOUS.resolve().as_uri()+'?mode=ro',uri=True)) as old,closing(sqlite3.connect(path)) as conn:
            old.backup(conn)
            with conn:
                conn.execute("CREATE TABLE mapping_adjudications (edition TEXT NOT NULL, book TEXT NOT NULL, chapter INTEGER NOT NULL, verse INTEGER NOT NULL, decision_id TEXT NOT NULL, PRIMARY KEY(edition,book,chapter,verse))")
                for edition,book,ch,v,osis,tokens in passages:
                    conn.execute('INSERT INTO mappings VALUES (?,?,?,?,?)',(edition,book,ch,v,osis))
                    conn.execute('INSERT INTO mapping_adjudications VALUES (?,?,?,?,?)',(edition,book,ch,v,decision['id']))
                    conn.executemany('INSERT INTO tokens VALUES (?,?,?,?,?,?)',[(osis,i,*t) for i,t in enumerate(tokens)])
                compare_previous(conn,PREVIOUS)
                q='SELECT edition,book,chapter,verse,role,osis FROM source_segments ORDER BY edition,book,chapter,verse,role';segs=old.execute(q).fetchall()
                if len(segs)!=4 or conn.execute(q).fetchall()!=segs: raise ValueError('Heading metadata changed')
                for row in segs:
                    t='SELECT osis,position,token_id,text,lemma,morphology FROM tokens WHERE osis=? ORDER BY position'
                    if old.execute(t,(row[-1],)).fetchall()!=conn.execute(t,(row[-1],)).fetchall(): raise ValueError('Heading excerpt changed')
                if digest(PREVIOUS)!=PREVIOUS_SHA256: raise ValueError('Prior store changed')
                if conn.execute('SELECT COUNT(*) FROM (SELECT token_id FROM tokens GROUP BY token_id HAVING COUNT(*)>1)').fetchone()[0]: raise ValueError('Duplicate source token')
                if conn.execute("SELECT COUNT(*) FROM tokens t WHERE NOT EXISTS (SELECT 1 FROM mappings m WHERE m.osis=t.osis) AND NOT EXISTS (SELECT 1 FROM source_segments s WHERE s.osis=t.osis)").fetchone()[0]: raise ValueError('Unreferenced source tokens')
                if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Integrity failure')
    publish_candidate(TARGET,build)
    print(json.dumps({'file':str(TARGET),'new_mappings':2,'new_tokens':sum(len(p[-1]) for p in passages),'sha256':digest(TARGET),'status':'locally adjudicated isolated candidate only'},indent=2))

if __name__=='__main__': main()
