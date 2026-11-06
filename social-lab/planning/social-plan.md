# Social lab plan and integration contract

This separate experiment addresses public insights, directed follows, a following feed and optional passage context. All current users and text are fictional. No scripture text, account service, cloud storage or existing notes are included.

## Model and behavior

An insight has one stable ID, author, draft/public state, body and a set of passage groups. A group is a contiguous inclusive range in one canonical work and book, with chapter and verse endpoints; one post may contain disjoint groups across books or works. Exact duplicates are removed and groups sorted deterministically. Overlap is inclusive, limited to the same work and book, and may cross chapters. The lab's catalog supports only two sample chapters per book; it rejects unknown books, missing verses, invalid bounds and reversed ranges. It is not an authoritative canon or mapping system. Links encode the reference, not the displayed edition.

Follow is directed. Context displays public posts by followed and unblocked authors when any anchor overlaps the selected range; the matching anchors are named without claiming the whole range was discussed. Drafts stay local and hidden from the feed. Explicit publish is limited to this browser. Editing and deletion update the local projection; blocking hides the author's public content locally. The sample reader is a reference selector, not an integration with CG's active reader.

## Reader integration contract

A future reader adapter should send `{workId, bookId, start:{chapter,verse}, end:{chapter,verse}, mappingVersion}` for each visible or selected canonical range, plus an explicit user-controlled enabled flag. The social module returns post IDs and the overlapping original anchor groups, preserving one post and all groups. It must never send selected ranges or reading activity remotely without a separate, informed consent and design decision. Edition switches change display only when a verified mapping exists. Missing, split, merged, or uncertain versification must return an explicit unresolved/partial mapping, never infer equivalence. Canonical IDs, mapping versions, selection event lifecycle and links must be agreed with the reader owner before connecting; this lab's strings and toy catalog are not that contract's final authority.

## Production work and decisions

1. Define canonical passage and edition mapping, stable IDs, migration/versioning, and ambiguous mappings against licensed authoritative data. Add cross-chapter, cross-work, split/merge and unmapped regression fixtures.
2. Design accounts and server-side authorization: private drafts visible only to owners, explicit public publish/review, owner-only edit/delete, follow and block enforcement in feeds and all direct access paths. Enforce rules on the server; browser controls are not security.
3. Establish abuse reporting, moderation queue, block semantics, rate limits, deletion/retention, account recovery, user safety and audit controls before a public deployment. This lab provides a local block only and no reporting backend.
4. Decide visibility, consent, attribution, terms and source licensing; publish a separate reviewed post rather than uploading private notes or reading history. Investigate secure storage, accessible mobile layouts and offline synchronization/conflict policy.
5. Test permission bypasses, public/private boundaries, deleted/blocked content, offline and cross-device behavior, accessibility and real reader selection integration before release. No hosting, real identities or data are configured.

## Next integration contract: portable social data

Define an independently versioned backup envelope and reader adapter separately. The adapter must accept a versioned canonical reference set plus per-group mapping status, and return post IDs and matched original groups without changing post privacy. Unmapped or partial edition mappings are explicit; no best-guess widening. Agree ownership of canonical identifiers, chapter boundaries and mapping migrations with reader maintainers before wiring it in. A production service must authorize drafts, publication, block and deletion server-side; local backup labels and client-side filters are not security controls. Portable data must not include reader activity or notes unless a later explicit consent and export design covers them.

## Concurrent local writes: assessment

The existing localStorage guard detects a prior write but its check and set are separate; two tabs may still pass the check at once. A bounded candidate is a named exclusive Web Lock held across reading the current saved value, comparing the revision, validating and writing, with every save, import, reset and recovery write routed through the same asynchronous coordinator. Reject writes when locking is unavailable; do not fall back silently to the current race. This coordinates only cooperating same-origin tabs: an older open version or other code that writes the key without acquiring the lock can still race. A stronger long-term option is an IndexedDB transaction with a revision check and explicit migration, plus tests for two concurrent writers, stale import previews, failed writes and recovery. It also needs UI tests for focus and unsaved-editor retention. Neither mechanism is implemented in this milestone; use one tab when editing.
