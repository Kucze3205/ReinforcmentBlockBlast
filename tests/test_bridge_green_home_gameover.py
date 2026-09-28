"""
Testy dla #169: trzy rozjazdy znalezione przez verifier na żywym moście w #164
(materiał `bridge/runs/1402cff/`, pełny opis w `pomiar.json`).

1. `is_block` nie widział ciemnozielonego klocka (rozpiętość/jasność kanałów poniżej progu),
   więc `read_board`/`read_tray` czytały pełną tackę jako pustą (kawałki 9-11 z #164).
2. `is_settings_screen` łapał ciemną tapetę ekranu głównego Androida po padzie apki jako modal
   Ustawień, więc most bił „wstecz" zamiast wywołać `restart_app` (kawałek 2 z #164).
3. Ekran końca partii „Can you Top that?"/„Beat Your Best Again!" z przyciskiem Play nie był
   rozpoznawany jako osobny koniec partii (kawałek 7 z #164).
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(ROOT, "bridge", "runs")


def _load(*parts):
    return np.asarray(Image.open(os.path.join(RUNS, *parts)).convert("RGB")).astype(int)


class TestIsBlockDarkGreen(unittest.TestCase):
    """#169 punkt 1: `chunk9_stuck_low_saturation_green.png` — plansza naprawdę pusta, tacka
    z 3 ciemnozielonymi klockami (RGB (74,142,66), (74,146,66), (41,97,41): rozpiętość
    kanałów 56-80, szczyt 97-146 — poniżej starego progu rozpiętość>=100 i szczyt>=150)."""

    def test_tray_has_three_pieces_on_stuck_frame(self):
        img = _load("1402cff", "chunk9_stuck_low_saturation_green.png")
        tray = bridge.read_tray(img)
        self.assertTrue(all(t is not None for t in tray))

    def test_board_is_empty_on_stuck_frame(self):
        img = _load("1402cff", "chunk9_stuck_low_saturation_green.png")
        grid = bridge.read_board(img)
        self.assertEqual(sum(sum(row) for row in grid), 0)

    def test_tray_has_pieces_on_other_stuck_frames(self):
        """Ten sam odcień zielonego pojawił się jeszcze dwa razy z rzędu w tej samej partii
        (kawałki 10 i 11 z #164) — sprawdzone na obu zrzutach."""
        for name in ("chunk10_stuck.png", "chunk11_stuck.png"):
            with self.subTest(name=name):
                img = _load("1402cff", name)
                tray = bridge.read_tray(img)
                self.assertTrue(any(t is not None for t in tray))

    def test_board_gets_the_manually_placed_piece(self):
        """Po ręcznym odblokowaniu (#164) most postawił klocek — `read_board` musi go teraz
        widzieć (przed poprawką ten sam ciemnozielony klocek na planszy też znikał)."""
        img = _load("1402cff", "chunk9_after_manual_unstick.png")
        grid = bridge.read_board(img)
        self.assertGreater(sum(sum(row) for row in grid), 0)


class TestIsBlockNoRegressionOnKnownBackgrounds(unittest.TestCase):
    """Rozróżnienie klocka od tła planszy: dominacja kanału G (silnie ponad R i B) łapie tylko
    ten konkretny zielony, nie tła innych skórek w tym samym paśmie rozpiętości/jasności —
    bordowe tło `bridge/runs/0d96333/120_state.png` ((132,61,74), rozpiętość 71, szczyt 132)
    i różowe tło tacki tamże ((255,166,181), rozpiętość 89, szczyt 255) leżą 5-90 jednostek od
    progów `is_block`, ale nie mają G jako kanału dominującego.

    Zweryfikowane też ilościowo (nie tylko tym testem) zgodnością 1:1 `read_board`/`read_tray`
    z zapisanym stanem gry w `bridge/runs/0d96333/moves.jsonl` na klatkach n=0, 60, 120 (poniżej)
    oraz na `bridge/runs/44a8ea2/p1{a,b,c}_before.png` (identyczne siatki jak przed poprawką,
    sprawdzone ręcznie przy kalibracji) — łącznie ok. 250 zrzutów z `bridge/runs/{0d96333,
    44a8ea2,495cd91,1402cff,1bd38fa}` bez ani jednego fałszywego trafienia tła jako klocka.
    """

    def _assert_matches_recorded_state(self, n):
        with open(os.path.join(RUNS, "0d96333", "moves.jsonl")) as fh:
            entry = next(json.loads(line) for line in fh if json.loads(line).get("n") == n)
        img = _load("0d96333", f"{n:03d}_state.png")
        self.assertEqual(bridge.read_board(img), entry["board"])
        tray = bridge.read_tray(img)
        self.assertEqual([t[0] if t else None for t in tray], entry["tray"])

    def test_matches_recorded_state_n0(self):
        self._assert_matches_recorded_state(0)

    def test_matches_recorded_state_n60(self):
        self._assert_matches_recorded_state(60)

    def test_matches_recorded_state_n120(self):
        self._assert_matches_recorded_state(120)


class TestIsHomeScreen(unittest.TestCase):
    """#169 punkt 2: ekran główny Androida po padzie apki ma pasek stanu systemu (zegar,
    ikony wifi/baterii) w górnych 24 px, którego gra nigdy nie pokazuje."""

    def test_positive_on_home_screen_after_crash(self):
        for name in ("chunk2_001_settings_falsepositive_home.png", "chunk2_final.png"):
            with self.subTest(name=name):
                self.assertTrue(bridge.is_home_screen(_load("1402cff", name)))

    def test_positive_on_home_screen_from_other_run(self):
        """Ten sam ekran domowy po innym padzie, zmierzony w #129."""
        self.assertTrue(bridge.is_home_screen(_load("1bd38fa", "111_state.png")))

    def test_negative_on_real_board_and_settings(self):
        for run, name in [("44a8ea2", "p1a_before.png"), ("44a8ea2", "p1a_settings.png"),
                           ("495cd91", "loop_after_back.png"), ("495cd91", "before_retry.png"),
                           ("1402cff", "chunk2_000_state.png")]:
            with self.subTest(run=run, name=name):
                self.assertFalse(bridge.is_home_screen(_load(run, name)))


class TestIsSettingsScreenExcludesHomeScreen(unittest.TestCase):
    """`is_settings_screen` (próg ciemności 0.44-0.85) łapał tę samą ciemną tapetę ekranu
    domowego (0.44-0.68, w przedziale) — wyklucza się teraz jawnie przez `is_home_screen`,
    tak jak dialog wyjścia wyklucza się przez `is_exit_dialog_screen` (#163)."""

    def test_settings_screen_is_false_on_home_screen_false_positive(self):
        for name in ("chunk2_001_settings_falsepositive_home.png", "chunk2_final.png"):
            with self.subTest(name=name):
                self.assertFalse(bridge.is_settings_screen(_load("1402cff", name)))

    def test_settings_screen_still_true_on_real_settings_modal(self):
        for name in ("p1a_settings.png", "p1b_settings.png", "p1c_settings.png"):
            with self.subTest(name=name):
                self.assertTrue(bridge.is_settings_screen(_load("44a8ea2", name)))


class TestMainRestartsInsteadOfPressingBackOnHomeScreen(unittest.TestCase):
    """Most bił „wstecz" w launcher zamiast wywołać `restart_app` (#129/#169): teraz
    `is_settings_screen` zwraca False na tej klatce, więc pętla dochodzi do sprawdzenia
    `in_game()` i restartuje apkę zamiast kręcić się w oknie Ustawień."""

    def test_restarts_app_on_home_screen_after_crash(self):
        home_img = _load("1402cff", "chunk2_001_settings_falsepositive_home.png")
        empty_grid = [[0] * 8 for _ in range(8)]

        def fake_settled_state():
            return home_img, empty_grid, [None, None, None]

        with mock.patch("bridge.settled_state", side_effect=fake_settled_state), \
             mock.patch("bridge.in_game", return_value=False), \
             mock.patch("bridge.restart_app", return_value=False) as restart_app, \
             mock.patch("bridge.press_back") as press_back, \
             mock.patch("bridge.read_score", return_value=None), \
             mock.patch("bridge.annotate"), \
             mock.patch("PIL.Image.Image.save"), \
             mock.patch("bridge.os.makedirs"), \
             mock.patch("builtins.open", mock.mock_open()):
            bridge.main(1, policy_spec="greedy")

        restart_app.assert_called_once()
        press_back.assert_not_called()


class TestIsGameOverScreen(unittest.TestCase):
    """#169 punkt 3: ekran „Can you Top that?"/„Beat Your Best Again!" z przyciskiem Play —
    tło to fioletowo-purpurowy gradient (kanał B > R > G z wyraźnym marginesem), zmierzone na
    dwóch niezależnych przebiegach z różnym wynikiem i różnym tekstem nagłówka."""

    def test_positive_on_gameover_screenshots(self):
        for run, name in [("1402cff", "chunk7_010_gameover_screen.png"),
                           ("44a8ea2", "p2_ad_video_closed.png"),
                           ("44a8ea2", "p2_after_tap_score.png"),
                           ("44a8ea2", "p2b_ad_closed_x.png")]:
            with self.subTest(run=run, name=name):
                self.assertTrue(bridge.is_game_over_screen(_load(run, name)))

    def test_negative_on_real_board_and_other_windows(self):
        cases = [
            ("1402cff", "chunk7_009_board_near_full.png"),
            ("1402cff", "chunk7_newgame_started.png"),
            ("44a8ea2", "p1a_before.png"),
            ("44a8ea2", "p1a_settings.png"),
            ("495cd91", "loop2_after_no.png"),
            ("0d96333", "121_end.png"),
            ("44a8ea2", "p2b_ad_before.png"),
            ("1402cff", "chunk2_001_settings_falsepositive_home.png"),
        ]
        for run, name in cases:
            with self.subTest(run=run, name=name):
                self.assertFalse(bridge.is_game_over_screen(_load(run, name)))

    def test_not_confused_with_ad_or_settings(self):
        img = _load("1402cff", "chunk7_010_gameover_screen.png")
        self.assertFalse(bridge.is_ad_screen(img))
        self.assertFalse(bridge.is_bright_ad_screen(img))
        self.assertFalse(bridge.is_settings_screen(img))
        self.assertFalse(bridge.is_exit_dialog_screen(img))


class TestMainEndsOnGameOverScreen(unittest.TestCase):
    """Most kończył kawałek poprawnie ale przez przypadek („brak legalnego ruchu wg odczytu",
    tło czytane jako plansza pełna) — teraz kończy jawnie z `"end": "koniec_partii"` i wynikiem
    końcowym odczytanym z ekranu (#169). Most nie gra dziś więcej niż jedną partię w wywołaniu,
    więc rozpoznanie kończy pętlę bez startowania nowej partii."""

    def test_logs_koniec_partii_with_score(self):
        gameover_img = _load("1402cff", "chunk7_010_gameover_screen.png")
        empty_grid = [[0] * 8 for _ in range(8)]

        def fake_settled_state():
            return gameover_img, empty_grid, [None, None, None]

        with mock.patch("bridge.settled_state", side_effect=fake_settled_state), \
             mock.patch("bridge.in_game", return_value=True), \
             mock.patch("bridge.read_score", return_value=8532), \
             mock.patch("bridge.annotate"), \
             mock.patch("PIL.Image.Image.save"), \
             mock.patch("bridge.os.makedirs"), \
             mock.patch("builtins.open", mock.mock_open()) as m_open:
            best_streak = bridge.main(5, policy_spec="greedy")

        handle = m_open()
        entries = [json.loads(c.args[0]) for c in handle.write.call_args_list]
        self.assertEqual(entries[-1]["end"], "koniec_partii")
        self.assertEqual(entries[-1]["wynik_koncowy"], 8532)
        self.assertEqual(best_streak, 0)


if __name__ == "__main__":
    unittest.main()
