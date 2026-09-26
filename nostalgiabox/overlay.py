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

from .config import Config, UiConfig
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
        duration: Optional[float] = None,
    ) -> None:
        """Flash the channel number + name, like changing channels on a cable box.

        ``subtitle`` adds a small third line (used for the "RESUMING - PRESS OK
        TO START OVER" banner).
        """
        dur = self._config.channel_bug_seconds if duration is None else duration
        ass = _channel_bug_ass(number, name, self._ui, subtitle=subtitle)
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
        # A blurred green border reads as phosphor bloom; a faint dark edge keeps
        # it legible over bright video.
        tags += rf"\bord2\blur4\3c{color}\4c{_BLACK}\shad0"
    else:
        tags += rf"\bord2\3c{_BLACK}\shad0"
    return tags


# --------------------------------------------------------------------------
# ASS builders (free functions so they are easy to unit test)
# --------------------------------------------------------------------------
def _channel_bug_ass(
    number: int, name: str, ui: UiConfig, *, subtitle: Optional[str] = None
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
    if ui.logo:
        lines.append(_logo_ass(ui))
    return "\n".join(lines)


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
    if ui.logo:
        parts.append(_logo_ass(ui))
    return "\n".join(parts)


def _message_ass(text: str, ui: UiConfig) -> str:
    """A centred green digital message (channel entry, 'NO SIGNAL', etc.)."""
    return rf"{{\an8\pos({_FRAME_CX},{_IY0}){_style(ui, size=60)}}}{_escape(text)}"


def _standby_ass(ui: UiConfig) -> str:
    return rf"{{\an5\pos({_FRAME_CX},{CANVAS_H // 2}){_style(ui, size=72)}}}STANDBY"


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
    title = _escape(brand or ui.brand)
    lines = [
        rf"{{\an8\pos({_FRAME_CX},{_IY0}){_style(ui, size=_GUIDE_TITLE_SIZE)}}}{title}",
        rf"{{\an8\pos({_FRAME_CX},{_IY0 + 88}){_style(ui, size=30)}}}CHANNEL GUIDE",
    ]

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
# A "Time Warp TV" mark in the bottom-right corner, shown whenever the channel
# banner or the volume bar is up. This is a PLACEHOLDER: the W held between two
# portal rings is the idea, but the real mark is still to be drawn.
#
# It is built from ASS vector paths - the same primitive the volume bar's
# rectangles and dots use - so it needs no image file and scales with the
# canvas. libass cannot read SVG, but an SVG path converts almost directly:
# "M x y" -> "m x y", "L x y" -> "l x y", "C ..." -> "b ...". So when the real
# logo exists as an SVG of simple paths, only _logo_ass below has to change.

_LOGO_SIZE = 52                          # cap height of the three letters
_LOGO_RIGHT = _IX1                       # right edge, on the safe-area margin
_LOGO_CY = _BAR_ROW_TOP - 46             # clear of the volume bar underneath
_LOGO_LETTER_GAP = 56                    # centre-to-centre, T to W to T
_PORTAL_RX = 12
_PORTAL_RY = 30
_PORTAL_GAP = 25                         # portal centre offset from the W's;
                                         # their inner edges just graze the W


def _logo_ass(ui: UiConfig) -> str:
    """The corner mark: T W T, with the middle W held between two portals."""
    green = _hex_to_ass(ui.color)
    # Laid out right-to-left, so the mark always ends flush with the margin.
    t_right = _LOGO_RIGHT - 18
    w_mid = t_right - _LOGO_LETTER_GAP
    t_left = w_mid - _LOGO_LETTER_GAP

    parts = [
        # Tight around the W, so it reads as held between them rather than
        # sitting beside them.
        _ring(cx=w_mid - _PORTAL_GAP, cy=_LOGO_CY,
              rx=_PORTAL_RX, ry=_PORTAL_RY, stroke=green),
        _ring(cx=w_mid + _PORTAL_GAP, cy=_LOGO_CY,
              rx=_PORTAL_RX, ry=_PORTAL_RY, stroke=green),
        rf"{{\an5\pos({t_left},{_LOGO_CY}){_style(ui, size=_LOGO_SIZE)}}}T",
        rf"{{\an5\pos({t_right},{_LOGO_CY}){_style(ui, size=_LOGO_SIZE)}}}T",
        # The W is a little larger and sheared, as if pulled by the portals.
        rf"{{\an5\pos({w_mid},{_LOGO_CY}){_style(ui, size=_LOGO_SIZE + 8)}"
        rf"\fax-0.1}}W",
    ]
    return "\n".join(parts)


def _ellipse_path(rx: float, ry: float) -> str:
    """An ellipse as four cubic bezier arcs, drawn from its top-left corner.

    Coordinates start at (0, 0) and run to (2rx, 2ry) rather than being centred
    on the origin, so the shape can be placed with ``\\an7`` - see _ring.
    """
    hx, hy = round(0.5523 * rx, 2), round(0.5523 * ry, 2)
    x0, y0 = round(rx, 2), round(ry, 2)          # centre, in path coordinates
    w, h = round(2 * rx, 2), round(2 * ry, 2)
    return (
        f"m {x0} 0 "
        f"b {x0 + hx} 0 {w} {y0 - hy} {w} {y0} "
        f"b {w} {y0 + hy} {x0 + hx} {h} {x0} {h} "
        f"b {x0 - hx} {h} 0 {y0 + hy} 0 {y0} "
        f"b 0 {y0 - hy} {x0 - hx} 0 {x0} 0"
    )


def _ring(*, cx: float, cy: float, rx: float, ry: float, stroke: str) -> str:
    """An unfilled ellipse outline: a transparent fill plus a coloured border.

    Anchored top-left (``\\an7``) at the shape's bounding box, like
    :func:`_filled_rect`. Centring a *bordered* drawing with ``\\an5`` does not
    land where the arithmetic says it should - libass sizes the box differently
    once there is a border - so the corner is positioned explicitly instead.
    """
    path = _ellipse_path(rx, ry)
    x, y = round(cx - rx), round(cy - ry)
    return (
        rf"{{\an7\pos({x},{y})\p1"
        rf"\1a&HFF&\bord2\3c{stroke}\3a&H00&\shad0}}{path}{{\p0}}"
    )


def _filled_rect(*, x: float, y: float, w: float, h: float, fill: str) -> str:
    """An ASS drawing (\\p1) filled rectangle at absolute canvas coordinates."""
    x, y = round(x), round(y)
    w, h = round(w), round(h)
    draw = f"m 0 0 l {w} 0 l {w} {h} l 0 {h}"
    return rf"{{\an7\pos({x},{y})\p1\c{fill}\1a&H00&\bord0\shad0}}{draw}{{\p0}}"


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
