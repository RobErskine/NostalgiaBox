# 0007: Drive the mpv binary over IPC on macOS, instead of libmpv

**Decision:** On macOS the app spawns the real `mpv` binary as a subprocess and
controls it over mpv's JSON IPC socket (`MpvIpcPlayer`), instead of loading
libmpv in-process (`MpvPlayer`). Selected automatically by
`player_backend: auto` (the default); can be forced either way with
`player_backend: libmpv | ipc`.

**Why:** libmpv cannot open its own window from a plain Python process on
macOS - it needs a Cocoa/NSApplication event loop running on the main thread,
which a CLI Python script doesn't provide. The symptom is exact and confusing:
audio plays fine (audio doesn't need the main thread) but no window ever
appears, with no error logged. This is a documented libmpv limitation, not
something fixable in our code or with an mpv option:
- https://github.com/mpv-player/mpv-examples/issues/29
- https://github.com/jaseg/python-mpv

The `mpv` binary runs its own event loop, so the window works normally. Cost is
one extra process and a socket.

**Alternatives considered:**
- Embedding into a GUI toolkit window (PyQt/Tk) so libmpv has a host window to
  draw into - drags a whole GUI framework into a project whose entire point is
  *not* having a desktop, and would only ever be used on dev machines.
- Only supporting the dev harness via `--dry-run` (mock player, no video) -
  rejected, since seeing real video locally before touching the Pi is the whole
  point of the desktop harness (Phase 1).
- Using IPC everywhere, dropping libmpv entirely - rejected, libmpv is one less
  process and works fine on the Pi (Linux), which is the actual deployment
  target. Keeping both means the Pi path stays exactly as it was.

**Two known simplifications in the IPC backend** (both fine for a dev machine,
and noted in the class docstring): `play_transition` cuts straight to the
episode rather than showing the static/glitch burst, and `get_time_pos` reads
an observed property rather than doing a synchronous query, so it can be a
moment stale.

**Date:** 2026-09-04
