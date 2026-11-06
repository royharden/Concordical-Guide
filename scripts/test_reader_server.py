"""Small security and database contract checks for the local reader."""
import unittest
from serve_reader import valid_host, valid_origin, lookup_words, hebrew_passage, oshb_store_path, Handler
import sqlite3
from contextlib import closing
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from build_webp import rows_from_xml
from build_word_study import rows_match_source
from build_oshb_subset import parse_passage, validate_genesis_map, validate_genesis_source, validate_unique_token_ids
from audit_oshb_mapping import audit, parse_source, catalog_targets, base_ref
from build_oshb_genesis10 import chapter_records, publish_candidate, verify_english_catalog, compare_previous
from build_oshb_genesis_complete import boundary_passages
from build_oshb_psalms1_10 import psalm_passages
from build_oshb_psalms11_30 import psalm_candidates
from build_oshb_psalms31_50 import note_claims, ensure_no_foreign_claim
from build_oshb_psalms51_75 import psalm_candidates as later_psalm_candidates
from oshb_main_reading import primary_and_note_tokens
from build_oshb_psalm13_segments import split_passages, EXPECTED_IDS
from build_oshb_psalm_headings import heading_cases, CASES
from audit_exodus1_10_map import candidates as exodus_map_candidates
from build_oshb_exodus1_10 import exodus_passages, SOURCE_COUNTS
from build_oshb_exodus11_20 import passages_for_range
from build_oshb_exodus21_30 import passages_for_range as exodus21_passages, SOURCE_COUNTS as EXODUS21_SOURCE_COUNTS, EXPECTED_VARIANTS as EXODUS21_VARIANTS
from build_oshb_exodus31_40 import passages_for_range as exodus31_passages
from build_oshb_psalm42_44 import adjudicated_passages, IDS as ADJUDICATED_IDS
from build_oshb_leviticus1_10 import leviticus_passages, SOURCE_COUNTS as LEV_SOURCE_COUNTS
from build_oshb_leviticus11_20 import passages_for_range as leviticus11_passages
from build_oshb_leviticus21_27 import passages_for_range as leviticus21_passages
from build_oshb_numbers1_10 import passages_for_range as numbers1_passages
from build_oshb_numbers11_20 import numbers_passages as numbers11_passages, SOURCE_COUNTS as NUM11_SOURCE_COUNTS
from build_oshb_numbers21_30 import numbers_passages as numbers21_passages, SOURCE_COUNTS as NUM21_SOURCE_COUNTS
from build_oshb_numbers31_36 import passages_for_range as numbers31_passages
from build_oshb_numbers26_1 import adjudicated_parts, IDS as NUMBERS26_IDS
from build_oshb_deuteronomy1_10 import passages_for_range as deuteronomy_passages
from build_oshb_deuteronomy11_14_20 import passages_for_range as deuteronomy_later_passages
from build_oshb_deuteronomy12_13 import passages_for_range as deuteronomy_shift_passages
from build_oshb_deuteronomy21_24_27_30 import passages_for_range as deuteronomy_next_passages
from build_oshb_deuteronomy31_34 import passages_for_range as deuteronomy_end_passages
from build_oshb_deuteronomy22_23_28_29 import passages_for_range as deuteronomy_double_shift_passages
import xml.etree.ElementTree as ET


class ReaderHostTests(unittest.TestCase):
    def test_deuteronomy_map_conflicts_and_note_words_are_rejected(self):
        # what_bug_this_catches: alternate note words or unreviewed verse-map changes entering main text.
        empty='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"/>'
        xml='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><osisText osisIDWork="OSHB"><chapter osisID="Deut.1"><verse osisID="Deut.1.1"><w id="a" lemma="1" morph="HN">x</w><note><rdg><w id="alt" lemma="2" morph="HN">z</w></rdg></note></verse></chapter></osisText></osis>'
        vm='<verseMap xmlns="http://www.APTBibleTools.com/namespace"/>'
        run=lambda x,m,g=empty: deuteronomy_passages(x.encode(),m.encode(),g.encode(),empty.encode(),empty.encode(),empty.encode(),empty.encode(),counts=(1,),expected_variants=(('Deut.1.1',1),))
        rows=run(xml,vm); self.assertEqual([t[0] for t in rows[0][-1]],['a'])
        edge=vm.replace('/>','><verse wlc="Deut.1.1" kjv="Deut.1.2" type="full"/></verseMap>')
        with self.assertRaises(ValueError): run(xml,edge)
        foreign=empty.replace('/>','><verse osisID="Gen.1.1"><note>KJV:Deut.1.1</note></verse></osis>')
        with self.assertRaises(ValueError): run(xml,vm,foreign)
        with self.assertRaises(ValueError): run(xml.replace('morph="HN">x','morph="AN">x'),vm)

    def test_deuteronomy_later_noncontiguous_ranges_and_edges(self):
        # what_bug_this_catches: accepting a shifted cross-boundary reference or importing skipped chapters.
        empty='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"/>'
        xml='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><osisText osisIDWork="OSHB">'+''.join(f'<chapter osisID="Deut.{c}"><verse osisID="Deut.{c}.1"><w id="{c}" lemma="1" morph="HN">x</w></verse></chapter>' for c in (11,12,13,14))+'</osisText></osis>'
        vm='<verseMap xmlns="http://www.APTBibleTools.com/namespace"/>'
        run=lambda start,m: deuteronomy_later_passages(xml.encode(),m.encode(),empty.encode(),empty.encode(),empty.encode(),empty.encode(),empty.encode(),counts=(1,),start=start,expected_variants=())
        rows=run(11,vm)+run(14,vm); self.assertEqual([r[2] for r in rows],[11,14])
        edge=vm.replace('/>','><verse wlc="Deut.13.1" kjv="Deut.14.1" type="full"/></verseMap>')
        with self.assertRaises(ValueError):run(14,edge)

    def test_deuteronomy_12_13_shift_and_alternate_note(self):
        # what_bug_this_catches: chapter-boundary shifts treated as identity or alternate words served as primary.
        empty='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"/>'
        chapters=''
        for ch,count in ((12,31),(13,19)):
            verses=''
            for v in range(1,count+1):
                target=(f'Deut.12.32' if v==1 else f'Deut.13.{v-1}') if ch==13 else None
                note=f'<note>KJV:{target}</note>' if target else ''
                alt='<note><rdg><w id="alternate" lemma="2" morph="HN">z</w></rdg></note>' if (ch,v)==(13,16) else ''
                verses+=f'<verse osisID="Deut.{ch}.{v}">{note}<w id="{ch}-{v}" lemma="1" morph="HN">x</w>{alt}</verse>'
            chapters+=f'<chapter osisID="Deut.{ch}">{verses}</chapter>'
        xml=f'<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><osisText osisIDWork="OSHB">{chapters}</osisText></osis>'
        edges='<verse wlc="Deut.13.1" kjv="Deut.12.32" type="full"/>'+''.join(f'<verse wlc="Deut.13.{v+1}" kjv="Deut.13.{v}" type="full"/>' for v in range(1,19))
        vm=f'<verseMap xmlns="http://www.APTBibleTools.com/namespace">{edges}</verseMap>'
        run=lambda x,m: deuteronomy_shift_passages(x.encode(),m.encode(),empty.encode(),empty.encode(),empty.encode(),empty.encode(),empty.encode())
        rows=run(xml,vm);lookup={(r[2],r[3]):r for r in rows}
        self.assertEqual(len(rows),50);self.assertEqual(lookup[12,32][4],'Deut.13.1');self.assertEqual(lookup[13,15][4],'Deut.13.16');self.assertEqual([t[0] for t in lookup[13,15][-1]],['13-16'])
        with self.assertRaises(ValueError):run(xml,vm.replace('Deut.12.32','Deut.12.31',1))
        with self.assertRaises(ValueError):run(xml.replace('KJV:Deut.12.32','KJV:Deut.12.31'),vm)
        with self.assertRaises(ValueError):run(xml,vm.replace('<verse wlc="Deut.13.1" kjv="Deut.12.32" type="full"/>',''))
        foreign=empty.replace('/>','><verse osisID="Gen.1.1"><note>KJV:Deut.12.1</note></verse></osis>')
        with self.assertRaises(ValueError): deuteronomy_shift_passages(xml.encode(),vm.encode(),foreign.encode(),empty.encode(),empty.encode(),empty.encode(),empty.encode())
        with self.assertRaises(ValueError):run(xml.replace('<w id="12-1"','<unknown><w id="12-1"',1).replace('>x</w>','>x</w></unknown>',1),vm)

    def test_deuteronomy_next_disjoint_scope_and_claim_guards(self):
        # what_bug_this_catches: importing skipped chapters or accepting foreign edges or alternate words.
        empty='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"/>'
        xml='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><osisText osisIDWork="OSHB">'+''.join(f'<chapter osisID="Deut.{c}"><verse osisID="Deut.{c}.1"><w id="{c}" lemma="1" morph="HN">x</w>'+('<note><rdg><w id="alt" lemma="2" morph="HN">z</w></rdg></note>' if c==21 else '')+'</verse></chapter>' for c in (21,22,23,24))+'</osisText></osis>'
        vm='<verseMap xmlns="http://www.APTBibleTools.com/namespace"/>'
        def run(start,edge=vm,gen=empty):return deuteronomy_next_passages(xml.encode(),edge.encode(),gen.encode(),empty.encode(),empty.encode(),empty.encode(),empty.encode(),counts=(1,),start=start,expected_variants=(('Deut.21.1',1),) if start==21 else ())
        rows=run(21)+run(24);self.assertEqual([r[2] for r in rows],[21,24]);self.assertEqual([t[0] for t in rows[0][-1]],['21'])
        edge=vm.replace('/>','><verse wlc="Deut.22.1" kjv="Deut.21.1" type="full"/></verseMap>')
        with self.assertRaises(ValueError):run(21,edge)
        outgoing=vm.replace('/>','><verse wlc="Deut.21.1" kjv="Deut.22.1" type="full"/></verseMap>')
        with self.assertRaises(ValueError):run(21,outgoing)
        foreign=empty.replace('/>','><verse osisID="Gen.1.1"><note>KJV:Deut.21.1</note></verse></osis>')
        with self.assertRaises(ValueError):run(21,gen=foreign)

    def test_deuteronomy_end_variant_and_edges(self):
        # what_bug_this_catches: end-of-book chapter shifts or note readings entering main words.
        empty='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"/>'
        xml='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><osisText osisIDWork="OSHB">'+''.join(f'<chapter osisID="Deut.{c}"><verse osisID="Deut.{c}.1"><w id="{c}" lemma="1" morph="HN">x</w>'+('<note><rdg><w id="alt" lemma="2" morph="HN">z</w></rdg></note>' if c==32 else '')+'</verse></chapter>' for c in (31,32,33,34))+'</osisText></osis>'
        vm='<verseMap xmlns="http://www.APTBibleTools.com/namespace"/>'
        run=lambda m: deuteronomy_end_passages(xml.encode(),m.encode(),empty.encode(),empty.encode(),empty.encode(),empty.encode(),empty.encode(),counts=(1,1,1,1),start=31,expected_variants=(('Deut.32.1',1),))
        rows=run(vm);self.assertEqual([r[2] for r in rows],[31,32,33,34]);self.assertEqual([t[0] for t in rows[1][-1]],['32'])
        edge=vm.replace('/>','><verse wlc="Deut.30.1" kjv="Deut.31.1" type="full"/></verseMap>')
        with self.assertRaises(ValueError):run(edge)

    def test_deuteronomy_two_shift_boundaries_and_note_guards(self):
        # what_bug_this_catches: wrong source references at two chapter boundaries or variants in primary text.
        empty='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"/>';chapters=''
        variants={15:2,16:1,20:1,21:1,23:1,24:1,25:1,26:2,27:1,28:1,29:1}
        for ch,count in ((22,29),(23,26),(28,69),(29,28)):
            verses=''
            for v in range(1,count+1):
                target=(('Deut.22.30' if v==1 else f'Deut.23.{v-1}') if ch==23 else 'Deut.29.1' if (ch,v)==(28,69) else f'Deut.29.{v+1}' if ch==29 else None)
                note=f'<note>KJV:{target}</note>' if target else ''
                n=variants.get(v,0) if ch==22 else 1 if (ch,v) in ((28,27),(28,30),(29,22)) else 0
                alt='<note><rdg>'+''.join(f'<w id="alt-{ch}-{v}-{i}" lemma="2" morph="HN">z</w>' for i in range(n))+'</rdg></note>' if n else ''
                verses+=f'<verse osisID="Deut.{ch}.{v}">{note}<w id="{ch}-{v}" lemma="1" morph="HN">x</w>{alt}</verse>'
            chapters+=f'<chapter osisID="Deut.{ch}">{verses}</chapter>'
        xml=f'<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><osisText osisIDWork="OSHB">{chapters}</osisText></osis>'
        edges='<verse wlc="Deut.23.1" kjv="Deut.22.30" type="full"/>'+''.join(f'<verse wlc="Deut.23.{v+1}" kjv="Deut.23.{v}" type="full"/>' for v in range(1,26))+'<verse wlc="Deut.28.69" kjv="Deut.29.1" type="full"/>'+''.join(f'<verse wlc="Deut.29.{v-1}" kjv="Deut.29.{v}" type="full"/>' for v in range(2,30))
        vm=f'<verseMap xmlns="http://www.APTBibleTools.com/namespace">{edges}</verseMap>'
        run=lambda x,m,g=empty: deuteronomy_double_shift_passages(x.encode(),m.encode(),g.encode(),empty.encode(),empty.encode(),empty.encode(),empty.encode())
        rows=run(xml,vm);lookup={(r[2],r[3]):r for r in rows};self.assertEqual(len(rows),152)
        for target,source in [((22,30),'Deut.23.1'),((23,25),'Deut.23.26'),((29,1),'Deut.28.69'),((29,23),'Deut.29.22')]:self.assertEqual(lookup[target][4],source)
        self.assertEqual([t[0] for t in lookup[29,23][-1]],['29-22'])
        with self.assertRaises(ValueError):run(xml,vm.replace('Deut.22.30','Deut.22.29',1))
        with self.assertRaises(ValueError):run(xml.replace('KJV:Deut.29.1','KJV:Deut.29.2',1),vm)
        foreign=empty.replace('/>','><verse osisID="Gen.1.1"><note>KJV:Deut.22.1</note></verse></osis>')
        with self.assertRaises(ValueError):run(xml,vm,foreign)

    def test_numbers26_two_source_decision_rejects_changed_evidence(self):
        # what_bug_this_catches: returning one source fragment or changing the approved source order.
        chapters=''
        for ch,count in ((25,19),(26,65)):
            verses=''
            for v in range(1,count+1):
                ref=f'Num.{ch}.{v}';ids=NUMBERS26_IDS.get(ref,[f'{ch}-{v}'])
                words=''.join(f'<w id="{i}" lemma="1" morph="HN">x</w>' for i in ids)
                note='<note>KJV:Num.26.1</note>' if ref=='Num.25.19' else ''
                verses+=f'<verse osisID="{ref}">{note}{words}</verse>'
            chapters+=f'<chapter osisID="Num.{ch}">{verses}</chapter>'
        xml=f'<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace">{chapters}</osis>'
        vm='<verseMap xmlns="http://www.APTBibleTools.com/namespace"><verse wlc="Num.25.19" kjv="Num.26.1" type="full"/></verseMap>'
        empty='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"/>'
        run=lambda x,m,g=empty: adjudicated_parts(x.encode(),m.encode(),g.encode(),empty.encode(),empty.encode(),empty.encode())
        parts=run(xml,vm);self.assertEqual([(ref,[t[0] for t in tokens]) for ref,tokens in parts],list(NUMBERS26_IDS.items()))
        with self.assertRaises(ValueError):run(xml,vm.replace('Num.25.19','Num.26.1'))
        with self.assertRaises(ValueError):run(xml.replace('KJV:Num.26.1','KJV:Num.26.2'),vm)
        with self.assertRaises(ValueError):run(xml.replace('04Scg','changed'),vm)
        foreign=empty.replace('/>','><verse osisID="Gen.1.1"><note>KJV:Num.26.1</note></verse></osis>')
        with self.assertRaises(ValueError):run(xml,vm,foreign)
    def test_numbers26_parts_api_is_ordered_and_fails_closed(self):
        # what_bug_this_catches: a partial, reordered, duplicate, or undisclosed multi-source response.
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'parts.sqlite'
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute('CREATE TABLE mappings(edition TEXT,book TEXT,chapter INTEGER,verse INTEGER,osis TEXT)')
                conn.execute('CREATE TABLE tokens(osis TEXT,position INTEGER,token_id TEXT,text TEXT,lemma TEXT,morphology TEXT)')
                conn.execute('CREATE TABLE mapping_source_parts(edition TEXT,book TEXT,chapter INTEGER,verse INTEGER,ordinal INTEGER,osis TEXT)')
                conn.execute('CREATE TABLE mapping_adjudications(edition TEXT,book TEXT,chapter INTEGER,verse INTEGER,decision_id TEXT)')
                conn.execute('INSERT INTO mappings VALUES(?,?,?,?,?)',('kjv','bcbooks:num',26,1,'Num.25.19+Num.26.1'))
                conn.executemany('INSERT INTO tokens VALUES(?,?,?,?,?,?)',[(ref,i,token,'x','1','HN') for ref,ids in [('Num.25.19',['04xYD','04Y15','047YH']),('Num.26.1',['04Scg','04VfY','043CP','04JCV','04kSK','04Dw8','04v1s','04Hhz','046Hr','04NqA'])] for i,token in enumerate(ids)])
                conn.executemany('INSERT INTO mapping_source_parts VALUES(?,?,?,?,?,?)',[('kjv','bcbooks:num',26,1,0,'Num.25.19'),('kjv','bcbooks:num',26,1,1,'Num.26.1')])
                conn.execute('INSERT INTO mapping_adjudications VALUES(?,?,?,?,?)',('kjv','bcbooks:num',26,1,'numbers26-1-local-reference-adjudication-v1'))
            r=hebrew_passage('kjv','bcbooks:num',26,1,db);self.assertEqual([p['osis'] for p in r['source_parts']],['Num.25.19','Num.26.1']);self.assertEqual(len(r['tokens']),13)
            self.assertFalse(hebrew_passage('webp','bcbooks:num',26,1,db)['available'])
            # Wrong identity, source order, token identity, position and partial data must fail closed.
            for sql in ["UPDATE mappings SET osis='wrong'", "UPDATE mapping_adjudications SET decision_id='other'", "UPDATE mapping_source_parts SET osis=CASE ordinal WHEN 0 THEN 'Num.26.1' ELSE 'Num.25.19' END", "DELETE FROM mapping_source_parts WHERE ordinal=1", "DELETE FROM tokens WHERE token_id='04NqA'", "UPDATE tokens SET position=99 WHERE token_id='04NqA'", "UPDATE tokens SET token_id='wrong' WHERE token_id='04NqA'"]:
                corrupt=Path(tmp)/'corrupt.sqlite'
                with closing(sqlite3.connect(db)) as conn, closing(sqlite3.connect(corrupt)) as target: conn.backup(target)
                with closing(sqlite3.connect(corrupt)) as conn, conn: conn.execute(sql)
                self.assertFalse(hebrew_passage('kjv','bcbooks:num',26,1,corrupt)['available'],sql)
                corrupt.unlink()
            with closing(sqlite3.connect(db)) as conn, conn: conn.execute('UPDATE mapping_source_parts SET ordinal=2 WHERE ordinal=1')
            self.assertFalse(hebrew_passage('kjv','bcbooks:num',26,1,db)['available'])
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute('UPDATE mapping_source_parts SET ordinal=1 WHERE ordinal=2');conn.execute('DELETE FROM mapping_adjudications')
            self.assertFalse(hebrew_passage('kjv','bcbooks:num',26,1,db)['available'])
    def test_final_numbers_identity_range_rejects_new_edges_and_variants(self):
        # what_bug_this_catches: silently accepting an altered final-range map or note word.
        empty='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"/>'
        xml='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><osisText osisIDWork="OSHB"><chapter osisID="Num.31"><verse osisID="Num.31.1"><w id="a" lemma="1" morph="HN">x</w></verse><verse osisID="Num.31.2"><w id="b" lemma="2" morph="HN">y</w><note><rdg><w id="alt" lemma="3" morph="HN">z</w></rdg></note></verse></chapter></osisText></osis>'
        vm='<verseMap xmlns="http://www.APTBibleTools.com/namespace"/>'
        run=lambda x,m: numbers31_passages(x.encode(),m.encode(),empty.encode(),empty.encode(),empty.encode(),empty.encode(),counts=(2,),start=31,expected_variants=(('Num.31.2',1),))
        rows=run(xml,vm);self.assertEqual([(r[4],[t[0] for t in r[5]]) for r in rows],[('Num.31.1',['a']),('Num.31.2',['b'])])
        edge=vm.replace('/>','><verse wlc="Num.30.1" kjv="Num.31.1" type="full"/></verseMap>')
        with self.assertRaises(ValueError): run(xml,edge)
        with self.assertRaises(ValueError): run(xml.replace('morph="HN">x','morph="AN">x'),vm)
    def test_numbers_26_join_is_unavailable_and_29_30_shift_is_exact(self):
        # what_bug_this_catches: showing one incomplete source verse as all of KJV Numbers 26:1.
        edges='<verse wlc="Num.25.19" kjv="Num.26.1" type="full"/><verse wlc="Num.30.1" kjv="Num.29.40" type="full"/>'
        edges+=''.join(f'<verse wlc="Num.30.{v+1}" kjv="Num.30.{v}" type="full"/>' for v in range(1,17))
        vm=f'<verseMap xmlns="http://www.APTBibleTools.com/namespace">{edges}</verseMap>'; chapters=''
        variants={'Num.21.32','Num.23.13','Num.26.9'}
        for ch,count in enumerate(NUM21_SOURCE_COUNTS,21):
            verses=''
            for v in range(1,count+1):
                ref=f'Num.{ch}.{v}';target='Num.26.1' if (ch,v)==(25,19) else 'Num.29.40' if (ch,v)==(30,1) else f'Num.30.{v-1}' if ch==30 else None
                note=f'<note>KJV:{target}</note>' if target else ''
                alt=f'<note><rdg><w id="alt-{ch}-{v}" lemma="2" morph="HN">a</w></rdg></note>' if ref in variants else ''
                verses+=f'<verse osisID="{ref}">{note}<w id="{ch}-{v}" lemma="1" morph="HN">x</w>{alt}</verse>'
            chapters+=f'<chapter osisID="Num.{ch}">{verses}</chapter>'
        xml=f'<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><osisText osisIDWork="OSHB">{chapters}</osisText></osis>'
        empty='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"/>'
        run=lambda x,m: numbers21_passages(x.encode(),m.encode(),empty.encode(),empty.encode(),empty.encode(),empty.encode())
        rows=run(xml,vm);lookup={(r[2],r[3]):r for r in rows};self.assertEqual(len(rows),323)
        self.assertNotIn((26,1),lookup);self.assertEqual((lookup[25,18][4],lookup[26,2][4],lookup[29,40][4],lookup[30,1][4],lookup[30,16][4]),('Num.25.18','Num.26.2','Num.30.1','Num.30.2','Num.30.17'))
        self.assertFalse({'Num.25.19','Num.26.1'} & {r[4] for r in rows})
        self.assertEqual([t[0] for t in lookup[26,9][5]],['26-9'])
        with self.assertRaises(ValueError): run(xml,vm.replace('Num.25.19','Num.25.18',1))
        with self.assertRaises(ValueError): run(xml.replace('KJV:Num.26.1','KJV:Num.26.2',1),vm)
    def test_numbers_16_17_shift_requires_exact_edges_and_note_markers(self):
        # what_bug_this_catches: lost verses across Numbers 16/17 or alternate note words in primary tokens.
        edges=''.join(f'<verse wlc="Num.17.{v-35}" kjv="Num.16.{v}" type="full"/>' for v in range(36,51))
        edges+=''.join(f'<verse wlc="Num.17.{v+15}" kjv="Num.17.{v}" type="full"/>' for v in range(1,14))
        vm=f'<verseMap xmlns="http://www.APTBibleTools.com/namespace">{edges}</verseMap>'
        chapters=''; variants={'Num.12.3','Num.14.36','Num.16.11'}
        for ch,count in enumerate(NUM11_SOURCE_COUNTS,11):
            verses=''
            for v in range(1,count+1):
                ref=f'Num.{ch}.{v}';target=(f'Num.16.{v+35}' if ch==17 and v<=15 else f'Num.17.{v-15}' if ch==17 else None)
                note=f'<note>KJV:{target}</note>' if target else ''
                alt=f'<note><rdg><w id="alt-{ch}-{v}" lemma="2" morph="HN">a</w></rdg></note>' if ref in variants else ''
                verses+=f'<verse osisID="{ref}">{note}<w id="{ch}-{v}" lemma="1" morph="HN">x</w>{alt}</verse>'
            chapters+=f'<chapter osisID="Num.{ch}">{verses}</chapter>'
        xml=f'<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><osisText osisIDWork="OSHB">{chapters}</osisText></osis>'
        empty='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"/>'
        run=lambda x,m: numbers11_passages(x.encode(),m.encode(),empty.encode(),empty.encode(),empty.encode(),empty.encode())
        rows=run(xml,vm);lookup={(r[2],r[3]):r for r in rows};self.assertEqual(len(rows),316)
        self.assertEqual((lookup[16,35][4],lookup[16,36][4],lookup[16,50][4],lookup[17,1][4],lookup[17,13][4]),('Num.16.35','Num.17.1','Num.17.15','Num.17.16','Num.17.28'))
        self.assertEqual([x[0] for x in lookup[16,11][5]],['16-11'])
        with self.assertRaises(ValueError):run(xml,vm.replace('Num.17.1','Num.17.2',1))
        with self.assertRaises(ValueError):run(xml.replace('KJV:Num.16.36','KJV:Num.16.37',1),vm)
    def test_numbers_identity_range_rejects_map_note_and_language_conflicts(self):
        # what_bug_this_catches: claiming identity after a new map edge or exposing a note variant.
        empty='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"/>'
        xml='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><osisText osisIDWork="OSHB"><chapter osisID="Num.1"><verse osisID="Num.1.1"><w id="a" lemma="1" morph="HN">x</w></verse><verse osisID="Num.1.2"><w id="b" lemma="2" morph="HN">y</w><note><rdg><w id="alt" lemma="3" morph="HN">z</w></rdg></note></verse></chapter></osisText></osis>'
        vm='<verseMap xmlns="http://www.APTBibleTools.com/namespace"/>'
        run=lambda x,m,p=empty: numbers1_passages(x.encode(),m.encode(),empty.encode(),empty.encode(),empty.encode(),p.encode(),counts=(2,),start=1,expected_variants=(('Num.1.2',1),))
        rows=run(xml,vm);self.assertEqual([(r[4],[t[0] for t in r[5]]) for r in rows],[('Num.1.1',['a']),('Num.1.2',['b'])])
        edge=vm.replace('/>','><verse wlc="Num.2.1" kjv="Num.1.1" type="full"/></verseMap>')
        with self.assertRaises(ValueError): run(xml,edge)
        foreign=empty.replace('/>','><verse osisID="Ps.1.1"><note>KJV:Num.1.1</note></verse></osis>')
        with self.assertRaises(ValueError): run(xml,vm,foreign)
        with self.assertRaises(ValueError): run(xml.replace('morph="HN">x','morph="AN">x'),vm)
    def test_final_leviticus_identity_range_fails_on_map_or_source_changes(self):
        # what_bug_this_catches: a new incoming edge or variant being silently treated as identity.
        empty='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"/>'
        xml='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><osisText osisIDWork="OSHB"><chapter osisID="Lev.21"><verse osisID="Lev.21.1"><w id="a" lemma="1" morph="HN">x</w></verse><verse osisID="Lev.21.2"><w id="b" lemma="2" morph="HN">y</w><note><rdg><w id="alt" lemma="3" morph="HN">z</w></rdg></note></verse></chapter></osisText></osis>'
        vm='<verseMap xmlns="http://www.APTBibleTools.com/namespace"/>'
        run=lambda x,m: leviticus21_passages(x.encode(),m.encode(),empty.encode(),empty.encode(),empty.encode(),counts=(2,),start=21,expected_variants=(('Lev.21.2',1),))
        rows=run(xml,vm);self.assertEqual([(r[4],[t[0] for t in r[5]]) for r in rows],[('Lev.21.1',['a']),('Lev.21.2',['b'])])
        edge=vm.replace('/>','><verse wlc="Lev.20.1" kjv="Lev.21.1" type="full"/></verseMap>')
        with self.assertRaises(ValueError): run(xml,edge)
        with self.assertRaises(ValueError): run(xml.replace('morph="HN">x','morph="AN">x'),vm)
    def test_leviticus_identity_range_rejects_map_and_note_conflicts(self):
        # what_bug_this_catches: hiding a new exception or note variant under an identity mapping.
        empty='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"/>'
        xml='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><osisText osisIDWork="OSHB"><chapter osisID="Lev.11"><verse osisID="Lev.11.1"><w id="a" lemma="1" morph="HN">x</w></verse><verse osisID="Lev.11.2"><w id="b" lemma="2" morph="HN">y</w><note><rdg><w id="alt" lemma="3" morph="HN">z</w></rdg></note></verse></chapter></osisText></osis>'
        vm='<verseMap xmlns="http://www.APTBibleTools.com/namespace"/>'
        run=lambda x,m,g=empty: leviticus11_passages(x.encode(),m.encode(),g.encode(),empty.encode(),empty.encode(),counts=(2,),start=11,expected_variants=(('Lev.11.2',1),))
        rows=run(xml,vm);self.assertEqual([(r[4],[t[0] for t in r[5]]) for r in rows],[('Lev.11.1',['a']),('Lev.11.2',['b'])])
        edge=vm.replace('/>','><verse wlc="Lev.11.1" kjv="Lev.10.1" type="full"/></verseMap>')
        with self.assertRaises(ValueError): run(xml,edge)
        foreign=empty.replace('/>','><verse osisID="Gen.1.1"><note>KJV:Lev.11.1</note></verse></osis>')
        with self.assertRaises(ValueError): run(xml,vm,foreign)
        with self.assertRaises(ValueError): run(xml.replace('morph="HN">x','morph="AN">x'),vm)
    def test_leviticus_5_6_shift_preserves_primary_and_rejects_conflicts(self):
        # what_bug_this_catches: treating Leviticus 5/6 as identical across editions or adding note variants.
        edges=''.join(f'<verse wlc="Lev.5.{v+19}" kjv="Lev.6.{v}" type="full"/>' for v in range(1,8))
        edges+=''.join(f'<verse wlc="Lev.6.{v-7}" kjv="Lev.6.{v}" type="full"/>' for v in range(8,31))
        vm=f'<verseMap xmlns="http://www.APTBibleTools.com/namespace">{edges}</verseMap>'
        chapters=''
        for ch,count in enumerate(LEV_SOURCE_COUNTS,1):
            verses=''
            for v in range(1,count+1):
                target=f'Lev.6.{v-19}' if ch==5 and v>=20 else f'Lev.6.{v+7}' if ch==6 else None
                note=f'<note>KJV:{target}</note>' if target else ''
                alt='<note><rdg><w id="alt" lemma="2" morph="HN">a</w></rdg></note>' if (ch,v)==(9,22) else ''
                verses+=f'<verse osisID="Lev.{ch}.{v}">{note}<w id="{ch}-{v}" lemma="1" morph="HN">x</w>{alt}</verse>'
            chapters+=f'<chapter osisID="Lev.{ch}">{verses}</chapter>'
        xml=f'<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><osisText osisIDWork="OSHB">{chapters}</osisText></osis>'
        empty='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"/>'
        run=lambda x,m,g=empty: leviticus_passages(x.encode(),m.encode(),g.encode(),empty.encode(),empty.encode())
        rows=run(xml,vm);lookup={(r[2],r[3]):r for r in rows}
        self.assertEqual(len(rows),252)
        self.assertEqual((lookup[5,19][4],lookup[6,1][4],lookup[6,7][4],lookup[6,8][4],lookup[6,30][4]),('Lev.5.19','Lev.5.20','Lev.5.26','Lev.6.1','Lev.6.23'))
        self.assertEqual([t[0] for t in lookup[9,22][5]],['9-22'])
        with self.assertRaises(ValueError): run(xml,vm.replace('Lev.5.20','Lev.5.19',1))
        with self.assertRaises(ValueError): run(xml.replace('KJV:Lev.6.1','KJV:Lev.6.2',1),vm)
        foreign=empty.replace('/>','><verse osisID="Gen.1.1"><note>KJV:Lev.1.1</note></verse></osis>')
        with self.assertRaises(ValueError): run(xml,vm,foreign)
    def test_psalm_42_44_override_is_narrow_and_fails_on_changed_evidence(self):
        # what_bug_this_catches: broad suppression of foreign notes or silently changed map edges.
        words=lambda ch: ''.join(f'<w id="{i}" lemma="1" morph="HN">x</w>' for i in ADJUDICATED_IDS[ch])
        xml='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace">'+''.join(f'<verse osisID="Ps.{ch}.2"><note>KJV:Ps.42.1</note>{words(ch)}</verse>' for ch in (42,44))+'</osis>'
        vm='<verseMap xmlns="http://www.APTBibleTools.com/namespace"><verse wlc="Ps.42.2" kjv="Ps.42.1" type="full"/><verse wlc="Ps.44.2" kjv="Ps.44.1" type="full"/></verseMap>'
        empty='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"/>'
        rows=adjudicated_passages(xml.encode(),vm.encode(),empty.encode(),empty.encode())
        self.assertEqual([(r[2],r[3],r[4],len(r[5])) for r in rows],[(42,1,'Ps.42.2',10),(44,1,'Ps.44.2',11)])
        with self.assertRaises(ValueError): adjudicated_passages(xml.encode(),vm.replace('Ps.44.1','Ps.42.1').encode(),empty.encode(),empty.encode())
        with self.assertRaises(ValueError): adjudicated_passages(xml.replace('KJV:Ps.42.1','KJV:Ps.44.1',1).encode(),vm.encode(),empty.encode(),empty.encode())
        foreign=empty.replace('/>','><verse osisID="Exod.1.1"><note>KJV:Ps.42.1</note></verse></osis>')
        with self.assertRaises(ValueError): adjudicated_passages(xml.encode(),vm.encode(),empty.encode(),foreign.encode())
    def test_psalm_reference_adjudication_is_disclosed_only_for_selected_case(self):
        # what_bug_this_catches: silent override or contaminating other editions and passages.
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'adjudication.sqlite'
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute('CREATE TABLE mappings(edition TEXT,book TEXT,chapter INTEGER,verse INTEGER,osis TEXT)')
                conn.execute('CREATE TABLE tokens(osis TEXT,position INTEGER,token_id TEXT,text TEXT,lemma TEXT,morphology TEXT)')
                conn.execute('CREATE TABLE mapping_adjudications(edition TEXT,book TEXT,chapter INTEGER,verse INTEGER,decision_id TEXT)')
                conn.execute('INSERT INTO mappings VALUES(?,?,?,?,?)',('kjv','bcbooks:ps',42,1,'Ps.42.2'))
                conn.execute('INSERT INTO tokens VALUES(?,?,?,?,?,?)',('Ps.42.2',0,'token','x','1','HN'))
                conn.execute('INSERT INTO mapping_adjudications VALUES(?,?,?,?,?)',('kjv','bcbooks:ps',42,1,'psalm-42-44-local-reference-adjudication-v1'))
            result=hebrew_passage('kjv','bcbooks:ps',42,1,db)
            self.assertEqual(result['adjudication_id'],'psalm-42-44-local-reference-adjudication-v1')
            self.assertFalse(hebrew_passage('webp','bcbooks:ps',42,1,db)['available'])
            self.assertFalse(hebrew_passage('kjv','bcbooks:ps',44,1,db)['available'])
    def test_exodus_final_range_is_fail_closed_and_excludes_note_variant(self):
        # what_bug_this_catches: turning a changed final-range map or variant into identity main words.
        empty='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"/>'
        xml='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><osisText osisIDWork="OSHB"><chapter osisID="Exod.31"><verse osisID="Exod.31.1"><w id="a" lemma="1" morph="HN">x</w></verse><verse osisID="Exod.31.2"><w id="b" lemma="2" morph="HN">y</w><note><rdg><w id="alt" lemma="3" morph="HN">z</w></rdg></note></verse></chapter></osisText></osis>'
        vm='<verseMap xmlns="http://www.APTBibleTools.com/namespace"/>'
        run=lambda x,m: exodus31_passages(x.encode(),m.encode(),empty.encode(),empty.encode(),counts=(2,),start=31,expected_variants=(('Exod.31.2',1),))
        rows=run(xml,vm);self.assertEqual([(r[4],[t[0] for t in r[5]]) for r in rows],[('Exod.31.1',['a']),('Exod.31.2',['b'])])
        edge=vm.replace('/>','><verse wlc="Exod.30.1" kjv="Exod.31.1" type="full"/></verseMap>')
        with self.assertRaises(ValueError): run(xml,edge)
        with self.assertRaises(ValueError): run(xml.replace('morph="HN">x','morph="AN">x'),vm)
    def test_exodus_21_22_explicit_shift_and_alternates(self):
        # what_bug_this_catches: losing a source verse across the 21/22 boundary or exposing note variants.
        edge='<verse wlc="Exod.21.37" kjv="Exod.22.1" type="full"/>'
        edge+=''.join(f'<verse wlc="Exod.22.{v-1}" kjv="Exod.22.{v}" type="full"/>' for v in range(2,32))
        vm=f'<verseMap xmlns="http://www.APTBibleTools.com/namespace">{edge}</verseMap>'
        chapters=''; variants={ref for ref,_ in EXODUS21_VARIANTS}
        for ch,count in enumerate(EXODUS21_SOURCE_COUNTS,21):
            verses=''
            for v in range(1,count+1):
                ref=f'Exod.{ch}.{v}'; target='Exod.22.1' if (ch,v)==(21,37) else f'Exod.22.{v+1}' if ch==22 else None
                note=f'<note>KJV:{target}</note>' if target else ''
                alt=f'<note><rdg><w id="alt-{ch}-{v}" lemma="2" morph="HN">a</w></rdg></note>' if ref in variants else ''
                verses+=f'<verse osisID="{ref}">{note}<w id="{ch}-{v}" lemma="1" morph="HN">x</w>{alt}</verse>'
            chapters+=f'<chapter osisID="Exod.{ch}">{verses}</chapter>'
        xml=f'<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><osisText osisIDWork="OSHB">{chapters}</osisText></osis>'
        empty='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"/>'
        rows=exodus21_passages(xml.encode(),vm.encode(),empty.encode(),empty.encode());lookup={(r[2],r[3]):r for r in rows}
        self.assertEqual(len(rows),343)
        self.assertEqual((lookup[21,36][4],lookup[22,1][4],lookup[22,2][4],lookup[22,31][4]),('Exod.21.36','Exod.21.37','Exod.22.1','Exod.22.30'))
        self.assertEqual([t[0] for t in lookup[22,5][5]],['22-4'])
        with self.assertRaises(ValueError): exodus21_passages(xml.encode(),vm.replace('Exod.21.37','Exod.21.36',1).encode(),empty.encode(),empty.encode())
        with self.assertRaises(ValueError): exodus21_passages(xml.replace('KJV:Exod.22.1','KJV:Exod.22.2',1).encode(),vm.encode(),empty.encode(),empty.encode())
        foreign=empty.replace('/>','><verse osisID="Ps.1.1"><note>KJV:Exod.23.1</note></verse></osis>')
        with self.assertRaises(ValueError): exodus21_passages(xml.encode(),vm.encode(),empty.encode(),foreign.encode())
    def test_exodus_identity_range_rejects_edges_foreign_notes_and_variants(self):
        # what_bug_this_catches: silently assuming identity despite map changes or source-note conflicts.
        empty='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"/>'
        xml='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><osisText osisIDWork="OSHB"><chapter osisID="Exod.11"><verse osisID="Exod.11.1"><w id="a" lemma="1" morph="HN">x</w></verse><verse osisID="Exod.11.2"><w id="b" lemma="2" morph="HN">y</w><note><rdg><w id="alt" lemma="3" morph="HN">z</w></rdg></note></verse></chapter></osisText></osis>'
        vm='<verseMap xmlns="http://www.APTBibleTools.com/namespace"/>'
        run=lambda x,m,g=empty,p=empty: passages_for_range(x.encode(),m.encode(),g.encode(),p.encode(),counts=(2,),start=11,expected_variants=(('Exod.11.2',1),))
        rows=run(xml,vm);self.assertEqual([(r[4],[t[0] for t in r[5]]) for r in rows],[('Exod.11.1',['a']),('Exod.11.2',['b'])])
        edge=vm.replace('/>','><verse wlc="Exod.11.1" kjv="Exod.10.1" type="full"/></verseMap>')
        with self.assertRaises(ValueError): run(xml,edge)
        foreign=empty.replace('/>','><verse osisID="Ps.1.1"><note>KJV:Exod.11.1</note></verse></osis>')
        with self.assertRaises(ValueError): run(xml,vm,p=foreign)
        with self.assertRaises(ValueError): run(xml.replace('morph="HN">x','morph="AN">x'),vm)
    def test_exodus_source_mapping_excludes_alternates_and_rejects_conflicts(self):
        # what_bug_this_catches: incorrect 7/8 shift, note variants in main words, or competing source claims.
        edges=''.join(f'<verse wlc="Exod.7.{v+25}" kjv="Exod.8.{v}" type="full"/>' for v in range(1,5))
        edges+=''.join(f'<verse wlc="Exod.8.{v-4}" kjv="Exod.8.{v}" type="full"/>' for v in range(5,33))
        vm=f'<verseMap xmlns="http://www.APTBibleTools.com/namespace">{edges}</verseMap>'
        chapters=''
        for ch,count in enumerate(SOURCE_COUNTS,1):
            verses=''
            for v in range(1,count+1):
                target=(f'Exod.8.{v-25}' if ch==7 and v>=26 else f'Exod.8.{v+4}' if ch==8 else None)
                note=f'<note>KJV:{target}</note>' if target else ''
                alt='<note><rdg><w id="a" lemma="1" morph="HN">a</w><w id="b" lemma="1" morph="HN">b</w></rdg></note>' if (ch,v)==(4,2) else ''
                verses+=f'<verse osisID="Exod.{ch}.{v}">{note}<w id="{ch}-{v}" lemma="1" morph="HN">x</w>{alt}</verse>'
            chapters+=f'<chapter osisID="Exod.{ch}">{verses}</chapter>'
        xml=f'<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><osisText osisIDWork="OSHB">{chapters}</osisText></osis>'
        empty='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"/>'
        rows=exodus_passages(xml.encode(),vm.encode(),empty.encode(),empty.encode()); lookup={(r[2],r[3]):r for r in rows}
        self.assertEqual(len(rows),274)
        self.assertEqual(lookup[8,1][4],'Exod.7.26');self.assertEqual(lookup[8,5][4],'Exod.8.1')
        self.assertEqual([x[0] for x in lookup[4,2][5]],['4-2'])
        with self.assertRaises(ValueError): exodus_passages(xml.replace('KJV:Exod.8.1','KJV:Exod.8.2',1).encode(),vm.encode(),empty.encode(),empty.encode())
        foreign='<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><verse osisID="Ps.1.1"><note>KJV:Exod.1.1</note></verse></osis>'
        with self.assertRaises(ValueError): exodus_passages(xml.encode(),vm.encode(),empty.encode(),foreign.encode())
        with self.assertRaises(ValueError): exodus_passages(xml.replace('<w id="4-2"','<seg><w id="4-2"',1).replace('>x</w><note><rdg>', '>x</w></seg><note><rdg>',1).encode(),vm.encode(),empty.encode(),empty.encode())
    def test_exodus_reference_audit_preserves_chapter_boundary_shift(self):
        # what_bug_this_catches: assuming WLC and KJV Exodus 7–8 use the same numbering.
        edges=''.join(f'<verse wlc="Exod.7.{v+25}" kjv="Exod.8.{v}" type="full"/>' for v in range(1,5))
        edges+=''.join(f'<verse wlc="Exod.8.{v-4}" kjv="Exod.8.{v}" type="full"/>' for v in range(5,33))
        vm=f'<verseMap xmlns="http://www.APTBibleTools.com/namespace">{edges}</verseMap>'
        rows=exodus_map_candidates(vm.encode());lookup={r['target']:r for r in rows}
        self.assertEqual(len(rows),274)
        self.assertEqual((lookup['Exod.7.25']['source'],lookup['Exod.8.1']['source'],lookup['Exod.8.4']['source'],lookup['Exod.8.5']['source'],lookup['Exod.8.32']['source']),('Exod.7.25','Exod.7.26','Exod.7.29','Exod.8.1','Exod.8.28'))
        with self.assertRaises(ValueError): exodus_map_candidates(vm.replace('Exod.7.26','Exod.7.25',1).encode())
        with self.assertRaises(ValueError): exodus_map_candidates(vm.replace('type="full"','type="partial"',1).encode())
    def test_heading_source_edges_are_separate_and_fail_closed(self):
        # what_bug_this_catches: promoting a heading as body or hiding an extra incoming claim.
        words=lambda ch,tag,count: ''.join(f'<w id="{ch}{tag}{i}" lemma="1" morph="HN">x</w>' for i in range(count))
        nodes=''; edges=''
        for ch,(_,h,b) in CASES.items():
            nodes+=f'<verse osisID="Ps.{ch}.2">{words(ch,"h",h)}</verse><verse osisID="Ps.{ch}.3"><note>KJV:Ps.{ch}.1</note>{words(ch,"b",b)}</verse>'
            edges+=f'<verse wlc="Ps.{ch}.2" kjv="Ps.{ch}.1" type="full"/><verse wlc="Ps.{ch}.3" kjv="Ps.{ch}.1" type="full"/>'
        xml=f'<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace">{nodes}</osis>'
        vm=f'<verseMap xmlns="http://www.APTBibleTools.com/namespace">{edges}</verseMap>'
        rows=heading_cases(xml.encode(),vm.encode())
        self.assertEqual([(ch,h[0],b[0],len(h[1]),len(b[1])) for ch,h,b in rows],[(ch,f'Ps.{ch}.2',f'Ps.{ch}.3',h,b) for ch,(_,h,b) in CASES.items()])
        with self.assertRaises(ValueError): heading_cases(xml.encode(),vm.replace('wlc="Ps.51.2"','wlc="Ps.51.1"').encode())
        with self.assertRaises(ValueError): heading_cases(xml.replace('</osis>','<verse osisID="Ps.99.1"><note>KJV:Ps.51.1</note></verse></osis>').encode(),vm.encode())
        with self.assertRaises(ValueError): heading_cases(xml.replace('morph="HN">x','morph="AN">x',1).encode(),vm.encode())
    def test_heading_api_returns_context_separately_from_body(self):
        # what_bug_this_catches: silently merging superscription words into a KJV verse.
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'segments.sqlite'
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute('CREATE TABLE mappings(edition TEXT,book TEXT,chapter INTEGER,verse INTEGER,osis TEXT)')
                conn.execute('CREATE TABLE tokens(osis TEXT,position INTEGER,token_id TEXT,text TEXT,lemma TEXT,morphology TEXT)')
                conn.execute('CREATE TABLE source_segments(edition TEXT,book TEXT,chapter INTEGER,verse INTEGER,role TEXT,osis TEXT)')
                conn.execute('INSERT INTO mappings VALUES(?,?,?,?,?)',('kjv','bcbooks:ps',51,1,'Ps.51.3'))
                conn.execute('INSERT INTO tokens VALUES(?,?,?,?,?,?)',('Ps.51.3',0,'body','b','1','HN'))
                conn.execute('INSERT INTO tokens VALUES(?,?,?,?,?,?)',('Ps.51.2',0,'heading','h','2','HN'))
                conn.execute('INSERT INTO source_segments VALUES(?,?,?,?,?,?)',('kjv','bcbooks:ps',51,1,'source_superscription_excerpt','Ps.51.2'))
            result=hebrew_passage('kjv','bcbooks:ps',51,1,db)
            self.assertEqual([x['token_id'] for x in result['tokens']],['body'])
            self.assertEqual(result['source_segments'][0]['role'],'source_superscription_excerpt')
            self.assertEqual([x['token_id'] for x in result['source_segments'][0]['tokens']],['heading'])
            self.assertFalse(hebrew_passage('webp','bcbooks:ps',51,1,db)['available'])
            self.assertFalse(hebrew_passage('kjv','bcbooks:ps',42,1,db)['available'])
    def test_psalm13_source_spans_require_exact_marker_boundary(self):
        # what_bug_this_catches: overlapping fragments, shifted notes, or a changed partial map.
        words = lambda ids: ''.join(f'<w id="{i}" lemma="1" morph="HN">x</w>' for i in ids)
        xml = ('<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><verse osisID="Ps.13.6"><note>KJV:Ps.13.5</note>' + words(EXPECTED_IDS[:6]) + '<note>KJV:Ps.13.6</note>' + words(EXPECTED_IDS[6:]) + '</verse></osis>')
        edges = ''.join(f'<verse wlc="Ps.13.{i+1}" kjv="Ps.13.{i}" type="full"/>' for i in range(1,5))
        edges += '<verse wlc="Ps.13.6!a" kjv="Ps.13.5" type="partial"/><verse wlc="Ps.13.6!b" kjv="Ps.13.6" type="partial"/>'
        vm = '<verseMap xmlns="http://www.APTBibleTools.com/namespace">' + edges + '</verseMap>'
        rows=split_passages(xml.encode(),vm.encode())
        self.assertEqual([(r[3],r[4],[t[0] for t in r[5]]) for r in rows],[(5,'Ps.13.6!a',EXPECTED_IDS[:6]),(6,'Ps.13.6!b',EXPECTED_IDS[6:])])
        moved=xml.replace('<note>KJV:Ps.13.6</note>', '', 1).replace('<w id="19fZr"', '<note>KJV:Ps.13.6</note><w id="19fZr"',1)
        with self.assertRaises(ValueError): split_passages(moved.encode(),vm.encode())
        with self.assertRaises(ValueError): split_passages(xml.encode(),vm.replace('Ps.13.6!b','Ps.13.6!a').encode())
        foreign=xml.replace('</osis>','<verse osisID="Ps.14.1"><note>KJV:Ps.13.5</note></verse></osis>')
        with self.assertRaises(ValueError): split_passages(foreign.encode(),vm.encode())
    def test_multiple_source_psalm_target_stays_unavailable(self):
        # what_bug_this_catches: choosing one source verse for a two-source KJV target.
        xml = '<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><chapter osisID="Ps.51"><verse osisID="Ps.51.1"><w id="h" lemma="1" morph="HN">h</w></verse><verse osisID="Ps.51.2"><w id="a" lemma="1" morph="HN">a</w></verse><verse osisID="Ps.51.3"><w id="b" lemma="1" morph="HN">b</w><note>KJV:Ps.51.1</note></verse><verse osisID="Ps.51.4"><w id="main" lemma="1" morph="HN">x</w><note>KJV:Ps.51.2</note><note type="variant"><rdg type="x-qere"><w id="alt" lemma="2" morph="HN">y</w></rdg></note></verse></chapter></osis>'
        vm = '<verseMap xmlns="http://www.APTBibleTools.com/namespace"><book osisID="Ps"><verse wlc="Ps.51.2" kjv="Ps.51.1" type="full"/><verse wlc="Ps.51.3" kjv="Ps.51.1" type="full"/><verse wlc="Ps.51.4" kjv="Ps.51.2" type="full"/></book></verseMap>'
        rows = later_psalm_candidates(xml.encode(),vm.encode(),(2,),start=51)
        self.assertEqual([(r[2],r[3],r[4],[t[0] for t in r[5]]) for r in rows],[(51,2,'Ps.51.4',['main'])])
        with self.assertRaises(ValueError): later_psalm_candidates(xml.encode(),vm.replace('wlc="Ps.51.3"','wlc="Ps.51.4"').encode(),(2,),start=51)
    def test_foreign_source_note_conflict_cannot_silently_map_a_verse(self):
        # what_bug_this_catches: Ps.44.2 incorrectly claiming KJV Ps.42.1 alongside Ps.42.2.
        xml = '<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><verse osisID="Ps.42.2"><note>KJV:Ps.42.1</note></verse><verse osisID="Ps.44.2"><note>KJV:Ps.42.1</note></verse></osis>'
        claims = note_claims(ET.fromstring(xml))
        self.assertEqual(claims['Ps.42.1'], ['Ps.42.2','Ps.44.2'])
        with self.assertRaises(ValueError): ensure_no_foreign_claim(claims,'Ps.42.1','Ps.42.2')
        ensure_no_foreign_claim({'Ps.42.1':['Ps.42.2']},'Ps.42.1','Ps.42.2')
    def test_later_psalm_offset_excludes_heading_and_note_alternatives(self):
        # what_bug_this_catches: shifted verse or qere note being exposed as main reading.
        xml = '<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><chapter osisID="Ps.12"><verse osisID="Ps.12.1"><w id="head" lemma="1" morph="HN">h</w></verse><verse osisID="Ps.12.2"><w id="main" lemma="2" morph="HN">b</w><note>KJV:Ps.12.1</note><note type="variant"><rdg type="x-qere"><w id="alt" lemma="3" morph="HN">v</w></rdg></note></verse></chapter></osis>'
        vm = '<verseMap xmlns="http://www.APTBibleTools.com/namespace"><book osisID="Ps"><verse wlc="Ps.12.2" kjv="Ps.12.1" type="full"/></book></verseMap>'
        row = psalm_candidates(xml.encode(),vm.encode(),(1,),start=12)[0]
        self.assertEqual((row[2],row[3],row[4],[t[0] for t in row[5]]),(12,1,'Ps.12.2',['main']))
        with self.assertRaises(ValueError): psalm_candidates(xml.encode(),vm.replace('type="full"','type="partial"').encode(),(1,),start=12)
        with self.assertRaises(ValueError): psalm_candidates(xml.replace('KJV:Ps.12.1','KJV:Ps.12.2').encode(),vm.encode(),(1,),start=12)

    def test_psalm_13_partial_targets_remain_unavailable(self):
        # what_bug_this_catches: assigning an unsplit source verse to either partial target.
        verses = '<verse osisID="Ps.13.1"><w id="head" lemma="1" morph="HN">h</w></verse>'
        verses += ''.join(f'<verse osisID="Ps.13.{i}"><w id="x{i}" lemma="1" morph="HN">x</w><note>KJV:Ps.13.{i-1}</note></verse>' for i in range(2,6))
        verses += '<verse osisID="Ps.13.6"><w id="split" lemma="1" morph="HN">s</w><note>KJV:Ps.13.5</note><note>KJV:Ps.13.6</note></verse>'
        xml = f'<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><chapter osisID="Ps.13">{verses}</chapter></osis>'
        edges = ''.join(f'<verse wlc="Ps.13.{i+1}" kjv="Ps.13.{i}" type="full"/>' for i in range(1,5))
        edges += '<verse wlc="Ps.13.6!a" kjv="Ps.13.5" type="partial"/><verse wlc="Ps.13.6!b" kjv="Ps.13.6" type="partial"/>'
        vm = f'<verseMap xmlns="http://www.APTBibleTools.com/namespace"><book osisID="Ps">{edges}</book></verseMap>'
        rows = psalm_candidates(xml.encode(),vm.encode(),(6,),start=13)
        self.assertEqual([(r[2],r[3]) for r in rows],[(13,1),(13,2),(13,3),(13,4)])
        with self.assertRaises(ValueError): psalm_candidates(xml.encode(),vm.replace('Ps.13.6!b','Ps.13.6!a').encode(),(6,),start=13)
    def test_note_variants_are_not_main_source_words(self):
        # what_bug_this_catches: qere words appended to the main ketiv stream or lost in an unknown wrapper.
        xml = '<verse xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><w id="main" lemma="1" morph="HN">x</w><note type="variant"><rdg type="x-qere"><w id="alt1" lemma="2" morph="HN">y</w><w id="alt2" lemma="3" morph="HN">z</w></rdg></note></verse>'
        primary, notes = primary_and_note_tokens(ET.fromstring(xml))
        self.assertEqual([t[0] for t in primary], ['main'])
        self.assertEqual([t[0] for t in notes], ['alt1','alt2'])
        with self.assertRaises(ValueError):
            primary_and_note_tokens(ET.fromstring(xml.replace('<w id="main"', '<seg><w id="main"').replace('>x</w>', '>x</w></seg>')))
    def test_psalm_heading_offset_requires_map_and_note(self):
        # what_bug_this_catches: exposing a superscription as KJV verse 1 or guessing a shift.
        xml = '<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><chapter osisID="Ps.3"><verse osisID="Ps.3.1"><w id="head" lemma="1" morph="HN">h</w></verse><verse osisID="Ps.3.2"><w id="body" lemma="2" morph="HN">b</w><note>KJV:Ps.3.1</note></verse></chapter></osis>'
        vm = '<verseMap xmlns="http://www.APTBibleTools.com/namespace"><book osisID="Ps"><verse wlc="Ps.3.2" kjv="Ps.3.1" type="full"/></book></verseMap>'
        row = psalm_passages(xml.encode(), vm.encode(), (1,), start=3)[0]
        self.assertEqual((row[2], row[3], row[4], row[5][0][0]), (3, 1, 'Ps.3.2', 'body'))
        with self.assertRaises(ValueError): psalm_passages(xml.encode(), vm.replace('Ps.3.2','Ps.3.1').encode(), (1,), start=3)
        with self.assertRaises(ValueError): psalm_passages(xml.replace('KJV:Ps.3.1','KJV:Ps.3.2').encode(), vm.encode(), (1,), start=3)
        with self.assertRaises(ValueError): psalm_passages(xml.replace('morph="HN">b','morph="AN">b').encode(), vm.encode(), (1,), start=3)
    def test_genesis_boundary_requires_explicit_edges_and_source_notes(self):
        # what_bug_this_catches: a one-verse shift or contradictory source note hidden by identity mapping.
        c31 = ''.join(f'<verse osisID="Gen.31.{i}"><w id="a{i}" lemma="1" morph="HN">x</w></verse>' for i in range(1,55))
        c32 = ''.join(f'<verse osisID="Gen.32.{i}"><w id="b{i}" lemma="1" morph="HN">x</w><note>KJV:{"Gen.31.55" if i==1 else f"Gen.32.{i-1}"}</note></verse>' for i in range(1,34))
        xml = f'<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><chapter osisID="Gen.31">{c31}</chapter><chapter osisID="Gen.32">{c32}</chapter></osis>'
        edges = ''.join(f'<verse wlc="Gen.32.{i}" kjv="{"Gen.31.55" if i==1 else f"Gen.32.{i-1}"}" type="full"/>' for i in range(1,34))
        vm = f'<verseMap xmlns="http://www.APTBibleTools.com/namespace"><book osisID="Gen">{edges}</book></verseMap>'
        rows = boundary_passages(xml.encode(), vm.encode())
        self.assertEqual([(rows[i][2], rows[i][3], rows[i][4]) for i in (53,54,55,86)],
                         [(31,54,'Gen.31.54'), (31,55,'Gen.32.1'), (32,1,'Gen.32.2'), (32,32,'Gen.32.33')])
        with self.assertRaises(ValueError): boundary_passages(xml.encode(), vm.replace('kjv="Gen.31.55"','kjv="Gen.31.54"').encode())
        with self.assertRaises(ValueError): boundary_passages(xml.replace('KJV:Gen.31.55','KJV:Gen.31.54').encode(), vm.encode())
        with self.assertRaises(ValueError): boundary_passages(xml.replace('morph="HN"','morph="X"',1).encode(), vm.encode())

    def test_candidate_builder_preserves_tokens_and_rejects_unsupported_language(self):
        # what_bug_this_catches: changed token fields or presenting Aramaic as Hebrew.
        xml = '<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><chapter osisID="Gen.1"><verse osisID="Gen.1.1"><w id="x1" lemma="b/7225" morph="HN">abc</w></verse></chapter></osis>'
        self.assertEqual(chapter_records(xml.encode(), (1,))[0][-1], [('x1', 'abc', 'b/7225', 'HN')])
        with self.assertRaises(ValueError): chapter_records(xml.replace('HN', 'AN').encode(), (1,))
        with self.assertRaises(ValueError): chapter_records(xml.replace('lemma="b/7225"', '').encode(), (1,))
        with self.assertRaises(ValueError): chapter_records(xml.replace('Gen.1.1', 'Gen.1.2').encode(), (1,))
        later = xml.replace('Gen.1.', 'Gen.33.').replace('osisID="Gen.1"', 'osisID="Gen.33"')
        self.assertEqual(chapter_records(later.encode(), (1,), start=33)[0][2:5], (33, 1, 'Gen.33.1'))
        with self.assertRaises(ValueError): chapter_records(later.encode(), (1,), start=34)
        vm = '<verseMap xmlns="http://www.APTBibleTools.com/namespace"><book osisID="Gen"><verse wlc="Gen.32.1" kjv="Gen.33.1" type="full"/></book></verseMap>'
        # what_bug_this_catches: an incoming chapter-33 exception silently treated as identity.
        with self.assertRaises(ValueError): validate_genesis_map(vm.encode(), 33)

    def test_candidate_publishing_never_leaves_partial_or_overwrites(self):
        # what_bug_this_catches: interrupted/failed build exposed as a completed candidate.
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'candidate.sqlite'
            def fail(path):
                Path(path).write_text('partial')
                raise ValueError('failed build')
            with self.assertRaises(ValueError): publish_candidate(target, fail)
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])
            target.write_text('existing')
            with self.assertRaises(FileExistsError): publish_candidate(target, lambda p: Path(p).write_text('replacement'))
            self.assertEqual(target.read_text(), 'existing')

    def test_candidate_rejects_wrong_raw_hash_and_changed_baseline(self):
        # what_bug_this_catches: provenance drift or quietly changing accepted mappings.
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / 'old-testament.json'
            raw.write_text('{}')
            with patch('build_oshb_genesis10.RAW_ENGLISH', raw):
                with self.assertRaises(ValueError):
                    verify_english_catalog({'source_files': [{'path': 'old/old-testament.json', 'sha256': 'wrong'}]})
            previous = Path(directory) / 'previous.sqlite'
            with closing(sqlite3.connect(previous)) as old, closing(sqlite3.connect(':memory:')) as candidate:
                for conn in (old, candidate):
                    conn.execute('create table mappings (edition,book,chapter,verse,osis)')
                    conn.execute('create table tokens (osis,position,token_id,text,lemma,morphology)')
                old.execute("insert into mappings values ('kjv','gen',1,1,'Gen.1.1')")
                old.commit()
                with patch('build_oshb_genesis10.PREVIOUS', previous):
                    with self.assertRaises(ValueError): compare_previous(candidate)
    def test_offline_mapping_audit_never_guesses_splits_or_missing(self):
        # what_bug_this_catches: an incoming shift, split or collision being treated as identity.
        source = {f'Gen.1.{n}': {'issues': [], 'kjv_notes': []} for n in (1, 2, 3, 4)}
        edges = [dict(wlc='Gen.1.2', kjv='Gen.1.1', type='full'),
                 dict(wlc='Gen.1.3!a', kjv='Gen.1.2', type='partial'),
                 dict(wlc='Gen.1.3!b', kjv='Gen.1.3', type='partial'),
                 dict(wlc='Gen.1.4', kjv='Gen.1.4', type='full'),
                 dict(wlc='Gen.1.2', kjv='Gen.1.4', type='full')]
        result = {r['target']: r for r in audit(source, [f'Gen.1.{n}' for n in range(1, 6)], edges)}
        self.assertIn('source_has_multiple_targets', result['Gen.1.1']['reasons'])
        self.assertIn('partial_or_ambiguous_exception', result['Gen.1.2']['reasons'])
        self.assertIn('multiple_incoming', result['Gen.1.4']['reasons'])
        self.assertIn('source_missing', result['Gen.1.5']['reasons'])
        self.assertTrue(all(r['status'] == 'review_required' for r in result.values()))

    def test_offline_audit_preserves_mixed_language_and_notes(self):
        # what_bug_this_catches: language inferred from a whole verse, or contradictory KJV note ignored.
        xml = '<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><verse osisID="Gen.31.47"><w id="a" morph="Hn">x</w><w id="b" morph="An">y</w><note>KJV:Gen.31.48</note></verse></osis>'
        source = parse_source(xml.encode())
        self.assertEqual(source['Gen.31.47']['language_markers'], {'H': 1, 'A': 1})
        self.assertIn('source_note_conflict', audit(source, ['Gen.31.47'], [])[0]['reasons'])

    def test_offline_audit_identity_cross_book_and_heading(self):
        # what_bug_this_catches: mapping an identity when its source goes elsewhere,
        # ignoring a cross-book incoming edge, or treating a heading as an English verse.
        record = {'issues': [], 'kjv_notes': []}
        source = {'Ps.3.1': record, 'Ps.3.2': {'issues': [], 'kjv_notes': ['Ps.3.1']}, 'Gen.1.1': record}
        edges = [dict(wlc='Ps.3.2', kjv='Ps.3.1', type='full'),
                 dict(wlc='Other.1.1', kjv='Gen.1.1', type='full')]
        ps = audit(source, ['Ps.3.1', 'Ps.3.2'], edges)
        self.assertEqual(ps[0]['source'], 'Ps.3.2')
        self.assertEqual(ps[0]['status'], 'candidate')
        self.assertIn('identity_source_has_outgoing_exception', ps[1]['reasons'])
        self.assertIn('source_missing', audit(source, ['Gen.1.1'], edges)[0]['reasons'])
        with self.assertRaises(ValueError): base_ref('Ps.3.1!')

    def test_offline_audit_rejects_incomplete_or_wrong_source_catalog(self):
        # what_bug_this_catches: empty or wrong-edition target catalog yielding plausible totals.
        with sqlite3.connect(':memory:') as conn:
            conn.execute('create table verses (book_id text, chapter_number integer, verse_number integer, source_id text)')
            with self.assertRaises(ValueError): catalog_targets(conn, 'Gen', 'bcbooks:gen')
            conn.executemany('insert into verses values (?,?,?,?)', [('bcbooks:gen', 1, n, 'wrong') for n in range(1533)])
            with self.assertRaises(ValueError): catalog_targets(conn, 'Gen', 'bcbooks:gen')

    def test_genesis1_source_and_mapping_guards(self):
        # what_bug_this_catches: an incoming KJV exception, missing or duplicate verse.
        xml = '<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><chapter osisID="Gen.1">' + ''.join(f'<verse osisID="Gen.1.{n}"><w id="w{n}" lemma="b/7225" morph="H">א</w></verse>' for n in range(1,32)) + '</chapter></osis>'
        validate_genesis_source(xml.encode('utf-8'),1,31)
        with self.assertRaises(ValueError): validate_genesis_source(xml.replace('Gen.1.31','Gen.1.30').encode('utf-8'),1,31)
        vm = '<verseMap xmlns="http://www.APTBibleTools.com/namespace"><book osisID="Gen"><verse wlc="Gen.32.1" kjv="Gen.31.55" type="full"/></book></verseMap>'
        validate_genesis_map(vm.encode(),1)
        with self.assertRaises(ValueError): validate_genesis_map(vm.replace('Gen.31.55','Gen.1.1').encode(),1)
        with self.assertRaises(ValueError): validate_genesis_map(vm.replace('Gen.32.1','Gen.1.1').encode(),1)
        incoming=vm.replace('</verseMap>', '<book osisID="Other"><verse wlc="Other.1.1" kjv="Gen.1.2" type="full"/></book></verseMap>')
        with self.assertRaises(ValueError): validate_genesis_map(incoming.encode(),1)
        for n in range(1,32):
            self.assertEqual(parse_passage(xml.encode('utf-8'),f'Gen.1.{n}'),[(f'w{n}','א','b/7225','H')])
    def test_genesis2_source_and_cross_passage_identity_guards(self):
        # what_bug_this_catches: chapter-2 exceptions, missing verses and repeated word IDs.
        xml = '<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><chapter osisID="Gen.2">' + ''.join(f'<verse osisID="Gen.2.{n}"><w id="g2-{n}" lemma="b/7225" morph="H">א</w></verse>' for n in range(1,26)) + '</chapter></osis>'
        validate_genesis_source(xml.encode('utf-8'),2,25)
        with self.assertRaises(ValueError): validate_genesis_source(xml.replace('Gen.2.25','Gen.2.24').encode('utf-8'),2,25)
        with self.assertRaises(ValueError): validate_genesis_source(xml.replace('<w id="g2-1"','<note>KJV:Gen.2.2</note><w id="g2-1"').encode('utf-8'),2,25)
        vm='<verseMap xmlns="http://www.APTBibleTools.com/namespace"><book osisID="Gen"><verse wlc="Gen.32.1" kjv="Gen.31.55" type="full"/></book></verseMap>'
        validate_genesis_map(vm.encode(),2)
        with self.assertRaises(ValueError): validate_genesis_map(vm.replace('Gen.31.55','Gen.2.1').encode(),2)
        with self.assertRaises(ValueError): validate_genesis_map(vm.replace('Gen.32.1','Gen.2.25').encode(),2)
        for n in range(1,26): self.assertEqual(parse_passage(xml.encode('utf-8'),f'Gen.2.{n}'),[(f'g2-{n}','א','b/7225','H')])
        validate_unique_token_ids([('x',[('a','x',None,None)]),('y',[('b','x',None,None)])])
        with self.assertRaises(ValueError): validate_unique_token_ids([('x',[('a','x',None,None)]),('y',[('a','x',None,None)])])
    def test_hebrew_api_rejects_invalid_requests_and_returns_mapping(self):
        handler=Handler.__new__(Handler)
        handler.server=SimpleNamespace(server_port=23800)
        handler.headers={'Host':'127.0.0.1:23800'}
        response=[]
        handler.send_error=lambda status, message='': response.append(('error',status))
        handler.json_response=lambda value: response.append(('json',value))
        handler.path='/api/hebrew-passage?edition=kjv&book=bcbooks%3Aps&chapter=3&verse=1'
        with patch('serve_reader.OSHB_DB') as db, patch('serve_reader.hebrew_passage',return_value={'available':True,'tokens':[]} ) as lookup:
            db.is_file.return_value=True
            handler.do_GET()
            lookup.assert_called_once_with('kjv','bcbooks:ps',3,1)
            self.assertEqual(response[-1][0],'json')
            handler.path='/api/hebrew-passage?edition=kjv&book=x&chapter=-1&verse=1'
            handler.do_GET()
            self.assertEqual(response[-1],('error',400))
            handler.path='/api/hebrew-passage?edition=unknown&book=x&chapter=1&verse=1'
            handler.do_GET()
            self.assertEqual(response[-1],('error',400))
    def test_operator_store_selection_and_missing_file(self):
        # what_bug_this_catches: silently falling back when an explicitly selected store is absent.
        self.assertEqual(oshb_store_path(Path('data')), Path('data/word-study/oshb-genesis-psalms1-150-ps13-spans.sqlite'))
        self.assertEqual(oshb_store_path(Path('data'), 'custom.sqlite'), Path('custom.sqlite'))
        handler=Handler.__new__(Handler); handler.server=SimpleNamespace(server_port=23800)
        handler.headers={'Host':'127.0.0.1:23800'}
        handler.path='/api/hebrew-passage?edition=kjv&book=bcbooks%3Agen&chapter=31&verse=47'
        response=[]; handler.send_error=lambda status, message='': response.append((status,message))
        with tempfile.TemporaryDirectory() as directory, patch('serve_reader.OSHB_DB', Path(directory)/'absent.sqlite'):
            handler.do_GET()
        self.assertEqual(response[-1],(503,'Original-language data not installed'))
    def test_hebrew_source_mapping_and_api_unavailable(self):
        # what_bug_this_catches: mapping a superscription or WEB verse by number.
        xml = '<osis xmlns="http://www.bibletechnologies.net/2003/OSIS/namespace"><verse osisID="Ps.3.1"><w id="heading">x</w></verse><verse osisID="Ps.3.2"><note>KJV:Ps.3.1</note><w id="token" lemma="b/7225" morph="H">א</w></verse></osis>'.encode('utf-8')
        self.assertEqual(parse_passage(xml, 'Ps.3.2', 'KJV:Ps.3.1'), [('token','א','b/7225','H')])
        with self.assertRaises(ValueError): parse_passage(xml, 'Ps.3.1', 'KJV:Ps.3.1')
        with self.assertRaises(ValueError): parse_passage(xml, 'Ps.3.3')
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'oshb.sqlite'
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute('CREATE TABLE mappings(edition TEXT, book TEXT, chapter INTEGER, verse INTEGER, osis TEXT)')
                conn.execute('CREATE TABLE tokens(osis TEXT, position INTEGER, token_id TEXT, text TEXT, lemma TEXT, morphology TEXT)')
                conn.execute('INSERT INTO mappings VALUES(?,?,?,?,?)',('kjv','bcbooks:ps',3,1,'Ps.3.2'))
                conn.execute('INSERT INTO tokens VALUES(?,?,?,?,?,?)',('Ps.3.2',0,'token','א','b/7225','H'))
                conn.execute('INSERT INTO mappings VALUES(?,?,?,?,?)',('kjv','bcbooks:gen',2,25,'Gen.2.25'))
                conn.execute('INSERT INTO tokens VALUES(?,?,?,?,?,?)',('Gen.2.25',0,'gen2-token','א','b/7225','H'))
            self.assertEqual(hebrew_passage('kjv','bcbooks:ps',3,1,db)['osis'],'Ps.3.2')
            self.assertEqual(hebrew_passage('kjv','bcbooks:gen',2,25,db)['tokens'][0]['token_id'],'gen2-token')
            self.assertFalse(hebrew_passage('webp','bcbooks:gen',2,25,db)['available'])
            self.assertFalse(hebrew_passage('webp','bcbooks:ps',3,1,db)['available'])
            self.assertFalse(hebrew_passage('kjv','bcbooks:ps',3,2,db)['available'])
            self.assertFalse(hebrew_passage('kjv','bcbooks:gen',3,1,db)['available'])
    def test_source_row_audit_detects_changed_or_duplicate_entries(self):
        # what_bug_this_catches: a matching row count masking changed dictionary data.
        source = [{'number':'H1', 'lemma':'אב', 'xlit':'ab', 'pronounce':'ab', 'description':'father'}]
        good = [('H1','hebrew','אב','ab','ab','father')]
        self.assertTrue(rows_match_source(source, good))
        self.assertFalse(rows_match_source(source, [('H1','hebrew','אב','ab','ab','altered')]))
        self.assertFalse(rows_match_source(source * 2, good * 2))
    def test_word_study_responsive_css_contract(self):
        # Static rule only; this does not replace a computed browser-layout check.
        css = (Path(__file__).resolve().parents[1] / 'app/src/style.css').read_text(encoding='utf-8')
        self.assertRegex(css, r'\.study-layout\s*\{[^}]*grid-template-columns\s*:\s*minmax\(0,1fr\)\s+minmax\(260px,320px\)')
        self.assertRegex(css, r'@media\s*\(max-width\s*:\s*1000px\)\s*\{\s*\.study-layout\s*\{[^}]*grid-template-columns\s*:\s*1fr')
    def test_literal_word_lookup(self):
        # what_bug_this_catches: SQL metacharacters broadening a word search.
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'words.sqlite'
            with closing(sqlite3.connect(db)) as conn, conn:
                conn.execute('CREATE TABLE entries(number TEXT,language TEXT,lemma TEXT,transliteration TEXT,pronunciation TEXT,definition TEXT)')
                conn.executemany('INSERT INTO entries VALUES(?,?,?,?,?,?)', [('H1','hebrew','אב','ab','ab','father, ancestor'),('G26','greek','ἀγάπη','agape','agape','love, affection')])
            self.assertEqual(lookup_words('h1', db)[0]['lemma'], 'אב')
            self.assertEqual(lookup_words('love', db)[0]['number'], 'G26')
            self.assertEqual(lookup_words('אב', db)[0]['number'], 'H1')
            self.assertEqual(lookup_words('%', db), [])
            self.assertEqual(lookup_words('x' * 81, db), [])
    def test_host_blocks_dns_rebinding(self):
        # what_bug_this_catches: a foreign Host can otherwise address the local API.
        self.assertTrue(valid_host("127.0.0.1:23800", 23800))
        self.assertTrue(valid_host("localhost:23800", 23800))
        self.assertFalse(valid_host("attacker.example:23800", 23800))
        self.assertFalse(valid_host("127.0.0.1:23801", 23800))
        self.assertFalse(valid_origin("https://attacker.example", 23800))
        self.assertTrue(valid_origin("http://127.0.0.1:23800", 23800))
        self.assertTrue(valid_host('localhost:23801',8000,('localhost:23801',)))
        self.assertFalse(valid_host('evil.example:23801',8000,('localhost:23801',)))
        self.assertTrue(valid_origin('http://localhost:23801',8000,('http://localhost:23801',)))
        self.assertFalse(valid_origin('https://evil.example',8000,('http://localhost:23801',)))

    def test_health_requires_readable_nonempty_catalog(self):
        handler=Handler.__new__(Handler);handler.server=SimpleNamespace(server_port=23800);handler.headers={'Host':'127.0.0.1:23800'};handler.path='/healthz';response=[]
        handler.send_error=lambda status, message='': response.append(('error',status))
        handler.json_response=lambda value: response.append(('json',value))
        with patch('serve_reader.query',return_value=[{'id':'x'}]): handler.do_GET()
        self.assertEqual(response[-1],('json',{'status':'ok'}))
        with patch('serve_reader.query',return_value=[]): handler.do_GET()
        self.assertEqual(response[-1],('error',503))
        with patch('serve_reader.query',side_effect=sqlite3.OperationalError('bad database')): handler.do_GET()
        self.assertEqual(response[-1],('error',503))

    def test_web_mapping_and_missing_verse(self):
        # what_bug_this_catches: an empty publisher verse must not become KJV or fake text.
        xml = b'<verseFile><v b="LUK" c="17" v="35">Synthetic.</v><v b="LUK" c="17" v="36" /></verseFile>'
        self.assertEqual(list(rows_from_xml(xml)), [("bcbooks:luke", 17, 35, "Synthetic.")])
        with self.assertRaises(ValueError):
            list(rows_from_xml(b'<verseFile><v b="ZZZ" c="1" v="1">x</v></verseFile>'))


if __name__ == "__main__":
    unittest.main()
