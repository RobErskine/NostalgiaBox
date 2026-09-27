# NostalgiaBox

**Turn a Raspberry Pi into a retro TV for your kids.**

NostalgiaBox plays folders of old children's shows off an SD card as if they were
real TV **channels**. Flip to a channel and a show is already playing (starting a
few seconds in, like you just tuned in); when an episode ends, the next one rolls
automatically on an endless shuffle. It boots straight to the TV on power-up, is
driven by a simple remote, sends audio over HDMI, and has an authentic
early-2000s vibe — a green on-screen channel banner and volume bar, and a curved
"CRT" picture. No menus, no apps, no touchscreens. Just a remote and channels.

This guide has three parts:

1. [**Try it on your computer first**](#0-try-it-on-your-computer-first-no-pi-needed) — see every feature working before buying anything
2. [**The hardware you'll need**](#1-hardware)
3. [**Step-by-step setup**](#2-step-by-step-setup) — the SD card, the terminal, and the programming

---

## 0. Try it on your computer first (no Pi needed)

Before flashing an SD card or wiring anything up, you can run the real thing —
real mpv playback, in a window — on a Mac or Linux machine, against a
synthetic fake library generated in under a minute. This is the fastest way
to try channel changes, the passcode lock, resume, and break blocks.

```bash
brew install mpv ffmpeg          # macOS (apt install mpv ffmpeg on Linux)
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,desktop]"
./scripts/make-dev-library.sh    # builds dev-media/ + config.dev.yaml (~1 min)
nostalgiabox --config config.dev.yaml --windowed
```

Control it with your keyboard, not a real remote. The keys work in **either**
window — the video window or the terminal you started it from — so whichever
one you clicked last is fine (see `--dry-run` in
[For the curious](#for-the-curious-how-it-works) for a no-video variant too):

| Key | Does |
|-----|------|
| ↑ / ↓ | Channel up / down |
| ← / → | Volume down / up |
| 0-9, then Enter | Jump to a channel (or enter a passcode on a locked channel — try `1997` on channel 9) |
| m | Mute |
| i | What's playing now |
| l | Last channel watched |
| h | Home (the guide channel) |
| , / . | Previous / next episode on this channel |
| p | Standby |
| q / Ctrl-C | Quit |

Every clip in the fake library is short (20s) and has its channel/show name
burned into the picture, so a shuffle, a break block (fires every 2 episodes
here, instead of a real TV's 20+ minutes), and a resume (try channel 6 or 10,
tune away and back) are all visible within a minute. Add `--with-bunny` to
also download one real long-form movie (Big Buck Bunny) for a genuine
decode/resume test. Re-run with `--force` to regenerate the clips.

Once this all looks right, move on to the hardware below — you already know
your `config.yaml` works.

---

## 1. Hardware

> Two Raspberry Pi generations both work: the **Pi 4** is the safe default
> and what the parts list below is for. A **Pi 3** is fine too for
> standard-definition content, with two caveats: try `hwdec: "no"` in
> `config.yaml` if playback stutters (hardware decode is unreliable on a Pi 3
> with the current Raspberry Pi OS video driver), and the Pi 3 has a
> **full-size HDMI port**, not micro-HDMI, so skip the micro-HDMI cable below.
> If the CRT shader effect (Part 2) is too much for a Pi 3's GPU, set
> `crt: { enabled: false }`.

Everything you need to build one:

| Part | Link | What it's for |
|------|------|---------------|
| **Raspberry Pi 4 Model B** | https://amzn.to/4w6HcSC | The "brain" of the box (2GB RAM or more is plenty) |
| **Flirc USB Remote Adapter** | https://amzn.to/4h7hZ5O | Plugs into the Pi and lets **any** remote control it |
| **Simple TV Remote** | https://amzn.to/4wId7bZ | The big-button remote your kids will actually use |
| **Micro-HDMI → Full HDMI cable** | https://amzn.to/4pn1TXS | Connects the Pi to the TV (the Pi 4 uses micro-HDMI) |
| **Raspberry Pi 4 case** | https://amzn.to/4fg4RJ5 | Housing so it looks tidy next to the TV |

**You'll also need (you may already have these):**

- A **micro SD card**, 32 GB or larger. Bigger = more shows. (This holds the
  operating system *and* your video files.)
- A **USB-C power supply** for the Pi 4 (the official 3A one is recommended).
- A **TV with an HDMI port**.
- A **computer** (Mac or Windows) to set up the SD card and program the remote.
- Your **show video files** (e.g. `.mp4`/`.mkv` episodes you own).

---

## 2. Step-by-step setup

Take it one part at a time. You do the first two parts on your **computer**, then
the rest by connecting to the Pi.

### Part A — Prepare the SD card

1. On your computer, install the **Raspberry Pi Imager** from
   [raspberrypi.com/software](https://www.raspberrypi.com/software/).
2. **Unplug your media drive first.** The Storage step lists every external
   disk, and it will happily erase a 1 TB library. With only the SD card
   plugged in, there's nothing to get wrong.
3. Put the micro SD card into your computer. If it's in a full-size SD adapter,
   make sure the adapter's little lock slider is pushed *up* (unlocked).
4. Open Raspberry Pi Imager (2.0 or later) and step through:
   - **Device:** your Pi model (e.g. *Raspberry Pi 3*).
   - **OS:** scroll **past** the first few entries — those include a desktop —
     to **Raspberry Pi OS (other)**, then pick **Raspberry Pi OS Lite
     (64-bit)**. "Lite" has no desktop, which is what you want: the box boots
     straight to the TV. (A Pi 3 runs 64-bit fine.)
   - **Storage:** the SD card — check the size matches (a "32 GB" card shows as
     about 31.9 GB).
   - **Customisation:**
     - **Hostname:** `nostalgiabox`
     - **Localisation:** your time zone and keyboard layout
     - **User:** a username and password (remember these!)
     - **Wi-Fi:** name, password and country. An original Pi 3 Model B only
       does **2.4 GHz** Wi-Fi — pick a 2.4 GHz network, or plug in Ethernet.
     - **Remote access:** enable **SSH** with password authentication
     - **Raspberry Pi Connect:** optional; skip it
5. Write it (macOS asks for your password), wait for it to verify, then eject.

### Part B — Assemble and power on

1. Put the Pi in its case.
2. Plug the **Flirc** adapter into a USB port on the Pi.
3. Connect the Pi to your TV with HDMI. A Pi 3 takes a regular **HDMI** cable;
   a Pi 4 or 5 needs **micro-HDMI → HDMI** (use the port nearest the power
   socket).
4. Insert the SD card.
5. Plug in power. Wait ~1 minute for it to boot.

### Part C — Open the terminal and connect to the Pi

You'll control the Pi from your computer over the network (SSH).

- **Mac:** open the **Terminal** app.
- **Windows:** open **PowerShell**.

Then connect (use the username you set; hostname is `nostalgiabox`):

```bash
ssh pi@nostalgiabox.local
```

- The first time, type `yes` to accept.
- Enter your password (the screen stays blank while you type — that's normal).

You're "inside" the Pi when the prompt changes to something like
`pi@nostalgiabox:~ $`.

> If `nostalgiabox.local` doesn't resolve, find the Pi's IP address from your
> router and use `ssh pi@THAT.IP.ADDRESS` instead.

### Part D — Install NostalgiaBox

Install git (if needed), download the project, and run the installer:

```bash
sudo apt update
sudo apt install -y git
git clone https://github.com/RobErskine/NostalgiaBox.git ~/NostalgiaBox
cd ~/NostalgiaBox
./scripts/install.sh
```

The installer sets up everything: the media player (mpv), video tools (ffmpeg),
the retro font, and all dependencies. It takes a few minutes (10–20 on a Pi 3).
Say `y` if it asks to continue. It's done when you see **"==> Done!"**.

### Part E — Load your shows

Put each show in its **own folder**, one folder per channel. For example, on a
USB drive or copied onto the Pi:

```
/media/nostalgiabox/
├── Dragon Tales/
│   ├── S01E01.mp4
│   └── S01E02.mp4
├── Arthur/
└── The Magic School Bus/
```

The easiest way to get files onto the Pi is a **USB drive**: create the show
folders on it from your computer, copy your episodes in, plug it into the Pi, and
copy them over (ask for the exact copy commands if you need them). Any common
video format works (`.mp4`, `.mkv`, `.avi`, `.m4v`, …), and season sub-folders
are fine.

> **A large library (100+ GB) needs its own drive**, not the SD card. Format it
> **exFAT** (readable and writable by both a Mac/PC and the Pi) and give it a
> label with no spaces, e.g. `WARPMEDIA`. Put your `config.yaml` in the **root
> of the drive**: then the drive carries everything — shows, channel list and
> resume positions — and `./scripts/install-service.sh` (Part I) mounts it by
> that label automatically. The SD card's read-only overlay (Part J) works
> fine alongside a separate, writable media drive.

If you're building "channels" out of categories of shows rather than one show
per channel (e.g. a "kids" channel that's really five different shows), give
each category its own folder and copy the matching shows into it:

```
/media/nostalgiabox/
├── 02-baby/            Wee Sing/, Barney & Friends/…
├── 03-toddler/         Mickey Mouse Clubhouse/…
├── 04-kids/            Rugrats/, Wild Thornberrys/…
├── 09-adult-swim/      Aqua Teen Hunger Force/, Sealab 2021/…
├── 10-movies/
└── breaks/             old commercials + your own bathroom/snack/stretch clips
```

`scan_recursive: true` (the default) means season sub-folders inside each
show folder are picked up automatically — no need to flatten anything.

### Part F — Set up your channels

The installer already created a `config.yaml` for you from the template. Open it
and point the channels at your show folders:

```bash
nano config.yaml
```

A minimal example (see [`config.example.yaml`](config.example.yaml) for every
option):

```yaml
channels:
  - number: 2
    name: "Dragon Tales"
    path: /media/nostalgiabox/dragon-tales
  - number: 3
    name: "Arthur"
    path: /media/nostalgiabox/arthur

tune_in: random          # a random episode starts when you flip to a channel
start_offset: [6, 10]    # begin each show 6-10 seconds in (skips the intro)
```

Save in nano with **Ctrl+O**, Enter, then exit with **Ctrl+X**. Check it:

```bash
nostalgiabox --check
```

This lists your channels and how many episodes it found in each. (You can also
leave out specific seasons/specials per channel — see `exclude_seasons` and
`exclude` in the example config.)

#### Optional: a welcome channel, like a hotel TV

Channel 1 can be a still card that lists everything else on the box — handy
when a guest (or a kid who forgot) needs to know what's on. It isn't a special
kind of channel: it's an ordinary channel folder holding one long, very boring
episode, generated from your config so it can never disagree with it.

```bash
mkdir -p /media/nostalgiabox/01-guide
python -m nostalgiabox.guide_gen --config config.yaml \
    --out /media/nostalgiabox/01-guide/welcome.mp4
```

Then add it to `config.yaml` and point both the start and HOME channels at it:

```yaml
start_channel: 1
home_channel: 1          # the remote's HOME button comes back here

channels:
  - number: 1
    name: "Guide"
    path: /media/nostalgiabox/01-guide
    breaks: false
    start_offset: 0
  # ...the rest of your channels
```

The card is drawn with the same font, phosphor green and glow as the channel
banner, so it looks like part of the same television. Set the station name with
`ui.brand`. **Re-run the command above whenever you add or rename a channel** —
the card is a picture, so it won't update by itself.

### Part G — Program the remote (Flirc)

> **Before buying a Flirc, try HDMI-CEC — it's free.** If the TV supports it
> (most since ~2010: Anynet+, SimpLink, BRAVIA Sync, …), NostalgiaBox can read
> button presses from the TV's own remote straight over the HDMI cable, no
> extra hardware. Install `cec-utils` (`sudo apt install cec-utils`, already
> done if you ran `install.sh`) and make sure `cec: true` is set under `input:`
> in `config.yaml` (it's the default). If that works for your TV, you can skip
> the rest of this section entirely. A Flirc-programmed remote (e.g. the Argon
> IR Remote or any other universal remote) is the reliable fallback if CEC
> doesn't work with your TV, and both can be enabled at once.

The **Flirc** adapter learns your Simple TV Remote and turns its buttons into
keys NostalgiaBox understands. Do this **on your computer**:

1. Unplug the Flirc from the Pi and plug it into your computer.

   > **On a Mac, a "Keyboard Setup Assistant" window may pop up** asking you to
   > press the key next to Shift, then say the keyboard can't be identified.
   > That's macOS, not Flirc — the Flirc announces itself as a keyboard, and it
   > has no Z key to press. Close the window; nothing is wrong, and you never
   > need that window again.

2. Install the **Flirc** app: go to [flirc.tv](https://flirc.tv/products/flirc-usb-receiver),
   open the Flirc USB page, and use its **Downloads** section. Open the app; the
   bottom of its window should say **Connected**. If it offers a firmware
   upgrade, accept it and don't unplug until it finishes.
3. Start clean with **File → Clear Configuration**, then choose
   **Controllers → Full Keyboard**.
4. Click a key on the on-screen keyboard, then press the button on your remote
   you want to use for it. The Flirc only ever sends keystrokes, so *any*
   button can be taught *any* key — the remote's own printed labels don't
   constrain what it does.

   For the **Argon IR Remote** (Argon ONE V2), map every button like this:

   | Press this Argon button | Click this on-screen key | Does |
   |-------------------------|--------------------------|------|
   | **▲ / ▼** (D-pad up/down)    | Up arrow / Down arrow  | Channel up / down |
   | **◀ / ▶** (D-pad left/right) | `,` / `.`              | Previous / next episode on this channel |
   | **OK**                       | Enter                  | Confirm a typed channel / passcode |
   | **Vol + / Vol −**            | `=` / `-`              | Volume up / down |
   | **Home**                     | Home                   | Jump to the guide channel |
   | **Back**                     | Backspace              | Jump to the last channel watched |
   | **Menu** (the ☰ "listing" button) | `i`               | Show what's playing now |
   | **Power**                    | `p`                    | Standby (blank the screen) |

   **Why `,` and `.` rather than the arrow keys for ◀ ▶?** The left/right
   arrows are volume for everything else — including your TV's own remote over
   HDMI-CEC, whose arrows arrive as the very same keys. Giving the Flirc its own
   keys means ◀ ▶ skip on the Argon remote without changing what any other
   remote does. (Think `<` and `>`, which share those keys.)

   **Skipping, in practice:** ▶ means "not this one" and draws another episode;
   ◀ goes back to the one before, and ▶ after that steps forward again rather
   than picking something new — the same as shuffle on a music player. Holding
   a skip button fires once, not repeatedly. Skipping does nothing on a locked
   channel, the guide, or a `broadcast` channel (it's "live" — the next tune-in
   would undo it). And since Vol − is now the only volume-down button, it's also
   the one that powers the box off when pressed again at zero.

   **Unlocking a channel with no number buttons.** A locked channel's screen
   is a combination lock:

   ```
           ADULT SWIM - LOCKED
               ENTER CODE
     ┌────┐ ┌────┐ ┌────┐ ┌────┐
     │ *  │ │▓ 7▓│ │    │ │    │
     └────┘ └────┘ └────┘ └────┘
        < >  CHOOSE     OK  NEXT
   ```

   It fills the middle of the screen on a dark panel, with the digit you're
   choosing in a solid green box. **◀ / ▶** turn that digit (0–9, wrapping
   round), **OK** locks it in
   and moves to the next. Each digit starts at 0, so `1997` is: ▶ OK, ◀ OK,
   ◀ OK, ◀◀◀ OK. A wrong code says so and starts again; ▲ / ▼ still surf away.
   Digits typed on a keyboard, or on the TV's own remote over HDMI-CEC, work on
   the same screen too.

   The one thing the Argon remote can't do is jump straight to a channel by
   number — use ▲ / ▼, or teach a spare remote's number pad to the same Flirc
   (a Flirc learns any number of remotes).

5. **Test it before it leaves your computer.** Open a blank text document and
   press ◀ ▶ Vol+ Vol− ☰ Power in that order. It should type exactly `,.=-ip`.
   ▲ ▼ should move the cursor, OK should start a new line, and Back should
   delete a character. If a button types the wrong thing, click **Erase** in the
   Flirc app, press that remote button, then record it again.
6. Optional: **File → Save Configuration** keeps a backup of the mapping, so
   a replacement Flirc can be set up in seconds.
7. Unplug the Flirc from your computer and plug it back into the Pi. The
   mapping is stored on the Flirc itself — nothing to install on the Pi.

That's it — no config changes needed; these keys work out of the box. (Advanced:
you can remap any key via `key_overrides` in the config — see the example.)

### Part H — Get audio out the TV (HDMI)

The Pi sometimes sends audio to its headphone jack by default. To force it out
HDMI, find your HDMI audio device:

```bash
nostalgiabox --list-audio
```

Look for the **HDMI** entry (e.g. `alsa/hdmi:CARD=vc4hdmi0,DEV=0`). The Pi 4 has
two HDMI ports: the one nearest the USB-C power is `vc4hdmi0`, the other is
`vc4hdmi1`. Put the matching name in `config.yaml`:

```yaml
audio_device: "alsa/hdmi:CARD=vc4hdmi0,DEV=0"   # use vc4hdmi1 if on the 2nd port
```

### Part I — Make it boot to TV on power-up

Test it first (with the drive plugged in and mounted — see Part E):

```bash
nostalgiabox --config /media/nostalgiabox/config.yaml
```

Your shows should appear on the TV and respond to the remote. Press `q` on a
keyboard (or `Ctrl+C` in SSH) to stop. Happy with it? Turn on auto-start:

```bash
./scripts/install.sh --service
```

Now the box is an appliance. It boots straight to TV whenever it gets power —
no login, no menus, no Wi-Fi needed — in whatever state you plug it in:

| Situation | What happens |
|---|---|
| Normal power-up | Mounts the drive, scans the library, starts on the guide |
| Powered up **without** the drive | Shows muted colour bars and *CONNECT THE MEDIA DRIVE*, then starts by itself when you plug it in |
| Drive pulled out while it's on | Goes back to *CONNECT THE MEDIA DRIVE* |
| Drive plugged back in | Mounts it, **re-scans everything**, and carries on |
| TV / room / house changes | Nothing to do — it runs fully offline |

The installer finds the drive by its **label** (`WARPMEDIA` by default), adds it
to `/etc/fstab`, adds a udev rule so it also mounts when plugged in later, and
points the service at the `config.yaml` **on the drive**. Different mount path
or label? `./scripts/install-service.sh /your/mount/path YOURLABEL`.

### Part J — Make it kid-proof (recommended)

Kids will unplug it. Two things keep the SD card from getting corrupted:

- **Turn it off with the remote:** turn the volume all the way down to 0, let
  go, then press volume-down **once more** — the Pi shuts down cleanly
  ("GOODBYE"), and it's safe to unplug once the green light stops blinking.
  (Holding the button down stops at 0 on purpose, so it can't be done by
  accident. To turn it back on, unplug the power and plug it in again.)
- **Read-only mode — do this if the box moves around.** Run `sudo raspi-config`
  → **Performance Options → Overlay File System → Enable** (and write-protect
  the boot partition), then reboot. The SD card becomes read-only, so pulling
  the plug can *never* corrupt it. Nothing is lost: resume positions and the
  channel list live on the media drive, which stays writable. Do this **last**,
  after everything else works — to update or change settings on the Pi later,
  disable the overlay the same way, reboot, update, and re-enable it.

**Done!** Plug it in and enjoy your nostalgia box.

---

## Adding shows later (no terminal needed)

1. Unplug the drive from the Pi (it's fine to leave the Pi on — it'll show
   *CONNECT THE MEDIA DRIVE*).
2. Plug the drive into your computer and add episodes to the channel folders —
   drag them in, or re-run `./scripts/build-library.sh`.
3. **Eject** it properly, then plug it back into the Pi.

That's it: the Pi mounts it and re-scans every folder on its own. Adding a new
*channel* works the same way — edit `config.yaml` on the drive while it's on
your computer — though then also regenerate the guide card (see "a welcome
channel" in Part F) so channel 1 lists it.

## Using it day to day

| Do this | On the remote |
|---------|---------------|
| Change channels | Channel up / down (D-pad ▲ ▼) |
| Something else on this channel | ▶ (next episode) / ◀ (back to the last one) |
| Adjust volume | Vol + / Vol − |
| Mute | Mute |
| See what's playing | Menu / Info — the show and episode (or film and year) appear bottom-right |
| Back to the channel guide | Home |
| Back to the last channel watched | Back |
| Jump to a channel | Type the number, then OK (needs a number pad) |
| Unlock a locked channel | ◀ / ▶ pick each digit, OK for the next |
| Standby (blank screen) | Power |
| **Turn off** (safe to unplug) | At volume 0, let go, then press Vol − once more |

Turn it on by plugging in power; it boots back to a channel automatically.

---

## Updating later

If a newer version is released:

```bash
cd ~/NostalgiaBox
git pull
sudo systemctl restart nostalgiabox
```

(If you enabled the read-only overlay in Part J, turn it off first via
`raspi-config`, update, then turn it back on.)

---

## Configuration reference (highlights)

All settings live in `config.yaml`:

```yaml
tune_in: random          # random | resume | broadcast
start_channel: 2         # channel to power on to
start_offset: [6, 10]    # start each episode a random 6-10s in (or a fixed number)
transition: none         # channel-change effect: none | glitch | static
bridge_seconds: 0.8      # keep the current show playing while the next loads
channel_bug_seconds: 4   # how long the channel banner lingers
initial_volume: 70       # 0-100
audio_device: "..."      # force HDMI audio (see Part H)

ui:                      # the green on-screen display
  color: "#4DFF5A"
  glow: true
crt:                     # the CRT picture effect (curve, rounding, scanlines)
  enabled: true
  max_height: 720        # auto-off above this source height (0 = never)
  curvature: 0.045       # roughly double every crt: number for the heavy look
```

The CRT effect takes itself out of the way for HD films: anything taller than
`crt.max_height` plays clean, and the effect comes back for the next SD show.
That keeps the tube look on period TV — including 720p kids' shows — without
watching a modern 1080p feature through curved glass, and it frees up GPU work
on exactly the files a Pi 3 finds hardest. Set `max_height: 0` to keep the
effect on regardless.

Leaving out episodes per channel:

```yaml
  - number: 3
    name: "Arthur"
    path: /media/nostalgiabox/arthur
    exclude_seasons: ["6-25"]   # only air seasons 1-5
    exclude: ["*special*"]      # skip the specials
```

### Passcode-locked channels

Gate a channel (an "older kids" or grown-up channel) behind a short code, so
tuning to it shows a lock screen instead of playing anything:

```yaml
  - number: 9
    name: "Adult Swim"
    path: /media/nostalgiabox/adult-swim
    passcode: "1997"                       # 1-8 digits
    locked_message: "ADULT SWIM - LIVE AT 9PM"
```

Typing the code unlocks it for the rest of the session. Standby and power-off
re-lock every gated channel automatically. This is a kid gate, not real
security - the code lives in plain text in `config.yaml`.

### Resume, and per-channel playback settings

A channel can override the global `tune_in` mode and `start_offset` - handy
for a movie channel, which should pick up where you left off and start at
0:00 instead of a few seconds in:

```yaml
  - number: 10
    name: "Movies"
    path: /media/nostalgiabox/movies
    tune_in: resume
    start_offset: 0
```

Add a top-level `state_file` so resume positions survive a power cut, not
just a channel change:

```yaml
state_file: /media/nostalgiabox/.nostalgiabox-state.json
```

On tuning into a resumed item, a small banner offers a way out:
`RESUMING - PRESS OK TO START OVER`. Pressing OK/ENTER within a few seconds
discards the saved position and starts fresh instead.

### Break blocks (commercials, bathroom/snack/stretch breaks)

Old commercials, station bumpers, or your own recorded "BATHROOM BREAK" /
"SNACK TIME" / "STRETCH" clips - just video files in a folder - can be played
between episodes. They never interrupt a show in progress; a break only fires
once an episode reaches a natural end.

```yaml
breaks:
  path: /media/nostalgiabox/breaks
  every: 2        # a break block after every 2 episodes
  count: [1, 2]   # 1-2 clips per block
```

Turn it off for one channel (e.g. the baby channel) with `breaks: false` on
that channel, or give a channel its own break-clip folder by nesting a
`breaks:` block on the channel instead of the boolean.

Validate any changes with `nostalgiabox --check`.

---

## Troubleshooting

- **`--check` shows 0 episodes for a channel** → the `path` is wrong, or the
  files use an extension not in `video_extensions`.
- **No video on the TV** → make sure the HDMI cable is in the right Pi port and
  the TV is on that input. Check logs with `journalctl -u nostalgiabox -f`.
- **No sound** → see Part H; try switching `vc4hdmi0` ↔ `vc4hdmi1`, or the
  `alsa/plughw:CARD=...` variant.
- **Audio plays but no window appears (macOS)** → this is a libmpv limitation:
  it can't open its own window from a plain Python process on macOS. The app
  detects macOS and drives the `mpv` binary over a socket instead
  (`player_backend: auto`, the default). If you somehow hit this anyway, make
  sure `mpv` itself is installed (`brew install mpv`) and force the backend
  with `player_backend: ipc` in your config.
- **Remote does nothing** → confirm the Flirc is plugged into the Pi and was
  programmed (Part G). Restart the box after plugging it in.
- **It won't boot / config errors after a power cut** → the SD got corrupted from
  an unclean shutdown. Enable the read-only overlay (Part J) to prevent it.

---

## For the curious (how it works)

The project is plain Python. The "brains" (channel scanning, the shuffle, the
state machine) have no hardware dependencies and are fully unit-tested; the
hardware-facing parts (the mpv video player and the remote input) are isolated
behind small interfaces. You can even drive the whole thing on a laptop with a
mock player:

```bash
pip install -e ".[dev]"
pytest
python -m nostalgiabox --dry-run --config config.yaml   # keyboard-controlled, no video
```

```
nostalgiabox/
├── config.py      YAML -> validated config
├── playlist.py    the shuffle bag (each episode once, then reshuffle)
├── channel.py     folder scanning, tune-in modes, locks, breaks, navigation
├── state.py       resume-position persistence (survives a power cut)
├── player.py      mpv player (+ a mock for tests)
├── overlay.py     the green on-screen display
├── crt.py         the CRT shader
├── input/         remote input (Flirc/keyboard, HDMI-CEC, keymap)
├── static_gen.py  ffmpeg-generated static/glitch/colour-bar clips
└── app.py         the TV state machine
```

## License

MIT. Enjoy your nostalgia box!
