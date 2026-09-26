# Szum oceny kandydata: sigma wyniku i przeżycia

Zadanie: [#101](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/101), kontynuacja
pytania z [#89](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/89) i badania
`docs/research/ocena-zaszumionych-kandydatow.md`: ile partii przypada na kandydata w CEM
(`tools/tune_weights.py`, dziś `games_per_candidate=6` z [#81](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/81),
liczba wzięta z sufitu). **Ten dokument raportuje liczby, nie zmienia CEM** — decyzję, co z
nich wynika, podejmuje zadanie następne (zgodnie z mandatem #101).

## Metoda

Narzędzie: `tools/measure_score_noise.py`. Dla podanej polityki i wag rozgrywa `--n-games`
partii, każdą na osobnym seedzie z `tools.tune_weights.training_seeds()` — ten sam podział
seedów treningowych/benchmarkowych, którego używa CEM, więc pomiar mierzy dokładnie te seedy,
na których naprawdę odbywa się strojenie. Dla każdej partii zapisuje wynik (`score`) i
przeżycie (`survival` = `game.placements`, liczba postawień do końca partii albo do sufitu
ruchów). Z serii liczy: średnią, odchylenie standardowe (`sigma`, `statistics.pstdev`),
współczynnik zmienności (`cv = sigma/mean`) i błąd standardowy średniej
(`sem = sigma/sqrt(n)`). Korelacje wynik↔przeżycie (Pearson i Spearman z rang, `statistics.correlation`)
liczone partia po partii, na tej samej serii.

Zmierzono **150 partii** na `lookahead:weights.json` i **150 partii tych samych seedów**
(sól `salt=101` w obu wywołaniach) na `tray:weights.json` — to samo kryterium akceptacji #101
("na tej samej liczbie partii i tych samych seedach"). Surowe wyniki (poza zakresem zapisu tego
zadania, nie commitowane): `.session/tray_noise.json`, `.session/lookahead_noise.json`.

    python3 tools/measure_score_noise.py --policy tray --weights-file weights.json --n-games 150
    python3 tools/measure_score_noise.py --policy lookahead --weights-file weights.json --n-games 150

Czas: `tray` — 2 min 11 s na 150 partii (zgodne z `docs/lookahead.md`: ~11 ms/decyzja ×
~85 postawień). `lookahead` — ok. 5 min na 150 partii (zgodne z szacunkiem z issue #101,
~2,0 s/partia).

## Tabela: sigma wyniku i przeżycia (150 partii, `weights.json`)

| polityka | sygnał | średnia | sigma | CV (sigma/średnia) | SEM | SEM w % średniej |
|---|---|---:|---:|---:|---:|---:|
| `tray` | wynik | 3888,82 | 4423,98 | 1,14 | 361,22 | 9,29% |
| `tray` | przeżycie | 85,11 | 61,88 | 0,73 | 5,05 | 5,94% |
| `lookahead` | wynik | 4750,07 | 6036,91 | 1,27 | 492,91 | 10,38% |
| `lookahead` | przeżycie | 89,90 | 67,25 | 0,75 | 5,49 | 6,11% |

**Przeżycie ma wyraźnie mniejszy CV niż wynik, w obu politykach** — `0,73`/`0,75` wobec
`1,14`/`1,27`. To potwierdza podejrzenie z #92 zacytowane w issue #101: przeżycie jest sygnałem
o mniejszym rozrzucie względnym niż wynik. `lookahead` ma **wyższy** CV wyniku niż `tray`
(1,27 wobec 1,14) — głębsze przeszukanie nie obniża szumu względnego wyniku, mimo że podnosi
średnią (patrz `docs/lookahead.md`: to samo zjawisko, „wynik jest szumem, przeżycie mniej",
zaobserwowane tam na 40 partiach dla wariantów `samples`/`branch`).

## Korelacja wynik ↔ przeżycie, partia po partii

| polityka | Pearson | Spearman |
|---|---:|---:|
| `tray` | 0,898 | 0,945 |
| `lookahead` | 0,823 | 0,954 |

Korelacja jest silna i dodatnia w obu politykach, silniejsza w rangach (Spearman) niż liniowo
(Pearson) — zgodne z rozkładem grubo-ogonowym wyniku (paru partii o bardzo wysokim wyniku
psuje korelację liniową, ale nie rangową). Razem z niższym CV przeżycia to **dwa niezależne
argumenty za tym, że przeżycie jest kandydatem na tańszy sygnał selekcji** w CEM — czego to
zadanie **nie wdraża**, zgodnie z mandatem.

## Tabela: ile partii na kandydata

SEM przy `n` partii = `sigma / sqrt(n)` (te same `sigma` co wyżej, 150-partiowe). Najmniejsza
różnica między **dwoma niezależnie ocenianymi kandydatami o tej samej sigma** rozróżnialna na
poziomie 2 błędów standardowych: `2·sqrt(2)·SEM` (SE różnicy dwóch niezależnych średnich o
równej wariancji to `sqrt(2)·SEM`; próg wykrywalności to dwukrotność tego SE). **Założenie:
próby niezależne (różne seedy), nie sparowane** — `tune_weights.py` dziś ocenia kolejnych
kandydatów na tych samych 6 seedach przez cały przebieg CEM (CRN, patrz
`docs/research/ocena-zaszumionych-kandydatow.md` sekcja 1), co przy dodatniej korelacji między
kandydatami dałoby **mniejszy** próg niż tabela niżej — to nie jest tu mierzone.

### `tray:weights.json`

| partii/kandydata | SEM wyniku (% średniej) | SEM przeżycia (% średniej) | najmniejsza różnica wyniku przy 2 SEM (% średniej) | najmniejsza różnica przeżycia przy 2 SEM (% średniej) |
|---:|---:|---:|---:|---:|
| 6 | 46,44% | 29,68% | 131,36% | 83,95% |
| 16 | 28,44% | 18,18% | 80,44% | 51,41% |
| 32 | 20,11% | 12,85% | 56,88% | 36,35% |
| 64 | 14,22% | 9,09% | 40,22% | 25,71% |

### `lookahead:weights.json`

| partii/kandydata | SEM wyniku (% średniej) | SEM przeżycia (% średniej) | najmniejsza różnica wyniku przy 2 SEM (% średniej) | najmniejsza różnica przeżycia przy 2 SEM (% średniej) |
|---:|---:|---:|---:|---:|
| 6 | 51,88% | 30,54% | 146,75% | 86,38% |
| 16 | 31,77% | 18,70% | 89,87% | 52,90% |
| 32 | 22,47% | 13,22% | 63,55% | 37,40% |
| 64 | 15,89% | 9,35% | 44,93% | 26,45% |

Przy `games_per_candidate=6` (dzisiejsza wartość z #81) **próg wykrywalności na samym wyniku
przekracza 100% średniej** w obu politykach (131%/147%) — dwaj kandydaci o realnie różnej
jakości potrafią się zamienić miejscami w rankingu elity czystym szumem, chyba że różnica
między nimi jest ogromna. Przeżycie jest w tym samym punkcie wyraźnie ostrzejsze (84%/86%), ale
wciąż powyżej różnicy między sąsiednimi generacjami w logu #81 (np. gen. 3→4:
`elita_best 11025,67 → 9984,67`, spadek mimo że polityka miała się poprawiać — dokładnie ten
rodzaj szumu, o który pyta issue #89). Dopiero **32 partie** sprowadzają próg wykrywalności
wyniku poniżej 65% średniej, a przeżycia poniżej 40%.

## Zdanie o `sd_diff` z `bench/97-lookahead.json`

`bench/97-lookahead.json` (300 sparowanych seedów, zestaw stały benchmarku, nie seedy
treningowe) daje `sd_diff = 9490,99` dla różnicy `lookahead − tray` (obie na `weights.json`),
średnia ramienia `lookahead` `6171,04`, błąd standardowy różnicy `9490,99/sqrt(300) ≈ 548`
(≈8,9% średniej).

Moje pomiary dają **sigma pojedynczego ramienia** (nie sigma różnicy): `sigma(lookahead) =
6036,91`, `sigma(tray) = 4423,98`, obie na seedach treningowych (rozłącznych z benchmarkowymi).
Gdyby wyniki obu polityk na tym samym seedzie były niezależne, sigma różnicy wyniosłaby
`sqrt(6036,91² + 4423,98²) ≈ 7484,4` — **mniej niż zmierzone w benchmarku `9490,99`**. Liczby
się **nie składają w stronę zgodności**: rzeczywista sigma różnicy z benchmarku jest **większa**
niż suma niezależnych wariancji obu ramion, co przy CRN (te same seedy dla obu ramion w
`benchmark.py`) sugerowałoby raczej **ujemną** korelację wynik-po-wyniku między `lookahead` a
`tray` na tym samym seedzie — sprzeczne z intuicją CRN (łatwa mapa powinna podnosić wynik
obu polityk razem, dając dodatnią korelację i **mniejszą**, nie większą, sigma różnicy).

Nie rozstrzygam, czy to realny efekt (np. `lookahead` i `tray` różnie reagują na te same
trudne układy tacki — tam, gdzie `tray` ledwo przeżywa, dodatkowy poziom `lookahead` może
akurat tam zyskiwać najwięcej, co dawałoby ujemną kowariancję *różnicy* mimo dodatnich
pojedynczych sigm) czy artefakt innej populacji seedów (300 seedów benchmarku, mieszanka
stałych i rotowanych, wobec 150 seedów treningowych tutaj — różne rozkłady trudności map mogą
mieć różną sigma). **To jest luka, nie zgodność** — piszę to wprost, zgodnie z kryterium
akceptacji #101, zamiast upiększać rozbieżność.

## Nawiązanie do wariantów budżetu z `docs/research/ocena-zaszumionych-kandydatow.md`

Ten dokument dawał trzy warianty (A: populacja wg reguły CMA-ES, B: dwustopniowy race, C:
budżet-nadwyżka na potwierdzenie zwycięzcy) i explicite zostawiał `σ` jako jedyną brakującą
liczbę do policzenia którejkolwiek reguły OCBA/racing. Teraz `σ` jest zmierzone: rzędu
`4400`–`6000` dla wyniku (CV rzędu `1,1`–`1,3`) i `62`–`67` dla przeżycia (CV rzędu `0,73`–
`0,75`) na wagach `weights.json`. To potwierdza literaturowe ostrzeżenie z sekcji 2.1 tamtego
dokumentu (bound Hoeffdinga skaluje się z zakresem, nie z sigma) w praktyce: przy sigma tego
rzędu i 6 grach na kandydata, różnica dwóch kandydatów musi przekroczyć **~130% średniej wyniku**
(patrz tabela wyżej), żeby CEM ją w ogóle wiarygodnie rozróżnił bez pomocy CRN.

## Czego nie wiem

- Czy CRN, którego dziś używa `tune_weights.py` (te same seedy przez cały przebieg CEM),
  faktycznie obniża próg wykrywalności poniżej tabeli wyżej (liczonej dla prób niezależnych) —
  zależy od korelacji wyników **dwóch konkretnych wektorów wag** na tym samym seedzie, a ta
  zmienia się w trakcie zbiegania CEM (na starcie populacja jest szeroko rozrzucona, korelacja
  może być słabsza niż pod koniec). Nie zmierzyłem tej korelacji dla par kandydatów CEM — tylko
  korelację wynik↔przeżycie **tego samego** kandydata.
- Dlaczego `sd_diff` z `bench/97-lookahead.json` (9490,99, seedy benchmarku) wychodzi większe niż
  suma niezależnych wariancji moich pomiarów (seedy treningowe) — czy to różnica populacji
  seedów, czy realna ujemna kowariancja różnicy dwóch konkretnych polityk. Rozstrzygnąłby to
  dopiero pomiar sigma **obu** polityk na tych samych 300 seedach benchmarku, którego to zadanie
  nie robi (zadanie mówi wprost: seedy treningowe, rozłączne z benchmarkowymi).
- Czy sigma zależy od punktu w przestrzeni wag (zmierzyłem tylko `weights.json`, jeden punkt
  zbieżny CEM #81) — wektor startowy albo losowa wczesna populacja CEM (szeroko rozrzucona wokół
  `DEFAULT_WEIGHTS`) może mieć inną sigma niż skonwergowany optimum, co zmieniłoby próg
  wykrywalności w pierwszych generacjach względem ostatnich.
- Nie liczyłem tabeli "ile partii" dla `heuristic` (jeden pół-ruch w przód, najtańsza polityka) —
  poza zakresem kryteriów akceptacji #101 (te wymieniają tylko `tray` i `lookahead`), ale byłaby
  tania do domierzenia, gdyby przyszłe zadanie potrzebowało punktu odniesienia taniej polityki.
