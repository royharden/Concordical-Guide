#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

from validate_imported_sqlite import validate_database


REPO_ROOT = Path(__file__).resolve().parents[1]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL_RE = re.compile(r"^https?://", re.IGNORECASE)

SOURCE_REQUIRED = {
    "id",
    "title",
    "kind",
    "language",
    "license_id",
    "provenance_url",
    "retrieved_at",
    "storage",
}
LICENSE_REQUIRED = {"id", "name", "status", "source_url", "usage_notes"}
LICENSE_STATUSES = {
    "public-domain",
    "permissive",
    "restricted",
    "pending-review",
    "unknown",
}


class Reporter:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def finish(self) -> int:
        for warning in self.warnings:
            print(f"WARN: {warning}")
        for error in self.errors:
            print(f"ERROR: {error}")
        if self.errors:
            print(f"CG validation failed with {len(self.errors)} error(s).")
            return 1
        print("CG validation passed.")
        return 0


def repo_path(relative: str) -> Path:
    return REPO_ROOT / relative


def display(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def load_json(relative: str, reporter: Reporter) -> Any:
    path = repo_path(relative)
    if not path.exists():
        reporter.error(f"{relative} is missing.")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        reporter.error(f"{relative} is not valid JSON: {exc}")
        return {}


def require_object(doc: Any, relative: str, reporter: Reporter) -> dict[str, Any]:
    if not isinstance(doc, dict):
        reporter.error(f"{relative} must be a JSON object.")
        return {}
    return doc


def require_list(doc: dict[str, Any], key: str, relative: str, reporter: Reporter) -> list[Any]:
    value = doc.get(key)
    if not isinstance(value, list):
        reporter.error(f"{relative} must contain a '{key}' array.")
        return []
    return value


def validate_unique_ids(items: list[Any], label: str, reporter: Reporter) -> set[str]:
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            reporter.error(f"{label}[{index}] must be an object.")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            reporter.error(f"{label}[{index}] needs a non-empty string id.")
            continue
        if item_id in seen:
            reporter.error(f"{label} has duplicate id '{item_id}'.")
        seen.add(item_id)
    return seen


def validate_manifests(reporter: Reporter) -> None:
    licenses_doc = require_object(
        load_json("data/manifests/licenses.json", reporter),
        "data/manifests/licenses.json",
        reporter,
    )
    sources_doc = require_object(
        load_json("data/manifests/sources.json", reporter),
        "data/manifests/sources.json",
        reporter,
    )

    licenses = require_list(licenses_doc, "licenses", "data/manifests/licenses.json", reporter)
    sources = require_list(sources_doc, "sources", "data/manifests/sources.json", reporter)

    license_ids = validate_unique_ids(licenses, "licenses", reporter)
    validate_unique_ids(sources, "sources", reporter)

    license_status_by_id: dict[str, str] = {}
    for index, license_item in enumerate(licenses):
        if not isinstance(license_item, dict):
            continue
        missing = sorted(LICENSE_REQUIRED - set(license_item))
        if missing:
            reporter.error(f"licenses[{index}] is missing fields: {', '.join(missing)}.")
        status = license_item.get("status")
        if status not in LICENSE_STATUSES:
            reporter.error(
                f"licenses[{index}] has invalid status '{status}'. "
                f"Allowed: {', '.join(sorted(LICENSE_STATUSES))}."
            )
        item_id = license_item.get("id")
        if isinstance(item_id, str) and isinstance(status, str):
            license_status_by_id[item_id] = status
        source_url = license_item.get("source_url")
        if isinstance(source_url, str) and source_url and not URL_RE.match(source_url):
            reporter.error(f"licenses[{index}].source_url must be http(s).")

    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            continue
        missing = sorted(SOURCE_REQUIRED - set(source))
        if missing:
            reporter.error(f"sources[{index}] is missing fields: {', '.join(missing)}.")
        provenance_url = source.get("provenance_url")
        if isinstance(provenance_url, str) and provenance_url and not URL_RE.match(provenance_url):
            reporter.error(f"sources[{index}].provenance_url must be http(s).")
        retrieved_at = source.get("retrieved_at")
        if isinstance(retrieved_at, str) and not DATE_RE.match(retrieved_at):
            reporter.error(f"sources[{index}].retrieved_at must be YYYY-MM-DD.")
        storage = source.get("storage")
        if storage is not None and not isinstance(storage, dict):
            reporter.error(f"sources[{index}].storage must be an object.")
        license_id = source.get("license_id")
        if isinstance(license_id, str):
            if license_id not in license_ids:
                reporter.error(f"sources[{index}] references unknown license_id '{license_id}'.")
            elif license_status_by_id.get(license_id) in {"restricted", "pending-review", "unknown"}:
                reporter.warn(
                    f"sources[{index}] references license '{license_id}' with "
                    f"status '{license_status_by_id[license_id]}'."
                )


def validate_sqlite(reporter: Reporter) -> None:
    schema_dir = repo_path("schema/sqlite")
    sql_files = sorted(schema_dir.glob("*.sql")) if schema_dir.exists() else []
    if sql_files:
        conn = sqlite3.connect(":memory:")
        try:
            for sql_file in sql_files:
                conn.executescript(sql_file.read_text(encoding="utf-8"))
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                reporter.error("In-memory SQLite schema integrity_check did not return ok.")
        except sqlite3.Error as exc:
            reporter.error(f"SQLite schema validation failed: {exc}")
        finally:
            conn.close()
    else:
        reporter.warn("No schema/sqlite/*.sql files yet; schema execution skipped.")

    candidates: list[Path] = []
    env_db = os.environ.get("CG_IMPORT_DB")
    if env_db:
        env_path = Path(env_db)
        candidates.append(env_path if env_path.is_absolute() else REPO_ROOT / env_path)
    default_db = repo_path("data/app/cg.sqlite")
    if default_db.exists():
        candidates.append(default_db)
    generated_db = repo_path("data/generated/sqlite/cg-source-v1.sqlite")
    if generated_db.exists():
        candidates.append(generated_db)

    for db_path in candidates:
        errors, warnings = validate_database(db_path, REPO_ROOT, repo_path("data/downloads"))
        for warning in warnings:
            reporter.warn(f"{display(db_path)}: {warning}")
        for error in errors:
            reporter.error(f"{display(db_path)}: {error}")


def git_ls_files(reporter: Reporter) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        reporter.error(f"Unable to list tracked files with git: {exc}")
        return []
    files: list[Path] = []
    for raw in result.stdout.split(b"\0"):
        if raw:
            files.append(Path(raw.decode("utf-8", errors="replace")))
    return files


def validate_tracked_files(reporter: Reporter) -> None:
    max_bytes = int(os.environ.get("CG_MAX_COMMITTED_BYTES", "5000000"))
    blocked_prefixes = (
        ".agent-work/",
        "data/raw/",
        "data/downloads/",
        "data/cache/",
        "data/processed/",
        "data/generated/",
    )
    blocked_suffixes = {
        ".sqlite",
        ".sqlite-shm",
        ".sqlite-wal",
        ".db",
        ".db-shm",
        ".db-wal",
    }
    for relative in git_ls_files(reporter):
        posix = relative.as_posix()
        full_path = REPO_ROOT / relative
        if any(posix.startswith(prefix) for prefix in blocked_prefixes):
            reporter.error(f"Tracked file is in a generated/scratch path: {posix}")
        if full_path.is_file():
            suffix = "".join(full_path.suffixes[-2:]).lower() if len(full_path.suffixes) > 1 else full_path.suffix.lower()
            if suffix in blocked_suffixes or full_path.suffix.lower() in blocked_suffixes:
                reporter.error(f"Tracked generated database file is not allowed: {posix}")
            size = full_path.stat().st_size
            if size > max_bytes:
                reporter.error(
                    f"Tracked file exceeds {max_bytes} bytes: {posix} ({size} bytes). "
                    "Use manifests plus gitignored raw/generated data instead."
                )


def main() -> int:
    reporter = Reporter()
    validate_manifests(reporter)
    validate_sqlite(reporter)
    validate_tracked_files(reporter)
    return reporter.finish()


if __name__ == "__main__":
    sys.exit(main())
