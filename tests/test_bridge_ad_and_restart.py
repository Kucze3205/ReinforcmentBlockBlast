"""
Testy dla #129: most przeżywa reklamę międzyplanszową i restart apki po jej śmierci.

Rozpoznanie reklamy testowane na prawdziwych zrzutach z przebiegu 0d96333
(`121_end.png` — reklama, `120_state.png` — ostatnia prawdziwa plansza sprzed niej)
i na zrzucie ekranu głównego po zabiciu procesu z 1bd38fa (`111_state.png`), żeby próg
ciemności nie łapał niczego poza reklamą. Restart korzysta z atrapy `adb`/`in_game` —
bez emulatora.
"""
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
RUNS = os.path.join(ROOT, "bridge", "runs")

BEAM2 = next(p for p in PIECE_POOL if p.shape == [[1, 1]])


def _load(*parts):
    return np.asarray(Image.open(os.path.join(RUNS, *parts)).convert("RGB")).astype(int)


class TestIsAdScreen(unittest.TestCase):
    def test_positive_on_ad_screenshot(self):
        self.assertTrue(bridge.is_ad_screen(_load("0d96333", "121_end.png")))

    def test_negative_on_real_game_state(self):
        self.assertFalse(bridge.is_ad_screen(_load("0d96333", "120_state.png")))

    def test_negative_on_home_screen_after_app_death(self):
        """Ekran główny po zabiciu procesu jest ciemny (tapeta), ale nie tak bardzo jak
        pełnoekranowa reklama — próg nie ma prawa pomylić jednego z drugim."""
        self.assertFalse(bridge.is_ad_screen(_load("1bd38fa", "111_state.png")))


class TestIsSettingsScreen(unittest.TestCase):
    """#150: modal Ustawień, w który most trafia po pomyłce `close_ad` (#130/#145)."""

    def test_positive_on_settings_opened_mid_game(self):
        for name in ("p1a_settings.png", "p1b_settings.png", "p1c_settings.png"):
            with self.subTest(name=name):
                self.assertTrue(bridge.is_settings_screen(_load("44a8ea2", name)))

    def test_positive_on_settings_reached_by_mistaken_close_ad(self):
        self.assertTrue(bridge.is_settings_screen(_load("44a8ea2", "p2e_stuck_settings_before.png")))

    def test_negative_before_and_after_manual_back(self):
        for name in ("p1a_before.png", "p1a_after_back.png",
                     "p1b_before.png", "p1b_after_back.png",
                     "p1c_before.png", "p1c_after_back.png"):
            with self.subTest(name=name):
                self.assertFalse(bridge.is_settings_screen(_load("44a8ea2", name)))

    def test_negative_after_back_from_mistaken_close_ad(self):
        self.assertFalse(bridge.is_settings_screen(_load("44a8ea2", "p2e_stuck_settings_after_back.png")))


class TestIsExitDialogScreen(unittest.TestCase):
    """#163: dialog wyjścia „Are you sure you want to leave?" — otwiera go „wstecz" naciśnięte
    na prawdziwej planszy (bez modalu), a `is_settings_screen` (próg ciemności) go z Ustawieniami
    myli. Zrzuty z `bridge/runs/495cd91/`: `loop2_after_no.png`, `after_back4.png`,
    `loop2_after_back.png` — dialog; `before_retry.png` — modal Ustawień; `loop_after_back.png`,
    `before_retry2.png` — prawdziwa plansza."""

    def test_positive_on_exit_dialog_screenshots(self):
        for name in ("loop2_after_no.png", "after_back4.png", "loop2_after_back.png"):
            with self.subTest(name=name):
                self.assertTrue(bridge.is_exit_dialog_screen(_load("495cd91", name)))

    def test_negative_on_settings_modal(self):
        self.assertFalse(bridge.is_exit_dialog_screen(_load("495cd91", "before_retry.png")))

    def test_negative_on_real_board(self):
        for name in ("loop_after_back.png", "before_retry2.png"):
            with self.subTest(name=name):
                self.assertFalse(bridge.is_exit_dialog_screen(_load("495cd91", name)))

    def test_settings_screen_is_false_on_exit_dialog(self):
        """`is_settings_screen` na próg jasności łapał ten dialog jako Ustawienia (#150) —
        teraz wyklucza się jawnie przez `is_exit_dialog_screen`."""
        for name in ("loop2_after_no.png", "after_back4.png", "loop2_after_back.png"):
            with self.subTest(name=name):
                self.assertFalse(bridge.is_settings_screen(_load("495cd91", name)))


class TestIsBrightAdScreen(unittest.TestCase):
    """#154: reklama jasna/interaktywna (quiz, „Connect Words") — `is_ad_screen` (próg
    ciemności) jej nie łapie."""

    def test_positive_on_bright_ad_screenshots(self):
        for name in ("p2_ad_video_before.png", "p2_ad_video_after_back.png",
                     "p2_ad_video_after_back2.png", "p2b_ad_before.png", "p2b_ad_after_back.png"):
            with self.subTest(name=name):
                self.assertTrue(bridge.is_bright_ad_screen(_load("44a8ea2", name)))

    def test_negative_on_board_screenshots(self):
        for name in ("p2_after_play.png", "p2b_after_play.png",
                     "p1a_before.png", "p1a_after_back.png",
                     "p1b_before.png", "p1c_before.png"):
            with self.subTest(name=name):
                self.assertFalse(bridge.is_bright_ad_screen(_load("44a8ea2", name)))

    def test_negative_on_settings_modal(self):
        for name in ("p1a_settings.png", "p2e_stuck_settings_before.png",
                     "p2c_real_ad_then_settings_before.png"):
            with self.subTest(name=name):
                self.assertFalse(bridge.is_bright_ad_screen(_load("44a8ea2", name)))

    def test_negative_on_dark_interstitial_ad(self):
        self.assertFalse(bridge.is_bright_ad_screen(_load("0d96333", "121_end.png")))


class TestPressBack(unittest.TestCase):
    @mock.patch("bridge.time.sleep", lambda *_: None)
    @mock.patch("bridge.adb")
    def test_sends_keycode_back(self, adb):
        bridge.press_back()
        adb.assert_called_once_with("shell", "input", "keyevent", "KEYCODE_BACK")


class TestBoardAndTrayEmpty(unittest.TestCase):
    def test_both_empty_is_suspicious(self):
        grid = [[0] * 8 for _ in range(8)]
        self.assertTrue(bridge.board_and_tray_empty(grid, [None, None, None]))

    def test_tray_piece_present_is_not_suspicious(self):
        grid = [[0] * 8 for _ in range(8)]
        slots = [([[1]], (0, 0)), None, None]
        self.assertFalse(bridge.board_and_tray_empty(grid, slots))

    def test_board_occupied_is_not_suspicious(self):
        grid = [[0] * 8 for _ in range(8)]
        grid[0][0] = 1
        self.assertFalse(bridge.board_and_tray_empty(grid, [None, None, None]))


class TestCloseAd(unittest.TestCase):
    @mock.patch("bridge.time.sleep", lambda *_: None)
    @mock.patch("bridge.touch")
    def test_recovers_after_one_tap(self, touch):
        game_img = _load("0d96333", "120_state.png")
        with mock.patch("bridge.screenshot", side_effect=[game_img]):
            self.assertTrue(bridge.close_ad())
        touch.assert_any_call("DOWN", *bridge.AD_CLOSE)
        touch.assert_any_call("UP", *bridge.AD_CLOSE)

    @mock.patch("bridge.time.sleep", lambda *_: None)
    @mock.patch("bridge.touch")
    def test_gives_up_after_tries(self, touch):
        ad_img = _load("0d96333", "121_end.png")
        with mock.patch("bridge.screenshot", side_effect=[ad_img, ad_img, ad_img]):
            self.assertFalse(bridge.close_ad(tries=3))


class TestRestartApp(unittest.TestCase):
    @mock.patch("bridge.time.sleep", lambda *_: None)
    @mock.patch("bridge.screenshot", return_value=_load("0d96333", "120_state.png"))
    @mock.patch("bridge.adb")
    def test_restarts_without_install_or_tos(self, adb, _screenshot):
        with mock.patch("bridge.in_game", side_effect=[True]):
            self.assertTrue(bridge.restart_app(tries=3, wait=0))
        adb.assert_called_once_with(
            "shell", "monkey", "-p", bridge.PACKAGE, "-c", "android.intent.category.LAUNCHER", "1")
        for call in adb.call_args_list:
            self.assertNotIn("install", call.args)
            self.assertNotIn("tap", call.args)

    @mock.patch("bridge.time.sleep", lambda *_: None)
    @mock.patch("bridge.adb")
    def test_gives_up_after_limit(self, adb):
        with mock.patch("bridge.in_game", side_effect=[False, False, False]):
            self.assertFalse(bridge.restart_app(tries=3, wait=0))
        self.assertEqual(adb.call_count, 3)


class TestMainSurvivesAdWindow(unittest.TestCase):
    """Stary odczyt kończył partię na 'pusta plansza i pusta tacka'. Ten test pokazuje,
    że most zamiast tego próbuje zamknąć okno i gra dalej (#129)."""

    def test_ad_window_does_not_end_the_game(self):
        empty_grid = [[0] * 8 for _ in range(8)]
        ad_img = _load("0d96333", "121_end.png")

        board = Board()
        board.grid = [row[:] for row in empty_grid]
        board.place_piece(BEAM2, 0, 0)
        playable_grid = board.grid
        playable_slot = ([[1, 1]], (20, 460))
        playable_slots = [playable_slot, None, None]
        game_img = _load("0d96333", "120_state.png")

        states = [(ad_img, empty_grid, [None, None, None])]

        def fake_settled_state():
            return states[0]

        def fake_stable_state(tries=6):
            return game_img, playable_grid, playable_slots

        with mock.patch("bridge.settled_state", side_effect=fake_settled_state), \
             mock.patch("bridge.stable_state", side_effect=fake_stable_state), \
             mock.patch("bridge.in_game", return_value=True), \
             mock.patch("bridge.close_ad", return_value=True) as close_ad, \
             mock.patch("bridge.read_score", return_value=None), \
             mock.patch("bridge.drag", return_value=({"finger": [0, 0]}, game_img)), \
             mock.patch("bridge.annotate"), \
             mock.patch("PIL.Image.Image.save"), \
             mock.patch("bridge.os.makedirs"), \
             mock.patch("builtins.open", mock.mock_open()):
            best_streak = bridge.main(1, policy_spec="greedy")

        close_ad.assert_called_once()
        self.assertEqual(best_streak, 0)  # jeden ruch bez porównania (drag zwraca atrapę), ale partia nie skończyła się na oknie


class TestMainRecoversFromSettingsWindow(unittest.TestCase):
    """#150: `close_ad` zamyka reklamę, ale trafia w Ustawienia (#130/#145) — most ma nacisnąć
    „wstecz" i wrócić do prawdziwej planszy zamiast uznać partię za skończoną."""

    def test_settings_window_after_close_ad_does_not_end_the_game(self):
        settings_img = _load("44a8ea2", "p2e_stuck_settings_before.png")
        empty_grid = [[0] * 8 for _ in range(8)]
        ad_img = _load("0d96333", "121_end.png")

        board = Board()
        board.grid = [row[:] for row in empty_grid]
        board.place_piece(BEAM2, 0, 0)
        playable_grid = board.grid
        playable_slot = ([[1, 1]], (20, 460))
        playable_slots = [playable_slot, None, None]
        game_img = _load("0d96333", "120_state.png")

        states = [(ad_img, empty_grid, [None, None, None])]

        def fake_settled_state():
            return states[0]

        stable_results = [
            (settings_img, empty_grid, [None, None, None]),  # zaraz po close_ad: Ustawienia
            (game_img, playable_grid, playable_slots),        # po wstecz: prawdziwa plansza
        ]

        def fake_stable_state(tries=6):
            # ostatni stan powtarza się po odczycie potwierdzającym ruch (jak w drag()).
            return stable_results.pop(0) if len(stable_results) > 1 else stable_results[0]

        with mock.patch("bridge.settled_state", side_effect=fake_settled_state), \
             mock.patch("bridge.stable_state", side_effect=fake_stable_state), \
             mock.patch("bridge.in_game", return_value=True), \
             mock.patch("bridge.close_ad", return_value=True) as close_ad, \
             mock.patch("bridge.press_back") as press_back, \
             mock.patch("bridge.read_score", return_value=None), \
             mock.patch("bridge.drag", return_value=({"finger": [0, 0]}, game_img)), \
             mock.patch("bridge.annotate"), \
             mock.patch("PIL.Image.Image.save"), \
             mock.patch("bridge.os.makedirs"), \
             mock.patch("builtins.open", mock.mock_open()):
            best_streak = bridge.main(1, policy_spec="greedy")

        close_ad.assert_called_once()
        press_back.assert_called_once()
        self.assertEqual(best_streak, 0)  # jeden ruch bez porównania, ale partia nie skończyła się na Ustawieniach


class TestMainSkipsCloseAdOnRealBoard(unittest.TestCase):
    """#163 punkt 2: `board_and_tray_empty` na przejściowej klatce prawdziwej planszy (bez
    reklamy) nie ma prawa wywołać `close_ad`, bo stuknięcie w (285,34) trafia w ikonę
    Ustawień na tej planszy, nie w X reklamy — otwiera pętlę od nowa."""

    def test_transient_empty_read_on_real_board_does_not_tap_ad_close(self):
        board_img = _load("495cd91", "loop_after_back.png")  # prawdziwa plansza, nie reklama
        empty_grid = [[0] * 8 for _ in range(8)]

        board = Board()
        board.grid = [row[:] for row in empty_grid]
        board.place_piece(BEAM2, 0, 0)
        playable_grid = board.grid
        playable_slot = ([[1, 1]], (20, 460))
        playable_slots = [playable_slot, None, None]

        def fake_settled_state():
            return board_img, empty_grid, [None, None, None]

        def fake_stable_state(tries=6):
            return board_img, playable_grid, playable_slots

        with mock.patch("bridge.settled_state", side_effect=fake_settled_state), \
             mock.patch("bridge.stable_state", side_effect=fake_stable_state), \
             mock.patch("bridge.in_game", return_value=True), \
             mock.patch("bridge.touch") as touch, \
             mock.patch("bridge.close_ad") as close_ad, \
             mock.patch("bridge.read_score", return_value=None), \
             mock.patch("bridge.drag", return_value=({"finger": [0, 0]}, board_img)), \
             mock.patch("bridge.annotate"), \
             mock.patch("PIL.Image.Image.save"), \
             mock.patch("bridge.os.makedirs"), \
             mock.patch("bridge.time.sleep"), \
             mock.patch("builtins.open", mock.mock_open()):
            bridge.main(1, policy_spec="greedy")

        close_ad.assert_not_called()
        for call in touch.call_args_list:
            self.assertNotEqual(tuple(call.args[1:]), bridge.AD_CLOSE)


class TestProgressSafeguard(unittest.TestCase):
    """#163 punkt 3: `settings_tries` się zerował na każdej nieokienkowej klatce, więc limit
    nigdy nie zatrzymywał pętli (materiał #159: >130 wpisów na stałym `n` w 10 minut). Licznik
    ogólny liczy wpisy okienkowe z rzędu, niezależnie od typu okna, i resetuje się tylko po
    wykonanym ruchu."""

    def _run_with_window_sequence(self, windows_before_move, max_moves=100):
        """`windows_before_move` liczy razem z pierwszym odczytem z `settled_state` (zawsze
        okienkowy w tym atrapie); potem jeden ruch, potem znowu okna aż do bezpiecznika."""
        window_img = _load("495cd91", "before_retry.png")  # modal Ustawień: zawsze "okienkowy"
        game_img = _load("0d96333", "120_state.png")
        empty_grid = [[0] * 8 for _ in range(8)]

        board = Board()
        board.grid = [row[:] for row in empty_grid]
        board.place_piece(BEAM2, 0, 0)
        playable_grid = board.grid
        playable_slot = ([[1, 1]], (20, 460))
        playable_slots = [playable_slot, None, None]

        remaining_before_move = [windows_before_move - 1]

        def fake_settled_state():
            return window_img, empty_grid, [None, None, None]

        def fake_stable_state(tries=6):
            if remaining_before_move[0] > 0:
                remaining_before_move[0] -= 1
                return window_img, empty_grid, [None, None, None]
            if remaining_before_move[0] == 0:
                remaining_before_move[0] = -1  # jeden ruch, potem znowu okno
                return game_img, playable_grid, playable_slots
            return window_img, empty_grid, [None, None, None]

        with mock.patch("bridge.settled_state", side_effect=fake_settled_state), \
             mock.patch("bridge.stable_state", side_effect=fake_stable_state), \
             mock.patch("bridge.in_game", return_value=True), \
             mock.patch("bridge.press_back"), \
             mock.patch("bridge.read_score", return_value=None), \
             mock.patch("bridge.drag", return_value=({"finger": [0, 0]}, game_img)), \
             mock.patch("bridge.annotate"), \
             mock.patch("PIL.Image.Image.save"), \
             mock.patch("bridge.os.makedirs"), \
             mock.patch("bridge.time.sleep"), \
             mock.patch("builtins.open", mock.mock_open()) as m_open:
            bridge.main(max_moves, policy_spec="greedy")

        handle = m_open()
        return [json.loads(c.args[0]) for c in handle.write.call_args_list]

    def test_stops_after_k_windowed_entries_without_progress(self):
        entries = self._run_with_window_sequence(windows_before_move=bridge.PROGRESS_SAFEGUARD_TRIES, max_moves=1)
        self.assertEqual(len(entries), bridge.PROGRESS_SAFEGUARD_TRIES)
        self.assertEqual(entries[-1]["end"], "okno: petla_bez_postepu")
        for e in entries[:-1]:
            self.assertNotIn("end", e)

    def test_move_resets_the_streak(self):
        k = bridge.PROGRESS_SAFEGUARD_TRIES
        entries = self._run_with_window_sequence(windows_before_move=k - 1, max_moves=100)
        # k-1 wpisów okienkowych, jeden ruch (nie liczy się do licznika), potem znowu k wpisów
        # okienkowych do zatrzymania: gdyby ruch nie zerował licznika, starczyłby jeden wpis.
        self.assertEqual(len(entries), (k - 1) + 1 + k)
        self.assertEqual(entries[-1]["end"], "okno: petla_bez_postepu")
        self.assertNotIn("end", entries[k - 1])  # wpis ruchu, w środku sekwencji


class TestMainStopsOnBrightAdWindow(unittest.TestCase):
    """#154: jasna reklama miesza most odczyt planszy jako pełną (#145); most ma się
    zatrzymać z oknem `reklama_jasna` zamiast fałszywego „brak legalnego ruchu"."""

    def test_bright_ad_window_stops_without_false_end(self):
        bright_ad_img = _load("44a8ea2", "p2b_ad_before.png")
        full_grid = [[1] * 8 for _ in range(8)]  # most odczytuje reklamę jako pełną planszę

        def fake_settled_state():
            return bright_ad_img, full_grid, [None, None, None]

        with mock.patch("bridge.settled_state", side_effect=fake_settled_state), \
             mock.patch("bridge.in_game", return_value=True), \
             mock.patch("bridge.read_score", return_value=None), \
             mock.patch("bridge.annotate"), \
             mock.patch("PIL.Image.Image.save"), \
             mock.patch("bridge.os.makedirs"), \
             mock.patch("builtins.open", mock.mock_open()):
            best_streak = bridge.main(1, policy_spec="greedy")

        self.assertEqual(best_streak, 0)


if __name__ == "__main__":
    unittest.main()
