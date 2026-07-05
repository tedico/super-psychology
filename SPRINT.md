# Sprint Plan — Super Psychology

## Phases
- [x] Phase 1 — Extraction: engine cloned from KontentMaschine worker (94 tests green), Alexandria adapter copied in, own test DB + migrations
- [ ] Phase 2 — First posts: Ted posts the 3 staged videos; channel identity (handle, bio, cover style) settled
- [ ] Phase 3 — Alexandria wiring: research stage reads the shared shelf (fetch Selected, stamp Used By on ship) instead of the local findings bank
- [ ] Phase 4 — Cadence: recurring production loop (topics per week, judge/QC gate before posting)

## Current phase
Phase 1 built (this PR) — standalone engine, no runtime coupling to
KontentMaschine or Alexandria (adapter is a committed copy).

## Next
Ted merges the extraction PR and posts the first three videos. Then Phase 3:
replace the engine's local research-findings selection with Alexandria shelf
reads + Used By stamping.

## Human
- Merge the extraction PR
- Post the 3 staged videos from ~/SuperPsychology-post-queue/ to the Super
  Psychology IG channel (01 Google Effect, 02 Third-Person Trick, 03
  Spotlight Effect); after posting, stamp their papers in Alexandria if they
  exist on the shelf
- Confirm channel handle/bio so the CTA card can carry it

## Blockers
none
