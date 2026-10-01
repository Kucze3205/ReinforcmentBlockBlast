"""
Testy dla #294: skórki i nakładki apki 10.7.5, które przerywały partie serii s1 (`docs/seria/s1/`).

Zrzuty to klatki z tej serii. Wartości (plansza, tacka, licznik) to odczyt wzrokowy ze zrzutu — `final.png`
ma narysowane kropki adnotacji poza środkami pól, więc czytniki widzą go tak samo jak `NNN_state.png`.

1. Skórka teal nie jest menu głównym (`is_main_menu_screen`).
2. Pusta tacka przy niepustej planszy to okno przejściowe, nie koniec partii.
3. Nakładka „Better than N%!" z pucharem to okno przejściowe.
4. `read_board`/`read_tray` na każdej skórce: teal, różowa, beżowa, domyślna, fioletowa.
5. `read_hud_score` na każdej skórce; zły odczyt jest gorszy niż brak.
"""
import glob
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
S1 = os.path.join(ROOT, "docs", "seria", "s1")
RUNS = os.path.join(ROOT, "bridge", "runs")


def s1(*parts):
    return np.asarray(Image.open(os.path.join(S1, *parts)).convert("RGB")).astype(int)


def rows(text):
    return [[int(ch == "#") for ch in line] for line in text.split()]


def shapes(tray):
    return [None if s is None else s[0] for s in tray]


TEAL = ("partia-4", "kawalek_1", "036_state.png")
TEAL_6 = ("partia-6", "kawalek_1", "148_state.png")
PINK = ("partia-2", "kawalek_1", "final.png")
PINK_8 = ("partia-8", "kawalek_2", "final.png")
TAN = ("partia-2", "kawalek_2", "054_state.png")
DEFAULT = ("partia-9", "kawalek_1", "044_state.png")
PURPLE = ("partia-2", "kawalek_2", "056_state.png")
TROPHY = ("partia-10", "kawalek_1", "048_state.png")
MENU = ("4a1796f", "chunk4_003_menu_end.png")


class TestMainMenuVsTealSkin(unittest.TestCase):
    def test_teal_skin_boards_are_not_the_main_menu(self):
        for frame in (TEAL, TEAL_6, ("partia-4", "kawalek_1", "final.png"), ("partia-6", "kawalek_1", "final.png"),
                      ("partia-4", "kawalek_1", "035_state.png"), ("partia-6", "kawalek_1", "147_state.png")):
            with self.subTest(frame=frame):
                self.assertFalse(bridge.is_main_menu_screen(s1(*frame)))

    def test_main_menu_is_still_the_main_menu(self):
        img = np.asarray(Image.open(os.path.join(RUNS, *MENU)).convert("RGB")).astype(int)
        self.assertTrue(bridge.is_main_menu_screen(img))

    def test_no_s1_frame_is_the_main_menu(self):
        for path in sorted(glob.glob(os.path.join(S1, "partia-*", "kawalek_*", "*.png"))):
            with self.subTest(path=os.path.relpath(path, S1)):
                img = np.asarray(Image.open(path).convert("RGB")).astype(int)
                self.assertFalse(bridge.is_main_menu_screen(img))


class TestTrophyOverlay(unittest.TestCase):
    def test_positive_on_better_than_45(self):
        self.assertTrue(bridge.is_trophy_overlay_screen(s1(*TROPHY)))

    def test_negative_on_every_other_s1_frame(self):
        for path in sorted(glob.glob(os.path.join(S1, "partia-*", "kawalek_*", "*.png"))):
            rel = os.path.relpath(path, S1)
            if rel.startswith(os.path.join("partia-10", "kawalek_1")) and (
                    rel.endswith("048_state.png") or rel.endswith("final.png")):
                continue
            with self.subTest(path=rel):
                img = np.asarray(Image.open(path).convert("RGB")).astype(int)
                self.assertFalse(bridge.is_trophy_overlay_screen(img))

    def test_negative_on_menu_and_game_over(self):
        for frame in (MENU, ("1402cff", "chunk7_010_gameover_screen.png"), ("0d96333", "120_state.png")):
            with self.subTest(frame=frame):
                img = np.asarray(Image.open(os.path.join(RUNS, *frame)).convert("RGB")).astype(int)
                self.assertFalse(bridge.is_trophy_overlay_screen(img))


class TestTrayAwaitingDeal(unittest.TestCase):
    def test_real_frames_with_empty_tray_and_board(self):
        """Partie 7, 8, 9 z s1: ostatni klocek tacki postawiony, nowa trójka jeszcze nie dosypana."""
        for frame in (DEFAULT, ("partia-7", "kawalek_2", "final.png"), PINK_8):
            with self.subTest(frame=frame):
                img = s1(*frame)
                grid, tray = bridge.read_board(img), bridge.read_tray(img)
                self.assertEqual(shapes(tray), [None, None, None])
                self.assertTrue(bridge.tray_awaiting_deal(grid, tray))

    def test_not_awaiting_when_tray_has_a_piece_or_board_is_empty(self):
        grid = [[0] * 8 for _ in range(8)]
        grid[2][2] = 1
        piece = ([[1]], (10, 10))
        self.assertFalse(bridge.tray_awaiting_deal(grid, [None, piece, None]))
        self.assertFalse(bridge.tray_awaiting_deal([[0] * 8 for _ in range(8)], [None, None, None]))


def run_main(first, then, max_moves=1, overlay=False, seria=False):
    """`bridge.main` z atrapami: pierwszy odczyt `first` = (obraz, plansza, tacka), kolejne `then()`.
    Zwraca wpisy logu ruchów."""
    def settled():
        return first

    def stable(tries=6):
        return then()

    playable_img = s1(*DEFAULT)
    with mock.patch("bridge.settled_state", side_effect=settled), \
         mock.patch("bridge.stable_state", side_effect=stable), \
         mock.patch("bridge.in_game", return_value=True), \
         mock.patch("bridge.read_score", return_value=None), \
         mock.patch("bridge.drag", return_value=({"finger": [0, 0]}, playable_img)), \
         mock.patch("bridge.annotate"), \
         mock.patch("bridge.press_back") as press_back, \
         mock.patch("bridge.tap_classic") as tap_classic, \
         mock.patch("bridge.time.sleep"), \
         mock.patch("PIL.Image.Image.save"), \
         mock.patch("bridge.os.makedirs"), \
         mock.patch("builtins.open", mock.mock_open()) as m_open:
        bridge.main(max_moves, policy_spec="greedy", seria=seria)
    press_back.assert_not_called()
    tap_classic.assert_not_called()
    return [json.loads(c.args[0]) for c in m_open().write.call_args_list]


class TestMainWaitsForTray(unittest.TestCase):
    def setUp(self):
        self.img = s1(*DEFAULT)
        self.grid = bridge.read_board(self.img)
        self.empty = (self.img, self.grid, [None, None, None])
        self.playable = (self.img, self.grid, [([[1, 1]], (20, 460)), None, None])

    def test_empty_tray_is_a_window_then_the_game_goes_on(self):
        states = [self.empty, self.empty, self.playable]
        entries = run_main(self.empty, lambda: states.pop(0) if len(states) > 1 else states[0])
        okna = [e.get("okno") for e in entries if "okno" in e]
        self.assertEqual(okna, ["tacka_pusta_przejsciowo"] * 3)
        self.assertFalse(any("end" in e for e in entries))
        self.assertIn("move", entries[-1])

    def test_endless_empty_tray_ends_by_the_progress_safeguard(self):
        entries = run_main(self.empty, lambda: self.empty, max_moves=5)
        self.assertEqual(len(entries), bridge.PROGRESS_SAFEGUARD_TRIES)
        self.assertEqual(entries[-1]["end"], "okno: petla_bez_postepu")
        self.assertEqual({e["okno"] for e in entries}, {"tacka_pusta_przejsciowo"})

    def test_board_with_no_legal_move_still_ends_the_game(self):
        """Pełna plansza z klockiem w tacce, którego nie da się postawić, to nadal koniec."""
        full = [[1] * 8 for _ in range(8)]
        state = (self.img, full, [([[1]], (20, 460)), None, None])
        entries = run_main(state, lambda: state)
        self.assertEqual(entries[-1]["end"], "brak legalnego ruchu wg odczytu")


class TestMainSurvivesTrophyOverlay(unittest.TestCase):
    def test_overlay_is_logged_as_a_window_not_read_as_board(self):
        trophy = s1(*TROPHY)
        game = s1(*DEFAULT)
        grid = bridge.read_board(game)
        overlay_state = (trophy, bridge.read_board(trophy), [None, None, None])
        playable = (game, grid, [([[1, 1]], (20, 460)), None, None])
        states = [overlay_state, playable]
        entries = run_main(overlay_state, lambda: states.pop(0) if len(states) > 1 else states[0])
        okna = [e.get("okno") for e in entries if "okno" in e]
        self.assertEqual(okna[0], "nakladka_better_than")
        self.assertFalse(any("end" in e for e in entries))
        self.assertIn("move", entries[-1])


class TestSeriaRereadsWhenNoMove(unittest.TestCase):
    """#295: napis combo na planszy (partia-5/kawalek_4/048_state.png) czytany jak klocki nie kończy partii serii."""
    def setUp(self):
        self.combo = s1("partia-5", "kawalek_4", "048_state.png")
        self.grid = bridge.read_board(self.combo)
        self.tray = [([[0, 1, 1], [1, 1, 0]], (20, 460)), None, None]
        self.stuck = (self.combo, self.grid, self.tray)
        self.good = (s1(*DEFAULT), bridge.read_board(s1(*DEFAULT)), [([[1, 1]], (20, 460)), None, None])

    def test_combo_frame_reads_as_no_move(self):
        board = bridge.Board()
        board.grid = [r[:] for r in self.grid]
        self.assertFalse(bridge.legal_moves(board, [bridge.Piece([[0, 1, 1], [1, 1, 0]], "s", -1), None, None]))

    def test_reread_then_game_goes_on(self):
        states = [self.stuck, self.good]
        entries = run_main(self.stuck, lambda: states.pop(0) if len(states) > 1 else states[0], seria=True)
        okna = [e.get("okno") for e in entries if "okno" in e]
        self.assertEqual(okna, ["brak_ruchu_ponowny_odczyt"] * 2)
        self.assertFalse(any("end" in e for e in entries))
        self.assertIn("move", entries[-1])

    def test_unchanging_state_ends_after_the_safeguard(self):
        entries = run_main(self.stuck, lambda: self.stuck, max_moves=5, seria=True)
        self.assertEqual(len(entries), bridge.NO_MOVE_REREAD_TRIES + 1)
        self.assertEqual(entries[-1]["end"], "brak legalnego ruchu wg odczytu")
        self.assertFalse(any("end" in e for e in entries[:-1]))


class TestSkinsReadBoardAndTray(unittest.TestCase):
    """Stan zgodny ze zrzutem (sprawdzony wzrokowo) na każdej skórce."""

    def check(self, frame, board, tray_shapes):
        img = s1(*frame)
        self.assertEqual(bridge.read_board(img), rows(board))
        self.assertEqual(shapes(bridge.read_tray(img)), tray_shapes)

    def test_teal(self):
        self.check(TEAL, """
            ..#.....
            ..#.....
            ..#.....
            ..#..###
            ....####
            ..######
            ..#.#...
            #.#.....""", [[[0, 1, 1], [1, 1, 0]], None, None])

    def test_pink(self):
        self.check(PINK, """
            #.#.....
            #.#.....
            #.......
            .....###
            ....#.##
            ..######
            ..#....#
            ..#.....""", [None, [[0, 1], [1, 1], [1, 0]], [[1], [1], [1], [1]]])

    def test_pink_second_game(self):
        self.check(PINK_8, """
            #....###
            ...#.#..
            ...#....
            ..#####.
            #...###.
            #......#
            .......#
            #..#....""", [None, None, None])

    def test_tan_with_three_pieces(self):
        self.check(TAN, """
            ........
            ........
            ........
            .....###
            .....###
            .....###
            ........
            ........""", [[[1] * 3] * 3, [[1, 1]] * 3, [[1] * 3] * 3])

    def test_default(self):
        self.check(DEFAULT, """
            ........
            ........
            ###.....
            ........
            ........
            ........
            ........
            ....#...""", [None, None, None])

    def test_purple_reads_one_piece_not_three_garbage_trays(self):
        """Dawniej trzy sloty 9x7 (opalizujące tło paska tacki), plansza pusta już wtedy była poprawna."""
        self.check(PURPLE, """
            ........
            ........
            ........
            ........
            ........
            ........
            ........
            ........""", [None, None, [[1] * 3] * 3])

    def test_blue_purple_skin_board_with_purple_blocks(self):
        """01eb4dd/chunk3_final.png (138629): niebieskofioletowa skórka, klocki fioletowe, niebieskie i żółty."""
        img = np.asarray(Image.open(os.path.join(RUNS, "01eb4dd", "chunk3_final.png")).convert("RGB")).astype(int)
        self.assertEqual(bridge.read_board(img), rows("""
            ........
            ##......
            ##......
            ##...#..
            ....##..
            .....#..
            #.......
            ........"""))
        self.assertEqual(shapes(bridge.read_tray(img)), [None, None, [[0, 1], [1, 1], [0, 1]]])


class TestHudScoreOnEverySkin(unittest.TestCase):
    TRUTH = (  # (zrzut, licznik widoczny na zrzucie)
        (TEAL, 5499),
        (TEAL_6, 19935),
        (PINK, 26949),
        (("partia-7", "kawalek_2", "final.png"), 42199),
        (PINK_8, 16209),
        (TAN, 43348),
        (("partia-2", "kawalek_2", "050_state.png"), 43023),
        (DEFAULT, 1326),
        (PURPLE, 44328),
    )

    def test_visible_number_on_each_skin(self):
        for frame, expected in self.TRUTH:
            with self.subTest(frame=frame):
                self.assertEqual(bridge.read_hud_score(s1(*frame)), expected)

    def test_gold_diamond_behind_digits(self):
        """Złoty romb za cyframi (#297): klatki int jak ze `screenshot()`, wartości wpisane z obrazu."""
        for frame, expected in (
            (("partia-5", "kawalek_1", "080_state.png"), 12730),
            (("partia-5", "kawalek_1", "140_state.png"), 44670),
            (("partia-5", "kawalek_2", "000_state.png"), 50115),
        ):
            with self.subTest(frame=frame):
                img = s1(*frame)
                self.assertEqual(img.dtype, int)
                self.assertEqual(bridge.read_hud_score(img), expected)

    def test_seven_digits_on_each_skin_in_s1_games_1_and_3(self):
        """7 cyfr (>= 1 mln, #302): licznik wypełnia całą szerokość, więc wąskie `SCORE_BOX` obcinało skrajne cyfry;
        klatki `int` jak ze `screenshot()`, wartości wpisane z obrazu. Różowa i granatowa skórka w tych partiach
        kończą się przed 1 mln — tam 7 cyfr nie występuje."""
        for frame, expected in (
            (("partia-1", "kawalek_13", "final.png"), 1371295),  # beżowa, złoty romb za cyframi
            (("partia-1", "kawalek_20", "050_state.png"), 2459073),  # beżowa
            (("partia-1", "kawalek_35", "final.png"), 4909600),  # beżowa
            (("partia-1", "kawalek_53", "final.png"), 8276063),  # beżowa, ostatni kawałek partii
            (("partia-3", "kawalek_10", "final.png"), 1281620),  # domyślna z turkusowym rombem
            (("partia-3", "kawalek_40", "050_state.png"), 5378565),  # domyślna
            (("partia-3", "kawalek_55", "final.png"), 6685059),  # domyślna, ostatni kawałek
        ):
            with self.subTest(frame=frame):
                img = s1(*frame)
                self.assertEqual(img.dtype, int)
                self.assertEqual(bridge.read_hud_score(img), expected)

    def test_overlay_over_seven_digits_is_none(self):
        """Napis „+432” zasłania cyfry licznika 2694319 — brak odczytu, nie zgadywanie."""
        self.assertIsNone(bridge.read_hud_score(s1("partia-3", "kawalek_24", "050_state.png")))

    def test_int_and_uint8_frames_agree(self):
        img = s1(*TEAL)
        self.assertEqual(bridge.read_hud_score(img.astype(np.uint8)), bridge.read_hud_score(img))

    def test_trophy_overlay_never_gives_a_wrong_number(self):
        """Licznik pod nakładką jest przyciemniony (8513); odczyt albo trafny, albo None."""
        self.assertIn(bridge.read_hud_score(s1(*TROPHY)), (None, 8513))

    def test_counter_never_decreases_along_a_game(self):
        """Na całym materiale s1 (hundreds klatek, 7 skórek) żaden odczyt nie wypada poza rosnący ciąg partii —
        zła cyfra zwykle łamie monotoniczność; klatki bez odczytu (animacja) są pomijane."""
        for partia in sorted(glob.glob(os.path.join(S1, "partia-*"))):
            seq = []
            for kawalek in sorted(glob.glob(os.path.join(partia, "kawalek_*")), key=lambda d: int(d.rsplit("_", 1)[1])):
                for path in sorted(glob.glob(os.path.join(kawalek, "*_state.png"))):
                    img = np.asarray(Image.open(path).convert("RGB")).astype(int)
                    value = bridge.read_hud_score(img)
                    if value is not None:
                        seq.append((os.path.relpath(path, S1), value))
            with self.subTest(partia=os.path.basename(partia)):
                self.assertGreater(len(seq), 5)
                for (p0, v0), (p1, v1) in zip(seq, seq[1:]):
                    self.assertLessEqual(v0, v1, f"{p0}={v0} > {p1}={v1}")

    def test_most_frames_are_read(self):
        total = read = 0
        for path in glob.glob(os.path.join(S1, "partia-*", "kawalek_*", "*_state.png")):
            img = np.asarray(Image.open(path).convert("RGB")).astype(int)
            total += 1
            read += bridge.read_hud_score(img) is not None
        # nieczytelne zostają klatki z nakładką "+N" na cyfrach (np. partia-5/kawalek_1/055, kawalek_3/100)
        self.assertGreater(read / total, 0.9)


S2 = os.path.join(ROOT, "docs", "seria", "s2")


def s2(*parts):
    return np.asarray(Image.open(os.path.join(S2, *parts)).convert("RGB")).astype(int)


@unittest.skipUnless(os.path.isdir(S2), "brak materialu s2")
class TestWoodenSkinTray(unittest.TestCase):
    """#307: tło paska tacki skórki drewnianej (173,89,58) przechodzi `is_block`; kształty czytamy w masce z tłem."""

    def test_z_and_s(self):
        t = shapes(bridge.read_tray(s2("partia-3", "kawalek_3", "087_state.png")))
        self.assertEqual(t[1], [[1, 1, 0], [0, 1, 1]])
        self.assertEqual(t[2], [[0, 1, 1], [1, 1, 0]])

    def test_l_t_and_2x3(self):
        t = shapes(bridge.read_tray(s2("partia-2", "kawalek_4", "060_state.png")))
        self.assertEqual(t, [[[1, 0], [1, 1]], [[0, 1, 0], [1, 1, 1]], [[1, 1], [1, 1], [1, 1]]])

    def test_whole_material_agrees_with_independent_reading(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import porownanie_odczytu as po
        paths = glob.glob(os.path.join(S1, "**", "*_state.png"), recursive=True) + \
            glob.glob(os.path.join(S2, "**", "*_state.png"), recursive=True)
        self.assertGreater(len(paths), 600)
        for path in paths:
            self.assertEqual(po.compare_state(po.load(path))["sloty_tacki_rozne"], [], path)


if __name__ == "__main__":
    unittest.main()
