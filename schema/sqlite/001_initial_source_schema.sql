PRAGMA foreign_keys = ON;
PRAGMA user_version = 1;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT 'static-schema'
);

INSERT OR IGNORE INTO schema_migrations(version, name)
VALUES (1, 'initial_source_schema');

CREATE TABLE IF NOT EXISTS licenses (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'public-domain',
        'permissive',
        'restricted',
        'pending-review',
        'unknown'
    )),
    source_url TEXT NOT NULL,
    usage_notes TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    kind TEXT NOT NULL,
    language TEXT NOT NULL,
    license_id TEXT NOT NULL REFERENCES licenses(id),
    provenance_url TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    storage_policy TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS source_files (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    path TEXT NOT NULL,
    bytes INTEGER NOT NULL CHECK (bytes >= 0),
    sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
    retrieved_at TEXT NOT NULL,
    UNIQUE(source_id, url)
);

CREATE TABLE IF NOT EXISTS data_packages (
    id TEXT PRIMARY KEY,
    package_version TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    package_kind TEXT NOT NULL,
    redistribution_status TEXT NOT NULL CHECK (redistribution_status IN (
        'open-redistributable',
        'pending-roy-review',
        'personal-use-only'
    )),
    build_id TEXT NOT NULL,
    sources_manifest_sha256 TEXT NOT NULL CHECK (length(sources_manifest_sha256) = 64),
    licenses_manifest_sha256 TEXT NOT NULL CHECK (length(licenses_manifest_sha256) = 64),
    raw_inputs_sha256 TEXT NOT NULL CHECK (length(raw_inputs_sha256) = 64)
);

CREATE TABLE IF NOT EXISTS package_sources (
    package_id TEXT NOT NULL REFERENCES data_packages(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES sources(id),
    PRIMARY KEY (package_id, source_id)
);

CREATE TABLE IF NOT EXISTS translations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    abbreviation TEXT NOT NULL,
    language TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES sources(id),
    license_id TEXT NOT NULL REFERENCES licenses(id),
    rights_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS volumes (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(id),
    slug TEXT NOT NULL,
    title TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    UNIQUE(source_id, slug)
);

CREATE TABLE IF NOT EXISTS books (
    id TEXT PRIMARY KEY,
    volume_id TEXT NOT NULL REFERENCES volumes(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES sources(id),
    slug TEXT NOT NULL,
    title TEXT NOT NULL,
    title_long TEXT,
    sort_order INTEGER NOT NULL,
    UNIQUE(volume_id, slug)
);

CREATE TABLE IF NOT EXISTS chapters (
    id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES sources(id),
    chapter_number INTEGER NOT NULL CHECK (chapter_number > 0),
    reference TEXT NOT NULL,
    sort_key INTEGER NOT NULL,
    UNIQUE(book_id, chapter_number)
);

CREATE TABLE IF NOT EXISTS verses (
    id TEXT PRIMARY KEY,
    chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES sources(id),
    chapter_number INTEGER NOT NULL CHECK (chapter_number > 0),
    verse_number INTEGER NOT NULL CHECK (verse_number > 0),
    reference TEXT NOT NULL,
    sort_key INTEGER NOT NULL,
    UNIQUE(chapter_id, verse_number),
    UNIQUE(reference)
);

CREATE TABLE IF NOT EXISTS verse_texts (
    id TEXT PRIMARY KEY,
    verse_id TEXT NOT NULL REFERENCES verses(id) ON DELETE CASCADE,
    translation_id TEXT NOT NULL REFERENCES translations(id),
    source_id TEXT NOT NULL REFERENCES sources(id),
    license_id TEXT NOT NULL REFERENCES licenses(id),
    text_plain TEXT NOT NULL,
    text_formatted TEXT,
    UNIQUE(verse_id, translation_id)
);

CREATE TABLE IF NOT EXISTS strongs_entries (
    id TEXT PRIMARY KEY,
    strongs_number TEXT NOT NULL UNIQUE,
    language TEXT NOT NULL CHECK (language IN ('hebrew', 'greek')),
    lemma TEXT,
    transliteration TEXT,
    pronunciation TEXT,
    definition_full TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES sources(id),
    license_id TEXT NOT NULL REFERENCES licenses(id),
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS import_receipts (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(id),
    importer TEXT NOT NULL,
    details_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_books_volume_sort
ON books(volume_id, sort_order);

CREATE INDEX IF NOT EXISTS idx_chapters_book_number
ON chapters(book_id, chapter_number);

CREATE INDEX IF NOT EXISTS idx_verses_book_chapter_verse
ON verses(book_id, chapter_number, verse_number);

CREATE INDEX IF NOT EXISTS idx_verses_sort_key
ON verses(sort_key);

CREATE INDEX IF NOT EXISTS idx_verse_texts_translation
ON verse_texts(translation_id);

CREATE INDEX IF NOT EXISTS idx_strongs_language
ON strongs_entries(language, strongs_number);

CREATE VIRTUAL TABLE IF NOT EXISTS verse_text_fts USING fts5(
    verse_text_id UNINDEXED,
    verse_id UNINDEXED,
    translation_id UNINDEXED,
    reference,
    text_plain,
    tokenize = 'unicode61'
);

CREATE VIRTUAL TABLE IF NOT EXISTS strongs_entries_fts USING fts5(
    strongs_entry_id UNINDEXED,
    strongs_number,
    lemma,
    transliteration,
    pronunciation,
    definition_full,
    tokenize = 'unicode61'
);
