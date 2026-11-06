"""Build an isolated Numbers 31-36 candidate."""
import hashlib,json,sqlite3,xml.etree.ElementTree as ET
from contextlib import closing
from build_oshb_subset import ROOT,RAW,MANIFEST,NS,validate_unique_token_ids
from build_oshb_genesis10 import CATALOG_RECEIPT,compare_previous,digest,publish_candidate,verify_english_catalog
from build_oshb_psalms31_50 import note_claims
from oshb_main_reading import primary_and_note_tokens

PREVIOUS=ROOT/'data/generated/word-study/oshb-numbers1-30-except26-1-candidate.sqlite'
TARGET=ROOT/'data/generated/word-study/oshb-numbers1-36-except26-1-candidate.sqlite'
EXOD_MANIFEST=ROOT/'data/manifests/oshb-exodus.json'
LEV_MANIFEST=ROOT/'data/manifests/oshb-leviticus.json'
NUM_MANIFEST=ROOT/'data/manifests/oshb-numbers.json'
PREVIOUS_SHA256='b74723e583af227058f2b393497537659202afc60c6a02d53e3659d046c11507'
COUNTS=(54,42,56,29,34,13)
MAP_NS={'m':'http://www.APTBibleTools.com/namespace'}

def passages_for_range(num,verse_map,genesis,exodus,leviticus,psalms,counts=COUNTS,start=31,expected_variants=(('Num.32.7',1),('Num.34.4',1))):
    root=ET.fromstring(num); vm=ET.fromstring(verse_map); chapters=set(range(start,start+len(counts)))
    if root.find('o:osisText',NS) is None or root.find('o:osisText',NS).get('osisIDWork')!='OSHB': raise ValueError('Unexpected source identity')
    for e in vm.findall('.//m:verse',MAP_NS):
        for k in ('wlc','kjv'):
            ref=e.get(k) or '';parts=ref.split('.')
            if len(parts)>=3 and parts[0]=='Num' and parts[1].isdigit() and int(parts[1]) in chapters: raise ValueError(f'Unexpected Numbers map exception: {ref}')
    claims={}
    for data in (num,genesis,exodus,leviticus,psalms):
        for target,sources in note_claims(ET.fromstring(data)).items(): claims.setdefault(target,[]).extend(sources)
    out=[];variant_refs=[]
    for ch,count in enumerate(counts,start):
        nodes=[n for n in root.findall('.//o:chapter',NS) if n.get('osisID')==f'Num.{ch}']
        if len(nodes)!=1: raise ValueError(f'Unexpected source chapter: {ch}')
        verses=nodes[0].findall('o:verse',NS)
        if [v.get('osisID') for v in verses]!=[f'Num.{ch}.{v}' for v in range(1,count+1)]: raise ValueError(f'Unexpected source coordinates: {ch}')
        for verse,node in enumerate(verses,1):
            osis=f'Num.{ch}.{verse}'
            notes=[(n.text or '')[4:] for n in node.findall('o:note',NS) if (n.text or '').startswith('KJV:')]
            if notes not in ([],[osis]) or any(other!=osis for other in claims.get(osis,[])): raise ValueError(f'Conflicting source notes: {osis}')
            tokens,variants=primary_and_note_tokens(node)
            if not tokens or any(not all(t) or not t[3].startswith('H') for t in tokens): raise ValueError(f'Invalid source token: {osis}')
            if variants: variant_refs.append((osis,len(variants)))
            out.append(('kjv','bcbooks:num',ch,verse,osis,tokens))
    if tuple(variant_refs)!=tuple(expected_variants): raise ValueError('Unexpected note-contained alternate words')
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
    if digest(PREVIOUS)!=PREVIOUS_SHA256: raise ValueError('Prior checkpoint hash mismatch')
    verify_english_catalog(json.loads(CATALOG_RECEIPT.read_text(encoding='utf8')),COUNTS,start=31,book_name='Numbers',book_id='bcbooks:num')
    passages=passages_for_range(data['Num.xml'],data['VerseMap.xml'],data['Gen.xml'],data['Exod.xml'],data['Lev.xml'],data['Ps.xml']);validate_unique_token_ids(passages)
    if len(passages)!=228 or sum(len(p[-1]) for p in passages)!=2693: raise ValueError('Unexpected candidate totals')
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
                if len(adjudications)!=2 or conn.execute('SELECT * FROM mapping_adjudications ORDER BY 1,2,3,4').fetchall()!=adjudications: raise ValueError('Adjudications changed')
                if digest(PREVIOUS)!=PREVIOUS_SHA256: raise ValueError('Prior store changed')
                if conn.execute('SELECT COUNT(*) FROM (SELECT token_id FROM tokens GROUP BY token_id HAVING COUNT(*)>1)').fetchone()[0]: raise ValueError('Duplicate token ID')
                if conn.execute("SELECT COUNT(*) FROM tokens t WHERE NOT EXISTS (SELECT 1 FROM mappings m WHERE m.osis=t.osis) AND NOT EXISTS (SELECT 1 FROM source_segments s WHERE s.osis=t.osis)").fetchone()[0]: raise ValueError('Unreferenced source tokens')
                if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Integrity failure')
    publish_candidate(TARGET,build)
    print(json.dumps({'file':str(TARGET),'new_mappings':len(passages),'new_tokens':sum(len(p[-1]) for p in passages),'sha256':digest(TARGET),'status':'isolated candidate only; live preview unchanged'},indent=2))

if __name__=='__main__': main()
