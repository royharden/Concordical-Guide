#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "schema" / "sqlite"
SOURCES_MANIFEST = REPO_ROOT / "data" / "manifests" / "sources.json"
LICENSES_MANIFEST = REPO_ROOT / "data" / "manifests" / "licenses.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def repo_relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def connect_sqlite(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def apply_schema(conn: sqlite3.Connection, schema_dir: Path = SCHEMA_DIR) -> None:
    sql_files = sorted(schema_dir.glob("*.sql"))
    if not sql_files:
        raise FileNotFoundError(f"No SQLite schema files found in {schema_dir}")
    for sql_file in sql_files:
        conn.executescript(sql_file.read_text(encoding="utf-8"))


def load_manifests(
    sources_path: Path = SOURCES_MANIFEST,
    licenses_path: Path = LICENSES_MANIFEST,
) -> tuple[dict[str, Any], dict[str, Any]]:
    sources_doc = load_json(sources_path)
    licenses_doc = load_json(licenses_path)
    return sources_doc, licenses_doc


def source_by_id(sources_doc: dict[str, Any], source_id: str) -> dict[str, Any]:
    for source in sources_doc.get("sources", []):
        if source.get("id") == source_id:
            return source
    raise KeyError(f"Unknown source id: {source_id}")


def license_by_id(licenses_doc: dict[str, Any], license_id: str) -> dict[str, Any]:
    for license_item in licenses_doc.get("licenses", []):
        if license_item.get("id") == license_id:
            return license_item
    raise KeyError(f"Unknown license id: {license_id}")


def upsert_manifest_metadata(
    conn: sqlite3.Connection,
    sources_doc: dict[str, Any],
    licenses_doc: dict[str, Any],
) -> None:
    for license_item in licenses_doc.get("licenses", []):
        conn.execute(
            """
            INSERT INTO licenses(id, name, status, source_url, usage_notes)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                status = excluded.status,
                source_url = excluded.source_url,
                usage_notes = excluded.usage_notes
            """,
            (
                license_item["id"],
                license_item["name"],
                license_item["status"],
                license_item["source_url"],
                license_item["usage_notes"],
            ),
        )

    for source in sources_doc.get("sources", []):
        storage = source.get("storage") or {}
        conn.execute(
            """
            INSERT INTO sources(
                id,
                title,
                kind,
                language,
                license_id,
                provenance_url,
                retrieved_at,
                storage_policy,
                storage_path,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                kind = excluded.kind,
                language = excluded.language,
                license_id = excluded.license_id,
                provenance_url = excluded.provenance_url,
                retrieved_at = excluded.retrieved_at,
                storage_policy = excluded.storage_policy,
                storage_path = excluded.storage_path,
                notes = excluded.notes
            """,
            (
                source["id"],
                source["title"],
                source["kind"],
                source["language"],
                source["license_id"],
                source["provenance_url"],
                source["retrieved_at"],
                storage.get("policy", ""),
                storage.get("path", ""),
                source.get("notes"),
            ),
        )
