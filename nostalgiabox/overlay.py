"""On-screen display: the green digital channel banner, volume bar, and messages.

These are drawn to look like a late-90s/early-2000s TV's on-screen display: a
chunky phosphor-green readout in a retro terminal font, with a soft CRT glow.
Two signature elements:

* the **channel banner** ("CH 03" + the show name) that flashes top-right when
  you change channels, and
* the **volume bar** - a row of solid green bars for the current level followed
  by green dots for the rest, with a "Volume" label - matching a classic TV OSD.

Everything is rendered as ASS overlays on a fixed 1280x720 virtual canvas (mpv
scales it to the TV) and cleared automatically after a few seconds by
:meth:`OverlayManager.tick`, which the main loop calls every iteration.
"""

from __future__ import annotations

import time
from typing import Callable, Dict, Optional

from . import brand as brand_art
from .config import Config, UiConfig
from .titles import NowPlaying
from .player import Player

# Virtual canvas the overlays are laid out on. This maps to the WHOLE display
# (a 16:9 TV), so mpv scales it to whatever the screen is.
CANVAS_W = 1280
CANVAS_H = 720

# The video is forced into a 4:3 frame centred on the 16:9 canvas (see
# MpvPlayer.force_4_3). We lay the OSD out *inside* that 4:3 frame - with a small
# safe-area inset so nothing sits under the CRT's rounded corners - so the green
# readouts always sit over the picture, never out in the black pillarbox bars.
_FRAME_W = int(round(CANVAS_H * 4 / 3))        # 960
_FRAME_X0 = (CANVAS_W - _FRAME_W) // 2          # 160
_FRAME_X1 = _FRAME_X0 + _FRAME_W                # 1120
_FRAME_CX = (_FRAME_X0 + _FRAME_X1) // 2        # 640
_SAFE = 0.06
_IX0 = _FRAME_X0 + int(_FRAME_W * _SAFE)        # ~217  (left safe edge)
_IX1 = _FRAME_X1 - int(_FRAME_W * _SAFE)        # ~1062 (right safe edge)
_IY0 = int(CANVAS_H * _SAFE)                     # ~43   (top safe edge)
_IY1 = CANVAS_H - int(CANVAS_H * _SAFE)          # ~677  (bottom safe edge)

# Overlay slots (ids). Each kind of overlay owns one id so it can be replaced
# or cleared independently.
_ID_CHANNEL = 1
_ID_VOLUME = 2
_ID_STANDBY = 3
_ID_MESSAGE = 4

_BLACK = "&H00000000"

# Volume bar geometry. Module-level because the corner logo has to sit clear of
# the bar, and both need to agree on where the bar's top edge is.
_BAR_W = 16
_BAR_PITCH = 38
_BAR_H = 48
_BAR_ROW_TOP = _IY1 - _BAR_H            # bar sits just above the bottom safe edge


class OverlayManager:
    """Draws and expires the TV's on-screen overlays."""

    def __init__(
        self,
        player: Player,
        config: Config,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._player = player
        self._config = config
        self._ui = config.ui
        self._clock = clock
        # overlay id -> wall time (monotonic) at which it should disappear.
        self._expiry: Dict[int, float] = {}

    # -- public API ---------------------------------------------------------
    def show_channel_bug(
        self,
        number: int,
        name: str,
        *,
        subtitle: Optional[str] = None,
        caption: Optional[NowPlaying] = None,
        duration: Optional[float] = None,
    ) -> None:
        """Flash the channel number + name, like changing channels on a cable box.

        ``subtitle`` adds a small third line (used for the "RESUMING - PRESS OK
        TO START OVER" banner). ``caption`` names what's playing, bottom-right.
        """
        dur = self._config.channel_bug_seconds if duration is None else duration
        ass = _channel_bug_ass(number, name, self._ui, subtitle=subtitle, caption=caption)
        self._player.set_overlay(_ID_CHANNEL, ass, CANVAS_W, CANVAS_H)
        self._arm(_ID_CHANNEL, dur)

    def show_volume(
        self, level: int, muted: bool, *, duration: Optional[float] = None
    ) -> None:
        dur = self._config.osd_duration if duration is None else duration
        ass = _volume_ass(level, muted, self._ui)
        self._player.set_overlay(_ID_VOLUME, ass, CANVAS_W, CANVAS_H)
        self._arm(_ID_VOLUME, dur)

    def show_message(self, text: str, *, duration: Optional[float] = None) -> None:
        dur = self._config.osd_duration if duration is None else duration
        ass = _message_ass(text, self._ui)
        self._player.set_overlay(_ID_MESSAGE, ass, CANVAS_W, CANVAS_H)
        self._arm(_ID_MESSAGE, dur)

    def show_lock(
        self,
        title: str,
        *,
        entered: int,
        dial: int,
        length: int,
        status: Optional[str] = None,
    ) -> None:
        """The combination lock. Stays up until replaced or cleared."""
        ass = _lock_ass(
            title, self._ui, entered=entered, dial=dial, length=length, status=status
        )
        self._player.set_overlay(_ID_MESSAGE, ass, CANVAS_W, CANVAS_H)
        self._expiry.pop(_ID_MESSAGE, None)

    def show_standby(self) -> None:
        """Persistent 'standby' notice for when the box is 'off'."""
        ass = _standby_ass(self._ui)
        self._player.set_overlay(_ID_STANDBY, ass, CANVAS_W, CANVAS_H)
        self._expiry.pop(_ID_STANDBY, None)

    def clear_standby(self) -> None:
        self._player.clear_overlay(_ID_STANDBY)
        self._expiry.pop(_ID_STANDBY, None)

    def tick(self) -> None:
        """Clear any overlays whose time is up. Call this every loop iteration."""
        now = self._clock()
        for overlay_id, when in list(self._expiry.items()):
            if now >= when:
                self._player.clear_overlay(overlay_id)
                self._expiry.pop(overlay_id, None)

    def clear_all(self) -> None:
        for overlay_id in (_ID_CHANNEL, _ID_VOLUME, _ID_STANDBY, _ID_MESSAGE):
            self._player.clear_overlay(overlay_id)
        self._expiry.clear()

    # -- internals ----------------------------------------------------------
    def _arm(self, overlay_id: int, duration: float) -> None:
        if duration <= 0:
            # duration 0 means "leave it until explicitly cleared"
            self._expiry.pop(overlay_id, None)
        else:
            self._expiry[overlay_id] = self._clock() + duration


# --------------------------------------------------------------------------
# Colour + style helpers
# --------------------------------------------------------------------------
def _hex_to_ass(hex_color: str, alpha: int = 0) -> str:
    """Convert ``#RRGGBB`` to an ASS ``&HAABBGGRR`` colour string."""
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _style(ui: UiConfig, *, size: int, alpha: int = 0) -> str:
    """Common ASS override tags: retro font, green fill, and a soft CRT glow."""
    color = _hex_to_ass(ui.color, alpha)
    tags = rf"\fn{ui.font}\b1\fs{size}\c{color}\1a&H{alpha:02X}&"
    if ui.glow:
        # Lit phosphor against the unlit screen: an edge in the dark "unlit"
        # green, softened by a pixel. It keeps text crisp and legible over
        # bright video - including the colour bars behind the lock screen. (It
        # used to be a 4px blurred *green* border, a halo that smeared text
        # into the background on anything light.)
        dim = _hex_to_ass(ui.dim_color, alpha)
        tags += rf"\bord2\blur1\3c{dim}\shad0"
    else:
        tags += rf"\bord2\3c{_BLACK}\shad0"
    return tags


# --------------------------------------------------------------------------
# ASS builders (free functions so they are easy to unit test)
# --------------------------------------------------------------------------
def _channel_bug_ass(
    number: int,
    name: str,
    ui: UiConfig,
    *,
    subtitle: Optional[str] = None,
    caption: Optional[NowPlaying] = None,
) -> str:
    """Green digital 'CH 03' + show name, flashed inside the top-right of the frame."""
    num = f"{number:02d}"
    number_line = (
        rf"{{\an9\pos({_IX1},{_IY0}){_style(ui, size=88)}}}CH {num}"
    )
    name_line = (
        rf"{{\an9\pos({_IX1},{_IY0 + 104}){_style(ui, size=40)}}}{_escape(name)}"
    )
    lines = [number_line, name_line]
    if subtitle:
        lines.append(
            rf"{{\an9\pos({_IX1},{_IY0 + 104 + 48}){_style(ui, size=28)}}}{_escape(subtitle)}"
        )
    if ui.logo and (logo := _logo_ass(ui)):
        lines.append(logo)
    if caption is not None and caption.title:
        lines.extend(_caption_ass(caption, ui))
    return "\n".join(lines)


# The "now playing" caption: bottom-right, right-aligned, stacked just above
# the corner logo - clear of the volume bar below and the banner above.
_CAPTION_TITLE_SIZE = 40
_CAPTION_DETAIL_SIZE = 30
_CAPTION_GAP = 8                        # between the caption and the logo


def _caption_ass(caption: NowPlaying, ui: UiConfig) -> list:
    """The show (or film) name, with the episode (or year) on a line below."""
    lines = []
    bottom = _LOGO_TOP - _CAPTION_GAP  # sits on the logo, whatever size it is
    if caption.detail:
        lines.append(
            rf"{{\an3\pos({_IX1},{bottom}){_style(ui, size=_CAPTION_DETAIL_SIZE)}}}"
            f"{_escape(caption.detail)}"
        )
        bottom -= _CAPTION_DETAIL_SIZE + 6
    lines.append(
        rf"{{\an3\pos({_IX1},{bottom}){_style(ui, size=_CAPTION_TITLE_SIZE)}}}"
        f"{_escape(caption.title)}"
    )
    return lines


def _volume_ass(level: int, muted: bool, ui: UiConfig) -> str:
    """A 'Volume' label with solid green bars (level) then green dots (remainder)."""
    level = max(0, min(100, int(level)))
    segments = 20
    filled = 0 if muted else round(level / 100 * segments)

    bar_w = _BAR_W
    pitch = _BAR_PITCH
    bar_h = _BAR_H
    total_w = (segments - 1) * pitch + bar_w
    x0 = _FRAME_CX - total_w // 2          # centre the bar within the 4:3 frame
    row_top = _BAR_ROW_TOP                  # sit just above the bottom safe edge
    dot_r = 6
    green = _hex_to_ass(ui.color)

    label = "Mute" if muted else "Volume"
    parts = [
        rf"{{\an7\pos({x0},{row_top - 62}){_style(ui, size=48)}}}{label}"
    ]

    for i in range(segments):
        cx = x0 + i * pitch + bar_w / 2
        if i < filled:
            parts.append(
                _filled_rect(x=x0 + i * pitch, y=row_top, w=bar_w, h=bar_h, fill=green)
            )
        else:
            parts.append(_dot(cx=cx, cy=row_top + bar_h / 2, r=dot_r, fill=green))
    if ui.logo and (logo := _logo_ass(ui)):
        parts.append(logo)
    return "\n".join(parts)


def _message_ass(text: str, ui: UiConfig) -> str:
    """A centred green digital message (channel entry, 'NO SIGNAL', etc.).

    A python ``\\n`` in ``text`` becomes a forced line break (``\\N``) within
    the same event. It must not reach mpv as a real newline: each line of an
    ``osd-overlay`` is a separate event, so every line after the first would
    lose the position and styling and land top-left in plain white.
    """
    body = r"\N".join(_escape(line) for line in text.split("\n"))
    return rf"{{\an8\pos({_FRAME_CX},{_IY0}){_style(ui, size=60)}}}{body}"


def _standby_ass(ui: UiConfig) -> str:
    return rf"{{\an5\pos({_FRAME_CX},{CANVAS_H // 2}){_style(ui, size=72)}}}STANDBY"


# --------------------------------------------------------------------------
# Lock screen (a combination lock)
# --------------------------------------------------------------------------
# Big enough to read from the couch, in the middle of the picture, on a dark
# panel so it's legible over the colour bars. One box per digit; the digit
# being chosen is in inverse video (black on a solid green box), the way a
# VCR's clock highlights the field you're setting. The panel sits between the
# channel banner (top right) and the volume bar / corner logo (bottom), so
# pressing Vol +/- on the lock screen doesn't collide with it.
_LOCK_PANEL_X = _FRAME_CX - 400
_LOCK_PANEL_Y = 196
_LOCK_PANEL_W = 800
_LOCK_PANEL_H = 330
_LOCK_BOX_H = 130
_LOCK_BOX_MAX_W = 110
_LOCK_BOX_GAP = 22
_LOCK_BOXES_Y = _LOCK_PANEL_Y + 112


def _lock_ass(
    title: str,
    ui: UiConfig,
    *,
    entered: int,
    dial: int,
    length: int,
    status: Optional[str] = None,
) -> str:
    """The lock screen: title, one box per digit, and a help (or status) line.

    ``entered`` digits show as ``*``; the next box shows ``dial`` highlighted;
    the rest are empty. Boxes narrow to fit a long code (up to 8 digits).
    """
    green = _hex_to_ass(ui.color)
    length = max(1, length)
    inner_w = _LOCK_PANEL_W - 100
    box_w = min(_LOCK_BOX_MAX_W, (inner_w - (length - 1) * _LOCK_BOX_GAP) // length)
    total_w = length * box_w + (length - 1) * _LOCK_BOX_GAP
    x0 = _FRAME_CX - total_w // 2
    digit_size = min(int(_LOCK_BOX_H * 0.8), int(box_w * 1.6))

    parts = [
        _filled_rect(
            x=_LOCK_PANEL_X, y=_LOCK_PANEL_Y, w=_LOCK_PANEL_W, h=_LOCK_PANEL_H,
            fill=_BLACK, alpha=0x18,  # nearly opaque: bars mustn't muddy it
        ),
        rf"{{\an8\pos({_FRAME_CX},{_LOCK_PANEL_Y + 16}){_style(ui, size=46)}}}"
        f"{_escape(title)}",
        rf"{{\an8\pos({_FRAME_CX},{_LOCK_PANEL_Y + 68}){_style(ui, size=30)}}}"
        "ENTER CODE",
    ]
    for i in range(length):
        x = x0 + i * (box_w + _LOCK_BOX_GAP)
        cx, cy = x + box_w // 2, _LOCK_BOXES_Y + _LOCK_BOX_H // 2
        if i == entered:
            # The digit being chosen: inverse video.
            parts.append(_filled_rect(x=x, y=_LOCK_BOXES_Y, w=box_w, h=_LOCK_BOX_H, fill=green))
            parts.append(
                rf"{{\an5\pos({cx},{cy})\fn{ui.font}\b1\fs{digit_size}"
                rf"\c{_BLACK}\bord0\shad0\blur0}}{dial}"
            )
        else:
            parts.append(_outlined_rect(x=x, y=_LOCK_BOXES_Y, w=box_w, h=_LOCK_BOX_H, stroke=green))
            if i < entered:
                parts.append(
                    rf"{{\an5\pos({cx},{cy})"
                    rf"{_style(ui, size=digit_size)}}}*"
                )
    footer = status or "< >  CHOOSE        OK  NEXT"
    parts.append(
        rf"{{\an8\pos({_FRAME_CX},{_LOCK_BOXES_Y + _LOCK_BOX_H + 22})"
        rf"{_style(ui, size=38)}}}{_escape(footer)}"
    )
    return "\n".join(parts)


# --------------------------------------------------------------------------
# Welcome / channel-guide screen
# --------------------------------------------------------------------------
# A full-screen "what's on this TV" card, like the welcome channel in a hotel
# room. It is not an overlay the app shows: nostalgiabox.guide_gen renders it
# once into a video file that becomes channel 1, so the running box treats it
# as an ordinary channel with one very boring episode. Built here anyway, with
# the same font, colour and glow as every other readout, so the welcome screen
# and the TV's own OSD are unmistakably the same television.

_GUIDE_TITLE_SIZE = 76
_GUIDE_FOOT_SIZE = 28
_GUIDE_ROWS_TOP = _IY0 + 142
_GUIDE_ROWS_BOTTOM = _IY1 - 82      # leaves room for the two footer lines
_GUIDE_MAX_ROW_H = 46
# The list is a centred block rather than the full safe width, so a short
# channel name does not leave its "LOCKED" tag stranded on the far side of the
# screen. Columns: number, name, and a right-aligned tag.
_GUIDE_COL_NUM = _FRAME_CX - 250
_GUIDE_COL_NAME = _FRAME_CX - 170
_GUIDE_COL_TAG = _FRAME_CX + 250


_GUIDE_LOGO_H = 96
_GUIDE_WORDMARK_H = 42
_GUIDE_LOCKUP_GAP = 22


def _guide_header(ui: UiConfig, brand: Optional[str]) -> list:
    """The station's name at the top of the card: the logo and wordmark side by
    side - unless a custom name is set (``ui.brand`` or ``brand``), or the
    artwork can't be loaded, in which case the name is typed out."""
    logo, wordmark = brand_art.logo(), brand_art.wordmark()
    custom = brand or (ui.brand if ui.brand != UiConfig().brand else None)
    if custom or logo is None or wordmark is None:
        title = _escape(custom or ui.brand)
        return [rf"{{\an8\pos({_FRAME_CX},{_IY0}){_style(ui, size=_GUIDE_TITLE_SIZE)}}}{title}"]

    fill, edge = _hex_to_ass(ui.color), _hex_to_ass(ui.dim_color)
    logo_w = _GUIDE_LOGO_H * logo.aspect
    word_w = _GUIDE_WORDMARK_H * wordmark.aspect
    x0 = _FRAME_CX - (logo_w + _GUIDE_LOCKUP_GAP + word_w) / 2
    top = _IY0 - 8
    return [
        brand_art.art_ass(logo, x=x0, y=top, height=_GUIDE_LOGO_H, fill=fill, edge=edge),
        brand_art.art_ass(
            wordmark,
            x=x0 + logo_w + _GUIDE_LOCKUP_GAP,
            y=top + (_GUIDE_LOGO_H - _GUIDE_WORDMARK_H) / 2,
            height=_GUIDE_WORDMARK_H,
            fill=fill,
            edge=edge,
        ),
    ]


def guide_ass(
    channels: list, ui: UiConfig, *, brand: Optional[str] = None, hint: str = ""
) -> str:
    """The welcome screen: station name, the channel line-up, remote hints.

    ``channels`` is a list of objects with ``number``, ``name`` and an optional
    ``passcode`` (i.e. :class:`~nostalgiabox.config.ChannelConfig`). Everything
    is laid out inside the 4:3 safe area, so the card reads correctly whether
    or not the box is forcing 4:3. Row height shrinks to fit a long line-up
    rather than running off the bottom of the screen.
    """
    lines = _guide_header(ui, brand)
    lines.append(
        rf"{{\an8\pos({_FRAME_CX},{_IY0 + 100}){_style(ui, size=30)}}}CHANNEL GUIDE"
    )

    count = max(1, len(channels))
    row_h = min(_GUIDE_MAX_ROW_H, (_GUIDE_ROWS_BOTTOM - _GUIDE_ROWS_TOP) // count)
    size = max(18, int(row_h * 0.82))
    tag_size = max(14, int(size * 0.62))

    row_y = _GUIDE_ROWS_TOP
    for channel in channels:
        lines.append(
            rf"{{\an7\pos({_GUIDE_COL_NUM},{row_y}){_style(ui, size=size)}}}"
            f"{channel.number:02d}"
        )
        lines.append(
            rf"{{\an7\pos({_GUIDE_COL_NAME},{row_y}){_style(ui, size=size)}}}"
            f"{_escape(channel.name)}"
        )
        if getattr(channel, "passcode", None):
            lines.append(
                rf"{{\an9\pos({_GUIDE_COL_TAG},{row_y + size // 5})"
                rf"{_style(ui, size=tag_size)}}}LOCKED"
            )
        row_y += row_h

    if hint:
        body = r"\N".join(_escape(part) for part in hint.split("\n"))
        lines.append(
            rf"{{\an2\pos({_FRAME_CX},{_IY1}){_style(ui, size=_GUIDE_FOOT_SIZE)}}}{body}"
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Corner logo
# --------------------------------------------------------------------------
# The Time Warp TV mark in the bottom-right corner, shown whenever the channel
# banner or the volume bar is up. Drawn from assets/logo.svg (see brand.py) as
# vector paths, like the volume bar - so it scales with the canvas and swapping
# the SVG swaps the logo everywhere.

_LOGO_H = 80
_LOGO_RIGHT = _IX1                       # right edge, on the safe-area margin
_LOGO_BOTTOM = _BAR_ROW_TOP - 10         # clear of the volume bar underneath
_LOGO_TOP = _LOGO_BOTTOM - _LOGO_H


def _logo_ass(ui: UiConfig) -> str:
    """The corner mark, or "" if the artwork can't be loaded."""
    art = brand_art.logo()
    if art is None:
        return ""
    return brand_art.art_ass(
        art,
        x=_LOGO_RIGHT - _LOGO_H * art.aspect,
        y=_LOGO_TOP,
        height=_LOGO_H,
        fill=_hex_to_ass(ui.color),
        edge=_hex_to_ass(ui.dim_color),
    )


def _filled_rect(
    *, x: float, y: float, w: float, h: float, fill: str, alpha: int = 0
) -> str:
    """An ASS drawing (\\p1) filled rectangle at absolute canvas coordinates.

    ``alpha`` is ASS transparency: 0 = opaque, 255 = invisible.
    """
    x, y = round(x), round(y)
    w, h = round(w), round(h)
    draw = f"m 0 0 l {w} 0 l {w} {h} l 0 {h}"
    return (
        rf"{{\an7\pos({x},{y})\p1\c{fill}\1a&H{alpha:02X}&\bord0\shad0}}"
        rf"{draw}{{\p0}}"
    )


def _outlined_rect(*, x: float, y: float, w: float, h: float, stroke: str) -> str:
    """A hollow rectangle: transparent fill, coloured border. Anchored top-left,
    because a bordered drawing centred with ``\\an5`` doesn't land where the
    arithmetic says (libass sizes the box differently once there's a border)."""
    x, y = round(x), round(y)
    w, h = round(w), round(h)
    draw = f"m 0 0 l {w} 0 l {w} {h} l 0 {h} l 0 0"  # closed: square corners
    return (
        rf"{{\an7\pos({x},{y})\p1\1a&HFF&\bord3\3c{stroke}\3a&H00&\shad0}}"
        rf"{draw}{{\p0}}"
    )


def _dot(*, cx: float, cy: float, r: float, fill: str) -> str:
    """A small filled circle centred at (cx, cy) using 4 bezier arcs."""
    c = 0.5523 * r  # magic constant to approximate a circle with cubic beziers
    x, y = round(cx), round(cy)
    r = round(r, 2)
    c = round(c, 2)
    path = (
        f"m 0 {-r} "
        f"b {c} {-r} {r} {-c} {r} 0 "
        f"b {r} {c} {c} {r} 0 {r} "
        f"b {-c} {r} {-r} {c} {-r} 0 "
        f"b {-r} {-c} {-c} {-r} 0 {-r}"
    )
    return rf"{{\an5\pos({x},{y})\p1\c{fill}\1a&H00&\bord0\shad0}}{path}{{\p0}}"


def _escape(text: str) -> str:
    """Escape characters that are meaningful inside an ASS override block."""
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


__all__ = ["OverlayManager", "guide_ass", "CANVAS_W", "CANVAS_H"]
