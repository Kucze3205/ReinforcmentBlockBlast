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
             mock.patch.multiple("bridge", hard_restart_app=mock.DEFAULT, screenshot=mock.DEFAULT), \
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
        # #318: pierwszy ciąg K wpisów kończy się twardym restartem, drugi dopiero `petla_bez_postepu`
        k = bridge.PROGRESS_SAFEGUARD_TRIES
        entries = self._run_with_window_sequence(windows_before_move=2 * k, max_moves=1)
        self.assertEqual(len(entries), 2 * k)
        self.assertEqual(entries[k - 1]["okno"], "restart_twardy")
        self.assertEqual(entries[-1]["end"], "okno: petla_bez_postepu")
        for e in entries[:-1]:
            self.assertNotIn("end", e)

    def test_move_resets_the_streak(self):
        k = bridge.PROGRESS_SAFEGUARD_TRIES
        entries = self._run_with_window_sequence(windows_before_move=k - 1, max_moves=100)
        # k-1 wpisów okienkowych, jeden ruch (nie liczy się do licznika), potem znowu k wpisów
        # okienkowych z twardym restartem i drugim ciągiem do zatrzymania: gdyby ruch nie zerował licznika, starczyłby jeden wpis.
        self.assertEqual(len(entries), (k - 1) + 1 + 2 * k)  # po ruchu znów twardy restart + drugi ciąg
        self.assertEqual(entries[-1]["end"], "okno: petla_bez_postepu")
        self.assertNotIn("end", entries[k - 1])  # wpis ruchu, w środku sekwencji


class _StaticScreenHarness:
    """#235: atrapa `main` na ekranie, który się nie zmienia; zlicza `press_back`."""

    def run(self, img, grid, max_moves=1000, patches=()):
        with mock.patch("bridge.settled_state", return_value=(img, grid, [None, None, None])), \
             mock.patch("bridge.stable_state", return_value=(img, grid, [None, None, None])), \
             mock.patch("bridge.in_game", return_value=True), \
             mock.patch.multiple("bridge", hard_restart_app=mock.DEFAULT, screenshot=mock.DEFAULT), \
             mock.patch("bridge.press_back") as press_back, \
             mock.patch("bridge.read_score", return_value=None), \
             mock.patch("bridge.annotate"), \
             mock.patch("PIL.Image.Image.save"), \
             mock.patch("bridge.os.makedirs"), \
             mock.patch("bridge.time.sleep"), \
             mock.patch("builtins.open", mock.mock_open()) as m_open:
            bridge.main(max_moves, policy_spec="greedy")
        entries = [json.loads(c.args[0]) for c in m_open().write.call_args_list]
        return entries, press_back


class TestMainStopsOnBrightAdWindow(unittest.TestCase):
    """#154/#235: jasna reklama → „wstecz" i dalsza gra; stała reklama kończy kawałek
    bezpiecznikiem postępu w skończonej liczbie kroków."""

    def test_static_bright_ad_presses_back_then_stops_by_safeguard(self):
        bright_ad_img = _load("44a8ea2", "p2b_ad_before.png")
        full_grid = [[1] * 8 for _ in range(8)]
        entries, press_back = _StaticScreenHarness().run(bright_ad_img, full_grid)
        k = bridge.PROGRESS_SAFEGUARD_TRIES
        self.assertEqual(len(entries), 2 * k)  # #318: K wpisów, twardy restart, K wpisów
        self.assertEqual([e["okno"] for e in entries].count("restart_twardy"), 1)
        self.assertEqual(entries[k - 1]["okno_przed_restartem"], "reklama_jasna")
        self.assertEqual(entries[-1]["end"], "okno: petla_bez_postepu")
        self.assertEqual(press_back.call_count, 2 * k)

    def test_bright_ad_closed_by_one_back_lets_game_continue(self):
        bright_ad_img = _load("44a8ea2", "p2b_ad_before.png")
        after_back = _load("7e25817", "chunk6_manual_ad_after_back.png")
        empty_grid = [[0] * 8 for _ in range(8)]
        states = iter([(bright_ad_img, empty_grid, [None] * 3)])

        def fake_stable_state(tries=6):
            return after_back, empty_grid, [None] * 3

        with mock.patch("bridge.settled_state", side_effect=lambda: next(states)), \
             mock.patch("bridge.stable_state", side_effect=fake_stable_state), \
             mock.patch("bridge.in_game", return_value=True), \
             mock.patch("bridge.press_back") as press_back, \
             mock.patch("bridge.read_score", return_value=None), \
             mock.patch("bridge.stable_score", return_value=(100, [100, 100])), \
             mock.patch("bridge.tap_play"), \
             mock.patch("bridge.annotate"), \
             mock.patch("PIL.Image.Image.save"), \
             mock.patch("bridge.os.makedirs"), \
             mock.patch("bridge.time.sleep"), \
             mock.patch("builtins.open", mock.mock_open()) as m_open:
            bridge.main(1, policy_spec="greedy")
        entries = [json.loads(c.args[0]) for c in m_open().write.call_args_list]
        press_back.assert_called_once()
        self.assertEqual(entries[0]["okno"], "reklama_jasna")
        self.assertNotIn("end", entries[0])
        self.assertTrue(entries[1].get("koniec_partii"))  # po „wstecz" widać koniec partii


class TestEmptyBoardSeriesPressesBack(unittest.TestCase):
    """#235: seria `plansza_pusta_przejsciowo` z rzędu (chunk6: 6 razy) → jeden „wstecz"."""

    def _run_static(self):
        # Klatka nie jest reklamą ani oknem, odczyt: pusta plansza i pusta taca, brak ruchów.
        img = _load("495cd91", "loop_after_back.png")
        empty_grid = [[0] * 8 for _ in range(8)]
        return _StaticScreenHarness().run(img, empty_grid)

    def test_series_triggers_back_and_static_screen_ends_by_safeguard(self):
        entries, press_back = self._run_static()
        self.assertEqual(len(entries), 2 * bridge.PROGRESS_SAFEGUARD_TRIES)  # #318: twardy restart w środku
        self.assertEqual(entries[-1]["end"], "okno: petla_bez_postepu")
        k = bridge.EMPTY_BOARD_BACK_TRIES
        okna = [e["okno"] for e in entries]
        self.assertEqual(okna[:k], ["plansza_pusta_przejsciowo"] * (k - 1) + ["plansza_pusta_wstecz"])
        self.assertEqual(okna[bridge.PROGRESS_SAFEGUARD_TRIES - 1], "restart_twardy")
        self.assertEqual(press_back.call_count, 2 * bridge.PROGRESS_SAFEGUARD_TRIES // k)


class TestChunk10WindowSequenceIsNotALoop(unittest.TestCase):
    """#235: sekwencja okien z chunk10 (7e25817) — 6 wpisów, po niej grywalna plansza —
    nie kończy się `petla_bez_postepu`; 30 naprzemiennych okien bez ruchu nadal tak."""

    WINDOWS = ("reklama_statyczna", "reklama_statyczna", "ustawienia_wstecz", "koniec_partii",
               "ustawienia_wstecz", "menu_glowne")

    def _run(self, windows, max_moves):
        game_img = _load("0d96333", "120_state.png")
        neutral = _load("495cd91", "loop_after_back.png")
        empty_grid = [[0] * 8 for _ in range(8)]
        board = Board()
        board.grid = [row[:] for row in empty_grid]
        board.place_piece(BEAM2, 0, 0)
        playable = (game_img, board.grid, [([[1, 1]], (20, 460)), None, None])
        queue = list(windows)
        current = [queue.pop(0) if queue else None]

        def state():
            if current[0] is None:
                return playable
            return neutral, empty_grid, [None] * 3

        def next_state(tries=6):
            current[0] = queue.pop(0) if queue else None
            return state()

        def is_(name):
            return lambda img: img is neutral and current[0] == name

        with mock.patch("bridge.settled_state", side_effect=state), \
             mock.patch("bridge.stable_state", side_effect=next_state), \
             mock.patch("bridge.in_game", return_value=True), \
             mock.patch("bridge.is_exit_dialog_screen", side_effect=is_("dialog_wyjscia")), \
             mock.patch("bridge.is_settings_screen", side_effect=is_("ustawienia_wstecz")), \
             mock.patch("bridge.is_main_menu_screen", side_effect=is_("menu_glowne")), \
             mock.patch("bridge.is_static_ad_screen", side_effect=is_("reklama_statyczna")), \
             mock.patch("bridge.is_bright_ad_screen", return_value=False), \
             mock.patch("bridge.is_game_over_screen", side_effect=is_("koniec_partii")), \
             mock.patch("bridge.stable_score", return_value=(100, [100, 100])), \
             mock.patch.multiple("bridge", press_back=mock.DEFAULT, tap_classic=mock.DEFAULT, tap_play=mock.DEFAULT,
                                 hard_restart_app=mock.DEFAULT, screenshot=mock.DEFAULT), \
             mock.patch("bridge.read_score", return_value=None), \
             mock.patch("bridge.drag", return_value=({"finger": [0, 0]}, game_img)), \
             mock.patch("bridge.annotate"), \
             mock.patch("PIL.Image.Image.save"), \
             mock.patch("bridge.os.makedirs"), \
             mock.patch("bridge.time.sleep"), \
             mock.patch("builtins.open", mock.mock_open()) as m_open:
            bridge.main(max_moves, policy_spec="greedy")
        return [json.loads(c.args[0]) for c in m_open().write.call_args_list]

    def test_chunk10_sequence_matches_log_and_passes(self):
        logged = []
        with open(os.path.join(RUNS, "7e25817", "chunk10_moves.jsonl")) as f:
            for line in f:
                e = json.loads(line)
                if "move" not in e:
                    logged.append("koniec_partii" if e.get("koniec_partii") else e["okno"])
        self.assertEqual(tuple(logged), self.WINDOWS)
        entries = self._run(self.WINDOWS, max_moves=1)
        self.assertEqual(len(entries), len(self.WINDOWS) + 1)  # sześć okien i ruch
        self.assertFalse(any("end" in e for e in entries))
        self.assertIn("move", entries[-1])

    def test_thirty_alternating_windows_still_end_as_loop(self):
        windows = ["ustawienia_wstecz", "reklama_statyczna"] * 15
        entries = self._run(windows, max_moves=1)
        self.assertEqual(entries[-1]["end"], "okno: petla_bez_postepu")
        self.assertTrue(all("move" not in e for e in entries))
        self.assertLess(len(entries), 30)


S2 = os.path.join(ROOT, "docs", "seria", "s2")
SPLASH_FRAMES = [("partia-1", "kawalek_2", "058_end.png"), ("partia-4", "kawalek_2", "046_end.png"),
                 ("partia-9", "kawalek_2", "063_end.png"), ("partia-10", "kawalek_2", "060_end.png")]
VIDEO_AD_FRAME = ("partia-2", "kawalek_4", "061_state.png")


def _load_s2(*parts):
    # jak `bridge.screenshot()`: int, nie uint8
    return np.asarray(Image.open(os.path.join(S2, *parts)).convert("RGB")).astype(int)


def _run_main_on(first_img, after_img, patches):
    empty = [[0] * 8 for _ in range(8)]
    board = Board()
    board.grid = [row[:] for row in empty]
    board.place_piece(BEAM2, 0, 0)
    slots = [([[1, 1]], (20, 460)), None, None]
    with mock.patch("bridge.settled_state", return_value=(first_img, empty, [None, None, None])), \
         mock.patch("bridge.stable_state", return_value=(after_img, board.grid, slots)), \
         mock.patch("bridge.in_game", return_value=True), \
         mock.patch("bridge.read_score", return_value=None), \
         mock.patch("bridge.drag", return_value=({"finger": [0, 0]}, after_img)), \
         mock.patch("bridge.annotate"), mock.patch("PIL.Image.Image.save"), \
         mock.patch("bridge.os.makedirs"), mock.patch("bridge.time.sleep"), \
         mock.patch("builtins.open", mock.mock_open()) as m_open:
        started = [mock.patch(*a, **k).start() for a, k in patches]
        try:
            bridge.main(1, policy_spec="greedy", seria=True)
        finally:
            mock.patch.stopall()
    return [json.loads(c.args[0]) for c in m_open().write.call_args_list], started


class TestSplashScreen(unittest.TestCase):
    """#304: ekran startowy apki po restarcie nie jest końcem partii."""

    def test_splash_is_not_game_over(self):
        for parts in SPLASH_FRAMES:
            with self.subTest(parts=parts):
                img = _load_s2(*parts)
                self.assertTrue(bridge.is_splash_screen(img))
                self.assertFalse(bridge.is_game_over_screen(img))
                self.assertFalse(bridge.is_settings_screen(img))
                self.assertFalse(bridge.is_video_ad_screen(img))

    def test_real_game_over_screens_stay_game_over(self):
        for img in (_load_s2("partia-3", "kawalek_3", "092_end.png"), _load("c1819ed", "chunk15_after_back.png")):
            self.assertTrue(bridge.is_game_over_screen(img))
            self.assertFalse(bridge.is_splash_screen(img))

    def test_live_board_s3_is_not_splash(self):
        # #311: czerwone/fioletowe klocki w wierszach 0-1 nie sa logiem
        s3 = os.path.join(ROOT, "docs", "seria", "s3")
        for partia, ns in (("partia-1", ("134_state", "135_state", "final")),
                           ("partia-2", ("090_state", "091_state", "final")),
                           ("partia-10", ("027_state", "028_state", "final"))):
            for n in ns:
                with self.subTest(partia=partia, n=n):
                    img = np.asarray(Image.open(os.path.join(s3, partia, "kawalek_1", n + ".png")).convert("RGB")).astype(int)
                    self.assertFalse(bridge.is_splash_screen(img))

    def test_live_board_s3_partia8_is_not_splash_nor_home(self):
        # #314: falszywy ekran_startowy na zywej planszy (granat, czerwone klocki w wierszach 0-1)
        d = os.path.join(ROOT, "docs", "seria", "s3", "partia-8", "kawalek_3")
        for n in ("007_state", "008_state", "009_state"):
            with self.subTest(n=n):
                img = np.asarray(Image.open(os.path.join(d, n + ".png")).convert("RGB")).astype(int)
                self.assertFalse(bridge.is_splash_screen(img))
                self.assertFalse(bridge.is_home_screen(img))

    def test_light_sky_board_is_not_home_screen(self):
        # #311: jasne niebo skorki w pasku stanu to nie launcher
        img = _load_s2("partia-2", "kawalek_2", "100_state.png")
        self.assertFalse(bridge.is_home_screen(img))

    def test_no_window_detector_fires_on_live_boards(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import detektory_na_planszy as d
        self.assertEqual(d.main([]), 0)

    def test_main_waits_and_logs_ekran_startowy_not_koniec_partii(self):
        splash = _load_s2(*SPLASH_FRAMES[0])
        board_img = _load("0d96333", "120_state.png")
        entries, _ = _run_main_on(splash, board_img, [])
        self.assertEqual(entries[0]["okno"], "ekran_startowy")
        self.assertFalse(any(e.get("koniec_partii") for e in entries))
        self.assertNotIn("end", entries[0])


class TestVideoAdScreen(unittest.TestCase):
    """#304: reklama wideo z „Skip" nie jest modalem Ustawień."""

    def test_video_ad_detected_and_not_settings(self):
        img = _load_s2(*VIDEO_AD_FRAME)
        self.assertTrue(bridge.is_video_ad_screen(img))

    def test_real_screens_not_video_ad(self):
        for img in (_load("44a8ea2", "p1a_settings.png"), _load("44a8ea2", "p2e_stuck_settings_before.png"),
                    _load("0d96333", "120_state.png"), _load("0d96333", "121_end.png")):
            self.assertFalse(bridge.is_video_ad_screen(img))
        self.assertTrue(bridge.is_settings_screen(_load("44a8ea2", "p1a_settings.png")))

    def test_main_taps_skip_and_logs_reklama_wideo(self):
        ad = _load_s2(*VIDEO_AD_FRAME)
        board_img = _load("0d96333", "120_state.png")
        entries, started = _run_main_on(ad, board_img, [(("bridge.tap_skip",), {}), (("bridge.press_back",), {})])
        tap_skip, press_back = started
        tap_skip.assert_called_once()
        press_back.assert_not_called()
        self.assertEqual(entries[0]["okno"], "reklama_wideo")


if __name__ == "__main__":
    unittest.main()
