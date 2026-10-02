# s6: przerwania p.1 i p.5 (#343)

Obie partie przerwał bezpiecznik `petla_bez_postepu` na grywalnej planszy. Odczytanie ekranu z issue było trafne w obu
przypadkach; mechanizm leży w progach detektora i odczytu koloru.

## p.1 — `nakladka_better_than` na zwykłej planszy

Zrzut: `partia-1/kawalek_6/final.png` (też `041_state.png`, `040_aim.png`). Ekran bez pucharu; plansza ma żółte
i czerwone klocki. `is_trophy_overlay_screen` wymaga trzech znaków naraz i wszystkie trzy zaszły na samej planszy:

| znak | próg | p.1 `final.png` | prawdziwa nakładka (s1 p.10 `048_state.png`) |
|---|---|---|---|
| złoto w środku planszy | > 0.25 | 0.29 (żółte klocki) | 0.47 |
| złoto w pasie napisu | 0.1–0.5 | 0.38 (żółty klocek) | 0.19 |
| czerwień „klejnotu" | > 100 px | 512 px (czerwone klocki) | 274 px |

Czerwony klocek wypełnia całe pole klejnotu: obwiednia czerwieni ma 40×30 px, klejnot na pucharze 22×25 px (też
`s1/partia-10/kawalek_1/final.png`: 252 px, 22×25). Poprawka: `TROPHY_GEM_MAX_SPAN = 32` — obwiednia czerwieni w polu
klejnotu nie może przekraczać 32 px. Nakładka s1 nadal wykrywana; to jedyna prawdziwa nakładka wśród zrzutów
`NNN_state/aim/final` s1–s6 (inne wpisy `okno: nakladka_better_than` w logach nie mają zrzutu z nakładką).

Przed: `is_trophy_overlay_screen` = True na 3 klatkach p.1 (24 wpisów z rzędu, potem bezpiecznik). Po: False na
wszystkich; tacka (1×4 i S) czytana jak wcześniej.

## p.5 — pusta tacka na drewnianej skórce

Zrzut: `partia-5/kawalek_3/final.png` i `106_state.png`; w prawym slocie fioletowy klocek 2×3. Piksele klocka:
(181,121,206), (189,130,214), (181,125,214) — rozpiętość kanałów 84–89, a `is_block` wymaga ≥ 100 (szczyt ≥ 150
spełniony). `read_tray` dostawało więc pustą maskę: `[None, None, None]`.

Poprawka: trzeci warunek w `is_block` — `purple_wood`: B > R > G, B−G ≥ 70, R−G ≥ 40, B ≥ 190. Tło drewna
(173,89,58), różowe tło tacki (255,166,181) i błękitne (148,202,255) mają R albo G dominujące nad B, więc nie wchodzą.

Przed: `read_tray` = `[None, None, None]`. Po: `[None, None, 2×3 pełny]`.

## Odczyt na całym `docs/seria` (`tools/porownanie_odczytu.py`, kawałek po kawałku, 1290 plików wyniku)

Zmieniło się 5 kawałków, wszystkie na korzyść: liczba pól różniących odczyt mostu od obrazu spada, nigdzie nie rośnie.

| kawałek | pola różnic przed → po |
|---|---|
| s1 p.5 k.2 (n=10) | 5 → 4 |
| s1 p.9 k.1 (n=15) | 4 → 0 |
| s4 p.10 k.8 (n=50) | 64 → 60 |
| s5 p.8 k.1 (n=49) | 6 → 5 |
| s6 p.5 k.3 | wiersze 77–83 i dalej: 0 pól różnic, bez zmiany (zmienia się tylko `log=most`: log zapisał pustą tackę, most czyta teraz klocek) |

Sloty bez różnic w obu przebiegach (pustych list `sloty: []` nie przybyło). `tools/detektory_na_planszy.py` ma s6 w
`SERIE` i daje zera we wszystkich detektorach na s1–s6 (446 klatek s6).

Testy: `tests/test_bridge_przerwania_s6.py`.
