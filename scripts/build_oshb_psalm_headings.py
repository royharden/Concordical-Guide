"""Build a candidate separating WLC superscription segments from verse bodies."""
import hashlib,json,sqlite3,xml.etree.ElementTree as ET
from contextlib import closing
from build_oshb_subset import ROOT,RAW,MANIFEST,NS,validate_unique_token_ids
from build_oshb_genesis10 import CATALOG_RECEIPT,RAW_ENGLISH,compare_previous,digest,publish_candidate,verify_english_catalog
from build_oshb_psalms31_50 import note_claims
from oshb_main_reading import primary_and_note_tokens

PREVIOUS=ROOT/'data/generated/word-study/oshb-genesis-psalms1-150-ps13-spans.sqlite'
TARGET=ROOT/'data/generated/word-study/oshb-psalm-heading-candidate-v3.sqlite'
PREVIOUS_SHA256='97923d6c5ff339855215b5b047a8daf2e65bca73753632780182ec81b3a548f7'
CASES={51:(19,9,7),52:(9,12,8),54:(7,8,5),60:(12,17,6)}
MAP_NS={'m':'http://www.APTBibleTools.com/namespace'}

def heading_cases(psalms,verse_map):
    root=ET.fromstring(psalms); vm=ET.fromstring(verse_map); claims=note_claims(root); out=[]
    for ch,(_,heading_count,body_count) in CASES.items():
        target=f'Ps.{ch}.1'; heading=f'Ps.{ch}.2'; body=f'Ps.{ch}.3'
        incoming=[tuple(e.get(k) for k in ('wlc','kjv','type')) for e in vm.findall('.//m:verse',MAP_NS) if e.get('kjv')==target or e.get('wlc') in (heading,body)]
        if sorted(incoming)!=sorted([(heading,target,'full'),(body,target,'full')]): raise ValueError(f'Unexpected map edges for {target}')
        if claims.get(target)!=[body]: raise ValueError(f'Conflicting source notes for {target}')
        records=[]
        for osis,count in ((heading,heading_count),(body,body_count)):
            matches=[v for v in root.findall('.//o:verse',NS) if v.get('osisID')==osis]
            if len(matches)!=1: raise ValueError(f'Unexpected source record: {osis}')
            node=matches[0]; notes=[(n.text or '')[4:] for n in node.findall('o:note',NS) if (n.text or '').startswith('KJV:')]
            if notes != ([] if osis==heading else [target]): raise ValueError(f'Unexpected source note: {osis}')
            tokens,variants=primary_and_note_tokens(node)
            if len(tokens)!=count or variants or any(not all(t) or not t[3].startswith('H') for t in tokens): raise ValueError(f'Unexpected token stream: {osis}')
            records.append((osis,tokens))
        out.append((ch,records[0],records[1]))
    return out

def main():
    if TARGET.exists(): raise SystemExit('Candidate exists; do not overwrite')
    manifest=json.loads(MANIFEST.read_text(encoding='utf8'));data={}
    for name,expected in manifest['files'].items():
        data[name]=(RAW/name).read_bytes()
        if hashlib.sha256(data[name]).hexdigest()!=expected: raise ValueError(f'Source hash mismatch: {name}')
    if digest(PREVIOUS)!=PREVIOUS_SHA256: raise ValueError('Prior store hash mismatch')
    receipt=json.loads(CATALOG_RECEIPT.read_text(encoding='utf8'))
    for ch,(count,_,_) in CASES.items(): verify_english_catalog(receipt,(count,),start=ch,book_name='Psalms',book_id='bcbooks:ps')
    raw_bytes=RAW_ENGLISH.read_bytes()
    receipt_entry=next(e for e in receipt['source_files'] if e['path'].endswith('/old-testament.json'))
    if hashlib.sha256(raw_bytes).hexdigest()!=receipt_entry['sha256']: raise ValueError('KJV heading/body source differs from receipt')
    raw=json.loads(raw_bytes.decode('utf8'))
    psalms=next(b for b in raw['books'] if b['book']=='Psalms')
    for ch in CASES:
        chapter=next(c for c in psalms['chapters'] if c['chapter']==ch)
        first=next(v for v in chapter['verses'] if v['verse']==1)
        if not isinstance(chapter.get('note'),str) or not chapter['note'].strip() or not first.get('text','').strip(): raise ValueError(f'Missing separate local KJV heading/body: {ch}')
    cases=heading_cases(data['Ps.xml'],data['VerseMap.xml'])
    validate_unique_token_ids([('kjv','bcbooks:ps',ch,1,osis,tokens) for ch,h,b in cases for osis,tokens in (h,b)])
    def build(path):
        with closing(sqlite3.connect(PREVIOUS.resolve().as_uri()+'?mode=ro',uri=True)) as old, closing(sqlite3.connect(path)) as conn:
            old.backup(conn)
            with conn:
                conn.execute("CREATE TABLE source_segments (edition TEXT NOT NULL, book TEXT NOT NULL, chapter INTEGER NOT NULL, verse INTEGER NOT NULL, role TEXT NOT NULL CHECK(role='source_superscription_excerpt'), osis TEXT NOT NULL, PRIMARY KEY(edition,book,chapter,verse,role))")
                for ch,heading,body in cases:
                    conn.execute('INSERT INTO mappings VALUES (?,?,?,?,?)',('kjv','bcbooks:ps',ch,1,body[0]))
                    conn.execute('INSERT INTO source_segments VALUES (?,?,?,?,?,?)',('kjv','bcbooks:ps',ch,1,'source_superscription_excerpt',heading[0]))
                    for osis,tokens in (heading,body): conn.executemany('INSERT INTO tokens VALUES (?,?,?,?,?,?)',[(osis,i,*t) for i,t in enumerate(tokens)])
                compare_previous(conn,PREVIOUS)
                if digest(PREVIOUS)!=PREVIOUS_SHA256: raise ValueError('Prior store changed')
                if conn.execute('SELECT COUNT(*) FROM (SELECT token_id FROM tokens GROUP BY token_id HAVING COUNT(*)>1)').fetchone()[0]: raise ValueError('Duplicate token')
                if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Integrity failure')
    publish_candidate(TARGET,build)
    print(json.dumps({'file':str(TARGET),'new_mappings':len(cases),'body_tokens':sum(len(b[1]) for _,h,b in cases),'heading_excerpt_tokens':sum(len(h[1]) for _,h,b in cases),'sha256':digest(TARGET),'status':'isolated candidate only'},indent=2))

if __name__=='__main__': main()
