"""Build isolated Exodus 21–30, explicitly preserving the 21/22 shift."""
import hashlib,json,sqlite3,xml.etree.ElementTree as ET
from contextlib import closing
from build_oshb_subset import ROOT,RAW,MANIFEST,NS,validate_unique_token_ids
from build_oshb_genesis10 import CATALOG_RECEIPT,compare_previous,digest,publish_candidate,verify_english_catalog
from build_oshb_psalms31_50 import note_claims
from oshb_main_reading import primary_and_note_tokens

PREVIOUS=ROOT/'data/generated/word-study/oshb-psalm-headings-exodus1-20-candidate.sqlite'
TARGET=ROOT/'data/generated/word-study/oshb-psalm-headings-exodus1-30-candidate.sqlite'
EXOD_MANIFEST=ROOT/'data/manifests/oshb-exodus.json'
PREVIOUS_SHA256='7da893707de7b959b260ec862395d84d442820cdfc1ea6efa029a899a43a0cf1'
COUNTS=(36,31,33,18,40,37,21,43,46,38)
SOURCE_COUNTS=(37,30,33,18,40,37,21,43,46,38)
EXPECTED_VARIANTS=(('Exod.21.8',1),('Exod.22.4',1),('Exod.22.26',1),('Exod.27.11',1),('Exod.28.28',1))
MAP_NS={'m':'http://www.APTBibleTools.com/namespace'}

def passages_for_range(exod,verse_map,genesis,psalms):
    root=ET.fromstring(exod);vm=ET.fromstring(verse_map)
    if root.find('o:osisText',NS) is None or root.find('o:osisText',NS).get('osisIDWork')!='OSHB': raise ValueError('Unexpected source identity')
    expected=[('Exod.21.37','Exod.22.1','full')]+[(f'Exod.22.{v-1}',f'Exod.22.{v}','full') for v in range(2,32)]
    rows=[]
    for e in vm.findall('.//m:verse',MAP_NS):
        row=tuple(e.get(k) for k in ('wlc','kjv','type'))
        if any((ref or '').startswith('Exod.') and len(ref.split('.'))>=3 and ref.split('.')[1].isdigit() and 21<=int(ref.split('.')[1])<=30 for ref in row[:2]): rows.append(row)
    if sorted(rows)!=sorted(expected): raise ValueError('Unexpected Exodus 21–30 map edge')
    incoming={target:source for source,target,_ in rows}
    if len(incoming)!=len(rows): raise ValueError('Duplicate map target')
    claims={}
    for data in (exod,genesis,psalms):
        for target,sources in note_claims(ET.fromstring(data)).items(): claims.setdefault(target,[]).extend(sources)
    nodes={}
    for node in root.findall('.//o:verse',NS):
        ref=node.get('osisID')
        if not ref or ref in nodes: raise ValueError('Missing or duplicate source reference')
        nodes[ref]=node
    for ch,count in enumerate(SOURCE_COUNTS,21):
        chapters=[n for n in root.findall('.//o:chapter',NS) if n.get('osisID')==f'Exod.{ch}']
        if len(chapters)!=1 or [v.get('osisID') for v in chapters[0].findall('o:verse',NS)]!=[f'Exod.{ch}.{v}' for v in range(1,count+1)]: raise ValueError(f'Unexpected source coordinates: {ch}')
    out=[];variant_refs=[];seen_sources=set()
    for ch,count in enumerate(COUNTS,21):
        for verse in range(1,count+1):
            target=f'Exod.{ch}.{verse}';osis=incoming.get(target,target);node=nodes.get(osis)
            if node is None or osis in seen_sources: raise ValueError(f'Missing or reused source: {osis}')
            seen_sources.add(osis)
            notes=[(n.text or '')[4:] for n in node.findall('o:note',NS) if (n.text or '').startswith('KJV:')]
            if notes != ([target] if target in incoming else []) and not (target not in incoming and notes==[target]): raise ValueError(f'Conflicting source note: {target}')
            if any(other!=osis for other in claims.get(target,[])): raise ValueError(f'Foreign source claim: {target}')
            tokens,variants=primary_and_note_tokens(node)
            if not tokens or any(not all(t) or not t[3].startswith('H') for t in tokens): raise ValueError(f'Invalid source token: {osis}')
            if variants: variant_refs.append((osis,len(variants)))
            out.append(('kjv','bcbooks:ex',ch,verse,osis,tokens))
    if tuple(variant_refs)!=EXPECTED_VARIANTS: raise ValueError('Unexpected note-contained alternate words')
    return out

def main():
    if TARGET.exists(): raise SystemExit('Candidate exists; do not overwrite')
    base=json.loads(MANIFEST.read_text(encoding='utf8'));extra=json.loads(EXOD_MANIFEST.read_text(encoding='utf-8-sig'));data={}
    if extra['revision']!=base['revision']: raise ValueError('Source revision mismatch')
    for name,expected in base['files'].items():
        data[name]=(RAW/name).read_bytes()
        if hashlib.sha256(data[name]).hexdigest()!=expected: raise ValueError(f'Source hash mismatch: {name}')
    data['Exod.xml']=(RAW/'Exod.xml').read_bytes()
    if hashlib.sha256(data['Exod.xml']).hexdigest()!=extra['sha256'] or hashlib.sha256(data['LICENSE.md']).hexdigest()!=extra['license_sha256']: raise ValueError('Exodus source or license mismatch')
    if digest(PREVIOUS)!=PREVIOUS_SHA256: raise ValueError('Prior checkpoint hash mismatch')
    verify_english_catalog(json.loads(CATALOG_RECEIPT.read_text(encoding='utf8')),COUNTS,start=21,book_name='Exodus',book_id='bcbooks:ex')
    passages=passages_for_range(data['Exod.xml'],data['VerseMap.xml'],data['Gen.xml'],data['Ps.xml']);validate_unique_token_ids(passages)
    if len(passages)!=343 or sum(len(p[-1]) for p in passages)!=4356: raise ValueError('Unexpected candidate totals')
    def build(path):
        with closing(sqlite3.connect(PREVIOUS.resolve().as_uri()+'?mode=ro',uri=True)) as old,closing(sqlite3.connect(path)) as conn:
            old.backup(conn)
            with conn:
                for edition,book,ch,v,osis,tokens in passages:
                    conn.execute('INSERT INTO mappings VALUES (?,?,?,?,?)',(edition,book,ch,v,osis))
                    conn.executemany('INSERT INTO tokens VALUES (?,?,?,?,?,?)',[(osis,i,*t) for i,t in enumerate(tokens)])
                compare_previous(conn,PREVIOUS)
                q='SELECT edition,book,chapter,verse,role,osis FROM source_segments ORDER BY edition,book,chapter,verse,role';segs=old.execute(q).fetchall()
                if len(segs)!=4 or conn.execute(q).fetchall()!=segs: raise ValueError('Heading metadata changed')
                for row in segs:
                    t='SELECT osis,position,token_id,text,lemma,morphology FROM tokens WHERE osis=? ORDER BY position'
                    if old.execute(t,(row[-1],)).fetchall()!=conn.execute(t,(row[-1],)).fetchall(): raise ValueError('Heading excerpt changed')
                if digest(PREVIOUS)!=PREVIOUS_SHA256: raise ValueError('Prior store changed')
                if conn.execute('SELECT COUNT(*) FROM (SELECT token_id FROM tokens GROUP BY token_id HAVING COUNT(*)>1)').fetchone()[0]: raise ValueError('Duplicate token ID')
                if conn.execute("SELECT COUNT(*) FROM tokens t WHERE NOT EXISTS (SELECT 1 FROM mappings m WHERE m.osis=t.osis) AND NOT EXISTS (SELECT 1 FROM source_segments s WHERE s.osis=t.osis)").fetchone()[0]: raise ValueError('Unreferenced source tokens')
                if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Integrity failure')
    publish_candidate(TARGET,build)
    print(json.dumps({'file':str(TARGET),'new_mappings':len(passages),'new_tokens':sum(len(p[-1]) for p in passages),'sha256':digest(TARGET),'status':'isolated candidate only; live preview unchanged'},indent=2))

if __name__=='__main__': main()
