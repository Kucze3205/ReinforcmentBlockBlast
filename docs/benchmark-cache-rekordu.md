# Cache ramienia rekordu w `benchmark.py` (#219)

## Problem

Każdy plik `@beam=128` przy suficie 4000 (300 seedów) trwa 15–20 min (`duration_s` w
`bench/213-*.json`: 887–1188 s). Ramię rekordu (`--record`) to ~połowa tego czasu, a w sesji
złożonej z kilku plików (patrz historia commitów `bench #213: ...`) jest to **ten sam** ramię, na
tych samych seedach stałych, liczone od nowa w każdym pliku.

## Rozwiązanie: `--record-from` + `--keep-record-scores`

Dwie nowe, w pełni opcjonalne flagi `benchmark.py`. Bez nich wynik jest bitowo taki sam jak przed
#219 (kryterium akceptacji #219).

- `--keep-record-scores` — nie ucina wyników per seed (`scores`) zestawu **stałego** ramienia
  `record` z pliku wyjściowego. Bez tej flagi `strip_scores` usuwa je tak jak dotąd (rekord ma być
  czytelny, nie pełny). Plik wyprodukowany z tą flagą może posłużyć jako źródło dla kolejnego
  przebiegu.
- `--record-from <plik.json>` — zamiast liczyć ramię `record` od nowa, bierze jego zestaw **stały**
  z podanego pliku `bench/*.json`, o ile plik go przechowuje (`--keep-record-scores` przy jego
  produkcji) i zgadzają się:
  - `source_hashes` (odcisk plików, które wpływają na wynik — bit w bit),
  - `config` (sufit ruchów, `n_seeds`, `epsilon`, próg, plik seedów stałych, sól rotowanych),
  - `spec` ramienia `record` (ta sama polityka, ten sam plik wag, te same parametry przeszukania),
  - `weights_hash` ramienia `record` (wykrywa podmianę pliku wag pod tą samą nazwą).

Każda niezgodność kończy przebieg statusem `status: blocked` i `blocked_reason` nazywającym pole
(`source_hashes` / `config` / `spec` / `weights_hash` / brak zapisanych wyników per seed) —
**nigdy ciche przeliczenie**.

### Zestaw rotowany liczy się zawsze

Seedy rotowane zależą od soli `issue` (`rotated_seeds(config, issue)`), więc ramię policzone dla
issue A mierzyłoby inną pulę niż to samo issue B. `--record-from` cache'uje **wyłącznie** zestaw
stały; zestaw rotowany ramienia `record` jest liczony na nowo przy każdym przebiegu, niezależnie od
`--record-from`.

### `--shard`

`--record-from` nie jest wspierane razem z `--shard` (odmowa na starcie, kod wyjścia != 0) —
kawałek `K/N` gra inny podzbiór seedów niż pełny plik źródłowy, więc porównanie sparowane
(`paired_delta`) na wspólnych seedach by się rozjechało.

## Wzór polecenia dla roli bench

Pierwszy plik sesji (liczy ramię rekordu od nowa i zapisuje jego wyniki per seed):

```
python3 benchmark.py --candidate <spec-kandydata-1> --record <spec-rekordu> --previous <spec-poprzednika> \
    --issue <N> --keep-record-scores --out bench/<N>-<etykieta-1>.json
```

Kolejne pliki tej samej sesji, ten sam `--record`, ta sama gałąź kodu (identyczne `source_hashes`):

```
python3 benchmark.py --candidate <spec-kandydata-2> --record <spec-rekordu> --previous <spec-poprzednika> \
    --issue <N> --record-from bench/<N>-<etykieta-1>.json --out bench/<N>-<etykieta-2>.json
```

Jeśli `--record-from` odmówi (np. commit się zmienił między plikami sesji), plik po prostu wychodzi
jako `status: blocked` z nazwą niezgodnego pola — trzeba albo zacząć nową sesję od pliku z
`--keep-record-scores`, albo pominąć `--record-from` i policzyć ramię rekordu od nowa.

## Nietknięte pliki

`game.py`, `scoring.py`, `generator.py`, `policies.py`, `ntuple.py`, `ntuple_native.c`,
`ntuple_native.py`, cały katalog `bench/` — bez zmian z tej sesji. Dotknięte celowo: `benchmark.py`
(flagi `--record-from`, `--keep-record-scores`, funkcje `load_record_cache`,
`cached_record_fixed`, `strip_scores` z nowym parametrem), testy
(`tests/test_benchmark_record_from.py`). `reward_shape_changed: no` — zmiana dotyczy wyłącznie
narzędzia pomiarowego, nie polityki ani nagrody.
