import pytest

from nostalgiabox.actions import Action, InputEvent
from nostalgiabox.app import TVApp
from nostalgiabox.config import config_from_dict
from nostalgiabox.input.manager import InputManager
from nostalgiabox.player import END_EOF, MockPlayer
from tests.helpers import FakeClock, make_show


def build_app(tmp_path, *, assets_dir=None, **overrides):
    for name in ("dragon", "arthur", "rugrats"):
        make_show(tmp_path, name, 4)
    data = {
        "shuffle_seed": 7,
        "start_channel": 2,
        "start_offset": 0,  # keep test assertions on start=0 unless overridden
        "power_off_command": [],  # no-op in tests (never actually shut down)
        "channels": [
            {"number": 2, "name": "Dragon Tales", "path": str(tmp_path / "dragon")},
            {"number": 3, "name": "Arthur", "path": str(tmp_path / "arthur")},
            {"number": 4, "name": "Rugrats", "path": str(tmp_path / "rugrats")},
        ],
    }
    data.update(overrides)
    config = config_from_dict(data)
    clock = FakeClock()
    player = MockPlayer()
    app = TVApp(
        config,
        player,
        InputManager([]),
        clock=clock,
        assets_dir=assets_dir,
    )
    return app, player, clock


def send(app, action, value=None):
    app.handle_event(InputEvent(action, value))


def test_start_tunes_to_start_channel_and_plays(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    assert app.lineup.current.number == 2
    assert player.current is not None  # an episode is playing
    assert player.volume == 70
    assert player.overlays.get(1) and "Dragon Tales" in player.overlays[1]


def test_channel_up_down_wraps(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.CHANNEL_UP)
    assert app.lineup.current.number == 3
    send(app, Action.CHANNEL_UP)
    assert app.lineup.current.number == 4
    send(app, Action.CHANNEL_UP)
    assert app.lineup.current.number == 2  # wrapped
    send(app, Action.CHANNEL_DOWN)
    assert app.lineup.current.number == 4  # wrapped back


def test_volume_controls(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.VOLUME_UP)
    assert app.volume == 75 and player.volume == 75
    send(app, Action.VOLUME_DOWN)
    assert app.volume == 70
    # volume overlay was drawn
    assert "Volume" in player.overlays[2]


def test_volume_clamps(tmp_path):
    app, player, _ = build_app(tmp_path, initial_volume=98, volume_step=5)
    app.start()
    send(app, Action.VOLUME_UP)
    assert app.volume == 100
    for _ in range(30):
        send(app, Action.VOLUME_DOWN)
    assert app.volume == 0


def test_volume_down_at_zero_powers_off(tmp_path):
    app, player, _ = build_app(tmp_path, initial_volume=10, volume_step=5)
    app.start()
    send(app, Action.VOLUME_DOWN)   # 10 -> 5
    send(app, Action.VOLUME_DOWN)   # 5 -> 0
    assert app.volume == 0 and not app.powered_off
    send(app, Action.VOLUME_DOWN)   # one more at 0 -> power off
    assert app.powered_off is True
    assert app._running is False
    assert player.current is None   # playback stopped


def test_power_off_disabled(tmp_path):
    app, player, _ = build_app(
        tmp_path, initial_volume=0, power_off_on_min_volume=False
    )
    app.start()
    send(app, Action.VOLUME_DOWN)   # at 0, but feature disabled
    assert app.powered_off is False


def test_mute_toggle_and_unmute_on_volume(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.MUTE)
    assert app.muted and player.muted
    send(app, Action.VOLUME_UP)  # changing volume unmutes
    assert not app.muted and not player.muted


def test_direct_channel_entry_with_enter(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.DIGIT, 4)
    assert app.lineup.current.number == 2  # not committed yet
    send(app, Action.ENTER)
    assert app.lineup.current.number == 4


def test_direct_channel_entry_times_out(tmp_path):
    app, player, clock = build_app(tmp_path)
    app.start()
    send(app, Action.DIGIT, 3)
    assert app.lineup.current.number == 2
    clock.advance(2.1)  # past the entry timeout
    app.step()
    assert app.lineup.current.number == 3


def test_invalid_channel_entry_shows_message(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    assert app.select_channel_number(99) is False
    assert "NO CHANNEL" in player.overlays.get(4, "")
    assert app.lineup.current.number == 2  # unchanged


def test_last_channel_jump(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.CHANNEL_UP)  # now on 3, last=2
    assert app.lineup.current.number == 3
    send(app, Action.LAST_CHANNEL)
    assert app.lineup.current.number == 2
    send(app, Action.LAST_CHANNEL)  # bounces back to 3
    assert app.lineup.current.number == 3


def test_episode_advances_on_end(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    first = player.current
    player.finish_current(END_EOF)  # simulate the episode ending
    app._drain_playback_events()
    assert player.current is not None
    assert player.current != first  # rolled into the next shuffled episode


def test_standby_blanks_and_ignores_input(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.POWER)
    assert app.standby
    assert player.current is None  # screen blanked
    assert 3 in player.overlays  # standby overlay
    # input is ignored while in standby
    send(app, Action.CHANNEL_UP)
    assert app.lineup.current.number == 2
    # power again wakes it up and resumes playback
    send(app, Action.POWER)
    assert not app.standby
    assert player.current is not None


def test_quit_stops_running(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    app._running = True
    send(app, Action.QUIT)
    assert app._running is False


def test_glitch_transition_then_episode(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "glitch.mp4").write_bytes(b"\x00")
    app, player, clock = build_app(tmp_path, assets_dir=assets, transition="glitch")
    app.start()
    send(app, Action.CHANNEL_UP)
    # A glitch->episode transition was issued (glitch clip + preloaded episode).
    assert player.transitions, "expected a transition on channel change"
    clip, target, _start = player.transitions[-1]
    assert clip == assets / "glitch.mp4"
    assert player.current == target  # the episode is what plays


def test_transition_none_cuts_straight(tmp_path):
    # bridge_seconds=0 -> switch immediately, no transition clip, no preload
    app, player, _ = build_app(tmp_path, transition="none", bridge_seconds=0)
    app.start()
    first = player.current
    send(app, Action.CHANNEL_UP)
    assert not player.transitions
    assert player.preloaded is None
    assert player.current is not None and player.current != first


def test_channel_change_bridges_current_until_next_ready(tmp_path):
    # With bridge_seconds>0 and no transition, the current show keeps playing
    # while the next channel preloads, then cuts over after the window.
    app, player, clock = build_app(tmp_path, bridge_seconds=0.8)
    app.start()
    first = player.current
    send(app, Action.CHANNEL_UP)
    assert player.current == first          # old show still playing...
    assert player.preloaded is not None     # ...next channel preloading
    clock.advance(1.0)
    app.step()                              # bridge window elapsed -> switch
    assert player.preloaded is None
    assert player.current is not None and player.current != first


def test_advance_within_channel_has_no_transition(tmp_path):
    # An episode ending should roll straight into the next one (no glitch burst).
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "glitch.mp4").write_bytes(b"\x00")
    app, player, _ = build_app(tmp_path, assets_dir=assets, transition="glitch")
    app.start()
    before = len(player.transitions)
    player.finish_current(END_EOF)
    app._drain_playback_events()
    assert len(player.transitions) == before  # no new transition
    assert player.current is not None


def test_start_offset_applied(tmp_path):
    app, player, _ = build_app(tmp_path, start_offset=5)
    app.start()
    # The episode should begin 5 seconds in, not at the very beginning.
    assert player.played[-1][1] == 5.0


def test_start_offset_range_applied(tmp_path):
    app, player, _ = build_app(tmp_path, start_offset=[6, 10])
    app.start()
    assert 6.0 <= player.played[-1][1] <= 10.0


def test_empty_channel_shows_no_signal(tmp_path):
    (tmp_path / "dragon").mkdir()
    make_show(tmp_path, "arthur", 2)
    config = config_from_dict(
        {
            "channels": [
                {"number": 2, "name": "Dragon Tales", "path": str(tmp_path / "dragon")},
                {"number": 3, "name": "Arthur", "path": str(tmp_path / "arthur")},
            ]
        }
    )
    app = TVApp(config, MockPlayer(), InputManager([]), clock=FakeClock())
    app.start()  # starts on ch 2 which is empty
    assert "NO SIGNAL" in app.player.overlays.get(4, "")


def test_channel_banner_deferred_until_switch(tmp_path):
    app, player, clock = build_app(tmp_path, bridge_seconds=0.8)
    app.start()
    player.overlays.pop(1, None)          # clear the power-on banner
    send(app, Action.CHANNEL_UP)
    assert 1 not in player.overlays       # banner NOT shown during the bridge
    clock.advance(1.0)
    app.step()                            # cut-over happens here
    assert "CH 03" in player.overlays.get(1, "")  # banner appears at the switch


def test_resume_mode_restarts_where_left(tmp_path):
    # bridge_seconds=0 keeps this test focused on resume (immediate switches)
    app, player, _ = build_app(tmp_path, tune_in="resume", bridge_seconds=0)
    app.start()
    playing = player.current
    player.time_pos = 42.0
    send(app, Action.CHANNEL_UP)  # leave ch 2, remembering position 42
    send(app, Action.CHANNEL_DOWN)  # back to ch 2 -> resume at 42
    assert player.current == playing
    assert player.played[-1] == (playing, 42.0)


def test_resume_banner_shown_and_enter_starts_over(tmp_path):
    app, player, clock = build_app(tmp_path, tune_in="resume", bridge_seconds=0)
    app.start()
    playing = player.current
    player.time_pos = 42.0
    send(app, Action.CHANNEL_UP)
    send(app, Action.CHANNEL_DOWN)  # back to ch 2 -> resume banner shown
    assert "RESUMING" in player.overlays.get(1, "")
    assert app._resume_offer_until is not None
    send(app, Action.ENTER)  # start over instead
    assert app._resume_offer_until is None
    assert app.lineup.current.number == 2
    # A fresh episode was started (position back at the configured offset, not 42).
    assert player.played[-1][1] != 42.0


def test_resume_offer_expires_after_window(tmp_path):
    app, player, clock = build_app(tmp_path, tune_in="resume", bridge_seconds=0)
    app.start()
    player.time_pos = 42.0
    send(app, Action.CHANNEL_UP)
    send(app, Action.CHANNEL_DOWN)
    assert app._resume_offer_until is not None
    clock.advance(10.0)
    app.step()
    assert app._resume_offer_until is None


def test_break_clip_does_not_update_resume_position(tmp_path):
    for name in ("dragon", "arthur", "rugrats"):
        make_show(tmp_path, name, 4)
    breaks_dir = make_show(tmp_path, "breaks", 2)
    data = {
        "shuffle_seed": 7,
        "start_channel": 2,
        "start_offset": 0,
        "power_off_command": [],
        "tune_in": "resume",
        "bridge_seconds": 0,
        "breaks": {"path": str(breaks_dir), "every": 1, "count": 1},
        "channels": [
            {"number": 2, "name": "Dragon Tales", "path": str(tmp_path / "dragon")},
        ],
    }
    config = config_from_dict(data)
    player = MockPlayer()
    app = TVApp(config, player, InputManager([]), clock=FakeClock())
    app.start()
    first_episode = player.current
    player.time_pos = 15.0
    player.finish_current(END_EOF)  # episode ends -> a break clip fires
    app._drain_playback_events()
    assert player.current != first_episode  # the break clip is now "playing"
    # Leaving/returning must not have latched onto the break clip's position.
    app._remember_position()
    snapshot = app.lineup.current.resume_snapshot
    assert snapshot is None or snapshot[0] != player.current


# -- passcode lock ------------------------------------------------------------
def build_locked_app(tmp_path, *, passcode="1997", **overrides):
    make_show(tmp_path, "dragon", 4)
    locked_dir = make_show(tmp_path, "adultswim", 4)
    data = {
        "start_channel": 2,
        "start_offset": 0,
        "power_off_command": [],
        "channels": [
            {"number": 2, "name": "Dragon Tales", "path": str(tmp_path / "dragon")},
            {
                "number": 9,
                "name": "Adult Swim",
                "path": str(locked_dir),
                "passcode": passcode,
                "locked_message": "ADULT SWIM - LOCKED",
            },
        ],
    }
    data.update(overrides)
    config = config_from_dict(data)
    clock = FakeClock()
    player = MockPlayer()
    app = TVApp(config, player, InputManager([]), clock=clock)
    return app, player, clock


def test_locked_channel_shows_custom_message(tmp_path):
    app, player, _ = build_locked_app(tmp_path)
    app.start()
    send(app, Action.CHANNEL_UP)  # ch 2 -> ch 9 (locked)
    assert "ADULT SWIM - LOCKED" in player.overlays.get(4, "")
    assert "ENTER CODE" in player.overlays.get(4, "")
    assert player.current is None or player.looping is not None


def test_locked_channel_falls_back_to_default_message(tmp_path):
    make_show(tmp_path, "dragon", 4)
    locked_dir = make_show(tmp_path, "adultswim", 4)
    data = {
        "start_channel": 2,
        "start_offset": 0,
        "power_off_command": [],
        "channels": [
            {"number": 2, "name": "Dragon Tales", "path": str(tmp_path / "dragon")},
            {"number": 9, "name": "Adult Swim", "path": str(locked_dir), "passcode": "1997"},
        ],
    }
    config = config_from_dict(data)
    app = TVApp(config, MockPlayer(), InputManager([]), clock=FakeClock())
    app.start()
    send(app, Action.CHANNEL_UP)
    text = app.player.overlays.get(4, "")
    assert "LOCKED" in text
    assert "CH 09" in text


def test_correct_passcode_unlocks_and_plays(tmp_path):
    app, player, _ = build_locked_app(tmp_path)
    app.start()
    send(app, Action.CHANNEL_UP)  # locked
    for digit in (1, 9, 9, 7):
        send(app, Action.DIGIT, digit)
    assert app.lineup.current.locked is False
    assert player.current is not None


def test_wrong_passcode_stays_locked_and_shows_incorrect(tmp_path):
    app, player, _ = build_locked_app(tmp_path)
    app.start()
    send(app, Action.CHANNEL_UP)
    for digit in (0, 0, 0, 0):
        send(app, Action.DIGIT, digit)
    assert app.lineup.current.locked is True
    assert "INCORRECT" in player.overlays.get(4, "")
    assert player.current is None  # never started playing


def test_digits_go_to_passcode_not_channel_jump_while_locked(tmp_path):
    app, player, _ = build_locked_app(tmp_path)
    app.start()
    send(app, Action.CHANNEL_UP)  # on locked channel 9
    send(app, Action.DIGIT, 2)  # first digit of the code, NOT a channel jump
    assert app.lineup.current.number == 9  # unchanged
    assert app._digit_buffer == ""  # channel-entry buffer untouched


def test_channel_up_cancels_passcode_entry(tmp_path):
    app, player, _ = build_locked_app(tmp_path)
    app.start()
    send(app, Action.CHANNEL_UP)  # on locked channel 9
    send(app, Action.DIGIT, 1)  # start entering a code
    assert app._code_buffer == "1"
    send(app, Action.CHANNEL_UP)  # surf away instead
    assert app._code_buffer is None
    assert app.lineup.current.number == 2  # wrapped back around


def test_standby_relocks_channel(tmp_path):
    app, player, _ = build_locked_app(tmp_path)
    app.start()
    send(app, Action.CHANNEL_UP)
    for digit in (1, 9, 9, 7):
        send(app, Action.DIGIT, digit)
    assert app.lineup.current.locked is False
    send(app, Action.POWER)  # standby
    send(app, Action.POWER)  # wake up
    assert app.lineup.select_number(9).locked is True


def test_power_off_relocks_channel(tmp_path):
    app, player, _ = build_locked_app(tmp_path, initial_volume=5, volume_step=5)
    app.start()
    send(app, Action.CHANNEL_UP)
    for digit in (1, 9, 9, 7):
        send(app, Action.DIGIT, digit)
    assert app.lineup.select_number(9).locked is False
    send(app, Action.VOLUME_DOWN)  # 5 -> 0
    send(app, Action.VOLUME_DOWN)  # one more at 0 -> power off
    assert app.powered_off is True
    assert app.lineup.select_number(9).locked is True


# -- player backend selection -------------------------------------------------
def test_default_player_backend_is_ipc_on_macos(monkeypatch):
    import nostalgiabox.player as player_mod

    monkeypatch.setattr(player_mod.sys, "platform", "darwin")
    assert player_mod.default_player_backend() == "ipc"


def test_default_player_backend_is_libmpv_elsewhere(monkeypatch):
    import nostalgiabox.player as player_mod

    monkeypatch.setattr(player_mod.sys, "platform", "linux")
    assert player_mod.default_player_backend() == "libmpv"


def test_create_player_rejects_unknown_backend():
    from nostalgiabox.player import create_player

    with pytest.raises(ValueError, match="unknown player backend"):
        create_player("vlc")


# -- keys pressed in the player's own video window --------------------------
# On a dev machine the video is a separate mpv window, and whichever window has
# focus gets the keystrokes. The player reports its window keys back as action
# names; they must land on the input queue like any other remote's.


def test_window_key_reaches_the_app(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()

    player.on_key("volume_up")
    app.step()

    assert app.volume == 75


def test_window_key_digit(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()

    player.on_key("digit_3")
    app.step()

    assert app._digit_buffer == "3"


def test_window_key_unknown_action_is_ignored(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()

    player.on_key("wiggle_the_antenna")
    app.step()

    assert app.volume == 70


def test_window_keys_off_when_a_real_keyboard_is_attached(tmp_path):
    """evdev reads the device whatever has focus, so the window must stay deaf.

    Otherwise one press of a remote button would be acted on twice.
    """
    from nostalgiabox.app import _window_keys_for
    from nostalgiabox.input.base import InputBackend

    class FakeBackend(InputBackend):
        def __init__(self, name):
            super().__init__()
            self.name = name

        def _run(self):
            pass

    assert _window_keys_for(InputManager([FakeBackend("stdin")])) is not None
    assert _window_keys_for(InputManager([FakeBackend("keyboard")])) is None
    assert _window_keys_for(InputManager([])) is not None


# -- HOME button ------------------------------------------------------------
# The remote's HOME key jumps to the welcome/guide channel. It falls back to
# start_channel so a box that boots onto the guide needs no extra setting.


def test_home_jumps_to_home_channel(tmp_path):
    app, _, _ = build_app(tmp_path, start_channel=2, home_channel=4)
    app.start()
    send(app, Action.CHANNEL_UP)
    assert app.lineup.current.number == 3

    send(app, Action.HOME)

    assert app.lineup.current.number == 4


def test_home_falls_back_to_start_channel(tmp_path):
    app, _, _ = build_app(tmp_path, start_channel=3)
    app.start()
    send(app, Action.CHANNEL_UP)
    assert app.lineup.current.number == 4

    send(app, Action.HOME)

    assert app.lineup.current.number == 3


def test_home_does_nothing_without_either_setting(tmp_path):
    app, _, _ = build_app(tmp_path, start_channel=None)
    app.start()
    send(app, Action.CHANNEL_UP)
    before = app.lineup.current.number

    send(app, Action.HOME)

    assert app.lineup.current.number == before


def test_home_sets_last_channel_so_back_returns(tmp_path):
    """HOME then BACK is the pair a lost viewer uses; it has to round-trip."""
    app, _, _ = build_app(tmp_path, start_channel=2, home_channel=2)
    app.start()
    send(app, Action.CHANNEL_UP)
    assert app.lineup.current.number == 3

    send(app, Action.HOME)
    assert app.lineup.current.number == 2
    send(app, Action.LAST_CHANNEL)

    assert app.lineup.current.number == 3


def test_home_on_the_home_channel_just_shows_info(tmp_path):
    app, player, _ = build_app(tmp_path, start_channel=2, home_channel=2)
    app.start()
    playing = player.current

    send(app, Action.HOME)

    assert app.lineup.current.number == 2
    assert player.current == playing        # did not restart the channel
    assert player.overlays.get(1)           # banner re-shown


# -- skip buttons (◀ / ▶) ------------------------------------------------------


def test_next_episode_plays_something_else_on_the_same_channel(tmp_path):
    app, player, _ = build_app(tmp_path, transition="none", bridge_seconds=0)
    app.start()
    before = player.current

    send(app, Action.NEXT_EPISODE)

    assert app.lineup.current.number == 2
    assert player.current != before


def test_previous_episode_goes_back(tmp_path):
    app, player, _ = build_app(tmp_path, transition="none", bridge_seconds=0)
    app.start()
    first = player.current
    send(app, Action.NEXT_EPISODE)

    send(app, Action.PREVIOUS_EPISODE)

    assert player.current == first


def test_skip_shows_the_channel_banner(tmp_path):
    """The viewer pressed something and the picture changed: say what's on."""
    app, player, _ = build_app(tmp_path, transition="none", bridge_seconds=0)
    app.start()
    player.overlays.pop(1, None)

    send(app, Action.NEXT_EPISODE)

    assert "Dragon Tales" in player.overlays.get(1, "")


def test_skip_uses_the_same_bridge_as_a_channel_change(tmp_path):
    """No frozen frame: the old episode keeps playing while the next preloads."""
    app, player, clock = build_app(tmp_path, bridge_seconds=0.8)
    app.start()
    before = player.current

    send(app, Action.NEXT_EPISODE)
    assert player.current == before          # still on screen...
    assert player.preloaded is not None      # ...while the next one loads

    clock.advance(1.0)
    app.step()
    assert player.current != before
    assert player.preloaded is None


def test_skip_straight_after_a_channel_change_skips_on_the_new_channel(tmp_path):
    """A skip inside the bridge window must replace the pending switch, not
    have the old commit fire later and cut away from the skipped-to episode."""
    app, player, clock = build_app(tmp_path, bridge_seconds=0.8)
    app.start()
    send(app, Action.CHANNEL_UP)             # to channel 3; bridge pending
    first_on_3 = player.preloaded[0]

    send(app, Action.NEXT_EPISODE)           # still inside the bridge window
    target = player.preloaded[0]
    clock.advance(1.0)
    app.step()

    assert app.lineup.current.number == 3
    assert target != first_on_3
    assert player.current == target


def test_skip_is_ignored_in_standby(tmp_path):
    app, player, _ = build_app(tmp_path, transition="none", bridge_seconds=0)
    app.start()
    send(app, Action.POWER)
    before = player.current

    send(app, Action.NEXT_EPISODE)

    assert player.current == before


def test_skip_clears_a_pending_resume_offer(tmp_path):
    """Otherwise OK a moment later would 'start over' the skipped-to episode."""
    app, _, _ = build_app(tmp_path, transition="none", bridge_seconds=0)
    app.start()
    app._resume_offer_until = app._clock() + 10

    send(app, Action.NEXT_EPISODE)

    assert app._resume_offer_until is None


# -- appliance mode: drive unplugged / config edited ---------------------------


def test_media_change_stops_the_app_so_systemd_can_rescan(tmp_path):
    from nostalgiabox.media_watch import MediaWatch

    app, _, clock = build_app(tmp_path)
    cfg = tmp_path / "config.yaml"
    cfg.write_text("channels: []\n")
    app._media_watch = MediaWatch(cfg, [tmp_path / "dragon"], clock=clock)
    app.start()
    app._running = True

    clock.advance(10)
    app.step()
    assert app._running is True           # nothing changed yet

    cfg.unlink()                          # drive pulled out
    clock.advance(10)
    app.step()

    assert app._running is False


def test_no_watch_means_no_restarts(tmp_path):
    """Plain `nostalgiabox` on a dev machine must not quit on a config edit."""
    app, _, clock = build_app(tmp_path)
    app.start()
    app._running = True

    clock.advance(60)
    app.step()

    assert app._running is True
