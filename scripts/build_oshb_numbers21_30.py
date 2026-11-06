"""Build isolated Numbers 21-30; withhold the unresolved 26:1 join."""
import hashlib,json,sqlite3,xml.etree.ElementTree as ET
from contextlib import closing
from build_oshb_subset import ROOT,RAW,MANIFEST,NS,validate_unique_token_ids
from build_oshb_genesis10 import CATALOG_RECEIPT,compare_previous,digest,publish_candidate,verify_english_catalog
from build_oshb_psalms31_50 import note_claims
from oshb_main_reading import primary_and_note_tokens

PREVIOUS=ROOT/'data/generated/word-study/oshb-numbers1-20-candidate.sqlite'
TARGET=ROOT/'data/generated/word-study/oshb-numbers1-30-except26-1-candidate.sqlite'
PREVIOUS_SHA256='d4587fa9ad1316f3a32bfcfc1195228a7a62790577490e772b8d8d2e42984c8e'
LEV_MANIFEST=ROOT/'data/manifests/oshb-leviticus.json'
NUM_MANIFEST=ROOT/'data/manifests/oshb-numbers.json'
EXOD_MANIFEST=ROOT/'data/manifests/oshb-exodus.json'
COUNTS=(35,41,30,25,18,65,23,31,40,16)
SOURCE_COUNTS=(35,41,30,25,19,65,23,31,39,17)
MAP_NS={'m':'http://www.APTBibleTools.com/namespace'}

def numbers_passages(num,verse_map,genesis,exodus,leviticus,psalms):
    root=ET.fromstring(num);vm=ET.fromstring(verse_map)
    if root.find('o:osisText',NS) is None or root.find('o:osisText',NS).get('osisIDWork')!='OSHB': raise ValueError('Unexpected source identity')
    expected=[('Num.25.19','Num.26.1','full'),('Num.30.1','Num.29.40','full')]+[(f'Num.30.{v+1}',f'Num.30.{v}','full') for v in range(1,17)]
    edges=[]
    for e in vm.findall('.//m:verse',MAP_NS):
        row=tuple(e.get(k) for k in ('wlc','kjv','type'))
        if any((ref or '').startswith('Num.') and len(ref.split('.'))>=3 and ref.split('.')[1].isdigit() and 21<=int(ref.split('.')[1])<=30 for ref in row[:2]): edges.append(row)
    if sorted(edges)!=sorted(expected): raise ValueError('Unexpected Numbers 21–30 map edge')
    incoming={target:source for source,target,_ in edges}
    if len(incoming)!=len(edges): raise ValueError('Duplicate map target')
    claims={}
    for data in (num,genesis,exodus,leviticus,psalms):
        for target,sources in note_claims(ET.fromstring(data)).items(): claims.setdefault(target,[]).extend(sources)
    nodes={}
    for node in root.findall('.//o:verse',NS):
        ref=node.get('osisID')
        if not ref or ref in nodes: raise ValueError('Missing or duplicate source reference')
        nodes[ref]=node
    for ch,count in enumerate(SOURCE_COUNTS,21):
        chapters=[n for n in root.findall('.//o:chapter',NS) if n.get('osisID')==f'Num.{ch}']
        if len(chapters)!=1 or [v.get('osisID') for v in chapters[0].findall('o:verse',NS)]!=[f'Num.{ch}.{v}' for v in range(1,count+1)]: raise ValueError(f'Unexpected source coordinates: {ch}')
    out=[];variants=[];seen=set()
    for ch,count in enumerate(COUNTS,21):
        for v in range(1,count+1):
            target=f'Num.{ch}.{v}'
            if target=='Num.26.1': continue  # Map omits additional source Num.26.1; never expose a partial verse as complete.
            osis=incoming.get(target,target);node=nodes.get(osis)
            if node is None or osis in seen: raise ValueError(f'Missing or reused source: {osis}')
            seen.add(osis)
            notes=[(n.text or '')[4:] for n in node.findall('o:note',NS) if (n.text or '').startswith('KJV:')]
            if notes != ([target] if target in incoming else []) and not (target not in incoming and notes==[target]): raise ValueError(f'Conflicting source note: {target}')
            if any(other!=osis for other in claims.get(target,[])): raise ValueError(f'Foreign source claim: {target}')
            tokens,alts=primary_and_note_tokens(node)
            if not tokens or any(not all(t) or not t[3].startswith('H') for t in tokens): raise ValueError(f'Invalid source token: {osis}')
            if alts: variants.append((osis,len(alts)))
            out.append(('kjv','bcbooks:num',ch,v,osis,tokens))
    source_refs={f'Num.{ch}.{v}' for ch,count in enumerate(SOURCE_COUNTS,21) for v in range(1,count+1)}
    if source_refs-seen != {'Num.25.19','Num.26.1'}: raise ValueError('Unexpected unselected source references')
    if claims.get('Num.26.1',[]) != ['Num.25.19']: raise ValueError('Numbers 26:1 source note changed')
    if variants!=[('Num.21.32',1),('Num.23.13',1),('Num.26.9',1)]: raise ValueError('Unexpected alternate words')
    return out

def main():
    if TARGET.exists(): raise SystemExit('Candidate exists; do not overwrite')
    base=json.loads(MANIFEST.read_text(encoding='utf8'));extra=json.loads(EXOD_MANIFEST.read_text(encoding='utf-8-sig'));levpin=json.loads(LEV_MANIFEST.read_text(encoding='utf-8-sig'));numpin=json.loads(NUM_MANIFEST.read_text(encoding='utf-8-sig'));data={}
    if any(pin['revision']!=base['revision'] for pin in (extra,levpin,numpin)): raise ValueError('Source revision mismatch')
    for name,expected in base['files'].items():
        data[name]=(RAW/name).read_bytes()
        if hashlib.sha256(data[name]).hexdigest()!=expected: raise ValueError(f'Source hash mismatch: {name}')
    for name,pin in (('Exod.xml',extra),('Lev.xml',levpin),('Num.xml',numpin)):
        data[name]=(RAW/name).read_bytes()
        if hashlib.sha256(data[name]).hexdigest()!=pin['sha256'] or hashlib.sha256(data['LICENSE.md']).hexdigest()!=pin['license_sha256']: raise ValueError(f'Source or license mismatch: {name}')
    if digest(PREVIOUS)!=PREVIOUS_SHA256: raise ValueError('Prior checkpoint hash mismatch')
    verify_english_catalog(json.loads(CATALOG_RECEIPT.read_text(encoding='utf8')),COUNTS,start=21,book_name='Numbers',book_id='bcbooks:num')
    passages=numbers_passages(data['Num.xml'],data['VerseMap.xml'],data['Gen.xml'],data['Exod.xml'],data['Lev.xml'],data['Ps.xml']);validate_unique_token_ids(passages)
    if len(passages)!=323 or sum(len(p[-1]) for p in passages)!=4062: raise ValueError('Unexpected candidate totals')
    def build(path):
        with closing(sqlite3.connect(PREVIOUS.resolve().as_uri()+'?mode=ro',uri=True)) as old,closing(sqlite3.connect(path)) as conn:
            old.backup(conn)
            with conn:
                for edition,book,ch,v,osis,tokens in passages:
                    conn.execute('INSERT INTO mappings VALUES (?,?,?,?,?)',(edition,book,ch,v,osis))
                    conn.executemany('INSERT INTO tokens VALUES (?,?,?,?,?,?)',[(osis,i,*t) for i,t in enumerate(tokens)])
                compare_previous(conn,PREVIOUS)
                for table in ('source_segments','mapping_adjudications'):
                    rows=old.execute(f'SELECT * FROM {table} ORDER BY 1,2,3,4').fetchall()
                    if conn.execute(f'SELECT * FROM {table} ORDER BY 1,2,3,4').fetchall()!=rows: raise ValueError(f'Metadata changed: {table}')
                segs=old.execute('SELECT osis FROM source_segments').fetchall()
                if len(segs)!=4: raise ValueError('Missing heading segments')
                for (osis,) in segs:
                    sql='SELECT osis,position,token_id,text,lemma,morphology FROM tokens WHERE osis=? ORDER BY position'
                    if old.execute(sql,(osis,)).fetchall()!=conn.execute(sql,(osis,)).fetchall(): raise ValueError('Heading excerpt changed')
                if digest(PREVIOUS)!=PREVIOUS_SHA256: raise ValueError('Prior store changed')
                if conn.execute('SELECT COUNT(*) FROM (SELECT token_id FROM tokens GROUP BY token_id HAVING COUNT(*)>1)').fetchone()[0]: raise ValueError('Duplicate source token')
                if conn.execute("SELECT COUNT(*) FROM tokens t WHERE NOT EXISTS (SELECT 1 FROM mappings m WHERE m.osis=t.osis) AND NOT EXISTS (SELECT 1 FROM source_segments s WHERE s.osis=t.osis)").fetchone()[0]: raise ValueError('Unreferenced source tokens')
                if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Integrity failure')
    publish_candidate(TARGET,build)
    print(json.dumps({'file':str(TARGET),'new_mappings':len(passages),'new_tokens':sum(len(p[-1]) for p in passages),'sha256':digest(TARGET),'status':'isolated candidate; live preview unchanged'},indent=2))

if __name__=='__main__': main()
