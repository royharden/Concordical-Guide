# Importer Mini Fixture

This fixture is synthetic and license-safe. It mimics the small parts of the
bcbooks and Strong's JSON shapes that the first CG importers support.

`what_bug_this_catches`: keeps the importer from silently dropping either the
normal `books -> chapters -> verses` path or the Doctrine and Covenants
`sections -> verses` path, and proves that verse and Strong's FTS rows are
rebuilt from imported content.
