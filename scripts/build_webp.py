"""Build a separate WEB Protestant store from the pinned publisher archive."""
import argparse
import hashlib
import json
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/manifests/webp.json"
# Explicit book identities, independent of title matching or import order.
MAP = dict(zip(
    "GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO ECC SNG ISA JER LAM EZK DAN HOS JOL AMO OBA JON MIC NAM HAB ZEP HAG ZEC MAL MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP COL 1TH 2TH 1TI 2TI TIT PHM HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV".split(),
    "gen ex lev num deut josh judg ruth 1-sam 2-sam 1-kgs 2-kgs 1-chr 2-chr ezra neh esth job ps prov eccl song isa jer lam ezek dan hosea joel amos obad jonah micah nahum hab zeph hag zech mal matt mark luke john acts rom 1-cor 2-cor gal eph philip col 1-thes 2-thes 1-tim 2-tim titus philem heb james 1-pet 2-pet 1-jn 2-jn 3-jn jude rev".split(),
    strict=True,
))


def rows_from_xml(data):
    root = ET.fromstring(data)
    if root.tag != "verseFile":
        raise ValueError("Unexpected WEB XML root")
    seen = set()
    for v in root:
        if v.tag != "v" or v.get("b") not in MAP or not (v.get("c", "").isdigit() and v.get("v", "").isdigit()):
            raise ValueError(f"Unexpected WEB verse: {v.attrib}")
        key = ("bcbooks:" + MAP[v.get("b")], int(v.get("c")), int(v.get("v")))
        if key in seen or len(v):
            raise ValueError(f"Duplicate or malformed WEB verse: {key}")
        seen.add(key)
        # The publisher uses empty elements for omitted verses; never fabricate text.
        if not v.text or not v.text.strip():
            continue
        yield (*key, v.text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/generated/webp/engwebp.sqlite")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    archive = ROOT / manifest["storage"]
    if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["archive_sha256"]:
        raise ValueError("WEB archive hash does not match manifest")
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite: {args.output}")
    with zipfile.ZipFile(archive) as z:
        rows = list(rows_from_xml(z.read(manifest["archive_member"])))
    if len(rows) != 31098 or len({r[0] for r in rows}) != 66:
        raise ValueError("Unexpected WEB corpus counts")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(args.output) as conn:
            conn.execute("CREATE TABLE verses(book_id TEXT NOT NULL,chapter INTEGER NOT NULL,verse INTEGER NOT NULL,text TEXT NOT NULL,PRIMARY KEY(book_id,chapter,verse))")
            conn.executemany("INSERT INTO verses VALUES (?,?,?,?)", rows)
            conn.execute("CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
            conn.executemany("INSERT INTO metadata VALUES (?,?)", [("source_id",manifest["id"]),("archive_sha256",manifest["archive_sha256"])])
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("WEB database integrity check failed")
    except Exception:
        args.output.unlink(missing_ok=True)
        raise
    print(f"Built {len(rows)} WEB verses in {args.output}")


if __name__ == "__main__":
    main()
