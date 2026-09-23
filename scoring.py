"""
Block Blast Scoring System

Wzór referencyjny ustalony w badaniu #2 — zbieżny co do cyfry w dwóch
niezależnych reimplementacjach:

    punkty = liczba_komorek_klocka + combo_po_inkrementacji * B(l)
    B(l)   = 0 dla l=0,  10 dla l=1,  10*l*(l-1) dla l>=2

Combo jest MNOŻNIKIEM całego bonusu za czyszczenie, nie dodatkiem (R-2).

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


def line_bonus(lines):
    """B(l) — bonus bazowy za wyczyszczenie l linii jednocześnie, przed mnożnikiem combo."""
    if lines <= 0:
        return 0
    if lines == 1:
        return 10
    return 10 * lines * (lines - 1)


def clear_points(combo, lines):
    """Punkty za czyszczenie: combo (po inkrementacji) mnoży bonus bazowy."""
    return combo * line_bonus(lines)
