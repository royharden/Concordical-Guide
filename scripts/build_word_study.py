"""Create a separate read-only lookup store from the existing local lexicon."""
import sqlite3
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/generated/sqlite/cg-source-v1.sqlite'
TARGET = ROOT / 'data/generated/word-study/strongs.sqlite'


def rows_match_source(entries, rows):
    by_id = {e['number']: (e['number'], 'hebrew' if e['number'].startswith('H') else 'greek', e.get('lemma'), e.get('xlit'), e.get('pronounce'), str(e.get('description') or '')) for e in entries}
    return len(by_id) == len(entries) == len(rows) == len({row[0] for row in rows}) and all(by_id.get(row[0]) == row for row in rows)


def main():
    if TARGET.exists():
        raise SystemExit('Target already exists; preserve it rather than overwrite it.')
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(SOURCE.resolve().as_uri() + '?mode=ro', uri=True) as source:
        receipt = source.execute("SELECT sha256 FROM source_files WHERE source_id=? AND path=?", ('mormon-documentation-project-strongs', 'data/downloads/strongs/strongs.json')).fetchone()
        raw = ROOT / 'data/downloads/strongs/strongs.json'
        expected = '2a6fa9d82c675de67785013a17c0cbbe8472a8ee02b91ce4a71b53ca540954ac'
        raw_bytes = raw.read_bytes()
        if not receipt or receipt[0] != expected or hashlib.sha256(raw_bytes).hexdigest() != expected:
            raise SystemExit('Strong’s source hash does not match the recorded receipt.')
        rows = source.execute('SELECT strongs_number,language,lemma,transliteration,pronunciation,definition_full FROM strongs_entries ORDER BY strongs_number').fetchall()
        entries = json.loads(raw_bytes)
        if not rows_match_source(entries, rows):
            raise SystemExit('Imported lexicon rows differ from the pinned local source JSON.')
    if len(rows) != 14298:
        raise SystemExit('Unexpected source entry count; inspect provenance before building.')
    try:
        with sqlite3.connect(TARGET) as target:
            target.execute('CREATE TABLE entries (number TEXT PRIMARY KEY, language TEXT NOT NULL, lemma TEXT, transliteration TEXT, pronunciation TEXT, definition TEXT NOT NULL)')
            target.executemany('INSERT INTO entries VALUES (?,?,?,?,?,?)', rows)
    except Exception:
        TARGET.unlink(missing_ok=True)
        raise
    print(f'Built {TARGET}: {len(rows)} entries')


if __name__ == '__main__':
    main()
