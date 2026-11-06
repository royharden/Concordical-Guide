"""Non-promoting Exodus KJV reference-map inventory; does not inspect source words."""
import hashlib,json,xml.etree.ElementTree as ET
from build_oshb_subset import MANIFEST,RAW
from build_oshb_genesis10 import CATALOG_RECEIPT,verify_english_catalog

COUNTS=(22,25,22,31,23,30,25,32,35,29)
MAP_NS={'m':'http://www.APTBibleTools.com/namespace'}

def candidates(content):
    root=ET.fromstring(content)
    refs={f'Exod.{ch}.{v}' for ch,n in enumerate(COUNTS,1) for v in range(1,n+1)}
    edges=[tuple(x.get(k) for k in ('wlc','kjv','type')) for x in root.findall('.//m:verse',MAP_NS)]
    relevant=[e for e in edges if any((value or '').startswith('Exod.') and value.split('.')[1].isdigit() and 1<=int(value.split('.')[1])<=10 for value in e[:2])]
    expected=[(f'Exod.7.{v+25}',f'Exod.8.{v}','full') for v in range(1,5)]+[(f'Exod.8.{v-4}',f'Exod.8.{v}','full') for v in range(5,33)]
    if sorted(relevant)!=sorted(expected): raise ValueError('Unexpected Exodus 1–10 reference-map edge; re-audit required')
    incoming={target:source for source,target,kind in relevant}
    if len(incoming)!=len(relevant) or not set(incoming)<=refs: raise ValueError('Duplicate or out-of-range target')
    rows=[{'target':target,'source':incoming.get(target,target),'kind':'explicit_full' if target in incoming else 'identity_candidate'} for target in sorted(refs,key=lambda r:tuple(map(int,r.split('.')[1:])))]
    sources=[r['source'] for r in rows]
    if len(sources)!=len(set(sources)): raise ValueError('Source reference reused; re-audit required')
    return rows

def main():
    manifest=json.loads(MANIFEST.read_text(encoding='utf8'));data=(RAW/'VerseMap.xml').read_bytes()
    if hashlib.sha256(data).hexdigest()!=manifest['files']['VerseMap.xml']: raise ValueError('Reference-map hash mismatch')
    receipt=json.loads(CATALOG_RECEIPT.read_text(encoding='utf8'))
    verify_english_catalog(receipt,COUNTS,start=1,book_name='Exodus',book_id='bcbooks:ex')
    raw_entry=next(e for e in receipt['source_files'] if e['path'].endswith('/old-testament.json'))
    rows=candidates(data)
    print(json.dumps({'status':'reference candidates only; no source-word verification or promotion','revision':manifest['revision'],'verse_map_sha256':manifest['files']['VerseMap.xml'],'kjv_catalog_sha256':receipt['db_sha256'],'kjv_raw_sha256':raw_entry['sha256'],'local_kjv_targets':len(rows),'identity_candidates':sum(r['kind']=='identity_candidate' for r in rows),'explicit_full_edges':sum(r['kind']=='explicit_full' for r in rows),'mappings':rows},indent=2))

if __name__=='__main__': main()
