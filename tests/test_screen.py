"""
Odczyt ekranu: progi zmierzone na zrzutach z przebiegów mostu.

Gra zmienia motyw graficzny w trakcie partii (#34), więc każdy test niesie parę
kolorów **z dwóch motywów naraz**. Pojedynczy motyw przechodzi przy każdym progu;
dopiero para pokazuje, że stała globalna ich nie rozdziela, a tło z klatki tak.

Kolory zmierzone na przebiegach 35879525460 (zrzuty 019_state.png i 206_end.png),
35842812364 (final.png) i 35887593719 (384_end.png).
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bridge import RATING_CLOSE, bg_color, readable_tray, stands_out

# tło planszy / kolor klocka, oba motywy
NIEBIESKI = (32, 40, 80), (172, 40, 41)     # plansza granatowa, klocek czerwony
BRAZOWY = (72, 56, 56), (74, 142, 66)       # plansza brązowa, klocek zielony
TLO_PASKA_NIEBIESKIE = (56, 80, 144)        # tło strony w motywie niebieskim
PASEK_BRAZOWY = (184, 168, 152)             # tło strony w motywie brązowym

# Okno oceny gry nad ekranem końca partii, zrzut 384_end.png (#35)
OCENA_X = (189, 206, 255)          # biały ✕ w punkcie RATING_CLOSE
OCENA_NAGLOWEK = (90, 125, 230)    # tło paska „Rating", na którym ✕ leży
REPLAY_PRZYGASZONY = (66, 69, 66)  # ▶ przytłumiony pod oknem
TACKA_OKNA_OCENY = [[[1, 1]] * 3, [[1] * 7] * 3, [[1] * 3] * 3]  # co czyta segmentacja


class ThemeAgnosticSegmentation(unittest.TestCase):
    """Klocek każdego motywu odstaje od tła **swojego** motywu."""

    def test_klocek_odstaje_od_tla_swojego_motywu(self):
        for bg, block in (NIEBIESKI, BRAZOWY):
            self.assertTrue(stands_out(np.array(block), np.array(bg)), block)

    def test_puste_pole_nie_odstaje(self):
        for bg, _ in (NIEBIESKI, BRAZOWY):
            self.assertFalse(stands_out(np.array(bg), np.array(bg)), bg)

    def test_nasycenie_nie_rozdziela_motywow(self):
        """Pułapka, która zatrzymała przebieg 35879525460 po 206 ruchach.

        Klocek brązowy ma nasycenie 72, tło paska niebieskiego 88 — każdy próg
        na nasyceniu albo gubi klocek w jednym motywie, albo bierze tło w drugim.
        """
        def nasycenie(c):
            return max(c) - min(c)

        self.assertLess(nasycenie(BRAZOWY[1]), nasycenie(TLO_PASKA_NIEBIESKIE))


class BackgroundFromFrame(unittest.TestCase):
    def test_tlo_to_kolor_wiekszosci(self):
        """Pole puste jest na planszy najczęstsze także wtedy, gdy klocków jest sporo."""
        region = np.full((80, 80, 3), BRAZOWY[0], dtype=int)
        region[:20, :20] = BRAZOWY[1]
        self.assertEqual(tuple(bg_color(region)), (72, 56, 56))


class GameOverButton(unittest.TestCase):
    """Pusty pasek tacki nie jest przyciskiem ▶ — w żadnym motywie."""

    def test_pasek_brazowy_miesci_sie_pod_progiem_przycisku(self):
        p = np.array(PASEK_BRAZOWY)
        self.assertLess(p.max() - p.min(), 33 + 1)   # rozrzut 33 wobec progu 30
        self.assertLess(p.mean(), 180)               # jasność 173 wobec progu 180
        self.assertFalse(stands_out(p, p))           # ale od własnego tła nie odstaje


class RatingWindow(unittest.TestCase):
    """Okno oceny gry: trzeci raz, gdy gra rysuje coś nad planszą (#35)."""

    def test_tacka_okna_oceny_jest_nieczytelna(self):
        self.assertFalse(readable_tray(TACKA_OKNA_OCENY))

    def test_dwa_bloby_z_trzech_udaja_klocek(self):
        """Pułapka, która zatrzymała przebieg 35887593719 po 384 ruchach.

        Bramka „którykolwiek slot wiarygodny" przepuszczała ten ekran, bo blob 3x2
        i blob 3x3 mieszczą się w 5x5. Dopiero „każdy wiarygodny" go odrzuca.
        """
        self.assertEqual([readable_tray([s]) for s in TACKA_OKNA_OCENY], [True, False, True])

    def test_x_odstaje_od_paska_okna(self):
        """RATING_CLOSE celuje w glif ✕, nie w tło nagłówka obok niego."""
        self.assertTrue(stands_out(np.array(OCENA_X), np.array(OCENA_NAGLOWEK)))
        self.assertEqual(RATING_CLOSE, (275, 192))

    def test_przygaszony_replay_nie_jest_ekranem_konca(self):
        """Dlatego `game_over()` słusznie mówi „nie" i potrzebna jest osobna droga."""
        p = np.array(REPLAY_PRZYGASZONY)
        self.assertLess(p.max() - p.min(), 30)  # rozrzut 3: przycisk jest jednolity
        self.assertLess(p.mean(), 180)          # ale jasność 67 zamiast 232


if __name__ == "__main__":
    unittest.main()
