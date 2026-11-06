"""Build a labeled, fail-closed two-source Numbers 26:1 adjudication candidate."""
import hashlib,json,sqlite3,xml.etree.ElementTree as ET
from contextlib import closing
from build_oshb_subset import ROOT,RAW,MANIFEST,NS,validate_unique_token_ids
from build_oshb_genesis10 import CATALOG_RECEIPT,RAW_ENGLISH,compare_previous,digest,publish_candidate,verify_english_catalog
from build_oshb_psalms31_50 import note_claims
from oshb_main_reading import primary_and_note_tokens

PREVIOUS=ROOT/'data/generated/word-study/oshb-numbers1-36-except26-1-candidate.sqlite'
TARGET=ROOT/'data/generated/word-study/oshb-numbers26-1-adjudicated-candidate.sqlite'
PREVIOUS_SHA256='1257b5c5a4396b400d9af00fe8a59939c029f26a2dec7707cac55b0b833458da'
DECISION=ROOT/'data/manifests/numbers26-1-adjudication.json'
PINS={'Exod.xml':ROOT/'data/manifests/oshb-exodus.json','Lev.xml':ROOT/'data/manifests/oshb-leviticus.json','Num.xml':ROOT/'data/manifests/oshb-numbers.json'}
MAP_NS={'m':'http://www.APTBibleTools.com/namespace'}
IDS={'Num.25.19':['04xYD','04Y15','047YH'],'Num.26.1':['04Scg','04VfY','043CP','04JCV','04kSK','04Dw8','04v1s','04Hhz','046Hr','04NqA']}

def adjudicated_parts(num,verse_map,genesis,exodus,leviticus,psalms):
    root=ET.fromstring(num);vm=ET.fromstring(verse_map);target='Num.26.1';sources=list(IDS)
    edges=[tuple(e.get(k) for k in ('wlc','kjv','type')) for e in vm.findall('.//m:verse',MAP_NS) if e.get('wlc') in sources or e.get('kjv')==target]
    if edges!=[('Num.25.19','Num.26.1','full')]: raise ValueError('Pinned incomplete map evidence changed')
    claims={}
    for data in (num,genesis,exodus,leviticus,psalms):
        for ref,values in note_claims(ET.fromstring(data)).items(): claims.setdefault(ref,[]).extend(values)
    if claims.get(target,[])!=['Num.25.19']: raise ValueError('Pinned KJV note claims changed')
    for ch,count in ((25,19),(26,65)):
        nodes=[n for n in root.findall('.//o:chapter',NS) if n.get('osisID')==f'Num.{ch}']
        if len(nodes)!=1 or [v.get('osisID') for v in nodes[0].findall('o:verse',NS)]!=[f'Num.{ch}.{v}' for v in range(1,count+1)]: raise ValueError('Source chapter boundary changed')
    parts=[]
    for index,osis in enumerate(sources):
        nodes=[n for n in root.findall('.//o:verse',NS) if n.get('osisID')==osis]
        if len(nodes)!=1: raise ValueError(f'Unexpected source record: {osis}')
        notes=[(n.text or '') for n in nodes[0].findall('o:note',NS) if (n.text or '').startswith('KJV:')]
        if notes!=(['KJV:Num.26.1'] if index==0 else []): raise ValueError(f'Pinned source notes changed: {osis}')
        tokens,variants=primary_and_note_tokens(nodes[0])
        if variants or [t[0] for t in tokens]!=IDS[osis] or any(not all(t) or not t[3].startswith('H') for t in tokens): raise ValueError(f'Source tokens changed: {osis}')
        parts.append((osis,tokens))
    return parts

def main():
    if TARGET.exists(): raise SystemExit('Candidate exists; do not overwrite')
    base=json.loads(MANIFEST.read_text(encoding='utf8'));decision=json.loads(DECISION.read_text(encoding='utf-8-sig'));data={}
    if decision['id']!='numbers26-1-local-reference-adjudication-v1' or decision['source_revision']!=base['revision'] or decision['target']!='Num.26.1' or decision['source_parts']!=list(IDS): raise ValueError('Decision scope or revision changed')
    if decision['source_map_edge']!={'wlc':'Num.25.19','kjv':'Num.26.1','type':'full'} or decision['verse_map_sha256']!=base['files']['VerseMap.xml']: raise ValueError('Decision map evidence changed')
    for name,expected in base['files'].items():
        data[name]=(RAW/name).read_bytes()
        if hashlib.sha256(data[name]).hexdigest()!=expected: raise ValueError(f'Source hash mismatch: {name}')
    for name,path in PINS.items():
        pin=json.loads(path.read_text(encoding='utf-8-sig'));data[name]=(RAW/name).read_bytes()
        if pin['revision']!=base['revision'] or hashlib.sha256(data[name]).hexdigest()!=pin['sha256'] or hashlib.sha256(data['LICENSE.md']).hexdigest()!=pin['license_sha256']: raise ValueError(f'Source/license mismatch: {name}')
    if hashlib.sha256(data['Num.xml']).hexdigest()!=decision['numbers_xml_sha256']: raise ValueError('Decision source hash mismatch')
    receipt=json.loads(CATALOG_RECEIPT.read_text(encoding='utf8'));raw=RAW_ENGLISH.read_bytes();entry=next(e for e in receipt['source_files'] if e['path'].endswith('/old-testament.json'))
    if receipt['db_sha256']!=decision['local_kjv_catalog_sha256'] or entry['sha256']!=decision['local_kjv_source_sha256'] or hashlib.sha256(raw).hexdigest()!=entry['sha256']: raise ValueError('Adjudication KJV receipt mismatch')
    verify_english_catalog(receipt,(18,65),start=25,book_name='Numbers',book_id='bcbooks:num')
    if digest(PREVIOUS)!=PREVIOUS_SHA256: raise ValueError('Prior checkpoint hash mismatch')
    parts=adjudicated_parts(data['Num.xml'],data['VerseMap.xml'],data['Gen.xml'],data['Exod.xml'],data['Lev.xml'],data['Ps.xml'])
    validate_unique_token_ids([('kjv','bcbooks:num',26,1,osis,tokens) for osis,tokens in parts])
    def build(path):
        with closing(sqlite3.connect(PREVIOUS.resolve().as_uri()+'?mode=ro',uri=True)) as old,closing(sqlite3.connect(path)) as conn:
            old.backup(conn)
            with conn:
                conn.execute('CREATE TABLE mapping_source_parts (edition TEXT NOT NULL,book TEXT NOT NULL,chapter INTEGER NOT NULL,verse INTEGER NOT NULL,ordinal INTEGER NOT NULL,osis TEXT NOT NULL,PRIMARY KEY(edition,book,chapter,verse,ordinal))')
                conn.execute('INSERT INTO mappings VALUES (?,?,?,?,?)',('kjv','bcbooks:num',26,1,'Num.25.19+Num.26.1'))
                conn.execute('INSERT INTO mapping_adjudications VALUES (?,?,?,?,?)',('kjv','bcbooks:num',26,1,decision['id']))
                for index,(osis,tokens) in enumerate(parts):
                    conn.execute('INSERT INTO mapping_source_parts VALUES (?,?,?,?,?,?)',('kjv','bcbooks:num',26,1,index,osis))
                    conn.executemany('INSERT INTO tokens VALUES (?,?,?,?,?,?)',[(osis,i,*t) for i,t in enumerate(tokens)])
                compare_previous(conn,PREVIOUS)
                q='SELECT edition,book,chapter,verse,role,osis FROM source_segments ORDER BY edition,book,chapter,verse,role';segs=old.execute(q).fetchall()
                if len(segs)!=4 or conn.execute(q).fetchall()!=segs: raise ValueError('Heading metadata changed')
                for row in segs:
                    sql='SELECT osis,position,token_id,text,lemma,morphology FROM tokens WHERE osis=? ORDER BY position'
                    if old.execute(sql,(row[-1],)).fetchall()!=conn.execute(sql,(row[-1],)).fetchall(): raise ValueError('Heading words changed')
                old_decisions=old.execute('SELECT * FROM mapping_adjudications ORDER BY 1,2,3,4').fetchall();new_decisions=conn.execute('SELECT * FROM mapping_adjudications ORDER BY 1,2,3,4').fetchall()
                if len(old_decisions)!=2 or any(row not in new_decisions for row in old_decisions) or len(new_decisions)!=3: raise ValueError('Prior adjudications changed')
                if digest(PREVIOUS)!=PREVIOUS_SHA256: raise ValueError('Prior store changed')
                if conn.execute('SELECT COUNT(*) FROM (SELECT token_id FROM tokens GROUP BY token_id HAVING COUNT(*)>1)').fetchone()[0]: raise ValueError('Duplicate source token')
                if conn.execute("SELECT COUNT(*) FROM tokens t WHERE NOT EXISTS (SELECT 1 FROM mappings m WHERE m.osis=t.osis) AND NOT EXISTS (SELECT 1 FROM source_segments s WHERE s.osis=t.osis) AND NOT EXISTS (SELECT 1 FROM mapping_source_parts p WHERE p.osis=t.osis)").fetchone()[0]: raise ValueError('Unreferenced source tokens')
                if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Integrity failure')
    publish_candidate(TARGET,build)
    print(json.dumps({'file':str(TARGET),'new_mappings':1,'new_tokens':sum(len(t) for _,t in parts),'sha256':digest(TARGET),'status':'locally adjudicated isolated candidate only'},indent=2))

if __name__=='__main__': main()
