# Questions for Rob

Non-blocking calls made while building, worth a look when you're back at the
keyboard. Nothing here stalled the build.

- **Passcode length/format.** `passcode:` accepts 1-8 digits (no letters -
  most remotes have no letters). The dev config uses `"1997"` on Adult Swim
  and Movies as a placeholder. Change it to whatever you want before this
  goes anywhere real.
- **Resume-banner wording.** Went with `RESUMING - PRESS OK TO START OVER`,
  shown for 6 seconds (`RESUME_OFFER_SECONDS` in `app.py`). Shout if you want
  different wording or a longer/shorter window.
- **Break cadence default.** Dev config breaks every 2 episodes, 1-2 clips
  per break. Real config can set whatever `every`/`count` you want per
  channel or globally.
- **`--check` output got new tags** (`locked`, `resume`, `breaks: N clips
  every M`) next to each channel's episode count - flag if that's too noisy
  once you're staring at 7 real channels.
