"""
Testy dla #266: przełącznik `BRIDGE_TEMPO`, liczba wywołań `adb` na ruch i znaczniki czasu.

`adb` podmieniony — bez emulatora. Ruch = `in_game` + `drag` + `stable_state` (ścieżka z `main()`).
"""
import io
import json
import os
import sys
import unittest
from unittest import mock

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bridge
from board import Board
from pieces import PIECE_POOL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEAM2 = next(p for p in PIECE_POOL if p.shape == [[1, 1]])


def _png():
    buf = io.BytesIO()
    Image.fromarray(np.zeros((640, 320, 3), dtype=np.uint8)).save(buf, format="PNG")
    return buf.getvalue()


PNG = _png()


def _calls_for_one_move(env):
    calls = []

    def fake_adb(*args):
        calls.append(args)
        if args[:2] == ("exec-out", "screencap"):
            return PNG
        if args[:2] == ("shell", "dumpsys"):
            return b"mCurrentFocus=Window{ com.block.juggle/x}"
        return b""

    with mock.patch.dict(os.environ, env, clear=False), \
         mock.patch("bridge.adb", side_effect=fake_adb), \
         mock.patch("bridge.time.sleep", lambda *_: None):
        bridge.in_game()
        bridge.drag((100, 500), BEAM2, 3, 3)
        bridge.stable_state()
    return calls


def _is_screencap(c):
    return c[:2] == ("exec-out", "screencap")


class TestTempoSwitch(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.pop("BRIDGE_TEMPO", None)

    def tearDown(self):
        os.environ.pop("BRIDGE_TEMPO", None)
        if self._saved is not None:
            os.environ["BRIDGE_TEMPO"] = self._saved

    def test_stare_replays_old_sequence(self):
        calls = _calls_for_one_move({"BRIDGE_TEMPO": "stare"})
        self.assertEqual(calls[0][:2], ("shell", "dumpsys"))
        actions = [c[3] for c in calls if c[:3] == ("shell", "input", "motionevent")]
        self.assertEqual(actions, ["DOWN"] + ["MOVE"] * 10 + ["UP"])
        self.assertEqual(calls[1][3], "DOWN")
        self.assertTrue(_is_screencap(calls[12]))  # celowanie tuż przed UP
        self.assertEqual(calls[13][3], "UP")
        self.assertEqual(sum(_is_screencap(c) for c in calls[14:]), 6)  # 2 x settled_state (3 klatki)
        self.assertEqual(len(calls), 20)

    def test_new_uses_fewer_adb_calls(self):
        old = _calls_for_one_move({"BRIDGE_TEMPO": "stare"})
        new = _calls_for_one_move({})
        print(f"wywolania adb na ruch: stara {len(old)} -> nowa {len(new)}")
        self.assertLess(len(new), len(old))

    def test_new_batches_down_and_moves_in_one_shell_call(self):
        calls = _calls_for_one_move({})
        batched = [c for c in calls if c[0] == "shell" and len(c) == 2 and "motionevent DOWN" in c[1]]
        self.assertEqual(len(batched), 1)
        self.assertEqual(batched[0][1].count("motionevent MOVE"), 10)

    def test_same_finger_target_in_both_paths(self):
        def finger(env):
            with mock.patch.dict(os.environ, env), mock.patch("bridge.adb", return_value=PNG), \
                 mock.patch("bridge.time.sleep", lambda *_: None):
                return bridge.drag((100, 500), BEAM2, 3, 3)[0]["finger"]
        self.assertEqual(finger({"BRIDGE_TEMPO": "stare"}), finger({}))

    def test_new_final_move_event_matches_old(self):
        old = _calls_for_one_move({"BRIDGE_TEMPO": "stare"})
        new = _calls_for_one_move({})
        last_old = [c for c in old if c[:4] == ("shell", "input", "motionevent", "MOVE")][-1]
        batch = [c for c in new if c[0] == "shell" and len(c) == 2 and "MOVE" in c[1]][0][1]
        self.assertEqual(batch.split("; ")[-1], " ".join(last_old[1:]))


class TestTimestamps(unittest.TestCase):
    def test_rows_have_t_and_move_rows_have_t_ms(self):
        runs = os.path.join(ROOT, "bridge", "runs")
        board_img = np.asarray(Image.open(os.path.join(runs, "0d96333", "120_state.png")).convert("RGB")).astype(int)
        board = Board()
        board.grid = [[0] * 8 for _ in range(8)]
        board.place_piece(BEAM2, 0, 0)
        grid = board.grid
        slots = [([[1, 1]], (20, 460)), None, None]
        with mock.patch("bridge.settled_state", return_value=(board_img, grid, slots)), \
             mock.patch("bridge.stable_state", return_value=(board_img, grid, slots)), \
             mock.patch("bridge.in_game", return_value=True), \
             mock.patch("bridge.read_score", return_value=100), \
             mock.patch("bridge.drag", return_value=({"finger": [0, 0]}, board_img)), \
             mock.patch("bridge.annotate"), mock.patch("PIL.Image.Image.save"), \
             mock.patch("bridge.os.makedirs"), \
             mock.patch("builtins.open", mock.mock_open()) as m_open:
            bridge.main(1, policy_spec="greedy")
        entries = [json.loads(c.args[0]) for c in m_open().write.call_args_list]
        self.assertTrue(entries)
        self.assertTrue(all(isinstance(e["t"], float) for e in entries))
        moves = [e for e in entries if "move" in e]
        self.assertTrue(moves)
        for e in moves:
            self.assertEqual(set(e["t_ms"]), {"odczyt", "decyzja", "przeciagniecie", "stabilny_stan"})


if __name__ == "__main__":
    unittest.main()
