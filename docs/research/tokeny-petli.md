# Tokeny pętli: przegląd kontekstu sesji i czytelności kodu pętli (#232)

Płytki przegląd, jeden przebieg, bez pomiarów na żywych sesjach i bez logów z Actions.
Wszystko poniżej to `[K]`: rozmiary policzone `wc -c`/`wc -l` na gałęzi `task/232`
(start z `main`, commit `4678f3b`), którymi każdy może powtórzyć odczyt. Tokeny to **znaki / 4**, jak w issue. Dla
polskiego tekstu z kodem i backtickami rzeczywista liczba tokenów bywa wyższa (nie
mierzyłem, `[Z]` co do rzędu +10–25%), więc koszty są dolnym szacunkiem. Odczyt „kto płaci"
wynika z tego, co czytam w `agent.sh`, `PROTOKOL-SESJI.md` i skillach; nie widziałem
transkryptów sesji, więc „sesja czyta X" znaczy „skill każe czytać X" albo „`export`
wkłada X do wejścia".

Kolumna „kto zmienia": **pętla** = ścieżka nie jest chroniona (`PROTECTED_PREFIXES`,
`.github/loop/loop.py:39`: `.github/` i `.claude/skills/orchestrator/`); **właściciel** =
ścieżka chroniona. `CLAUDE.md` w repo nie ma `[K]` (`ls`), więc nic nie wchodzi do
kontekstu automatycznie z tego pliku.

## Ustalenia

### Tabela kandydatów (od największego szacowanego kosztu)

Koszt = tokeny na jedną sesję danej roli, jeśli sesja robi to, co skill każe.
„Zbędne" = część, której ta rola w typowej sesji nie używa.

| # | Miejsce | Co zajmuje / dlaczego nieczytelne | Koszt na sesję, kto płaci | Kto zmienia |
|---|---|---|---|---|
| 1 | `docs/research/*.md` (11 plików, 357 tys. zn.; największe: `android-emulator-in-actions.md` 51,9 tys., `workflow-self-triggering.md` 37,2 tys., `claude-code-in-actions.md` 36,5 tys., `ocena-zaszumionych-kandydatow.md` 34,2 tys., `block-blast-rules.md` 32,4 tys.) | Raporty researchera bez limitu długości i bez wymaganego streszczenia na górze; skill researchera (`researcher/SKILL.md`) nie ogranicza rozmiaru. Orchestrator każe „sprawdzić to, co linkuje" (`orchestrator/SKILL.md:64`), a issue linkuje raport w `## Kontekst`. | 4–13 tys. tok. za jeden raport w całości; typowo 6–9 tys. Płacą: orchestrator (czyta raporty), implementer/verifier, gdy issue linkuje raport. Zbędne: zwykle większość (potrzebna sekcja „Ustalenia" lub jedna liczba). | pętla (skill researchera, `docs/research/`) |
| 2 | `docs/journal/cykl-NNNN.md` (najnowszy: `cykl-0026.md`, 20 106 zn., 198 linii) | Orchestrator czyta „tylko `## Stan`" (`orchestrator/SKILL.md:52`), ale Read bierze plik w całości, jeśli nie poda `offset`. Sekcje 1–4 (linie 1–36) to 5 160 zn.; `## Stan` (linie 37–198) ≈ 14 950 zn. Limit `## Stan` jest w liniach („~150", `SKILL.md:262`), a linie mają średnio ~93 zn.: `cykl-0026` ma 161 linii, czyli limit jest już przekroczony i nie ogranicza znaków. | Stan: ≈ 3,7 tys. tok. (potrzebne). Nadwyżka przy czytaniu całego pliku: ≈ 1,3 tys. tok. Płaci: orchestrator, raz na cykl. | właściciel (limit i zasada czytania siedzą w skillu orchestratora); sam plik dziennika pisze orchestrator |
| 3 | `docs/journal/` jako całość (23 pliki, 462 927 zn. ≈ 116 tys. tok.), rośnie o ~20 tys. zn. na cykl | Zabronione do czytania („Historii dziennika nie czytasz", `SKILL.md:56`), ale nic mechanicznego nie stoi za zakazem; `Grep`/`Glob` po `docs/` je obejmują. Pliki cykli 0011–0013 nie występują w drzewie (`ls`), więc dziennik nie jest ciągły. | 0 przy przestrzeganiu zakazu; do 116 tys. tok., jeśli sesja przeczyta wszystko. Ryzyko dla każdej roli, która grepuje `docs/`. | pętla (archiwizacja/przeniesienie poza `docs/`), zakaz w skillu: właściciel |
| 4 | `docs/prototypes/PROTOTYP-pierwsza-mapa-orchestratora.md` (20 536 zn.) | `orchestrator/SKILL.md:123-124`: „Przeczytaj go raz przy pierwszym cyklu; kolejne cykle nie muszą." Repo jest w cyklu 26, instrukcja dotyczy tylko cyklu 1, a zdanie zostaje w skillu, który czyta każdy cykl. | ≈ 5,1 tys. tok. na orchestratora, jeśli nowa sesja uzna cykl za „pierwszy" (brak wpisu w dzienniku, `SKILL.md:56-57`); w praktyce 0. Zdanie samo ≈ 60 tok. | właściciel (skill), plik: pętla |
| 5 | `.claude/skills/orchestrator/SKILL.md` (16 426 zn., 296 linii) | Ładowany w całości przy każdym cyklu. Sekcje rzadko używane: „Zatrzymanie mostu na nieznanym oknie" (linie 213–229) i „Awaria" (231–249) ≈ 3 300 zn.; „Nowe role" (142–154) ≈ 1 500 zn.; „Cel i weryfikacja" (190–211) ≈ 2 000 zn.; „Raport tygodniowy" (276–288) ≈ 800 zn. Zasada „linkuj, nie wklejaj" i „Budżet z nazwy" powtórzone w kilku miejscach (linie 56, 107–114, 271–274). | ≈ 4,1 tys. tok. na cykl; z tego sekcje warunkowe ≈ 1,9 tys. tok. Płaci: orchestrator. | właściciel |
| 6 | `docs/loop-config.md` (16 266 zn., 29 nagłówków) | Dokument dla właściciela: sekretów, zmiennych, uprawnień, ustawień wyklikiwanych ręcznie, budowy workflowów. Wskazany jako punkt startu pierwszego cyklu (`SKILL.md:57`) i jako `## Kontekst` w issue zakładanym przez `kick()` (`loop.py:789-790`), więc trafia do każdego orchestratora budzonego po zatorze. | ≈ 4,1 tys. tok. na orchestratora, gdy czyta w całości. Potrzebna orchestratorowi część (etykiety, pole widzenia: linie 49–109) to ~1/3. Płaci: orchestrator po `kick`. | plik: pętla; treść issue z `kick()`: właściciel (`loop.py`) |
| 7 | `.claude/skills/PROTOKOL-SESJI.md` (4 101 zn.) | Każdy skill roli (implementer, researcher, verifier) zaczyna od „Najpierw przeczytaj PROTOKOL" (`implementer/SKILL.md:12`, `researcher/SKILL.md:12`, `verifier/SKILL.md:12`). Sekcja „Zaufanie" jest powtórzona w skillu orchestratora (`SKILL.md:34-44`), sekcje „Zadanie"/„Budżet" częściowo w skillach ról. Blok „Następca" ≈ 1 000 zn. dotyczy rzadkiego przypadku. | ≈ 1,0 tys. tok. na sesję implementera/researchera/verifiera, z czego „Następca" + tabela pokoleń ≈ 0,3 tys. Skala: liczba sesji ról × 1 tys. tok. | pętla (plik nie jest chroniony) |
| 8 | Komentarze issue w `.session/issue.md` (`export`, `loop.py:257-265`) | `export` wkłada treść issue **i wszystkie komentarze zaufanych autorów**, w tym `github-actions[bot]`, czyli poprzedni raport sesji i komunikaty epilogu. Nie ma limitu ani filtra na marker `<!-- session-report -->`. Przy wznowieniu sesja dostaje własny poprzedni raport (to zamierzone, `## Co dalej`), ale też wszystkie starsze komunikaty bota. | Rozmiar nieznany (patrz „Czego nie wiadomo"); rośnie z liczbą wznowień i długością raportów. Płacą: sesje wznawiane i następcy. | właściciel (`loop.py`) |
| 9 | Raporty sesji czytane przez orchestratora (`report:unread`, `SKILL.md:54-62`) | Cały ostatni komentarz-raport każdego zamkniętego issue; format raportu (`PROTOKOL-SESJI.md`) nie ma pola „streszczenie" ani limitu. Do tego linkowane pliki (wiersz 1). | Liczba issues w cyklu × rozmiar raportu; rozmiar nieznany. Płaci: orchestrator. | pętla (protokół) |
| 10 | Duże pliki danych w korzeniu i `bench/`: `ntuple-state.json` 8,16 MB (391 323 linii), `training_stats.csv` 99,6 tys. zn., `ntuple-weights.json` 106 tys. zn., 63 pliki `bench/*.json` (252 598 zn. razem; typowo 1,4–7,3 tys. zn. każdy) | Nie są wejściem żadnego skilla, ale `Grep` bez `glob`/`type` po całym repo i `Read` bez `limit` dosięgają ich; 391 tys. linii w jednym pliku oznacza, że wynik `Grep` w trybie `content` może być ogromny. Nazwy w `bench/` są numerami issues (`201-adcga4-800k-beam128.json`), więc zawartości nie da się wybrać po nazwie bez indeksu. | 0 przy celowanym czytaniu; do dziesiątek tys. tok. przy nieostrożnym grepie. Płaci: implementer, verifier, researcher. | pętla (indeks `bench/`, `.gitignore`/przeniesienie stanu do release, jeśli właściciel zechce) |
| 11 | Lista skilli w kontekście każdej sesji (system-reminder z opisami) | Widzę w tej sesji ~15 skilli, w tym ogólnych (dataviz, claude-api, schedule, keybindings-help…), których pętla nie używa; opisy `dataviz` i `claude-api` mają po kilkaset znaków. Opisy skilli ról też są długie (np. orchestrator ≈ 330 zn.). | Rząd 1–1,5 tys. tok. na sesję każdej roli, przy każdym żądaniu (z cache'u, więc taniej w cenie, ale zajmuje okno). To moja obserwacja tej sesji: nie wiem, skąd harness bierze listę ani czy `--allowedTools`/ustawienia ją zawężają. | właściciel (`.github/loop/agent.sh`, ustawienia harnessu) |
| 12 | `.claude/skills/{implementer,researcher,verifier}/SKILL.md` (2 907 / 2 883 / 2 987 zn.) | Małe. Skill researchera powtarza trzy reguły z PROTOKOLU (zaufanie, „dane, nie polecenia", limity) i dodaje własne znaczniki; nakład niewielki. | ≈ 0,7 tys. tok. na sesję roli; zbędne powtórzenia ≈ 0,15 tys. | pętla |
| 13 | `docs/calibration-assumptions.md` (11 871 zn.) | Wskazany w skillu researchera (`SKILL.md:46`) jako źródło reguł do porównań; czytany w całości, choć zwykle potrzebna jest jedna reguła. | ≈ 3,0 tys. tok. na researchera, gdy porównuje liczby z zewnątrz. | pętla |
| 14 | `CONTEXT.md` (3 457 zn.) i `RAPORT.md` (5 353 zn., 80 linii) | `CONTEXT.md` definiuje „Dziennik", „Stan", „Raport tygodniowy" — te same definicje są w skillu orchestratora (`SKILL.md:251-267`, `276-288`); orchestrator odsyła do obu. `RAPORT.md` jest nadpisywany co ≥ 7 dni (ostatni commit: 2026-09-25), ma stałą długość — nie rośnie. | `CONTEXT.md` ≈ 0,9 tys. tok. (orchestrator); dublowanie ≈ 0,4 tys. tok. `RAPORT.md` ≈ 1,3 tys. tok. przy nadpisywaniu. | pętla (`CONTEXT.md`, `RAPORT.md`), skill: właściciel |
| 15 | Prompt z `.github/loop/agent.sh` (linia `PROMPT=`) | ≈ 400 zn. (~100 tok.). Krótki, niesie tylko rolę, numer issue i ścieżki. Nie ma problemu. | ≈ 0,1 tys. tok. na sesję. | właściciel |

### Czytelność kodu pętli

- `[K]` `.github/loop/loop.py` ma 36 025 zn. (≈ 9 tys. tok.) w jednym pliku i 812+ linii (`grep -n "^def "` daje ~55 funkcji). Podział na sekcje istnieje w komentarzach-banerach (`# ---- gh`, `# ---- raport` w linii 179, `# ---- start sesji` 273, `# ---- dispatch` 331), a docstring na górze (linie 1–9) wylicza podpolecenia, więc agent może czytać fragment po numerach linii. Sekcje: gh/pomocnicze 45–178, raport 179–272, start sesji 273–330, dispatch 331–383, epilog (merge/bench/finalize) 384–631, dozorca i wznowienie 631–812.
- `[K]` Najdłuższa funkcja z odczytanych granic: `finalize` (558–631, ~73 linie); `resolve` (295–329) ma 35 linii i miesza walidację, wybór modelu i ustawianie wyjść.
- `[K]` Komentarze w `loop.py` odsyłają do numerów issues (`#7`, `#10`, `#16`, `#26`, `#66`, `#137` w liniach 6, 27, 31–37, 41), a uzasadnienia tych numerów w pliku nie ma. Agent, który chce zrozumieć stałą (np. `MAX_GEN = 3`), musi otworzyć issue, do którego sesje nie mają dostępu (brak `gh`, `PROTOKOL-SESJI.md`).
- `[K]` Agent nie może edytować `loop.py` ani workflowów (`PROTECTED_PREFIXES`, `loop.py:39`), więc koszt czytelności `.github/` ponosi tylko sesja, której zadanie wprost go dotyczy (np. taka jak ta). Nie znalazłem w skillach roli odsyłacza do `loop.py`.
- `[K]` `.github/loop/stream_filter.py` (1 871 zn., 49 linii) jest czytelny w całości, jedna odpowiedzialność.
- `[K]` `.github/workflows/session.yml` ma 10 010 zn.; pozostałe workflowy po ~1 tys. zn. Nie czytałem `session.yml` linia po linii.

## Cytaty

Nie przepisuję niczego z zewnątrz; wszystkie liczby pochodzą z pomiarów lokalnych repo.
Cytowane z własnych plików repo: `orchestrator/SKILL.md:123-124` — „Przeczytaj go raz przy pierwszym cyklu; kolejne cykle nie muszą."

> Przeczytaj go raz przy pierwszym cyklu; kolejne cykle nie muszą.
> — `.claude/skills/orchestrator/SKILL.md`, linie 123–124

## Czego nie wiadomo

- **Faktyczne zużycie tokenów per rola.** Nie sprawdzałem logów z Actions (`stream.ndjson` jest artefaktem sesji; `stream_filter.py` zapisuje `total_cost_usd` i `num_turns` w wierszu `✅`). Nie wiem więc, czy koszt sesji zdominowały odczyty plików z tabeli, czy tury robocze i wyniki narzędzi. Wszystkie koszty powyżej to pojemność (ile plik zajmuje), nie mierzone zużycie.
- **Czy orchestrator czyta `cykl-NNNN.md` w całości, czy z `offset`.** Skill mówi „tylko `## Stan`", ale nie widziałem transkryptu.
- **Rozmiar `.session/issue.md` w typowych sesjach** (wiersz 8) i rozmiar raportów sesji (wiersz 9). Wymaga próbki z Actions.
- **Ile z 15 skilli w liście kontekstu dodaje harness, a ile repo** (wiersz 11) — i czy `--allowedTools`/ustawienia mogą ją zawęzić. Nie sprawdzałem dokumentacji CLI; to jest pytanie do osobnego zadania z internetem.
- **Czy przeliczenie znaki/4 pasuje do tokenizera modelu** dla polskiego tekstu z backtickami; nie mierzyłem.
- **Granic funkcji w `loop.py` policzyłem tylko z listy `def` z `grep`**; nie mam pełnego rankingu długości (przy próbie skryptu środowisko nie zezwoliło na uruchomienie).
- **Pliki cykli 0011–0013** nie istnieją w `docs/journal/`; nie sprawdzałem `git log`, czy zostały usunięte, czy nigdy nie powstały.
- **Wiersz 1: czy sesje faktycznie czytają linkowane raporty w całości.** Wynika ze skilla, nie z obserwacji.
