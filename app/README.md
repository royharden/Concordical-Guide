# Concordical Guide local reader

This is an early **private local preview**. It reads the existing generated `data/generated/sqlite/cg-source-v1.sqlite` database in read-only mode; its redistribution rights remain under review. Do not publish or expose this server to a network. The alternate Bible is World English Bible Protestant Edition, a public-domain text from eBible.org; its exact publisher archive, hash, edition and attribution are recorded in `data/manifests/webp.json`. The separate derived database is `data/generated/webp/engwebp.sqlite`. Verse numbers are matched directly, but versification may differ; a missing verse is shown as unavailable. Church study aids are link-outs. Word study offers a manual lexicon and a limited, source-verified Hebrew passage subset; it does not provide English-word alignment.

From the repository root, with Python 3, Node.js and npm installed:

```powershell
npm ci --prefix app
npm --prefix app run build
python scripts/build_webp.py
python scripts/serve_reader.py --port <registered-free-port>
```

Before starting the server, claim and check a loopback port using the `agent-ports` skill. For this session the registered port is 23800, giving `http://127.0.0.1:23800/`. Stop the server with Ctrl+C. Run `build_webp.py` only when its output is missing; it refuses to overwrite. It requires the pinned archive at the path in its manifest. If the original local database is missing, consult `scripts/build_source_sqlite.py` and the source manifests; do not download or distribute source text without the required rights review. Generated databases and source downloads are not part of the app bundle.

Notes stay in this browser's local storage. They are scoped to the exact origin: changing `127.0.0.1` to `localhost`, changing the port, or using another browser gives a separate store. Export notes before changing origin or clearing browser data. Select **Export notes**, then **Download JSON**, or copy the displayed backup text into a `.json` file if the download is blocked. Imports merge new IDs; existing IDs are never overwritten, and differing IDs are reported as conflicts. Browser storage is not a backup. The app uses browser Web Locks to prevent competing windows from silently overwriting one another, and disables writes if locks or storage are unavailable. Automated browser tests verified the copyable-text round-trip; that browser's blob download handler canceled the file download, so download completion remains unverified there.

To validate: `npm --prefix app run build`, `npm --prefix app test`, `python scripts/test_reader_server.py`, and `pwsh -NoProfile -File scripts/gauntlet.ps1`. With the private preview running and `agent-browser` available, `pwsh -NoProfile -File scripts/reader_browser_smoke.ps1 -Url http://127.0.0.1:23800/` runs isolated browser checks; its test notes do not use the user's browser profile.
# Word-study lookup

Run `python scripts/build_word_study.py` once after the original local source database is built; it refuses to overwrite an existing word-study store. Restart the reader server after changing its Python code. The separate generated store provides 14,298 manual Strong's dictionary entries, not verse-to-word alignments. The source is the existing `mormon-documentation-project/strongs` import, identified in `data/manifests/sources.json` and `licenses.json` (Unlicense, derived from OpenScriptures). The recorded local `strongs.json` SHA-256 is `2a6fa9d82c675de67785013a17c0cbbe8472a8ee02b91ce4a71b53ca540954ac`. Its upstream URL used a mutable branch; the exact upstream revision was not recorded. The builder verifies the local file and import receipt, then compares every imported dictionary row with its corresponding JSON fields before copying. A read-only audit on 2026-10-29 also found that all 14,298 current derived entries matched those imported rows. Do not treat this as release provenance approval.

## Hebrew subset

The Docker and host readers use the independently reviewed main-reading store for complete Genesis and Psalms 1-150 except 42:1, 44:1, 51:1, 52:1, 54:1 and 60:1. Build in order with `python scripts/build_oshb_subset.py`, `python scripts/build_oshb_genesis10.py`, `python scripts/build_oshb_genesis30.py`, `python scripts/build_oshb_genesis50.py`, `python scripts/build_oshb_genesis_complete.py`, `python scripts/build_oshb_psalms1_10.py`, `python scripts/build_oshb_psalms11_30.py`, `python scripts/build_oshb_psalms31_50.py`, `python scripts/build_oshb_psalms51_75.py`, `python scripts/build_oshb_psalms76_100.py`, `python scripts/build_oshb_psalms101_125.py`, `python scripts/build_oshb_psalms126_150.py`, and `python scripts/build_oshb_psalm13_segments.py`. Earlier Genesis outputs are historical prerequisites and **must not be served**: they contain alternate note words mixed into the main stream in 15 verses. The Psalms 1-10 builder verifies and removes those note words, preserves the raw source, and adds Psalm mappings. The corrected Psalms 1-150 store without the Psalm 13 spans is the rollback target. Builders use separate paths and do not overwrite stores. Psalm 13:5-6 uses source-derived word spans; the six remaining Psalm conflict and heading cases are unavailable. This is source-token data, not English-word alignment.

`data/manifests/oshb-subset.json` pins OSHB 2.0 source revision, license and SHA-256 hashes. Retrieve the two XML files and license at the immutable URLs in `data/manifests/sources.json` into ignored `data/downloads/oshb-v2/`, then run `python scripts/build_oshb_subset.py`; it refuses to overwrite its generated target. The builder verifies each hash, checks catalog references and enforces the source's Psalm 3 mapping note. Restart the reader server after updating Python source.

KJV Genesis 1-50 and Psalms 1-150 except 42:1, 44:1, 51:1, 52:1, 54:1 and 60:1 map to OSHB references using the pinned exception map and source notes; KJV Psalm 3:1 maps to OSHB Psalm 3:2. Each token is labeled Hebrew, Aramaic, or unspecified from its raw source morphology; a source label is not an independent linguistic determination. The main reading excludes alternate words inside source notes; those notes, punctuation and non-word segments are not displayed. WEB and other references remain unavailable until separately verified. Raw lemma/morphology are displayed with limited dictionary links for simple Hebrew lemmas; English-word alignment is not provided.

For the host launcher, the default is the same corrected store used by Docker. After the required registered-port check, run the following from the repository root. An optional `CG_OSHB_DB` selects a trusted local store; a missing selected or default file gives a 503 rather than silently falling back. Notes remain scoped to the exact browser origin.

```powershell
npm --prefix app run build
python scripts/serve_reader.py --port 23800
```

## Fictional Friends’ Insights integration

The reader has a default-off **Show Friends’ Insights** button. It shows read-only fictional in-memory examples, independent of the standalone social lab and all private notes. This demo does not access social-lab storage, upload reading context, or publish anything. Its versioned reference adapter supports KJV Genesis and John chapters 1–2 and Book of Mormon 1 Nephi chapters 1–2 only; other references and WEB display unavailable. Matching uses inclusive same-book ranges and shows only the original groups that overlap. No live follows or real social accounts are connected.

## Container preparation

`Dockerfile` and `compose.yaml` prepare a loopback-only local preview with read-only source data. The Compose file references a locally provisioned external network and must be adapted for another machine. Notes remain in the browser and do not automatically move between ports. Railway deployment, content rights, authentication and privacy remain unreviewed release gates.

## Mapping candidate status

Additional local-only candidate importers cover parts of Exodus, Leviticus, Numbers and Deuteronomy. The final Deuteronomy 22–23 and 28–29 candidate has not completed independent data review, full API comparison and rollback acceptance. Candidate importers and their tests do not imply the corresponding data is installed, accepted for distribution, or active in the live preview.
