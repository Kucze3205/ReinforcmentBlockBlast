"""
Block Blast Scoring System

Wzór referencyjny ustalony w badaniu #2 — zbieżny co do cyfry w dwóch
niezależnych reimplementacjach:

    punkty = liczba_komorek_klocka + combo_po_inkrementacji * B(l, combo)
    B(l, combo) = U(combo) * (1 dla l=1,  l*(l-1) dla l>=2),  0 dla l=0
    U(combo)    = 10 dla combo 1-5,  15 dla 6-10,  20 od 11 wzwyz

Combo jest MNOŻNIKIEM całego bonusu za czyszczenie, nie dodatkiem (R-2), a rosnie
o LICZBE CZYSZCZONYCH LINII, nie o 1 (#33): czyszczenie dwoch linii na raz podnosi
combo o 2. Drabinka U to trzy schodki i zadnego czwartego: pomiar #33 trzyma 20
nieprzerwanie do combo 39 (najwyzsze zmierzone), wiec granice 5|6 i 10|11 to jedyne.
Wczesniejsze "11-16 -> 20" bylo zmierzone licznikiem symulatora, ktory gubil jedno
combo na kazde dodatkowe czyszczenie z jednego ruchu, wiec gorna granica 16 byla
artefaktem pomiaru.

Za opróżnienie planszy nie ma nic. Oba źródła referencyjne dawały 300, farma SEO
360 — a pomiar na oryginale (Z-4, #30) pokazał zero na dwóch niezależnych pełnych
czyszczeniach. Dlatego nie ma tu stałej do przestrojenia: bonus nie istnieje.
Reszta wzoru zgadza się z apką co do cyfry, skumulowana przez cały przebieg.
"""

# Ile postawień bez czyszczenia przeżywa combo, gdy tacka jest pusta/1/2 klocki.
COMBO_COUNTER_BASE = 3


def placement_points(piece):
    """Punkty za samo postawienie = liczba komórek klocka."""
    return sum(int(cell) for row in piece.shape for cell in row)


def combo_unit(combo):
    """U(combo) — bazowy bonus za jedna linie; rosnie schodkami 10/15/20 z combo."""
    if combo <= 5:
        return 10
    if combo <= 10:
        return 15
    return 20


def line_bonus(lines, combo=1):
    """B(l, combo) — bonus bazowy za wyczyszczenie l linii jednoczesnie, przed mnoznikiem combo."""
    if lines <= 0:
        return 0
    if lines == 1:
        return combo_unit(combo)
    return combo_unit(combo) * lines * (lines - 1)


def clear_points(combo, lines):
    """Punkty za czyszczenie: combo (po inkrementacji) mnozy bonus bazowy."""
    return combo * line_bonus(lines, combo)
