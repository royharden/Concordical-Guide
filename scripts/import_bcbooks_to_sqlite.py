#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any

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


SOURCE_ID = "bcbooks-scriptures-json"
TRANSLATION_ID = "bcbooks-lds-standard-works"
DEFAULT_SOURCE_DIR = REPO_ROOT / "data" / "downloads" / "lds-scriptures-json"

BCBOOKS_FILE_ORDER = [
    "old-testament.json",
    "new-testament.json",
    "book-of-mormon.json",
    "doctrine-and-covenants.json",
    "pearl-of-great-price.json",
]


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    if not slug:
        raise ValueError(f"Cannot derive slug from value: {value!r}")
    return slug


def stable_id(*parts: object) -> str:
    return ":".join(slugify(str(part)) for part in parts if str(part))


def iter_bcbooks_files(source_dir: Path) -> list[Path]:
    ordered = [source_dir / name for name in BCBOOKS_FILE_ORDER if (source_dir / name).exists()]
    remaining = sorted(
        path
        for path in source_dir.glob("*.json")
        if path.name not in BCBOOKS_FILE_ORDER
    )
    return ordered + remaining


def iter_volume_books(volume_doc: dict[str, Any]) -> list[dict[str, Any]]:
    books = volume_doc.get("books")
    if isinstance(books, list):
        return books

    sections = volume_doc.get("sections")
    if isinstance(sections, list):
        slug_source = volume_doc.get("lds_slug") or volume_doc.get("title") or "doctrine-and-covenants"
        return [
            {
                "book": volume_doc.get("title") or "Doctrine and Covenants",
                "full_title": volume_doc.get("title") or "Doctrine and Covenants",
                "lds_slug": slugify(str(slug_source).split("/")[-1] or "dc"),
                "chapters": [
                    {
                        "chapter": section["section"],
                        "reference": section.get("reference") or f"D&C {section['section']}",
                        "verses": section.get("verses", []),
                    }
                    for section in sections
                ],
            }
        ]

    return []


def clear_bcbooks_rows(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM verse_text_fts WHERE translation_id = ?", (TRANSLATION_ID,))
    conn.execute("DELETE FROM volumes WHERE source_id = ?", (SOURCE_ID,))
    conn.execute("DELETE FROM translations WHERE source_id = ?", (SOURCE_ID,))
    conn.execute("DELETE FROM import_receipts WHERE source_id = ?", (SOURCE_ID,))


def rebuild_verse_fts(conn: sqlite3.Connection, translation_id: str = TRANSLATION_ID) -> int:
    conn.execute("DELETE FROM verse_text_fts WHERE translation_id = ?", (translation_id,))
    conn.execute(
        """
        INSERT INTO verse_text_fts(
            verse_text_id,
            verse_id,
            translation_id,
            reference,
            text_plain
        )
        SELECT
            verse_texts.id,
            verse_texts.verse_id,
            verse_texts.translation_id,
            verses.reference,
            verse_texts.text_plain
        FROM verse_texts
        JOIN verses ON verses.id = verse_texts.verse_id
        WHERE verse_texts.translation_id = ?
        ORDER BY verses.sort_key
        """,
        (translation_id,),
    )
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM verse_text_fts WHERE translation_id = ?",
            (translation_id,),
        ).fetchone()[0]
    )


def import_bcbooks(
    conn: sqlite3.Connection,
    source_dir: Path = DEFAULT_SOURCE_DIR,
    clear_existing: bool = True,
    rebuild_fts: bool = True,
) -> dict[str, int]:
    if not source_dir.exists():
        raise FileNotFoundError(f"bcbooks source directory does not exist: {source_dir}")

    sources_doc, licenses_doc = load_manifests()
    source = source_by_id(sources_doc, SOURCE_ID)
    license_id = source["license_id"]

    if clear_existing:
        clear_bcbooks_rows(conn)

    conn.execute(
        """
        INSERT INTO translations(
            id,
            title,
            abbreviation,
            language,
            source_id,
            license_id,
            rights_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            abbreviation = excluded.abbreviation,
            language = excluded.language,
            source_id = excluded.source_id,
            license_id = excluded.license_id,
            rights_status = excluded.rights_status
        """,
        (
            TRANSLATION_ID,
            "LDS standard works from bcbooks/scriptures-json",
            "LDS",
            source["language"],
            SOURCE_ID,
            license_id,
            "public-domain-claim-pending-roy-review",
        ),
    )

    counts = {
        "volumes": 0,
        "books": 0,
        "chapters": 0,
        "verses": 0,
        "verse_texts": 0,
        "verse_text_fts": 0,
    }

    for volume_index, path in enumerate(iter_bcbooks_files(source_dir), start=1):
        volume_doc = load_json(path)
        volume_slug = slugify(str(volume_doc.get("lds_slug") or path.stem))
        volume_id = stable_id("bcbooks", volume_slug)
        volume_title = str(volume_doc.get("title") or path.stem)
        conn.execute(
            """
            INSERT INTO volumes(id, source_id, slug, title, sort_order)
            VALUES (?, ?, ?, ?, ?)
            """,
            (volume_id, SOURCE_ID, volume_slug, volume_title, volume_index),
        )
        counts["volumes"] += 1

        for book_index, book_doc in enumerate(iter_volume_books(volume_doc), start=1):
            book_title = str(book_doc.get("book") or book_doc.get("full_title") or f"Book {book_index}")
            book_slug = slugify(str(book_doc.get("lds_slug") or book_title))
            book_id = stable_id("bcbooks", book_slug)
            conn.execute(
                """
                INSERT INTO books(
                    id,
                    volume_id,
                    source_id,
                    slug,
                    title,
                    title_long,
                    sort_order
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    book_id,
                    volume_id,
                    SOURCE_ID,
                    book_slug,
                    book_title,
                    book_doc.get("full_title"),
                    book_index,
                ),
            )
            counts["books"] += 1

            for chapter_doc in book_doc.get("chapters", []):
                chapter_number = int(chapter_doc["chapter"])
                chapter_reference = str(chapter_doc.get("reference") or f"{book_title} {chapter_number}")
                chapter_sort_key = volume_index * 1_000_000_000 + book_index * 1_000_000 + chapter_number * 1_000
                chapter_id = stable_id(book_id, chapter_number)
                conn.execute(
                    """
                    INSERT INTO chapters(
                        id,
                        book_id,
                        source_id,
                        chapter_number,
                        reference,
                        sort_key
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chapter_id,
                        book_id,
                        SOURCE_ID,
                        chapter_number,
                        chapter_reference,
                        chapter_sort_key,
                    ),
                )
                counts["chapters"] += 1

                for verse_doc in chapter_doc.get("verses", []):
                    verse_number = int(verse_doc["verse"])
                    verse_reference = str(
                        verse_doc.get("reference")
                        or f"{chapter_reference}:{verse_number}"
                    )
                    verse_sort_key = chapter_sort_key + verse_number
                    verse_id = stable_id(book_id, chapter_number, verse_number)
                    conn.execute(
                        """
                        INSERT INTO verses(
                            id,
                            chapter_id,
                            book_id,
                            source_id,
                            chapter_number,
                            verse_number,
                            reference,
                            sort_key
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            verse_id,
                            chapter_id,
                            book_id,
                            SOURCE_ID,
                            chapter_number,
                            verse_number,
                            verse_reference,
                            verse_sort_key,
                        ),
                    )
                    counts["verses"] += 1

                    verse_text_id = stable_id(TRANSLATION_ID, verse_id)
                    conn.execute(
                        """
                        INSERT INTO verse_texts(
                            id,
                            verse_id,
                            translation_id,
                            source_id,
                            license_id,
                            text_plain,
                            text_formatted
                        )
                        VALUES (?, ?, ?, ?, ?, ?, NULL)
                        """,
                        (
                            verse_text_id,
                            verse_id,
                            TRANSLATION_ID,
                            SOURCE_ID,
                            license_id,
                            str(verse_doc.get("text") or ""),
                        ),
                    )
                    counts["verse_texts"] += 1

    if rebuild_fts:
        counts["verse_text_fts"] = rebuild_verse_fts(conn)

    conn.execute(
        """
        INSERT INTO import_receipts(id, source_id, importer, details_json)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            importer = excluded.importer,
            details_json = excluded.details_json
        """,
        (
            "import-bcbooks-scriptures-json",
            SOURCE_ID,
            Path(__file__).name,
            dump_json({"source_dir": source_dir.as_posix(), "counts": counts}),
        ),
    )
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Import bcbooks LDS scripture JSON into CG SQLite.")
    parser.add_argument("--db", type=Path, required=True, help="SQLite database path.")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help="Directory containing bcbooks JSON files.",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Do not clear existing bcbooks rows before import.",
    )
    parser.add_argument(
        "--no-rebuild-fts",
        action="store_true",
        help="Do not rebuild verse FTS rows after import.",
    )
    args = parser.parse_args()

    conn = connect_sqlite(args.db)
    try:
        apply_schema(conn)
        sources_doc, licenses_doc = load_manifests()
        upsert_manifest_metadata(conn, sources_doc, licenses_doc)
        counts = import_bcbooks(
            conn,
            args.source_dir,
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
