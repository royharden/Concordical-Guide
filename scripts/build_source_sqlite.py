#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from cg_import_common import (
    LICENSES_MANIFEST,
    REPO_ROOT,
    SOURCES_MANIFEST,
    apply_schema,
    connect_sqlite,
    dump_json,
    load_manifests,
    repo_relative,
    sha256_file,
    sha256_text,
    source_by_id,
    upsert_manifest_metadata,
)
from import_bcbooks_to_sqlite import DEFAULT_SOURCE_DIR, SOURCE_ID as BCBOOKS_SOURCE_ID
from import_bcbooks_to_sqlite import import_bcbooks
from import_strongs_to_sqlite import DEFAULT_STRONGS_PATH, SOURCE_ID as STRONGS_SOURCE_ID
from import_strongs_to_sqlite import import_strongs
from validate_imported_sqlite import validate_database


DEFAULT_DB_PATH = REPO_ROOT / "data" / "generated" / "sqlite" / "cg-source-v1.sqlite"
PACKAGE_VERSION = "0.1.0"
SCHEMA_VERSION = 1


def collect_source_files(sources_doc: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in sources_doc.get("sources", []):
        storage = source.get("storage") or {}
        storage_path = storage.get("path")
        if not storage_path:
            continue
        target_dir = REPO_ROOT / storage_path
        for url in source.get("download_urls", []):
            file_name = Path(str(url)).name
            target_path = target_dir / file_name
            if not target_path.exists():
                raise FileNotFoundError(
                    f"Missing raw source file for {source['id']}: {target_path}"
                )
            rows.append(
                {
                    "source_id": source["id"],
                    "url": url,
                    "path": repo_relative(target_path),
                    "bytes": target_path.stat().st_size,
                    "sha256": sha256_file(target_path),
                    "retrieved_at": source["retrieved_at"],
                }
            )
    return rows


def insert_source_files(conn, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        row_id = sha256_text(dump_json({"source_id": row["source_id"], "url": row["url"]}))
        conn.execute(
            """
            INSERT INTO source_files(id, source_id, url, path, bytes, sha256, retrieved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                path = excluded.path,
                bytes = excluded.bytes,
                sha256 = excluded.sha256,
                retrieved_at = excluded.retrieved_at
            """,
            (
                row_id,
                row["source_id"],
                row["url"],
                row["path"],
                row["bytes"],
                row["sha256"],
                row["retrieved_at"],
            ),
        )


def build_identity(source_files: list[dict[str, Any]]) -> dict[str, str]:
    sources_manifest_sha = sha256_file(SOURCES_MANIFEST)
    licenses_manifest_sha = sha256_file(LICENSES_MANIFEST)
    raw_inputs_sha = sha256_text(dump_json(source_files))
    build_payload = {
        "package_version": PACKAGE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "sources_manifest_sha256": sources_manifest_sha,
        "licenses_manifest_sha256": licenses_manifest_sha,
        "raw_inputs_sha256": raw_inputs_sha,
    }
    build_id = sha256_text(dump_json(build_payload))
    return {
        "package_id": f"cg-source-{build_id[:12]}",
        "build_id": build_id,
        "sources_manifest_sha256": sources_manifest_sha,
        "licenses_manifest_sha256": licenses_manifest_sha,
        "raw_inputs_sha256": raw_inputs_sha,
    }


def insert_package(
    conn,
    identity: dict[str, str],
    sources_doc: dict[str, Any],
    redistribution_status: str,
) -> None:
    conn.execute("DELETE FROM data_packages")
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            identity["package_id"],
            PACKAGE_VERSION,
            SCHEMA_VERSION,
            "source-scriptures-and-lexicon",
            redistribution_status,
            identity["build_id"],
            identity["sources_manifest_sha256"],
            identity["licenses_manifest_sha256"],
            identity["raw_inputs_sha256"],
        ),
    )
    for source_id in (BCBOOKS_SOURCE_ID, STRONGS_SOURCE_ID):
        source_by_id(sources_doc, source_id)
        conn.execute(
            """
            INSERT INTO package_sources(package_id, source_id)
            VALUES (?, ?)
            """,
            (identity["package_id"], source_id),
        )


def write_sidecar_manifest(
    db_path: Path,
    identity: dict[str, str],
    source_files: list[dict[str, Any]],
    counts: dict[str, Any],
    validation_errors: list[str],
    validation_warnings: list[str],
) -> Path:
    sidecar_path = db_path.with_suffix(".manifest.json")
    sidecar = {
        "package_id": identity["package_id"],
        "package_version": PACKAGE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "db_path": repo_relative(db_path),
        "db_sha256": sha256_file(db_path),
        "sources_manifest_sha256": identity["sources_manifest_sha256"],
        "licenses_manifest_sha256": identity["licenses_manifest_sha256"],
        "raw_inputs_sha256": identity["raw_inputs_sha256"],
        "source_files": source_files,
        "counts": counts,
        "validation": {
            "errors": validation_errors,
            "warnings": validation_warnings,
        },
    }
    sidecar_path.write_text(json.dumps(sidecar, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return sidecar_path


def build_database(
    db_path: Path,
    force: bool,
    redistribution_status: str,
    validate: bool,
) -> dict[str, Any]:
    if db_path.exists():
        if not force:
            raise FileExistsError(f"Database already exists; pass --force to replace it: {db_path}")
        db_path.unlink()
    sidecar_path = db_path.with_suffix(".manifest.json")
    if sidecar_path.exists() and force:
        sidecar_path.unlink()

    sources_doc, licenses_doc = load_manifests()
    source_files = collect_source_files(sources_doc)
    identity = build_identity(source_files)

    conn = connect_sqlite(db_path)
    try:
        apply_schema(conn)
        upsert_manifest_metadata(conn, sources_doc, licenses_doc)
        insert_source_files(conn, source_files)
        insert_package(conn, identity, sources_doc, redistribution_status)
        bcbooks_counts = import_bcbooks(conn, DEFAULT_SOURCE_DIR)
        strongs_counts = import_strongs(conn, DEFAULT_STRONGS_PATH)
        conn.commit()
        conn.execute("PRAGMA optimize")
        conn.commit()
    finally:
        conn.close()

    validation_errors: list[str] = []
    validation_warnings: list[str] = []
    if validate:
        validation_errors, validation_warnings = validate_database(
            db_path,
            REPO_ROOT,
            REPO_ROOT / "data" / "downloads",
        )
        if validation_errors:
            sidecar = write_sidecar_manifest(
                db_path,
                identity,
                source_files,
                {"bcbooks": bcbooks_counts, "strongs": strongs_counts},
                validation_errors,
                validation_warnings,
            )
            raise RuntimeError(
                f"Generated database failed validation; wrote sidecar {sidecar}: "
                + "; ".join(validation_errors)
            )

    sidecar = write_sidecar_manifest(
        db_path,
        identity,
        source_files,
        {"bcbooks": bcbooks_counts, "strongs": strongs_counts},
        validation_errors,
        validation_warnings,
    )
    return {
        "db_path": repo_relative(db_path),
        "sidecar_path": repo_relative(sidecar),
        "package_id": identity["package_id"],
        "db_sha256": sha256_file(db_path),
        "counts": {"bcbooks": bcbooks_counts, "strongs": strongs_counts},
        "validation_warnings": validation_warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the generated CG source SQLite database.")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Output SQLite database path.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing generated database.",
    )
    parser.add_argument(
        "--redistribution-status",
        choices=["open-redistributable", "pending-roy-review", "personal-use-only"],
        default="pending-roy-review",
        help="Package redistribution gate recorded in data_packages.",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip post-build imported database validation.",
    )
    args = parser.parse_args()

    summary = build_database(
        args.db,
        force=args.force,
        redistribution_status=args.redistribution_status,
        validate=not args.no_validate,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
