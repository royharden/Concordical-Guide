"""Build an isolated Leviticus 1–10 candidate; never promote or overwrite inputs."""
import hashlib,json,sqlite3,xml.etree.ElementTree as ET
from contextlib import closing
from build_oshb_subset import ROOT,RAW,MANIFEST,NS,validate_unique_token_ids
from build_oshb_genesis10 import CATALOG_RECEIPT,compare_previous,digest,publish_candidate,verify_english_catalog
from build_oshb_psalms31_50 import note_claims
from oshb_main_reading import primary_and_note_tokens

PREVIOUS=ROOT/'data/generated/word-study/oshb-psalm42-44-adjudicated-candidate.sqlite'
TARGET=ROOT/'data/generated/word-study/oshb-leviticus1-10-candidate.sqlite'
PREVIOUS_SHA256='f908f4511b8946a76b8d952e792023d94db8791ffca8b4ea257f75fff88c2a32'
LEV_MANIFEST=ROOT/'data/manifests/oshb-leviticus.json'
EXOD_MANIFEST=ROOT/'data/manifests/oshb-exodus.json'
COUNTS=(17,16,17,35,19,30,38,36,24,20)
SOURCE_COUNTS=(17,16,17,35,26,23,38,36,24,20)
MAP_NS={'m':'http://www.APTBibleTools.com/namespace'}

def leviticus_passages(lev,verse_map,genesis,exodus,psalms):
    root=ET.fromstring(lev);vm=ET.fromstring(verse_map)
    if root.find('o:osisText',NS) is None or root.find('o:osisText',NS).get('osisIDWork')!='OSHB': raise ValueError('Unexpected source identity')
    expected=[(f'Lev.5.{v+19}',f'Lev.6.{v}','full') for v in range(1,8)]+[(f'Lev.6.{v-7}',f'Lev.6.{v}','full') for v in range(8,31)]
    edges=[]
    for e in vm.findall('.//m:verse',MAP_NS):
        row=tuple(e.get(k) for k in ('wlc','kjv','type'))
        if any((ref or '').startswith('Lev.') and len(ref.split('.'))>=3 and ref.split('.')[1].isdigit() and 1<=int(ref.split('.')[1])<=10 for ref in row[:2]): edges.append(row)
    if sorted(edges)!=sorted(expected): raise ValueError('Unexpected Leviticus 1–10 map edge')
    incoming={target:source for source,target,_ in edges}
    if len(incoming)!=len(edges): raise ValueError('Duplicate map target')
    claims={}
    for data in (lev,genesis,exodus,psalms):
        for target,sources in note_claims(ET.fromstring(data)).items(): claims.setdefault(target,[]).extend(sources)
    nodes={}
    for node in root.findall('.//o:verse',NS):
        ref=node.get('osisID')
        if not ref or ref in nodes: raise ValueError('Missing or duplicate source reference')
        nodes[ref]=node
    for ch,count in enumerate(SOURCE_COUNTS,1):
        chapters=[n for n in root.findall('.//o:chapter',NS) if n.get('osisID')==f'Lev.{ch}']
        if len(chapters)!=1 or [v.get('osisID') for v in chapters[0].findall('o:verse',NS)]!=[f'Lev.{ch}.{v}' for v in range(1,count+1)]: raise ValueError(f'Unexpected source coordinates: {ch}')
    out=[];variants=[];seen=set()
    for ch,count in enumerate(COUNTS,1):
        for v in range(1,count+1):
            target=f'Lev.{ch}.{v}';osis=incoming.get(target,target);node=nodes.get(osis)
            if node is None or osis in seen: raise ValueError(f'Missing or reused source: {osis}')
            seen.add(osis)
            notes=[(n.text or '')[4:] for n in node.findall('o:note',NS) if (n.text or '').startswith('KJV:')]
            if notes != ([target] if target in incoming else []) and not (target not in incoming and notes==[target]): raise ValueError(f'Conflicting source note: {target}')
            if any(other!=osis for other in claims.get(target,[])): raise ValueError(f'Foreign source claim: {target}')
            tokens,alts=primary_and_note_tokens(node)
            if not tokens or any(not all(t) or not t[3].startswith('H') for t in tokens): raise ValueError(f'Invalid source token: {osis}')
            if alts: variants.append((osis,len(alts)))
            out.append(('kjv','bcbooks:lev',ch,v,osis,tokens))
    if variants!=[('Lev.9.22',1)]: raise ValueError('Unexpected alternate words')
    return out

def main():
    if TARGET.exists(): raise SystemExit('Candidate exists; do not overwrite')
    base=json.loads(MANIFEST.read_text(encoding='utf8'));extra=json.loads(EXOD_MANIFEST.read_text(encoding='utf-8-sig'));levpin=json.loads(LEV_MANIFEST.read_text(encoding='utf-8-sig'));data={}
    if any(pin['revision']!=base['revision'] for pin in (extra,levpin)): raise ValueError('Source revision mismatch')
    for name,expected in base['files'].items():
        data[name]=(RAW/name).read_bytes()
        if hashlib.sha256(data[name]).hexdigest()!=expected: raise ValueError(f'Source hash mismatch: {name}')
    for name,pin in (('Exod.xml',extra),('Lev.xml',levpin)):
        data[name]=(RAW/name).read_bytes()
        if hashlib.sha256(data[name]).hexdigest()!=pin['sha256'] or hashlib.sha256(data['LICENSE.md']).hexdigest()!=pin['license_sha256']: raise ValueError(f'Source or license mismatch: {name}')
    if digest(PREVIOUS)!=PREVIOUS_SHA256: raise ValueError('Prior checkpoint hash mismatch')
    verify_english_catalog(json.loads(CATALOG_RECEIPT.read_text(encoding='utf8')),COUNTS,start=1,book_name='Leviticus',book_id='bcbooks:lev')
    passages=leviticus_passages(data['Lev.xml'],data['VerseMap.xml'],data['Gen.xml'],data['Exod.xml'],data['Ps.xml']);validate_unique_token_ids(passages)
    if len(passages)!=252 or sum(len(p[-1]) for p in passages)!=3671: raise ValueError('Unexpected candidate totals')
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
