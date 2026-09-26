# 0006: Decision log convention

**Decision:** Every non-obvious call made during planning or implementation gets a short markdown
file under `docs/decisions/`, numbered sequentially, indexed in `docs/decisions/README.md` (newest
first). Non-blocking questions Rob should weigh in on later, but that don't need to stall the build,
go in a running `docs/decisions/questions-for-rob.md` instead of a numbered decision file (they
aren't decided yet).

**Why:** Rob asked for a way to catch up on *why* things were built a certain way without
re-reading the whole planning conversation, especially since he's away from the keyboard organizing
media while the build runs unattended.

**Alternatives considered:** a single running CHANGELOG-style file — rejected, one file per decision
is easier to link to and to skim by title in the index.

**Date:** 2026-09-04
