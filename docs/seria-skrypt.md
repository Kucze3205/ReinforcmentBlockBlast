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

## Kody wyjścia i `zakonczenie`

| kod | `zakonczenie` | kiedy |
|---|---|---|
| 0 | `cel` | licznik apki ≥ progu na stabilnej klatce (odczyty zgodne). Klatka niestabilna ≥ progu **nie** kończy — gra idzie dalej |
| 1 | `przegrana` | ekran końca partii |
| 2 | `przerwanie` | nieznane okno, `petla_bez_postepu`, `plansza_zawieszona`, apka nie wraca po restarcie, limit minut, wyjątek |
| 3 | — | błąd argumentów |

`przerwanie` nie liczy się do serii. `przyczyna` ∈ `nieznane_okno`, `petla_bez_postepu`, `plansza_zawieszona`,
`apka_nie_wraca`, `limit_minut`, `brak_legalnego_ruchu_wg_odczytu` (most nie widzi legalnego ruchu), `brak_pliku_ruchow`,
`pusty_plik_ruchow`, `wyjatek: ...`; pole `okno` niesie nazwę okna, jeśli było.

## `KATALOG/pomiar.json`

Zapisywany atomowo (plik `.tmp` + `os.replace`) po każdym kawałku i na końcu.

| pole | opis |
|---|---|
| `polityka` | napis specyfikacji |
| `zakonczenie` | `w_toku` do końca, potem `cel`/`przegrana`/`przerwanie` |
| `przyczyna`, `okno` | patrz wyżej (`null` dla `cel`/`przegrana`/`w_toku`) |
| `licznik_apki` | `{wartosc, odczyty, stabilny, zrzut}` — ostatni odczyt po kawałku; `zrzut` to PNG w `KATALOG` |
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
