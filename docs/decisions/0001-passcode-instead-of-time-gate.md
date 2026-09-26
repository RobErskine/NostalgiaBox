# 0001: Passcode lock instead of a 9pm time gate

**Decision:** Adult Swim / Movies are gated by a 4-digit passcode (`passcode:` on the channel), not
a wall-clock airing window.

**Why:** The box runs offline at the in-laws' with no network and no RTC (battery-backed clock).
A Raspberry Pi's clock drifts and resets across power cuts with no network to correct it via NTP.
A time gate built on a wrong clock fails in the worst direction — it can silently show the adult
channel during the day. A passcode has no time dependency at all, so it can't fail that way, and it
is also less code: no wall-clock injection, no per-tick boundary re-check.

**Alternatives considered:**
- Wall-clock airing window (the original design) — parked, see the "deliberately not building"
  section of the plan, in case an RTC or Wi-Fi is added later.
- Wi-Fi + NTP to keep the clock correct — rejected, the box must work with no network.
- A DS3231 RTC module (~$7, I2C) — would make a time gate reliable, but is unnecessary hardware for
  what a passcode already solves in software.

**Date:** 2026-09-04
