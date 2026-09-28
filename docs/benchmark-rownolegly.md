# `benchmark.py --jobs`: partie równolegle (#148)

Pełny przebieg dwóch ramion przestał mieścić się w limicie 3600 s na polecenie
([#144](../../issues/144): 3542 s). Runner ma 4 rdzenie, a `benchmark.py` liczył
partie (seed × ramię) po kolei na jednym. `--jobs N` liczy je w `N` procesach
przez `multiprocessing.Pool`; wynik na seed zależy tylko od seeda i polityki,
więc `Pool.map` — zwracający wyniki w kolejności zadań, nie ukończenia — daje
plik wyjściowy bitowo identyczny z `--jobs 1` (poza `duration_s`, i `sha`/`dirty`,
jeśli stan repo się zmienił między przebiegami).

## Pomiar: `lookahead` kontra `lookahead`, 30 seedów, `--jobs 1` vs `--jobs 4`

```
python3 benchmark.py --candidate lookahead --previous lookahead --issue 148 \
    --n-seeds 30 --jobs 1 --out .session/bench148/jobs1.json
python3 benchmark.py --candidate lookahead --previous lookahead --issue 148 \
    --n-seeds 30 --jobs 4 --out .session/bench148/jobs4.json
```

| `--jobs` | `duration_s` |
|---|---|
| 1 | 133.6 s |
| 4 | 69.4 s |

Przyspieszenie: **1.93×** na 4 rdzeniach (mniej niż 4× — narzut na start procesów
w `Pool` i to, że każdy proces roboczy odbudowuje politykę z `spec` przy starcie).
Oba rekordy identyczne poza `duration_s`/`sha`/`dirty`: te same `arms`, `deltas`,
`source_hashes` — zweryfikowane programowo (porównanie słowników JSON).

Ekstrapolacja na pełny przebieg #144 (3542 s, `--jobs 1`) przy podobnym
przyspieszeniu: ok. **1830 s** przy `--jobs 4` — z powrotem pod limitem 3600 s.

## Kawałki: `--shard K/N` i `tools/merge_bench.py` (#167)

`--jobs` przyspiesza jedno polecenie, ale samo polecenie wciąż musi zmieścić
się w limicie 3600 s. Koszt benchmarku rośnie z postępem partii (rekord #161:
1948,7 s), więc dalszy wzrost (więcej łat, dłuższe partie) potrzebuje podziału
na **osobne polecenia**, nie tylko procesy w jednym.

`--shard K/N` gra tylko seedy (stałe i rotowane) o indeksie `i` (0-based)
takim, że `i % N == K - 1` — tę samą pulę seedów co przebieg bez `--shard`,
przy każdym ramieniu. Plik kawałka niesie surowe wyniki per seed (potrzebne do
sparowanej różnicy po złożeniu) i pole `"shard": "K/N"`, żeby nikt nie wziął go
za pełny wynik. `tools/merge_bench.py` składa `N` kawałków w plik o tym samym
kształcie co przebieg bez `--shard` (agregaty — średnia, mediana, p10,
przeżycie, % uciętych — są niezależne od kolejności seedów, więc złożenie daje
`arms`/`deltas` bitowo równe pełnemu przebiegowi; `duration_s` to suma
kawałków). Odmawia (niezerowy kod wyjścia), gdy kawałki mają różny `sha`,
`issue`, `config`, specyfikację ramienia (polityka albo `weights_hash`), gdy
brakuje kawałka albo któryś się powtarza.

```
python3 benchmark.py --candidate <spec> --record <spec> --issue N --jobs 4 --shard 1/4 --out bench/N-x-shard1.json
...
python3 benchmark.py --candidate <spec> --record <spec> --issue N --jobs 4 --shard 4/4 --out bench/N-x-shard4.json
python3 tools/merge_bench.py --out bench/N-x.json bench/N-x-shard1.json bench/N-x-shard2.json bench/N-x-shard3.json bench/N-x-shard4.json
```
