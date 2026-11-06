"""Offline, non-promoting OSHB reference audit; output is candidate evidence only."""
import collections
import hashlib
import json
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
from contextlib import closing

from build_oshb_subset import CATALOG, MANIFEST, NS, RAW

MAP_NS = {'m': 'http://www.APTBibleTools.com/namespace'}
BOOKS = {'Gen': ('Gen.xml', 'bcbooks:gen'), 'Ps': ('Ps.xml', 'bcbooks:ps')}
REF = re.compile(r'^[A-Za-z0-9]+\.[0-9]+\.[0-9]+$')
MAP_REF = re.compile(r'^[A-Za-z0-9]+\.[0-9]+\.[0-9]+(?:![A-Za-z0-9]+)?$')
CATALOG_SOURCE = 'bcbooks-scriptures-json'
EXPECTED_COUNTS = {'Gen': 1533, 'Ps': 2461}


def base_ref(value):
    if not value or not MAP_REF.fullmatch(value):
        raise ValueError(f'invalid mapped reference: {value}')
    return value.split('!', 1)[0]


def catalog_targets(conn, osis, book_id):
    rows = conn.execute('SELECT chapter_number, verse_number, source_id FROM verses WHERE book_id=?', (book_id,)).fetchall()
    if len(rows) != EXPECTED_COUNTS[osis] or {r[2] for r in rows} != {CATALOG_SOURCE}:
        raise ValueError(f'missing, incomplete or unexpected catalog source for {book_id}')
    targets = [f'{osis}.{ch}.{v}' for ch, v, _ in rows]
    if len(set(targets)) != len(targets):
        raise ValueError(f'duplicate catalog coordinates: {book_id}')
    return targets


def audit(source_verses, target_refs, exceptions):
    """Return every target candidate and every anomaly; never resolve partials by guess."""
    incoming, outgoing = collections.defaultdict(list), collections.defaultdict(list)
    for item in exceptions:
        incoming[base_ref(item['kjv'])].append(item)
        outgoing[base_ref(item['wlc'])].append(item)
    results = []
    for target in sorted(target_refs):
        edges = incoming[target]
        source = base_ref(edges[0]['wlc']) if len(edges) == 1 else target
        reasons = []
        if len(edges) > 1:
            reasons.append('multiple_incoming')
        if edges and (len(edges) != 1 or edges[0]['type'] != 'full' or '!' in edges[0]['wlc'] or '!' in edges[0]['kjv']):
            reasons.append('partial_or_ambiguous_exception')
        if not edges and outgoing[target]:
            reasons.append('identity_source_has_outgoing_exception')
        if len(outgoing[source]) > 1:
            reasons.append('source_has_multiple_targets')
        if source not in source_verses:
            reasons.append('source_missing')
        else:
            record = source_verses[source]
            if record['issues']:
                reasons.extend(record['issues'])
            notes = record['kjv_notes']
            if notes and (len(notes) != 1 or notes[0] != target):
                reasons.append('source_note_conflict')
        results.append({'target': target, 'source': source, 'kind': 'exception' if edges else 'identity_candidate',
                        'status': 'review_required' if reasons else 'candidate', 'reasons': sorted(set(reasons)),
                        'edges': edges})
    return results


def parse_source(content):
    root = ET.fromstring(content)
    records, ids = {}, collections.Counter()
    for verse in root.findall('.//o:verse', NS):
        ref = verse.get('osisID')
        if not ref or not REF.fullmatch(ref) or ref in records:
            raise ValueError(f'invalid or duplicate source reference: {ref}')
        words = verse.findall('.//o:w', NS)
        issues = []
        if not words:
            issues.append('no_tokens')
        for word in words:
            token_id = word.get('id')
            if not token_id or not ''.join(word.itertext()):
                issues.append('invalid_token')
            if token_id:
                ids[token_id] += 1
        records[ref] = {'issues': issues, 'token_count': len(words),
                        'missing_lemma': sum(not w.get('lemma') for w in words),
                        'missing_morph': sum(not w.get('morph') for w in words),
                        'kjv_notes': [(n.text or '')[4:] for n in verse.findall('o:note', NS)
                                      if (n.text or '').startswith('KJV:')],
                        'language_markers': dict(collections.Counter((w.get('morph') or '')[:1] or 'missing' for w in words))}
    duplicate = sorted(k for k, v in ids.items() if v > 1)
    if duplicate:
        raise ValueError(f'duplicate source token IDs: {duplicate[:10]}')
    return records


def main():
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    contents = {}
    for name, expected in manifest['files'].items():
        contents[name] = (RAW / name).read_bytes()
        if hashlib.sha256(contents[name]).hexdigest() != expected:
            raise ValueError(f'Source hash mismatch: {name}')
    map_root = ET.fromstring(contents['VerseMap.xml'])
    exceptions = []
    for entry in map_root.findall('.//m:verse', MAP_NS):
        item = {key: entry.get(key) for key in ('wlc', 'kjv', 'type')}
        if not all(item.values()) or item['type'] not in ('full', 'partial'):
            raise ValueError(f'invalid exception entry: {item}')
        base_ref(item['wlc'])
        base_ref(item['kjv'])
        exceptions.append(item)
    report = {'revision': manifest['revision'], 'sha256': manifest['files'], 'exception_entries': exceptions,
              'scope': 'offline candidates only; no promotion, WEB mapping or English-word alignment', 'books': {}}
    with closing(sqlite3.connect(CATALOG.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        # One read transaction supplies a consistent snapshot for both books.
        conn.execute('BEGIN')
        for osis, (filename, book_id) in BOOKS.items():
            source = parse_source(contents[filename])
            targets = catalog_targets(conn, osis, book_id)
            target_set = set(targets)
            results = audit(source, targets, exceptions)
            used = {r['source'] for r in results if r['status'] == 'candidate'}
            catalog_fingerprint = hashlib.sha256(('\n'.join(sorted(targets)) + '\n').encode('utf-8')).hexdigest()
            report['books'][osis] = {'source_verses': len(source), 'source_tokens': sum(x['token_count'] for x in source.values()),
                'catalog_source_id': CATALOG_SOURCE, 'catalog_coordinates_sha256': catalog_fingerprint,
                'missing_lemma_tokens': sum(x['missing_lemma'] for x in source.values()),
                'missing_morph_tokens': sum(x['missing_morph'] for x in source.values()),
                'aramaic_marker_refs': sorted(k for k, v in source.items() if v['language_markers'].get('A')),
                'target_verses': len(targets), 'candidate_count': sum(r['status'] == 'candidate' for r in results),
                'review_count': sum(r['status'] != 'candidate' for r in results), 'results': results,
                'source_not_candidate': sorted(set(source) - used),
                'exception_targets_not_in_catalog': sorted({base_ref(e['kjv']) for e in exceptions
                    if base_ref(e['kjv']).startswith(osis + '.') and base_ref(e['kjv']) not in target_set}),
                'source_language_markers': dict(sum((collections.Counter(v['language_markers']) for v in source.values()), collections.Counter()))}
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    print()


if __name__ == '__main__':
    main()
