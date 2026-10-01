# Przegrane partii 2 i 3 serii s2 (skórka drewniana) — diagnoza #305

Zaraportowano, nie naprawiano: `bridge.py`, polityka i pliki odcisku bez zmian.

## Wniosek

Obie partie przegrały z tego samego powodu: **`bridge.read_tray` na skórce drewnianej czyta każdy klocek niebędący
prostokątem jako pełny prostokąt jego bounding boxa**. Most układał więc nieistniejące kształty (S/Z jako 3x2, T jako 3x2,
L jako 2x2), stawiał prawdziwe klocki w innym miejscu, niż planował, a plansza z odczytu rozjeżdżała się z planem
(`ok=false`). Polityka na prawdziwym obrazie rozdania przeżywa je bez trudu. To nie generator apki i nie ślepa plamka.

Przyczyna w kodzie (`bridge.py:513`, `read_tray`): maska klocków odejmuje tło paska (mediana, `TRAY_BG_DIST`), ale
kształt jest potem próbkowany przez `is_block(img[punkt])` bez tej maski. Tło paska tacki skórki drewnianej to
RGB (173, 89, 58), które `is_block` uznaje za klocek, więc każda komórka bounding boxa wychodzi jako zajęta. Plansza
(`read_board`) czyta się poprawnie: 0 różnic na pole w obu partiach.

## Partia 3 — przegrana, 392 postawienia (`partia-3/przegrana.json`)

- Werdykt `tools/przegrana_serii.py`: **`rozjazd_mostu`** (`ok_false_przed_ostatnim_ruchem`, `ok=false` w n = 87, 88, 90).
- Pierwszy `ok=false` (n=87) to pierwsza tacka z klockiem Z/S: obraz `kawalek_3/087_state.png` pokazuje zielone Z i
  turkusowe S, log ma `[[1,1,1],[1,1,1]]` dla obu. Most „położył" prostokąt 3x2 w (2,2), a na planszy wylądował
  Z — `expected` i `observed` różnią się o 8 pól.
- Stan końcowy: po ruchu 91 zostaje pionowy I4, a na planszy (`przed_koncem`) nie ma w żadnej kolumnie czterech wolnych
  pól pod rząd — przegrana prawdziwa (ekran „Can you Top that?" 55 567), ale zrobiona przez plansze zepsute ruchami
  z błędnymi kształtami z n=87, 88, 90.
- Rozdanie ostatnie z pełną trójką (n=90, `partia-3/rozdanie_90.json`): prawdziwa tacka I4 + Z + O, na prawdziwej planszy
  istnieje ułożenie całej trójki, a polityka `lookahead-ntuple ...@beam=128,samples=0,complete=1,gain_weight=100000`
  kładzie wszystkie trzy (slot 2 → (6,0), slot 1 → (4,1), slot 0 → (6,2)).

## Partia 2 — to jest przegrana (przerwanie `petla_bez_postepu` było skutkiem reklamy po końcu)

- Narzędzie nie przyjmuje `przerwanie` (kończy komunikatem), więc kroki ręcznie na `chunk4_moves.jsonl`, n=60:
  - ruch 60 (`ok=false`): most wziął L (cyjan, 3 pola) za 2x2 i postawił w (3,6); `observed` (plansza z obrazu po ruchu)
    różni się od `expected` o 1 pole;
  - w tacce zostały T i pionowy 2x3 (obraz `kawalek_4/060_state.png`); na planszy `observed` **nie ma dla nich legalnego
    ruchu** (sprawdzone `bridge.legal_moves`) — gra była skończona;
  - wiersze n=61 to już reklama wideo (`061_state.png`, `final.png`): odczyt planszy/tacki z reklamy to śmieci,
    stąd dwa `brak_ruchu_ponowny_odczyt`, potem `ustawienia_wstecz` i `petla_bez_postepu`. Ekranu końca most nie zobaczył,
    bo reklama go zasłoniła; stan końcowy wyprowadzony z `observed` i tacki z obrazu (nie z ekranu końca).
- Rozdanie n=60 (`partia-2/rozdanie_60.json`): prawdziwa tacka L + T + pionowy 2x3 jest układalna, a polityka na prawdziwej
  planszy ułożyła wszystkie trzy (slot 1 → (3,5), slot 0 → (1,5), slot 2 → (3,5)).
- Czego nie wiemy: ekranu końca nie ma, więc „przegrana" to wniosek z braku legalnego ruchu na `observed`; wynik końcowy
  partii 2 nieznany (ostatni licznik 146 481 na `060_state.png`).

## Porównanie odczytu z obrazem (ostatnie 10 stanów)

`tools/porownanie_odczytu.py` (odczyt niezależny: plansza — różnica od koloru pustej komórki; tacka — maska z odjętym
tłem także przy próbkowaniu kształtu). Pliki: `partia-3/porownanie_odczytu.json` (n 82–91),
`partia-2/porownanie_odczytu.json` (n 51–60).

| partia | stany | pola planszy różne | stany z błędnym klockiem tacki | błędne sloty |
|---|---|---|---|---|
| 3 | 82–91 | 0 | 5 (n 84, 85, 87, 88, 90) | n84: 1,2; n85: 1; n87: 1,2; n88: 2; n90: 1 |
| 2 | 51–60 | 0 | 9 (wszystkie poza n 59) | n51: 1,2; n52, 53, 58: 2; n54, 55, 56: 1; n57: 1,2; n60: 0,1 |

Błędnie czytane są wszystkie klocki inne niż prostokąt/I (S, Z, T, L); I4, O, 2x3 czytają się dobrze. Log zgadza się
z odczytem `bridge` na zrzucie w 100% stanów (to ten sam kod) — rozjazd jest między kodem a obrazem.

## Co naprawić, żeby s3 miała sens

1. `read_tray`: próbkować komórki kształtu tą samą maską (z odjętym tłem paska), nie samym `is_block`; test na
   `partia-3/kawalek_3/087_state.png` (Z i S) i `partia-2/kawalek_4/060_state.png` (L, T, 2x3). Testu usterki
   pilnuje `tests/test_porownanie_odczytu.py` — po naprawie ma zacząć padać i trzeba go zamienić na test poprawnego odczytu.
2. Bezpiecznik: trzy `ok=false` w czterech ruchach (n 87–90 w partii 3) nie zatrzymały mostu. Warto kończyć serię po
   kilku `ok=false` z rzędu zamiast grać dalej na rozjechanej planszy.
3. Po ekranie reklamy po końcu partii zaliczać koniec partii (przerwanie z reklamą po ruchu bez legalnego ruchu to
   przegrana), albo zapisać ostatnią klatkę przed reklamą.
4. Dopisać skórkę drewnianą do tabeli skórek (`docs/seria-skrypt.md`) — zrobione w tym zadaniu.
5. Partie s2 na skórce drewnianej przed tą naprawą nie liczą się jako dowód o polityce (kształty były czytane błędnie
   od pierwszej tacki z S/Z/T/L).
