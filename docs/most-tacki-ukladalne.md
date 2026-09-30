# Czy apka daje tylko układalne tacki? Pomiar z logów mostu (#249)

Narzędzie: `tools/most_tacki_ukladalne.py` (czyta `bridge/runs/*/*.jsonl` i `pomiar.json` d550db3, woła
`board.tray_playable`). Dane per tacka i per koniec partii: `docs/data/249-most-tacki.json`.
**Zaraportowano, nie naprawiono** — nic w moście, polityce, generatorze ani symulatorze nie zmienione.

## Wynik główny

Z **1160 unikalnych tacek** (trzy niepuste sloty) w 12 przebiegach: **1147 układalnych, 0 nieukładalnych,
13 nieocenianych** (wszystkie: kształt spoza `PIECE_POOL`, patrz niżej). Dodatkowo 33 pary z `d550db3/pomiar.json`
(przebieg bez surowych `*.jsonl`): 33 układalne, 0 nieukładalnych. **Nie znaleziono ani jednej tacki, której
nie dałoby się ułożyć w całości** — zgodnie z hipotezą, że apka (jak generator symulatora) daje tacki układalne.

Uwaga o sile wniosku: to ~1150 tacek, w partiach granych przez polityki bez gwarancji. Nieukładalna tacka jest
możliwa tylko na gęstej planszy; 0/1147 wyklucza częstość wyższą niż ok. 0,3% (95%), ale nie wyklucza rzadszej.
Na planszach z długich partii polityki `complete=1` most nie grał.

### Podział na przebiegi

| przebieg | układalne | nieukładalne | nieoceniane | powtórzenia (nie liczone) |
|---|---:|---:|---:|---:|
| 0d96333 | 39 | 0 | 0 | 1 |
| 1402cff | 79 | 0 | 1 | 5 |
| 1b1763a | 251 | 0 | 1 | 64 |
| 1bd38fa | 37 | 0 | 1 | 0 |
| 495cd91 | 20 | 0 | 4 | 280 |
| 4a1796f | 83 | 0 | 1 | 0 |
| 4fb5ed9 | 217 | 0 | 1 | 0 |
| 7e25817 | 175 | 0 | 1 | 0 |
| b4a7d26 | 19 | 0 | 1 | 143 |
| c1819ed | 86 | 0 | 1 | 1 |
| cb91077 | 111 | 0 | 0 | 0 |
| d878d79 | 30 | 0 | 1 | 1 |
| **razem** | **1147** | **0** | **13** | 495 |
| d550db3 (`pomiar.json`, pary) | 33 | 0 | 0 | — |

(44a8ea2 nie ma `*.jsonl`.) „Powtórzenie" = kolejny wiersz z identyczną planszą i tacką (ponowienie po `ok=false`,
chunk-loop przy zawieszeniu apki) — liczone raz.

### Wpisy nieoceniane (13)

Wszystkie z powodu `ksztalt_nierozpoznany`: kształt tacki spoza `PIECE_POOL` (błąd odczytu). Powody
`plansza_niezgodna_z_poprzednim_observed` i `budzet_wezlow_wyczerpany` (`tray_playable` → `None`): 0.
Wiersze końca partii (`koniec_partii` / `end`, 21) są **pominięte** w liczeniu tacek — ich „tacka" to odczyt
nakładki ekranu końca gry (kształty-śmieci, macierze 9×7 z samych jedynek), nie tacka apki. Kształty są przycinane
do bounding boxa przed `tray_playable` (logi trzymają je w macierzach z dopełnieniem).

## Końce partii

21 końców w logach: 16 z ekranem końca gry (`koniec_partii`), 5 z `end: brak legalnego ruchu wg odczytu`
(to ostatnie to wniosek mostu z odczytu, nie potwierdzona śmierć; bywa fałszywe).

| klasa | liczba |
|---|---:|
| ostatnia tacka układalna w całości, partia skończyła się w jej trakcie (śmierć z chybienia polityki — lub błędu odczytu) | 17 |
| ostatnia tacka nieoceniona (kształt nierozpoznany) | 1 |
| brak tacki w pliku (koniec na początku kawałka; tacka w poprzednim pliku) | 3 |
| ostatnia tacka nieukładalna (śmierć wymuszona przez apkę) | **0** |

W żadnym ocenionym końcu tacka nie była nieukładalna: w 17 z 17 ocenionych apka dała układalną tackę, a polityki
z logów (greedy/lookahead, bez `complete=1`) rozegrały ją tak, że reszta się nie zmieściła. Ograniczenie: gdyby
ostatnia tacka została ułożona w całości, a śmiertelną była następna, most jej nie widzi (nakładka); w logach
takiego końca nie ma (`postawien_z_ostatniej_tacki` < 3 wszędzie). Lista per koniec: `koniec_partii` w JSON.

## Przepustowość mostu

- Logi mają tylko `decision_ms` (czas decyzji polityki) — **brak znaczników czasu**, więc postawień na minutę
  z logów nie da się wyliczyć. `pomiar.json` podaje czas tylko w prozie (szacunki weryfikatora): ok. 145 ruchów
  w 25–30 min (1402cff) i ok. 293 ruchy w 30–35 min (c1819ed), czyli **ok. 5–10 postawień/min** — rząd wielkości,
  nie pomiar.
- Postawienia na kawałek: 3627 wierszy z ruchem (3375 `ok`) w 127 plikach = **28,6 wiersza/plik** (kawałki
  30-ruchowe, część krótsza po końcu partii/oknie; kawałków po 60 w logach nie ma).
- Na przebieg (sesję): od 56 do 739 udanych postawień (max `1b1763a`, 27 kawałków); `b4a7d26` ma 200 wierszy
  z ruchem, ale tylko 56 `ok` (zawieszka apki).

## Koszt realnej partii ≥ 1 mln pkt apki

Założenie: 141 pkt/postawienie naszym wzorem (`docs/dlugie-partie-gwarancja.md`, beam=128, `complete=1`) razy
przelicznik apka/wzór z `docs/punktacja-apka-vs-wzor.md` (1,43–4,68×), zakładając że przelicznik jest stały
(założenie, nie pomiar).

| przelicznik | pkt apki/postawienie | postawień na 1 mln | kawałki po 60 | sesje verifiera (max 739 postawień) | czas przy 5–10/min |
|---|---:|---:|---:|---:|---|
| 1,00× (sam wzór) | 141 | 7 092 | 119 | 9,6 | 12–24 h |
| 1,43× | 201,6 | 4 960 | 83 | 6,7 | 8–17 h |
| 4,68× | 659,9 | 1 515 | 26 | 2,05 | 2,5–5 h |

Wniosek: przy braku nieukładalnych tacek (a polityka z gwarancją wtedy nie umiera) realna partia 1 mln to kwestia
czasu mostu — rzędu kilku do kilkunastu godzin ciągłej gry, 26–119 kawałków. Wąskie gardło to nie polityka, tylko
reklamy, okna i zawieszki apki, które w logach przerywały partie po kilkuset ruchach; partia bez przerwy
1500–7000 postawień nie była na moście jeszcze grana.

## Odkrycia

- Wiersz końca partii w logach niesie w polu `tray` kształty-śmieci z nakładki końca gry; każdy pomiar par
  plansza→tacka musi go pomijać (`tools/z6_pary.py` odrzuca je jako `ksztalt_tacki_nierozpoznany`).
