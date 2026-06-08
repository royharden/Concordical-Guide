#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from cg_import_common import REPO_ROOT, apply_schema, connect_sqlite, load_manifests
from cg_import_common import upsert_manifest_metadata
from import_bcbooks_to_sqlite import SOURCE_ID as BCBOOKS_SOURCE_ID
from import_bcbooks_to_sqlite import import_bcbooks
from import_strongs_to_sqlite import SOURCE_ID as STRONGS_SOURCE_ID
from import_strongs_to_sqlite import import_strongs
from validate_imported_sqlite import validate_database


FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "importer-mini"


def insert_fixture_package(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT INTO data_packages(
            id,
            package_version,
            schema_version,
            package_kind,
            redistribution_status,
            build_id,
            sources_manifest_sha256,
            licenses_manifest_sha256,
            raw_inputs_sha256
        )
        VALUES (
            'fixture-package',
            'fixture',
            1,
            'source-scriptures-and-lexicon',
            'pending-roy-review',
            'fixture-build',
            '0000000000000000000000000000000000000000000000000000000000000000',
            '0000000000000000000000000000000000000000000000000000000000000000',
            '0000000000000000000000000000000000000000000000000000000000000000'
        )
        """
    )
    for source_id in (BCBOOKS_SOURCE_ID, STRONGS_SOURCE_ID):
        conn.execute(
            "INSERT INTO package_sources(package_id, source_id) VALUES (?, ?)",
            ("fixture-package", source_id),
        )


def run_fixture_import() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="cg-import-fixture-") as temp_dir:
        db_path = Path(temp_dir) / "fixture.sqlite"
        conn = connect_sqlite(db_path)
        try:
            apply_schema(conn)
            sources_doc, licenses_doc = load_manifests()
            upsert_manifest_metadata(conn, sources_doc, licenses_doc)
            insert_fixture_package(conn)
            bcbooks_counts = import_bcbooks(
                conn,
                FIXTURE_ROOT / "lds-scriptures-json",
            )
            strongs_counts = import_strongs(
                conn,
                FIXTURE_ROOT / "strongs" / "strongs.json",
            )
            conn.commit()
        finally:
            conn.close()

        errors, warnings = validate_database(db_path, REPO_ROOT, FIXTURE_ROOT)
        if errors:
            raise AssertionError("\n".join(errors))

        expected = {
            "bcbooks": {
                "books": 2,
                "chapters": 2,
                "verse_text_fts": 3,
                "verse_texts": 3,
                "verses": 3,
                "volumes": 2,
            },
            "strongs": {
                "greek": 1,
                "hebrew": 1,
                "strongs_entries": 2,
                "strongs_entries_fts": 2,
            },
        }
        observed = {"bcbooks": bcbooks_counts, "strongs": strongs_counts}
        if observed != expected:
            raise AssertionError(
                "Fixture import counts changed.\n"
                f"Expected: {json.dumps(expected, sort_keys=True)}\n"
                f"Observed: {json.dumps(observed, sort_keys=True)}"
            )
        return {"counts": observed, "warnings": warnings}


def main() -> int:
    summary = run_fixture_import()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
