"""Create a corrected Genesis-only fallback from the reviewed main-reading store."""
import json
import sqlite3
from contextlib import closing
from build_oshb_genesis10 import digest, publish_candidate
from build_oshb_subset import ROOT

SOURCE = ROOT / 'data/generated/word-study/oshb-genesis-psalms1-10-main-reading.sqlite'
SOURCE_SHA256 = '7ce35e2177b00e9c8f9b6ec4f850f356093bd78093334a777f18a3264090237e'
TARGET = ROOT / 'data/generated/word-study/oshb-genesis-main-reading-fallback.sqlite'


def main():
    if TARGET.exists():
        raise SystemExit('Fallback exists; do not overwrite it')
    if digest(SOURCE) != SOURCE_SHA256:
        raise ValueError('Corrected source store hash mismatch')
    def build(path):
        with closing(sqlite3.connect(SOURCE.resolve().as_uri() + '?mode=ro', uri=True)) as src:
            with closing(sqlite3.connect(path)) as out:
                src.backup(out)
                with out:
                    out.execute("DELETE FROM tokens WHERE osis IN (SELECT osis FROM mappings WHERE book='bcbooks:ps' AND NOT (chapter=3 AND verse=1))")
                    out.execute("DELETE FROM mappings WHERE book='bcbooks:ps' AND NOT (chapter=3 AND verse=1)")
                    if out.execute('SELECT COUNT(*) FROM mappings').fetchone()[0] != 1534:
                        raise ValueError('Unexpected fallback mapping count')
                    if out.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or digest(SOURCE) != SOURCE_SHA256:
                        raise ValueError('Fallback integrity or source hash check failed')
    publish_candidate(TARGET, build)
    print(json.dumps({'file': str(TARGET), 'sha256': digest(TARGET), 'status': 'corrected fallback; not active'}, indent=2))


if __name__ == '__main__':
    main()
