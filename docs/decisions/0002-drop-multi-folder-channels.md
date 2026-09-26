# 0002: Dropped multi-folder channels

**Decision:** A channel is still exactly one folder (`path:`). The originally-planned `paths:` list
(a channel drawing from several folders) was dropped.

**Why:** The feature existed to let a channel pull from several existing Plex show folders without
moving media. Once the decision was made to physically reorganize the drive into one folder per
channel (`02-baby/`, `04-kids/`, etc. — see the drive layout in the plan), the need disappeared:
`scan_recursive: true` + the existing recursive `rglob` scan already flattens everything under one
folder, including nested `Season NN/` subfolders. Building `paths:` would have been unused code.

**Alternatives considered:** keep `paths:` for future flexibility — rejected per the project's
"don't build for hypothetical future requirements" convention; it can be added later if the drive
layout ever changes back.

**Date:** 2026-09-04
