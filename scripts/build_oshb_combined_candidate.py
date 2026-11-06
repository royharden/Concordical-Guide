"""Merge two independently reviewed additive candidates into a new isolated store."""
import json,sqlite3
from contextlib import closing
from build_oshb_subset import ROOT
from build_oshb_genesis10 import compare_previous,digest,publish_candidate

BASE=ROOT/'data/generated/word-study/oshb-genesis-psalms1-150-ps13-spans.sqlite'
HEADING=ROOT/'data/generated/word-study/oshb-psalm-heading-candidate-v3.sqlite'
EXODUS=ROOT/'data/generated/word-study/oshb-exodus1-10-candidate.sqlite'
TARGET=ROOT/'data/generated/word-study/oshb-psalm-headings-exodus1-10-combined-v2.sqlite'
HASHES={BASE:'97923d6c5ff339855215b5b047a8daf2e65bca73753632780182ec81b3a548f7',HEADING:'6c39aa7d7bcddb44c8cfed9e0e04c42d60fc83a18c1f5f836949fa641ca2301e',EXODUS:'a16ab425457cba829303fa1ee047449be9f515310b6a1a4df5c499a552526191'}

def open_read(path): return sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)

def main():
    if TARGET.exists(): raise SystemExit('Candidate exists; do not overwrite')
    for path,expected in HASHES.items():
        if digest(path)!=expected: raise ValueError(f'Input hash mismatch: {path.name}')
    def build(path):
        with closing(open_read(HEADING)) as heading, closing(open_read(EXODUS)) as exodus, closing(sqlite3.connect(path)) as dest:
            heading.backup(dest)
            additions=exodus.execute("SELECT edition,book,chapter,verse,osis FROM mappings WHERE edition='kjv' AND book='bcbooks:ex' ORDER BY chapter,verse").fetchall()
            if len(additions)!=274 or {r[2] for r in additions}!=set(range(1,11)): raise ValueError('Unexpected Exodus candidate coverage')
            if exodus.execute('SELECT COUNT(*) FROM mappings').fetchone()[0]!=4262 or heading.execute('SELECT COUNT(*) FROM mappings').fetchone()[0]!=3992: raise ValueError('Unexpected input mapping counts')
            with dest:
                for row in additions:
                    if dest.execute('SELECT COUNT(*) FROM mappings WHERE edition=? AND book=? AND chapter=? AND verse=?',row[:4]).fetchone()[0]: raise ValueError('Target already exists')
                    tokens=exodus.execute('SELECT osis,position,token_id,text,lemma,morphology FROM tokens WHERE osis=? ORDER BY position',(row[4],)).fetchall()
                    if not tokens or dest.execute('SELECT COUNT(*) FROM tokens WHERE osis=?',(row[4],)).fetchone()[0]: raise ValueError('Missing or duplicate source verse')
                    dest.execute('INSERT INTO mappings VALUES (?,?,?,?,?)',row)
                    dest.executemany('INSERT INTO tokens VALUES (?,?,?,?,?,?)',tokens)
                compare_previous(dest,BASE);compare_previous(dest,HEADING);compare_previous(dest,EXODUS)
                sql='SELECT edition,book,chapter,verse,role,osis FROM source_segments ORDER BY edition,book,chapter,verse,role'
                segments=heading.execute(sql).fetchall()
                if len(segments)!=4 or dest.execute(sql).fetchall()!=segments: raise ValueError('Heading segment metadata changed')
                for row in segments:
                    q='SELECT osis,position,token_id,text,lemma,morphology FROM tokens WHERE osis=? ORDER BY position'
                    if heading.execute(q,(row[-1],)).fetchall()!=dest.execute(q,(row[-1],)).fetchall(): raise ValueError('Heading segment tokens changed')
                if dest.execute('SELECT COUNT(*) FROM mappings').fetchone()[0]!=4266 or dest.execute('SELECT COUNT(*) FROM tokens').fetchone()[0]!=43861: raise ValueError('Unexpected combined totals')
                if dest.execute('SELECT COUNT(*) FROM (SELECT token_id FROM tokens GROUP BY token_id HAVING COUNT(*)>1)').fetchone()[0]: raise ValueError('Duplicate token ID')
                if dest.execute("SELECT COUNT(*) FROM tokens t WHERE NOT EXISTS (SELECT 1 FROM mappings m WHERE m.osis=t.osis) AND NOT EXISTS (SELECT 1 FROM source_segments s WHERE s.osis=t.osis)").fetchone()[0]: raise ValueError('Unreferenced source tokens')
                if any(row[4]!='source_superscription_excerpt' or row[:2]!=('kjv','bcbooks:ps') for row in segments): raise ValueError('Unexpected heading segment role or owner')
                if dest.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Integrity failure')
                for source,expected in HASHES.items():
                    if digest(source)!=expected: raise ValueError(f'Input changed while building: {source.name}')
    publish_candidate(TARGET,build)
    print(json.dumps({'file':str(TARGET),'mappings':4266,'tokens':43861,'sha256':digest(TARGET),'status':'isolated combined candidate; not promoted'},indent=2))

if __name__=='__main__': main()
