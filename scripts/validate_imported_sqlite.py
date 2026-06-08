#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from cg_import_common import REPO_ROOT, load_json


BLOCKED_BUNDLED_LICENSE_STATUSES = {"restricted", "pending-review", "unknown"}
SAFE_CONTENT_LICENSE_STATUSES = {"public-domain", "permissive"}
TOKEN_RE = re.compile(r"[A-Za-z]{4,}")


def connect_readonly(db_path: Path) -> sqlite3.Connection:
    uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def quote_fts_phrase(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def table_count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def derive_bcbooks_expected(downloads_root: Path) -> dict[str, int] | None:
    source_dir = downloads_root / "lds-scriptures-json"
    if not source_dir.exists():
        return None

    counts = {"volumes": 0, "books": 0, "chapters": 0, "verses": 0}
    json_files = sorted(source_dir.glob("*.json"))
    if not json_files:
        return None

    for path in json_files:
        doc = load_json(path)
        if not isinstance(doc, dict):
            continue
        counts["volumes"] += 1
        books = doc.get("books")
        if isinstance(books, list):
            counts["books"] += len(books)
            for book in books:
                chapters = book.get("chapters", []) if isinstance(book, dict) else []
                counts["chapters"] += len(chapters)
                for chapter in chapters:
                    if isinstance(chapter, dict):
                        counts["verses"] += len(chapter.get("verses", []))
        sections = doc.get("sections")
        if isinstance(sections, list):
            counts["books"] += 1
            counts["chapters"] += len(sections)
            for section in sections:
                if isinstance(section, dict):
                    counts["verses"] += len(section.get("verses", []))
    return counts


def derive_strongs_expected(downloads_root: Path) -> dict[str, int] | None:
    strongs_path = downloads_root / "strongs" / "strongs.json"
    if not strongs_path.exists():
        return None
    entries = load_json(strongs_path)
    if not isinstance(entries, list):
        return None
    hebrew = 0
    greek = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        number = str(entry.get("number") or "")
        if number.startswith("H"):
            hebrew += 1
        elif number.startswith("G"):
            greek += 1
    return {"strongs_entries": len(entries), "hebrew": hebrew, "greek": greek}


def validate_integrity(conn: sqlite3.Connection, errors: list[str]) -> None:
    integrity = conn.execute("PRAGMA integrity_check").fetchone()
    if not integrity or integrity[0] != "ok":
        errors.append("PRAGMA integrity_check did not return ok.")

    fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk_rows:
        sample = [tuple(row) for row in fk_rows[:5]]
        errors.append(f"PRAGMA foreign_key_check returned {len(fk_rows)} row(s): {sample}")


def validate_required_tables(conn: sqlite3.Connection, errors: list[str]) -> None:
    required = {
        "data_packages",
        "sources",
        "licenses",
        "source_files",
        "translations",
        "volumes",
        "books",
        "chapters",
        "verses",
        "verse_texts",
        "strongs_entries",
        "verse_text_fts",
        "strongs_entries_fts",
    }
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
    ).fetchall()
    found = {str(row[0]) for row in rows}
    missing = sorted(required - found)
    if missing:
        errors.append(f"Database is missing required table(s): {', '.join(missing)}.")


def validate_counts(
    conn: sqlite3.Connection,
    downloads_root: Path,
    errors: list[str],
    warnings: list[str],
) -> None:
    expected_bcbooks = derive_bcbooks_expected(downloads_root)
    if expected_bcbooks is None:
        warnings.append(f"No bcbooks fixture/download JSON found under {downloads_root}.")
    else:
        actual = {
            "volumes": table_count(conn, "volumes"),
            "books": table_count(conn, "books"),
            "chapters": table_count(conn, "chapters"),
            "verses": table_count(conn, "verses"),
            "verse_texts": table_count(conn, "verse_texts"),
        }
        expected = dict(expected_bcbooks)
        expected["verse_texts"] = expected_bcbooks["verses"]
        for key, expected_value in expected.items():
            if actual[key] != expected_value:
                errors.append(
                    f"{key} count mismatch: expected {expected_value}, observed {actual[key]}."
                )

    expected_strongs = derive_strongs_expected(downloads_root)
    if expected_strongs is None:
        warnings.append(f"No Strong's fixture/download JSON found under {downloads_root}.")
    else:
        actual_strongs = table_count(conn, "strongs_entries")
        if actual_strongs != expected_strongs["strongs_entries"]:
            errors.append(
                "strongs_entries count mismatch: "
                f"expected {expected_strongs['strongs_entries']}, observed {actual_strongs}."
            )
        for language in ("hebrew", "greek"):
            observed = int(
                conn.execute(
                    "SELECT COUNT(*) FROM strongs_entries WHERE language = ?",
                    (language,),
                ).fetchone()[0]
            )
            if observed != expected_strongs[language]:
                errors.append(
                    f"{language} Strong's count mismatch: "
                    f"expected {expected_strongs[language]}, observed {observed}."
                )

    verse_text_count = table_count(conn, "verse_texts")
    verse_fts_count = table_count(conn, "verse_text_fts")
    if verse_fts_count != verse_text_count:
        errors.append(
            f"verse_text_fts count mismatch: expected {verse_text_count}, observed {verse_fts_count}."
        )

    strongs_count = table_count(conn, "strongs_entries")
    strongs_fts_count = table_count(conn, "strongs_entries_fts")
    if strongs_fts_count != strongs_count:
        errors.append(
            "strongs_entries_fts count mismatch: "
            f"expected {strongs_count}, observed {strongs_fts_count}."
        )


def validate_manifest_boundaries(
    conn: sqlite3.Connection,
    repo_root: Path,
    errors: list[str],
) -> None:
    sources_doc = load_json(repo_root / "data" / "manifests" / "sources.json")
    licenses_doc = load_json(repo_root / "data" / "manifests" / "licenses.json")
    manifest_sources = {
        source["id"]: source
        for source in sources_doc.get("sources", [])
        if isinstance(source, dict) and "id" in source
    }
    manifest_licenses = {
        license_item["id"]: license_item
        for license_item in licenses_doc.get("licenses", [])
        if isinstance(license_item, dict) and "id" in license_item
    }

    for row in conn.execute("SELECT id, license_id FROM sources ORDER BY id"):
        source_id = str(row["id"])
        manifest_source = manifest_sources.get(source_id)
        if manifest_source is None:
            errors.append(f"Database source is missing from source manifest: {source_id}.")
            continue
        if row["license_id"] != manifest_source.get("license_id"):
            errors.append(
                f"Database source {source_id} license_id {row['license_id']} "
                f"does not match manifest {manifest_source.get('license_id')}."
            )

    for row in conn.execute("SELECT id, status FROM licenses ORDER BY id"):
        license_id = str(row["id"])
        manifest_license = manifest_licenses.get(license_id)
        if manifest_license is None:
            errors.append(f"Database license is missing from license manifest: {license_id}.")
            continue
        if row["status"] != manifest_license.get("status"):
            errors.append(
                f"Database license {license_id} status {row['status']} "
                f"does not match manifest {manifest_license.get('status')}."
            )


def validate_license_boundaries(conn: sqlite3.Connection, errors: list[str]) -> None:
    content_queries = {
        "verse_texts": """
            SELECT DISTINCT verse_texts.source_id, licenses.id AS license_id, licenses.status
            FROM verse_texts
            JOIN licenses ON licenses.id = verse_texts.license_id
        """,
        "strongs_entries": """
            SELECT DISTINCT strongs_entries.source_id, licenses.id AS license_id, licenses.status
            FROM strongs_entries
            JOIN licenses ON licenses.id = strongs_entries.license_id
        """,
    }
    for table, query in content_queries.items():
        for row in conn.execute(query):
            if row["status"] not in SAFE_CONTENT_LICENSE_STATUSES:
                errors.append(
                    f"{table} includes source {row['source_id']} with blocked license "
                    f"{row['license_id']} status {row['status']}."
                )

    blocked_open_package_rows = conn.execute(
        """
        SELECT
            data_packages.id AS package_id,
            data_packages.redistribution_status,
            sources.id AS source_id,
            licenses.id AS license_id,
            licenses.status
        FROM data_packages
        JOIN package_sources ON package_sources.package_id = data_packages.id
        JOIN sources ON sources.id = package_sources.source_id
        JOIN licenses ON licenses.id = sources.license_id
        WHERE data_packages.redistribution_status = 'open-redistributable'
          AND licenses.status IN ('restricted', 'pending-review', 'unknown')
        """
    ).fetchall()
    for row in blocked_open_package_rows:
        errors.append(
            f"Open package {row['package_id']} includes blocked source {row['source_id']} "
            f"with license {row['license_id']} status {row['status']}."
        )


def validate_fts_smoke(conn: sqlite3.Connection, errors: list[str]) -> None:
    nephi_row = conn.execute(
        """
        SELECT verse_texts.id AS verse_text_id
        FROM verses
        JOIN verse_texts ON verse_texts.verse_id = verses.id
        WHERE verses.reference = '1 Nephi 1:1'
        """
    ).fetchone()
    if nephi_row is not None:
        rows = conn.execute(
            """
            SELECT verse_text_id
            FROM verse_text_fts
            WHERE verse_text_fts MATCH ?
            LIMIT 10
            """,
            (quote_fts_phrase("goodly parents"),),
        ).fetchall()
        if nephi_row["verse_text_id"] not in {row["verse_text_id"] for row in rows}:
            errors.append("Verse FTS smoke query did not find 1 Nephi 1:1 for 'goodly parents'.")
    else:
        sample = conn.execute(
            """
            SELECT verse_texts.id AS verse_text_id, verse_texts.text_plain
            FROM verse_texts
            JOIN verses ON verses.id = verse_texts.verse_id
            WHERE verse_texts.text_plain <> ''
            ORDER BY verses.sort_key
            LIMIT 1
            """
        ).fetchone()
        if sample is not None:
            match = TOKEN_RE.search(str(sample["text_plain"]))
            if match:
                rows = conn.execute(
                    """
                    SELECT verse_text_id
                    FROM verse_text_fts
                    WHERE verse_text_fts MATCH ?
                    LIMIT 10
                    """,
                    (match.group(0),),
                ).fetchall()
                if sample["verse_text_id"] not in {row["verse_text_id"] for row in rows}:
                    errors.append(
                        f"Verse FTS smoke query did not find sample token {match.group(0)!r}."
                    )

    h1_row = conn.execute(
        "SELECT id FROM strongs_entries WHERE strongs_number = 'H1'"
    ).fetchone()
    if h1_row is not None:
        rows = conn.execute(
            """
            SELECT strongs_entry_id
            FROM strongs_entries_fts
            WHERE strongs_entries_fts MATCH ?
            LIMIT 10
            """,
            (quote_fts_phrase("H1"),),
        ).fetchall()
        if h1_row["id"] not in {row["strongs_entry_id"] for row in rows}:
            errors.append("Strong's FTS smoke query did not find H1 by number.")
    else:
        sample = conn.execute(
            "SELECT id, strongs_number FROM strongs_entries ORDER BY strongs_number LIMIT 1"
        ).fetchone()
        if sample is not None:
            rows = conn.execute(
                """
                SELECT strongs_entry_id
                FROM strongs_entries_fts
                WHERE strongs_entries_fts MATCH ?
                LIMIT 10
                """,
                (quote_fts_phrase(str(sample["strongs_number"])),),
            ).fetchall()
            if sample["id"] not in {row["strongs_entry_id"] for row in rows}:
                errors.append(
                    f"Strong's FTS smoke query did not find {sample['strongs_number']} by number."
                )


def validate_reference_lookup(conn: sqlite3.Connection, errors: list[str]) -> None:
    duplicate_refs = conn.execute(
        """
        SELECT reference, COUNT(*) AS count
        FROM verses
        GROUP BY reference
        HAVING COUNT(*) > 1
        LIMIT 5
        """
    ).fetchall()
    if duplicate_refs:
        errors.append(f"Duplicate verse references found: {[dict(row) for row in duplicate_refs]}")

    if table_count(conn, "verses") and not conn.execute(
        "SELECT id FROM verses WHERE reference <> '' LIMIT 1"
    ).fetchone():
        errors.append("Verse table has rows but no non-empty references.")


def validate_database(
    db_path: Path,
    repo_root: Path = REPO_ROOT,
    downloads_root: Path | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if downloads_root is None:
        downloads_root = repo_root / "data" / "downloads"
    if not db_path.exists():
        return [f"SQLite database does not exist: {db_path}"], warnings

    try:
        conn = connect_readonly(db_path)
    except sqlite3.Error as exc:
        return [f"Could not open SQLite database {db_path}: {exc}"], warnings

    try:
        validate_required_tables(conn, errors)
        if errors:
            return errors, warnings
        validate_integrity(conn, errors)
        validate_counts(conn, downloads_root, errors, warnings)
        validate_manifest_boundaries(conn, repo_root, errors)
        validate_license_boundaries(conn, errors)
        validate_reference_lookup(conn, errors)
        validate_fts_smoke(conn, errors)
    except sqlite3.Error as exc:
        errors.append(f"SQLite validation failed: {exc}")
    finally:
        conn.close()
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an imported CG SQLite source database.")
    parser.add_argument("--db", type=Path, required=True, help="SQLite database to validate.")
    parser.add_argument(
        "--downloads-root",
        type=Path,
        default=REPO_ROOT / "data" / "downloads",
        help="Root containing lds-scriptures-json/ and strongs/ source files.",
    )
    args = parser.parse_args()

    errors, warnings = validate_database(args.db, REPO_ROOT, args.downloads_root)
    for warning in warnings:
        print(f"WARN: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        print(json.dumps({"valid": False, "errors": errors}, indent=2))
        return 1
    print(json.dumps({"valid": True, "db": str(args.db)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
