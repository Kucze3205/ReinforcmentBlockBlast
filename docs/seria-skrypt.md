# Partia serii weryfikacyjnej — `tools/partia_serii.py` (#283)

Gra **jedną partię do końca bez agenta** (`CONTEXT.md`, „Cel i weryfikacja"). Przeznaczony na osobny krok joba
emulatora, po jednym na partię (10 równoległych jobów). Nie woła `git`, nie startuje apki.

## Polecenie

```
python3 tools/partia_serii.py POLITYKA KATALOG [--limit-minut 300] [--prog 1000000] [--kawalek 150]
```

| argument | znaczenie |
|---|---|
| `POLITYKA` | napis specyfikacji jak `argv[2]` mostu (np. `greedy`) |
| `KATALOG` | katalog wyjściowy (tworzony) |
| `--limit-minut` | limit czasu partii (zegar ścienny od startu skryptu; sprawdzany między kawałkami) |
| `--prog` | próg licznika apki, domyślnie 1 000 000 |
| `--kawalek` | ruchów w jednym wywołaniu mostu, domyślnie 150 |

Gra kawałkami przez `bridge.main(..., seria=True)` (ścieżka ruchu z `docs/most-tempo.md`, ta sama obsługa znanych
okien). Jedyna różnica względem zwykłego mostu: **ekran końca partii nie stuka „Play"** — kończy partię.
Po każdym kawałku skrypt czyta licznik apki na stabilnej klatce (dwa zgodne odczyty; `stable_score`).
Odczyt HUD robi `bridge.read_hud_score` (dopasowanie wzorców cyfr z `bridge_digits.npz`, nie tesseract; #290).
**Reguła akceptacji:** odczyt liczy się (do `cel` i jako punkt odniesienia), tylko gdy jest stabilny i spójny z poprzednim
zaakceptowanym — licznik nie maleje i nie rośnie dziesięciokrotnie (zgubiona lub dopisana cyfra). Odczyt niespójny to
brak odczytu: nie kończy `cel`, ląduje w `licznik_odrzucone`. Zrzut `licznik_apki.zrzut` to klatka ostatniego odczytu,
z której pochodzi wartość.

## Kody wyjścia i `zakonczenie`

| kod | `zakonczenie` | kiedy |
|---|---|---|
| 0 | `cel` | licznik apki ≥ progu na stabilnej klatce (odczyty zgodne i spójne z poprzednim). Klatka niestabilna ≥ progu **nie** kończy — gra idzie dalej |
| 1 | `przegrana` | ekran końca partii |
| 2 | `przerwanie` | nieznane okno, `petla_bez_postepu`, `plansza_zawieszona`, `restart_utracil_partie`, apka nie wraca po restarcie, limit minut, wyjątek |
| 3 | — | błąd argumentów |

`przerwanie` nie liczy się do serii. `przyczyna` ∈ `nieznane_okno`, `petla_bez_postepu`, `plansza_zawieszona`,
`restart_utracil_partie`, `apka_nie_wraca`, `limit_minut`, `brak_legalnego_ruchu_wg_odczytu` (most nie widzi legalnego ruchu), `brak_pliku_ruchow`,
`pusty_plik_ruchow`, `wyjatek: ...`; pole `okno` niesie nazwę okna, jeśli było.

## `KATALOG/pomiar.json`

Zapisywany atomowo (plik `.tmp` + `os.replace`) po każdym kawałku i na końcu.

| pole | opis |
|---|---|
| `polityka` | napis specyfikacji |
| `zakonczenie` | `w_toku` do końca, potem `cel`/`przegrana`/`przerwanie` |
| `przyczyna`, `okno` | patrz wyżej (`null` dla `cel`/`przegrana`/`w_toku`) |
| `licznik_apki` | `{wartosc, odczyty, stabilny, zrzut}` — ostatni spójny odczyt po kawałku; `zrzut` to PNG w `KATALOG` z klatką tego odczytu |
| `licznik_odrzucone` | odczyty odrzucone jako niespójne: `{kawalek, wartosc, odczyty, poprzedni}` |
| `wynik_wzor` | wynik naszym wzorem (`tools/score_from_trajectory.py`, `wynik_main`) z dotychczasowych kawałków |
| `postawienia` | liczba ruchów w plikach ruchów |
| `minuty` | od pierwszego do ostatniego pola `t` pliku ruchów (bez startu apki) |
| `postawien_na_minute` | postawienia / minuty liczone z pól `t` wpisów z ruchem |
| `decision_ms` | `{mediana, p95, max}` |
| `okna` | lista zatrzymań: `{kawalek, n, okno, t}` (`okno: "restart"` dla restartu apki) |
| `kawalki` | pliki ruchów `chunkN_moves.jsonl` w `KATALOG` (format `docs/most-zapis-ruchow.md`) |
| `ostatnie_ruchy`, `wynik_koncowy`, `zrzut_konca` | tylko `przegrana`: plansza i tacki z ostatnich 5 ruchów, wynik z ekranu końca, zrzut (ścieżka względem `KATALOG`) |

Reszta artefaktów: `kawalek_K/` (zrzuty mostu: `NNN_state.png`, `NNN_aim.png`, `NNN_end.png`, `final.png`).

## Co job robi przed i po

**Przed:** uruchomić emulator i apkę (`tools/start_apki.sh`, jak `tools/bridge.sh`) — pauza 90 s po starcie obrazu, wyłączenie
weryfikatora pakietów, `adb install-multiple`, `monkey` z Accept ToS (do 3 prób, aż gra utrzyma pierwszy plan).
Nie wołać `python3 bridge.py`. Skrypt startuje z apką **na planszy**. Na start (ok. 2–3 min) zostawić margines poza
`--limit-minut`; limit liczy zegar skryptu, nie joba. Wymagane: `adb`, `tesseract`.

**Po:** niezależnie od kodu wyjścia (krok `if: always()`) zachować `KATALOG` jako artefakt lub commit;
`adb logcat -d` jak w `bridge.sh`. Kod wyjścia 1 i 2 to wyniki, nie awarie joba.

## Job serii — `.github/workflows/seria.yml` (#287)

```
gh workflow run seria.yml -f polityka='<spec>' -f seria=<id> [-f limit_minut=300]
```

Macierz 10 jobów (`partia` 1–10), każdy: KVM, emulator, `tools/seria.sh` (start apki z `tools/start_apki.sh`,
wspólny z `bridge.sh`, potem skrypt partii). Job ma 355 min; `limit_minut` + ~3 min startu musi się w tym zmieścić.
Kody 0/1/2 kończą krok zerem, kod trafia do `KATALOG/kod_wyjscia.txt`. Trwa co najwyżej jedna seria (grupa
`concurrency: seria`; kolejne wywołanie czeka).

Wyniki: artefakt `seria-<id>-partia-K` na partię (cały `KATALOG`, także `logcat.txt`):

```
gh run list --workflow seria.yml --json databaseId,displayTitle,status   # displayTitle: "seria <id>"
gh run download <run-id> -n seria-<id>-partia-K
```

## Po przegranej — `tools/przegrana_serii.py` (#292)

```
python3 tools/przegrana_serii.py KATALOG [--polityka SPEC] [--out PLIK.json]
```

Czyta `KATALOG/pomiar.json` i pliki z `kawalki`. Dla `zakonczenie` innego niż `przegrana` wypisuje komunikat i kończy
kodem 0. Dla `przegrana` odtwarza ostatnią tackę z logu (plansza z jej pojawienia się i trzy klocki), sprawdza przeglądem
wyczerpującym (`board.tray_playable`), czy dało się ją ułożyć w całości, i porównuje ruchy mostu z wyborem polityki
`--polityka` (domyślnie `arms.candidate.spec` z `bench/record.json`; uwaga na stderr, gdy różni się od `polityka` serii)
na tych samych zalogowanych stanach — dla ostatniej i poprzedniej tacki. Zawsze kod 0; werdykt w stdout i w `--out`.
Gdy ostatnia tacka była ułożona w całości, a po ostatnim ruchu jest wiersz `okno: brak_ruchu_ponowny_odczyt` (#299),
narzędzie diagnozuje tackę z tego wiersza (w `dane.tacka_smierci`) zamiast `nowa_tacka_niezalogowana`: plansza
niezgodna z `expected` → `rozjazd_mostu`, tacka nieukładalna → `tacka_nieukladalna`.

| werdykt | znaczenie |
|---|---|
| `tacka_nieukladalna` | tacka, przy której padła gra, nie dawała się ułożyć w całości — generator apki przeczy #249 |
| `slepa_plamka` | ułożenie istniało, a polityka w symulatorze wybiera te same ruchy co most (albo jej przeszukanie go nie widzi) |
| `rozjazd_mostu` | polityka w symulatorze gra inaczej niż most na tej samej planszy i tacce; albo `ok=false` przed ostatnim ruchem; albo koniec mimo legalnego ruchu wg odczytu (zły odczyt planszy/tacki) |
| `nieoceniane` | brak stanu do werdyktu; `powod`: `nowa_tacka_niezalogowana`, `ksztalt_nierozpoznany`, `brak_ruchow_z_pelna_tacka`, `budzet_wezlow_wyczerpany`, `polityka_niedostepna`, `zla_wielkosc_planszy`, `brak_wiersza_koniec_partii` |

Wiersz `koniec_partii` to odczyt nakładki ekranu końca (plansza i kształty-śmieci), a `observed` ostatniego ruchu bywa już
nakładką (`ok=false` bez znaczenia). Stan końcowy narzędzie bierze więc z `expected` ostatniego ruchu i tacki bez postawionego
klocka; most niesie go też w polu `przed_koncem` wiersza końca (`{board, tray}`). **Czego log nie niesie:** gdy ostatnia
tacka została ułożona w całości, nowa tacka, przy której padła gra, nie jest zapisana — werdykt `nieoceniane`
(`nowa_tacka_niezalogowana`); można ją odczytać ze zrzutu `zrzut_konca` ręcznie.

## Skórki i nakładki (s1) — `bridge.py` (#294)

Apka 10.7.5 zmienia w trakcie partii skórkę (tło, plansza, kolor klocków, kolor i waga cyfr licznika) i pokazuje nakładki;
seria s1 zakończyła tak 7 partii przerwaniem. Test na zrzutach: `tests/test_bridge_skorki.py`.

| skórka | rozpoznanie | uwagi |
|---|---|---|
| domyślna (granatowa, zielone i żółte klocki, białe cyfry) | `read_board`/`read_tray`/`read_hud_score` | `partia-9/kawalek_1/044_state.png` |
| różowa (bordowa plansza, różowe klocki, białe cyfry) | jw. | partie 2, 7, 8 |
| beżowa (brązowa plansza, zielone klocki, białe cyfry) | jw. | `partia-2/kawalek_2/054_state.png` |
| teal (jasne tło, turkusowe klocki i cyfry) | jw.; **nie jest menu głównym** — `is_main_menu_screen` wymaga też kafelka „Classic" (`MAIN_MENU_TILE_BOX`) | partie 4, 6 |
| drewniana (ceglasta rama, wielokolorowe klocki, białe cyfry; s2) | `read_board` poprawny; `read_tray` czytał S/Z/T/L jako pełne prostokąty (tło paska (173,89,58) przechodzi `is_block`; przyczyna przegranych s2 partii 2 i 3, `docs/seria/s2/przegrane.md`, #305) — **naprawione w #307** (komórki kształtu próbkowane w masce z odjętym tłem paska) | `partia-3/kawalek_3/087_state.png` |
| fioletowa (opalizujące tło, fioletowa plansza, niebieskie cyfry) | jw.; `read_tray` odejmuje tło paska (mediana, `TRAY_BG_DIST`) | `partia-2/kawalek_2/056_state.png`; w s1 tylko klatki z pustą planszą |

**7 cyfr licznika (#302).** Licznik ≥ 1 mln zajmuje cały pas HUD, więc `SCORE_BOX` obejmuje x 10–310 (wcześniej 60–260
obcinał skrajne cyfry i odczyt był `None`). Cienka smuga od krawędzi złotego rombu (≤ 3 px, < 10 wierszy) jest pomijana
przy podziale na glify w ścieżce tusz/tło. Partie 1 (beżowa) i 3 (domyślna z turkusowym rombem) czytają się w całości
poza klatkami z nakładką „+N”; różowa i granatowa skórka w tych partiach kończą się przed 1 mln.

**Combo i ponowny odczyt (#295).** Napis „Combo N" (zielone litery, „+1560") leży na planszy i `read_board` czyta litery jako
klocki (`partia-5/kawalek_4/048_state.png`: klocek z tacki ma miejsce, odczyt mówi, że nie). Detektora combo nie ma —
zamiast łatki na jedną nakładkę działa reguła ogólna: w trybie serii (`seria=True`) „brak legalnego ruchu" bez ekranu końca
(`is_game_over_screen`) to okno `brak_ruchu_ponowny_odczyt` (odczekanie `TRAY_DEAL_WAIT`, ponowny odczyt). Koniec
„brak legalnego ruchu wg odczytu" (→ `przerwanie`) dopiero, gdy ten sam stan wraca `NO_MOVE_REREAD_TRIES` (4) razy z rzędu;
zmiana odczytu zeruje licznik, ale wpisy liczą się do `PROGRESS_SAFEGUARD_TRIES`. Prawdziwa przegrana ma ekran końca i nadal
kończy się `koniec_partii`.

| nakładka | okno w logu | działanie |
|---|---|---|
| „Better than N%!" z pucharem (`is_trophy_overlay_screen`) | `nakladka_better_than` | czeka 1 s, nie dotyka ekranu, czyta ponownie |
| ekran startowy apki po restarcie (`is_splash_screen`: czerwone „O” i fioletowe „K” logo w `SPLASH_LOGO_BOX`) | `ekran_startowy` | czeka `SPLASH_WAIT` (3 s), nie dotyka ekranu; limit = `PROGRESS_SAFEGUARD_TRIES` wpisów (→ `przerwanie`). Nie jest końcem partii (#304: 4 fałszywe przegrane s2) |
| reklama wideo z „Skip” (`is_video_ad_screen`: czarna góra, szara pigułka, film) | `reklama_wideo` | stuka „Skip” (257, 34); przed `is_settings_screen`, bo ciemność myliła ją z Ustawieniami |
| pusta tacka przy niepustej planszy (`tray_awaiting_deal`) | `tacka_pusta_przejsciowo` | jw. — nowa trójka jeszcze nie dosypana, pusta tacka nie jest końcem gry |

Oba okna liczą się do bezpiecznika `PROGRESS_SAFEGUARD_TRIES` (12 z rzędu → `petla_bez_postepu`).

**Twardy restart (#318).** Zanim bezpiecznik zakończy kawałek, most robi jeden `hard_restart_app` (`am force-stop` + `restart_app`; sam
`restart_app` przy oknie w procesie apki jest no-opem) — też po `INTERACTIVE_AD_BACK_TRIES` nieudanych „>>” koła fortuny. Wpis ma
`okno: restart_twardy`, `okno_przed_restartem`, `licznik_przed`, `licznik_po`; ciąg liczy od nowa, drugi ciąg bez ruchu → `petla_bez_postepu`.
Licznik HUD po restarcie mniejszy niż przed, albo pusta plansza z tacką po niepustej → `okno: restart_utracil_partie` (`przerwanie`;
nowa partia nie jest grana dalej, bo seria przyjęłaby jej licznik jako fałszywy cel). Ekran końca partii nie restartuje. Pusta tacka przy pustej
planszy to nadal `plansza_pusta_przejsciowo`.

**Licznik HUD.** `read_hud_score` najpierw próbuje maski ciemnych cyfr skórki oryginalnej (`bridge_digits.npz`), a gdy ta nie
daje odczytu — rozdzielenia tło/tusz (kolor cyfr = najczęstszy kolor odległy od tła) i wzorców `bridge_digits_ink.npz`
(`tools/wzorce_hud.py`). Nie umie: licznika pod przyciemnioną nakładką pucharu i klatek z animacją rombu — zwraca `None`. Złoty romb za cyframi na granatowej skórce (#297) czyta się: odczyt tło/tusz odcina wiersze z pojedynczymi pikselami rombu (`HUD_ROW_MIN_FRAC`); nieczytelne zostają klatki z nakładką „+N” na cyfrach.
Ścieżka ciemna dostaje `uint8`: wzorce powstały z tej reprezentacji, a `int` ze `screenshot()` dawał `None` także na skórce
oryginalnej (przed #294 licznik w serii nie czytał niczego).

**Zabijanie gry przez Play (#304).** ~16 min po starcie emulatora `installPackageLI` usług Google zabijał grę (logcat
`docs/seria/s2/partia-{1,4}/logcat_*.txt`). `tools/start_apki.sh` po udanym starcie robi `pm disable-user --user 0
com.android.vending`: sklep nie aktualizuje już pakietów w trakcie partii, a gra niczego z niego nie potrzebuje. Wybór
ponad `settings put global auto_update…`: te ustawienia nie obejmują aktualizacji usług Google. Skutek wyjdzie w następnym przebiegu.
