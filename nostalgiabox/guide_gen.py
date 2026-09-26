"""Render the welcome / channel-guide screen into a video file.

Channel 1 is a "welcome channel", the way a hotel TV has one: tune to it and it
tells you what else is on. The running box has no concept of such a channel -
it is an ordinary channel folder holding one very boring episode, produced here
and copied onto the media drive.

Why a video file rather than something the app draws live: a channel is a
folder of episodes, and keeping it that way means the welcome screen needs no
new state, no new code path, and cannot break playback. The cost is that the
card has to be regenerated when the line-up changes - which is what this module
is for::

    python -m nostalgiabox.guide_gen --config config.yaml \\
        --out /Volumes/WARPMEDIA/01-guide/welcome.mp4

The card itself is drawn by :func:`nostalgiabox.overlay.guide_ass`, so it uses
the same font, phosphor green and glow as the channel banner and volume bar.
Rendering goes through mpv rather than ffmpeg's ``drawtext`` because libass is
what draws every other readout (and because a stock Homebrew ffmpeg is built
without freetype, so ``drawtext`` is often missing entirely).
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from .config import Config, load_config
from .overlay import CANVAS_H, CANVAS_W, guide_ass

log = logging.getLogger(__name__)

GUIDE_FILENAME = "welcome.mp4"

# What the remote can do, spelled out at the foot of the card. Two short lines
# read better on a TV across the room than one long one.
DEFAULT_HINT = (
    "UP / DOWN  change channel        LEFT / RIGHT  skip episode\n"
    "+ / -  volume      HOME  this guide      BACK  last channel"
)

# Long enough that the loop point is rare, short enough to stay a small file.
# The picture never changes, so the encoder spends almost nothing on it.
DEFAULT_SECONDS = 300


def render_card(
    config: Config,
    out_png: Path,
    *,
    hint: str = DEFAULT_HINT,
    mpv_binary: str = "mpv",
    timeout: float = 30.0,
) -> Path:
    """Draw the guide card to a PNG using mpv/libass, and return its path."""
    if shutil.which(mpv_binary) is None:
        raise RuntimeError(
            f"the '{mpv_binary}' binary was not found. Install it with "
            "`brew install mpv` (macOS) or `sudo apt install mpv` (Linux)."
        )
    ass = guide_ass(config.channels, config.ui, hint=hint)
    fonts_dir = Path(__file__).resolve().parent / "assets" / "fonts"

    sock_dir = tempfile.mkdtemp(prefix="nostalgiabox-guide-")
    sock_path = str(Path(sock_dir) / "mpv.sock")
    out_png.parent.mkdir(parents=True, exist_ok=True)

    proc = subprocess.Popen(
        [
            mpv_binary,
            # A plain black frame to draw the card onto. Paused on frame one:
            # nothing moves, so there is nothing to wait for.
            f"avdevice://lavfi:color=c=black:s={CANVAS_W}x{CANVAS_H}",
            f"--input-ipc-server={sock_path}",
            "--idle=yes",
            "--force-window=yes",
            "--pause=yes",
            "--osc=no",
            "--no-audio",
            "--input-default-bindings=no",
            "--input-vo-keyboard=no",
            "--input-terminal=no",
            f"--geometry={CANVAS_W}x{CANVAS_H}",
            f"--sub-fonts-dir={fonts_dir}",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        sock = _connect(sock_path, proc, timeout)
        try:
            _send(sock, ["osd-overlay", 1, "ass-events", ass, CANVAS_W, CANVAS_H])
            time.sleep(1.0)  # let libass lay the text out before capturing
            _send(sock, ["screenshot-to-file", str(out_png), "window"])
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if out_png.exists() and out_png.stat().st_size > 0:
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError("mpv never wrote the guide screenshot")
        finally:
            sock.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:  # pragma: no cover - stubborn mpv
            proc.kill()
        shutil.rmtree(sock_dir, ignore_errors=True)

    log.info("wrote guide card: %s", out_png)
    return out_png


def generate_guide(
    config: Config,
    out_path: Path,
    *,
    seconds: int = DEFAULT_SECONDS,
    hint: str = DEFAULT_HINT,
    keep_png: bool = False,
) -> Path:
    """Render the card and encode it as the welcome channel's one episode."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found (brew install ffmpeg / apt install ffmpeg)")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    png = out_path.with_suffix(".png")
    render_card(config, png, hint=hint)

    # A still picture at 5fps: tiny file, and mpv is happy to seek in it. Silent
    # on purpose - the welcome channel should not blare when a kid lands on it.
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-framerate", "5", "-i", str(png),
        "-t", str(seconds),
        "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
        "-pix_fmt", "yuv420p", "-r", "5", "-g", "25",
        "-movflags", "+faststart",
        str(out_path),
    ]
    log.info("running: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    if not keep_png:
        png.unlink(missing_ok=True)
    log.info("wrote welcome channel: %s", out_path)
    return out_path


# -- plumbing ---------------------------------------------------------------
def _connect(sock_path: str, proc: subprocess.Popen, timeout: float):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"mpv exited (code {proc.returncode}) before its socket")
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(sock_path)
            return sock
        except OSError:
            time.sleep(0.05)
    raise RuntimeError(f"timed out waiting for mpv's IPC socket at {sock_path}")


def _send(sock: socket.socket, command: list) -> None:
    sock.sendall((json.dumps({"command": command}) + "\n").encode("utf-8"))


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render the welcome / channel-guide screen as channel 1's episode."
    )
    parser.add_argument("-c", "--config", required=True, help="path to config.yaml")
    parser.add_argument(
        "-o", "--out", required=True,
        help=f"output video (e.g. /Volumes/WARPMEDIA/01-guide/{GUIDE_FILENAME})",
    )
    parser.add_argument(
        "--seconds", type=int, default=DEFAULT_SECONDS,
        help=f"length of the clip before it loops (default {DEFAULT_SECONDS})",
    )
    parser.add_argument(
        "--keep-png", action="store_true",
        help="also keep the rendered still, next to the video",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    config = load_config(args.config)
    generate_guide(
        config, Path(args.out), seconds=args.seconds, keep_png=args.keep_png
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["generate_guide", "render_card", "GUIDE_FILENAME", "DEFAULT_HINT"]
