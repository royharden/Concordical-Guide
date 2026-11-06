"""Build an isolated Deuteronomy 12-13 candidate."""
import hashlib,json,sqlite3,xml.etree.ElementTree as ET
from contextlib import closing
from build_oshb_subset import ROOT,RAW,MANIFEST,NS,validate_unique_token_ids
from build_oshb_genesis10 import CATALOG_RECEIPT,compare_previous,digest,publish_candidate,verify_english_catalog
from build_oshb_psalms31_50 import note_claims
from oshb_main_reading import primary_and_note_tokens

PREVIOUS=ROOT/'data/generated/word-study/oshb-deuteronomy11-14-20-candidate.sqlite'
TARGET=ROOT/'data/generated/word-study/oshb-deuteronomy12-13-candidate.sqlite'
EXOD_MANIFEST=ROOT/'data/manifests/oshb-exodus.json'
LEV_MANIFEST=ROOT/'data/manifests/oshb-leviticus.json'
NUM_MANIFEST=ROOT/'data/manifests/oshb-numbers.json'
DEUT_MANIFEST=ROOT/'data/manifests/oshb-deuteronomy.json'
PREVIOUS_SHA256='87cecb66ee65559d2da102359bf6be7772eff12974e6fd08973cae710c889137'
COUNTS=(46,37,29,49,33,25,26,20,29,22)
MAP_NS={'m':'http://www.APTBibleTools.com/namespace'}

def passages_for_range(num,verse_map,genesis,exodus,leviticus,psalms,numbers):
    root=ET.fromstring(num);vm=ET.fromstring(verse_map)
    if root.find('o:osisText',NS) is None or root.find('o:osisText',NS).get('osisIDWork')!='OSHB': raise ValueError('Unexpected source identity')
    expected=[('Deut.13.1','Deut.12.32','full')]+[(f'Deut.13.{v+1}',f'Deut.13.{v}','full') for v in range(1,19)]
    edges=[]
    for e in vm.findall('.//m:verse',MAP_NS):
        row=tuple(e.get(k) for k in ('wlc','kjv','type'))
        if any((ref or '').startswith(('Deut.12.','Deut.13.')) for ref in row[:2]): edges.append(row)
    if sorted(edges)!=sorted(expected): raise ValueError('Unexpected Deuteronomy 12–13 edge')
    incoming={target:source for source,target,_ in edges}
    if len(incoming)!=len(edges): raise ValueError('Duplicate target')
    claims={}
    for data in (num,genesis,exodus,leviticus,psalms,numbers):
        for target,sources in note_claims(ET.fromstring(data)).items(): claims.setdefault(target,[]).extend(sources)
    nodes={}
    for node in root.findall('.//o:verse',NS):
        ref=node.get('osisID')
        if not ref or ref in nodes: raise ValueError('Missing or duplicate source reference')
        nodes[ref]=node
    for ch,count in ((12,31),(13,19)):
        chapters=[n for n in root.findall('.//o:chapter',NS) if n.get('osisID')==f'Deut.{ch}']
        if len(chapters)!=1 or [v.get('osisID') for v in chapters[0].findall('o:verse',NS)]!=[f'Deut.{ch}.{v}' for v in range(1,count+1)]: raise ValueError('Unexpected source coordinates')
    out=[];variants=[];seen=set()
    for ch,count in ((12,32),(13,18)):
        for v in range(1,count+1):
            target=f'Deut.{ch}.{v}';osis=incoming.get(target,target);node=nodes.get(osis)
            if node is None or osis in seen: raise ValueError('Missing or reused source')
            seen.add(osis)
            notes=[(n.text or '')[4:] for n in node.findall('o:note',NS) if (n.text or '').startswith('KJV:')]
            if notes != ([target] if target in incoming else []) and not (target not in incoming and notes==[target]): raise ValueError(f'Conflicting source note: {target}')
            if any(other!=osis for other in claims.get(target,[])): raise ValueError(f'Foreign claim: {target}')
            tokens,alts=primary_and_note_tokens(node)
            if not tokens or any(not all(t) or not t[3].startswith('H') for t in tokens): raise ValueError(f'Invalid source token: {osis}')
            if alts: variants.append((osis,len(alts)))
            out.append(('kjv','bcbooks:deut',ch,v,osis,tokens))
    if variants!=[('Deut.13.16',1)]: raise ValueError('Unexpected alternate words')
    return out

def main():
    if TARGET.exists(): raise SystemExit('Candidate exists; do not overwrite')
    base=json.loads(MANIFEST.read_text(encoding='utf8'));additional=json.loads(EXOD_MANIFEST.read_text(encoding='utf-8-sig'));levpin=json.loads(LEV_MANIFEST.read_text(encoding='utf-8-sig'));numpin=json.loads(NUM_MANIFEST.read_text(encoding='utf-8-sig'));data={}
    if additional['revision']!=base['revision'] or levpin['revision']!=base['revision'] or numpin['revision']!=base['revision']: raise ValueError('Source revision mismatch')
    for name,expected in base['files'].items():
        data[name]=(RAW/name).read_bytes()
        if hashlib.sha256(data[name]).hexdigest()!=expected: raise ValueError(f'Source hash mismatch: {name}')
    data['Exod.xml']=(RAW/'Exod.xml').read_bytes()
    if hashlib.sha256(data['Exod.xml']).hexdigest()!=additional['sha256'] or hashlib.sha256(data['LICENSE.md']).hexdigest()!=additional['license_sha256']: raise ValueError('Exodus source or license mismatch')
    data['Lev.xml']=(RAW/'Lev.xml').read_bytes()
    if hashlib.sha256(data['Lev.xml']).hexdigest()!=levpin['sha256'] or hashlib.sha256(data['LICENSE.md']).hexdigest()!=levpin['license_sha256']: raise ValueError('Leviticus source or license mismatch')
    data['Num.xml']=(RAW/'Num.xml').read_bytes()
    if hashlib.sha256(data['Num.xml']).hexdigest()!=numpin['sha256'] or hashlib.sha256(data['LICENSE.md']).hexdigest()!=numpin['license_sha256']: raise ValueError('Numbers source or license mismatch')
    deutpin=json.loads(DEUT_MANIFEST.read_text(encoding='utf-8-sig'))
    data['Deut.xml']=(RAW/'Deut.xml').read_bytes()
    if deutpin['revision']!=base['revision'] or hashlib.sha256(data['Deut.xml']).hexdigest()!=deutpin['sha256'] or hashlib.sha256(data['LICENSE.md']).hexdigest()!=deutpin['license_sha256']: raise ValueError('Deuteronomy source or license mismatch')
    if digest(PREVIOUS)!=PREVIOUS_SHA256: raise ValueError('Prior checkpoint hash mismatch')
    receipt=json.loads(CATALOG_RECEIPT.read_text(encoding='utf8'))
    verify_english_catalog(receipt,(32,18),start=12,book_name='Deuteronomy',book_id='bcbooks:deut')
    passages=passages_for_range(data['Deut.xml'],data['VerseMap.xml'],data['Gen.xml'],data['Exod.xml'],data['Lev.xml'],data['Ps.xml'],data['Num.xml']);validate_unique_token_ids(passages)
    if len(passages)!=50 or sum(len(p[-1]) for p in passages)!=848: raise ValueError('Unexpected candidate totals')
    def build(path):
        with closing(sqlite3.connect(PREVIOUS.resolve().as_uri()+'?mode=ro',uri=True)) as old,closing(sqlite3.connect(path)) as conn:
            old.backup(conn)
            with conn:
                for edition,book,ch,v,osis,tokens in passages:
                    conn.execute('INSERT INTO mappings VALUES (?,?,?,?,?)',(edition,book,ch,v,osis))
                    conn.executemany('INSERT INTO tokens VALUES (?,?,?,?,?,?)',[(osis,i,*t) for i,t in enumerate(tokens)])
                compare_previous(conn,PREVIOUS)
                q='SELECT edition,book,chapter,verse,role,osis FROM source_segments ORDER BY edition,book,chapter,verse,role'
                segs=old.execute(q).fetchall()
                if len(segs)!=4 or conn.execute(q).fetchall()!=segs: raise ValueError('Heading segment metadata changed')
                for row in segs:
                    t='SELECT osis,position,token_id,text,lemma,morphology FROM tokens WHERE osis=? ORDER BY position'
                    if old.execute(t,(row[-1],)).fetchall()!=conn.execute(t,(row[-1],)).fetchall(): raise ValueError('Heading excerpt changed')
                adjudications=old.execute('SELECT * FROM mapping_adjudications ORDER BY 1,2,3,4').fetchall()
                if len(adjudications)!=3 or conn.execute('SELECT * FROM mapping_adjudications ORDER BY 1,2,3,4').fetchall()!=adjudications: raise ValueError('Adjudications changed')
                parts=old.execute('SELECT * FROM mapping_source_parts ORDER BY 1,2,3,4,5').fetchall()
                if len(parts)!=2 or conn.execute('SELECT * FROM mapping_source_parts ORDER BY 1,2,3,4,5').fetchall()!=parts: raise ValueError('Prior source parts changed')
                for row in parts:
                    t='SELECT osis,position,token_id,text,lemma,morphology FROM tokens WHERE osis=? ORDER BY position'
                    if old.execute(t,(row[-1],)).fetchall()!=conn.execute(t,(row[-1],)).fetchall(): raise ValueError('Prior part words changed')
                if digest(PREVIOUS)!=PREVIOUS_SHA256: raise ValueError('Prior store changed')
                if conn.execute('SELECT COUNT(*) FROM (SELECT token_id FROM tokens GROUP BY token_id HAVING COUNT(*)>1)').fetchone()[0]: raise ValueError('Duplicate token ID')
                if conn.execute("SELECT COUNT(*) FROM tokens t WHERE NOT EXISTS (SELECT 1 FROM mappings m WHERE m.osis=t.osis) AND NOT EXISTS (SELECT 1 FROM source_segments s WHERE s.osis=t.osis) AND NOT EXISTS (SELECT 1 FROM mapping_source_parts p WHERE p.osis=t.osis)").fetchone()[0]: raise ValueError('Unreferenced source tokens')
                if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Integrity failure')
    publish_candidate(TARGET,build)
    print(json.dumps({'file':str(TARGET),'new_mappings':len(passages),'new_tokens':sum(len(p[-1]) for p in passages),'sha256':digest(TARGET),'status':'isolated candidate only; live preview unchanged'},indent=2))

if __name__=='__main__': main()
