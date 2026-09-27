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
