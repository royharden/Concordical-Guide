# SQLite Schema

Place versioned SQLite schema or migration SQL files here when the schema is chosen.

`scripts/validate_cg.py` executes `*.sql` files in lexical order against an in-memory SQLite database and runs `PRAGMA integrity_check`.
