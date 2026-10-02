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
from board import Board
from pieces import PIECE_POOL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = os.path.join(ROOT, "bridge", "runs")

BEAM2 = next(p for p in PIECE_POOL if p.shape == [[1, 1]])


def _load(*parts):
    return np.asarray(Image.open(os.path.join(RUNS, *parts)).convert("RGB")).astype(int)



def setUpModule():
    # #351: atrapy mostu nie mają zrzutów do ponownego odczytu po `ok: false` — pętlę wyłączamy limitem 0
    p = mock.patch("bridge.PONOWNY_ODCZYT_LIMIT", 0)
    p.start()
    unittest.addModuleCleanup(p.stop)

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
    tło czytane jako plansza pełna) — teraz rozpoznaje jawnie `"koniec_partii": True` z wynikiem
    końcowym odczytanym z ekranu (#169), stuka „Play" i gra dalej (#173). Ekran końca partii nie
    znika w tym teście (atrapa `settled_state` zawsze go zwraca), więc bezpiecznik postępu
    (#163) kończy pętlę po `PROGRESS_SAFEGUARD_TRIES` wpisach zamiast kręcić się bez końca."""

    def test_logs_koniec_partii_with_score_and_taps_play(self):
        gameover_img = _load("1402cff", "chunk7_010_gameover_screen.png")
        empty_grid = [[0] * 8 for _ in range(8)]

        def fake_settled_state():
            return gameover_img, empty_grid, [None, None, None]

        with mock.patch("bridge.settled_state", side_effect=fake_settled_state), \
             mock.patch("bridge.in_game", return_value=True), \
             mock.patch("bridge.screenshot", return_value=gameover_img), \
             mock.patch("bridge.read_score", return_value=8532), \
             mock.patch("bridge.tap_play") as tap_play, \
             mock.patch("bridge.annotate"), \
             mock.patch("PIL.Image.Image.save"), \
             mock.patch("bridge.os.makedirs"), \
             mock.patch("builtins.open", mock.mock_open()) as m_open:
            best_streak = bridge.main(50, policy_spec="greedy")

        handle = m_open()
        entries = [json.loads(c.args[0]) for c in handle.write.call_args_list]
        self.assertTrue(entries[0]["koniec_partii"])
        self.assertEqual(entries[0]["wynik_koncowy"], 8532)
        self.assertEqual(entries[0]["wynik_koncowy_odczyty"], [8532, 8532])
        self.assertEqual(entries[0]["zrzut_konca"], "000_end.png")
        self.assertEqual(entries[0]["nowa_partia"], 2)
        self.assertTrue(tap_play.called)
        self.assertEqual(entries[-1]["end"], "okno: petla_bez_postepu")
        self.assertEqual(best_streak, 0)


class TestIsMainMenuScreen(unittest.TestCase):
    """#204: ekran głównego menu apki („Block Blast Adventure Master", kafelki
    Adventure/Classic/More Games) — most go mylił z modalem Ustawień (`is_settings_screen`) na
    innej, nieutrwalonej klatce tego samego epizodu (sesja `4a1796f`, kawałek 4), a po
    `press_back` i `restart_app` wciąż lądował na tym samym menu."""

    def test_positive_on_main_menu_screenshot(self):
        self.assertTrue(bridge.is_main_menu_screen(_load("4a1796f", "chunk4_003_menu_end.png")))

    def test_negative_on_settings_and_board_and_gameover(self):
        cases = [
            ("44a8ea2", "p1a_settings.png"),
            ("44a8ea2", "p1b_settings.png"),
            ("44a8ea2", "p1a_before.png"),
            ("0d96333", "120_state.png"),
            ("1402cff", "chunk7_010_gameover_screen.png"),
            ("c1819ed", "chunk15_after_back.png"),
            ("1402cff", "chunk2_001_settings_falsepositive_home.png"),
            ("0d96333", "121_end.png"),
            ("4a1796f", "chunk4_after_recovery.png"),
        ]
        for run, name in cases:
            with self.subTest(run=run, name=name):
                self.assertFalse(bridge.is_main_menu_screen(_load(run, name)))

    def test_settings_screen_is_false_on_main_menu(self):
        self.assertFalse(bridge.is_settings_screen(_load("4a1796f", "chunk4_003_menu_end.png")))


class TestMainTapsClassicInMainMenu(unittest.TestCase):
    """#204: zamiast „wstecz" (jak w Ustawieniach), most stuka kafelek „Classic" i loguje wpis
    okna `menu_glowne`, żeby kontynuować partię w toku."""

    def test_taps_classic_and_logs_menu_glowne(self):
        menu_img = _load("4a1796f", "chunk4_003_menu_end.png")
        board_img = _load("0d96333", "120_state.png")
        empty_grid = [[0] * 8 for _ in range(8)]

        board = Board()
        board.grid = [row[:] for row in empty_grid]
        board.place_piece(BEAM2, 0, 0)
        playable_grid = board.grid
        playable_slot = ([[1, 1]], (20, 460))
        playable_slots = [playable_slot, None, None]

        def fake_settled_state():
            return menu_img, empty_grid, [None, None, None]

        def fake_stable_state(tries=6):
            return board_img, playable_grid, playable_slots

        with mock.patch("bridge.settled_state", side_effect=fake_settled_state), \
             mock.patch("bridge.stable_state", side_effect=fake_stable_state), \
             mock.patch("bridge.in_game", return_value=True), \
             mock.patch("bridge.tap_classic") as tap_classic, \
             mock.patch("bridge.press_back") as press_back, \
             mock.patch("bridge.read_score", return_value=None), \
             mock.patch("bridge.drag", return_value=({"finger": [0, 0]}, board_img)), \
             mock.patch("bridge.annotate"), \
             mock.patch("PIL.Image.Image.save"), \
             mock.patch("bridge.os.makedirs"), \
             mock.patch("builtins.open", mock.mock_open()) as m_open:
            bridge.main(1, policy_spec="greedy")

        tap_classic.assert_called_once()
        press_back.assert_not_called()
        handle = m_open()
        entries = [json.loads(c.args[0]) for c in handle.write.call_args_list]
        self.assertEqual(entries[0]["okno"], "menu_glowne")


class TestRestartAppTapsClassicWhenLandingInMenu(unittest.TestCase):
    """#204: start apki po restarcie czasem ląduje w menu głównym zamiast w partii w toku
    (sesja `4a1796f`, kawałek 4) — `restart_app` ma to rozpoznać i stuknąć „Classic" zanim
    zwróci sukces."""

    def test_taps_classic_after_restart_lands_on_menu(self):
        menu_img = _load("4a1796f", "chunk4_003_menu_end.png")
        with mock.patch("bridge.time.sleep", lambda *_: None), \
             mock.patch("bridge.adb"), \
             mock.patch("bridge.in_game", side_effect=[True]), \
             mock.patch("bridge.screenshot", return_value=menu_img), \
             mock.patch("bridge.touch") as touch:
            self.assertTrue(bridge.restart_app(tries=3, wait=0))
        touch.assert_any_call("DOWN", *bridge.CLASSIC_BUTTON)
        touch.assert_any_call("UP", *bridge.CLASSIC_BUTTON)

    def test_does_not_tap_classic_when_landing_in_game(self):
        board_img = _load("0d96333", "120_state.png")
        with mock.patch("bridge.time.sleep", lambda *_: None), \
             mock.patch("bridge.adb"), \
             mock.patch("bridge.in_game", side_effect=[True]), \
             mock.patch("bridge.screenshot", return_value=board_img), \
             mock.patch("bridge.touch") as touch:
            self.assertTrue(bridge.restart_app(tries=3, wait=0))
        touch.assert_not_called()


class TestIsStaticAdScreen(unittest.TestCase):
    """#173: reklama statyczna tekstowa (biało-czarna, np. BlackRock) — ani `is_ad_screen`
    (próg ciemności), ani `is_bright_ad_screen` (liczba kolorów) jej nie łapią."""

    def test_positive_on_static_ad(self):
        self.assertTrue(bridge.is_static_ad_screen(_load("c1819ed", "chunk15_unknown.png")))

    def test_negative_on_all_other_screenshots(self):
        checked = 0
        for run in os.listdir(RUNS):
            run_dir = os.path.join(RUNS, run)
            if not os.path.isdir(run_dir):
                continue
            for name in os.listdir(run_dir):
                if not name.endswith(".png") or (run, name) == ("c1819ed", "chunk15_unknown.png"):
                    continue
                img = _load(run, name)
                if img.shape[:2] != (640, 320):
                    continue
                checked += 1
                with self.subTest(run=run, name=name):
                    self.assertFalse(bridge.is_static_ad_screen(img))
        self.assertGreater(checked, 700)

    def test_not_confused_with_known_ads(self):
        img = _load("c1819ed", "chunk15_unknown.png")
        self.assertFalse(bridge.is_ad_screen(img))
        self.assertFalse(bridge.is_bright_ad_screen(img))


class TestMainClosesStaticAdWithBack(unittest.TestCase):
    """`main()` zamyka `reklama_statyczna` klawiszem „wstecz" (#173), tak jak modal Ustawień."""

    def test_press_back_and_logs_okno(self):
        ad_img = _load("c1819ed", "chunk15_unknown.png")
        gameover_img = _load("1402cff", "chunk7_010_gameover_screen.png")
        empty_grid = [[0] * 8 for _ in range(8)]
        frames = [ad_img]

        def fake_settled_state():
            return frames.pop(0) if frames else gameover_img, empty_grid, [None, None, None]

        with mock.patch("bridge.settled_state", side_effect=fake_settled_state), \
             mock.patch("bridge.in_game", return_value=True), \
             mock.patch("bridge.screenshot", return_value=gameover_img), \
             mock.patch("bridge.press_back") as press_back, \
             mock.patch("bridge.tap_play"), \
             mock.patch("bridge.read_score", return_value=None), \
             mock.patch("bridge.annotate"), \
             mock.patch("PIL.Image.Image.save"), \
             mock.patch("bridge.os.makedirs"), \
             mock.patch("builtins.open", mock.mock_open()) as m_open:
            bridge.main(1, policy_spec="greedy")

        press_back.assert_called_once()
        handle = m_open()
        entries = [json.loads(c.args[0]) for c in handle.write.call_args_list]
        self.assertEqual(entries[0]["okno"], "reklama_statyczna")


class TestIsGameOverScreenBlueVariant(unittest.TestCase):
    """#173: wariant „Your Best is Next" na niebieskim tle — test fioletu daje 0,0 na tym
    zrzucie, więc `is_game_over_screen` rozpoznaje go po osobnym teście koloru niebieskiego."""

    def test_positive_on_blue_variant(self):
        self.assertTrue(bridge.is_game_over_screen(_load("c1819ed", "chunk15_after_back.png")))

    def test_purple_variants_still_recognized(self):
        for run, name in [("1402cff", "chunk7_010_gameover_screen.png"),
                           ("44a8ea2", "p2_ad_video_closed.png"),
                           ("c1819ed", "chunk9_gameover.png")]:
            with self.subTest(run=run, name=name):
                self.assertTrue(bridge.is_game_over_screen(_load(run, name)))

    def test_score_box_matches_blue_variant(self):
        img = _load("c1819ed", "chunk15_after_back.png")
        box = bridge.game_over_score_box(img)
        self.assertEqual(box, bridge.GAME_OVER_SCORE_BOX_BLUE)
        x0, y0, x1, y1 = box
        crop = img[y0:y1, x0:x1]
        self.assertGreater((crop.min(axis=-1) > 200).mean(), 0.05)

    def test_purple_variant_still_uses_purple_box(self):
        img = _load("c1819ed", "chunk9_gameover.png")
        self.assertEqual(bridge.game_over_score_box(img), bridge.GAME_OVER_SCORE_BOX)


if __name__ == "__main__":
    unittest.main()
