#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

from cg_import_common import (
    REPO_ROOT,
    apply_schema,
    connect_sqlite,
    dump_json,
    load_json,
    load_manifests,
    source_by_id,
    upsert_manifest_metadata,
)


SOURCE_ID = "mormon-documentation-project-strongs"
DEFAULT_STRONGS_PATH = REPO_ROOT / "data" / "downloads" / "strongs" / "strongs.json"
STRONGS_RE = re.compile(r"^[HG]\d+[A-Za-z]?$")


def strongs_language(number: str) -> str:
    if number.startswith("H"):
        return "hebrew"
    if number.startswith("G"):
        return "greek"
    raise ValueError(f"Unsupported Strong's number: {number}")


def clear_strongs_rows(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM strongs_entries_fts")
    conn.execute("DELETE FROM strongs_entries WHERE source_id = ?", (SOURCE_ID,))
    conn.execute("DELETE FROM import_receipts WHERE source_id = ?", (SOURCE_ID,))


def rebuild_strongs_fts(conn: sqlite3.Connection) -> int:
    conn.execute("DELETE FROM strongs_entries_fts")
    conn.execute(
        """
        INSERT INTO strongs_entries_fts(
            strongs_entry_id,
            strongs_number,
            lemma,
            transliteration,
            pronunciation,
            definition_full
        )
        SELECT
            id,
            strongs_number,
            COALESCE(lemma, ''),
            COALESCE(transliteration, ''),
            COALESCE(pronunciation, ''),
            definition_full
        FROM strongs_entries
        ORDER BY language, strongs_number
        """
    )
    return int(conn.execute("SELECT COUNT(*) FROM strongs_entries_fts").fetchone()[0])


def import_strongs(
    conn: sqlite3.Connection,
    strongs_path: Path = DEFAULT_STRONGS_PATH,
    clear_existing: bool = True,
    rebuild_fts: bool = True,
) -> dict[str, int]:
    if not strongs_path.exists():
        raise FileNotFoundError(f"Strong's source file does not exist: {strongs_path}")

    sources_doc, _licenses_doc = load_manifests()
    source = source_by_id(sources_doc, SOURCE_ID)
    license_id = source["license_id"]
    entries = load_json(strongs_path)
    if not isinstance(entries, list):
        raise ValueError(f"Strong's JSON must be a list: {strongs_path}")

    if clear_existing:
        clear_strongs_rows(conn)

    counts = {
        "strongs_entries": 0,
        "strongs_entries_fts": 0,
        "hebrew": 0,
        "greek": 0,
    }
    seen: set[str] = set()

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"Strong's entry {index} must be an object.")
        number = str(entry.get("number") or "")
        if not STRONGS_RE.match(number):
            raise ValueError(f"Invalid Strong's number at index {index}: {number!r}")
        if number in seen:
            raise ValueError(f"Duplicate Strong's number: {number}")
        seen.add(number)

        language = strongs_language(number)
        conn.execute(
            """
            INSERT INTO strongs_entries(
                id,
                strongs_number,
                language,
                lemma,
                transliteration,
                pronunciation,
                definition_full,
                source_id,
                license_id,
                raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                number,
                number,
                language,
                entry.get("lemma"),
                entry.get("xlit"),
                entry.get("pronounce"),
                str(entry.get("description") or ""),
                SOURCE_ID,
                license_id,
                dump_json(entry),
            ),
        )
        counts["strongs_entries"] += 1
        counts[language] += 1

    if rebuild_fts:
        counts["strongs_entries_fts"] = rebuild_strongs_fts(conn)

    conn.execute(
        """
        INSERT INTO import_receipts(id, source_id, importer, details_json)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            importer = excluded.importer,
            details_json = excluded.details_json
        """,
        (
            "import-mormon-documentation-project-strongs",
            SOURCE_ID,
            Path(__file__).name,
            dump_json({"source_path": strongs_path.as_posix(), "counts": counts}),
        ),
    )
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Strong's JSON into CG SQLite.")
    parser.add_argument("--db", type=Path, required=True, help="SQLite database path.")
    parser.add_argument(
        "--strongs-path",
        type=Path,
        default=DEFAULT_STRONGS_PATH,
        help="Path to strongs.json.",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Do not clear existing Strong's rows before import.",
    )
    parser.add_argument(
        "--no-rebuild-fts",
        action="store_true",
        help="Do not rebuild Strong's FTS rows after import.",
    )
    args = parser.parse_args()

    conn = connect_sqlite(args.db)
    try:
        apply_schema(conn)
        sources_doc, licenses_doc = load_manifests()
        upsert_manifest_metadata(conn, sources_doc, licenses_doc)
        counts = import_strongs(
            conn,
            args.strongs_path,
            clear_existing=not args.no_clear,
            rebuild_fts=not args.no_rebuild_fts,
        )
        conn.commit()
    finally:
        conn.close()

    print(json.dumps(counts, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
