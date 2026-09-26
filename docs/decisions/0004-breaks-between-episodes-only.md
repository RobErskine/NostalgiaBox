# 0004: Break clips fire only between episodes

**Decision:** "Commercial"/break-time clips (old ads, or Rob's own bathroom/snack/stretch cards)
only ever play after an episode finishes, never mid-episode.

**Why:** Rob was explicit: nothing should interrupt a show in progress, the way real TV commercials
would. Firing breaks only from `Channel.advance()` (called on natural episode end-of-file) makes
this true by construction — there is no code path that can start a break while an episode is
playing, so no "was it a real interruption" edge case exists to test for.

**Alternatives considered:** mid-episode breaks at a scheduled offset — would need seeking into the
episode and a resume-after-break state machine; explicitly out of scope, listed in
`.ai/todo.md`.

**Date:** 2026-09-04
