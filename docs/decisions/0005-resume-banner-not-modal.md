# 0005: Resume offers "start over" via a banner, not a blocking popup

**Decision:** A channel with `tune_in: resume` always resumes automatically. On tune-in it shows a
non-blocking banner (`RESUMING - PRESS OK TO START OVER`) for a few seconds; pressing OK/ENTER in
that window discards the resume position and starts a fresh episode instead.

**Why:** Rob's original ask was a yes/no popup asking whether to save the spot. A modal blocks the
screen on every channel change, needs a two-button decision from a 1st-grader on a big-button
remote, and asks the question at the exact moment the viewer has already decided to leave the
channel. Always-resume-with-an-escape-hatch has the right default, is undoable, and never blocks
the screen. Rob agreed to this when it was proposed.

**Alternatives considered:** the original blocking yes/no modal — same implementation effort,
rejected for the UX reasons above.

**Date:** 2026-09-04
