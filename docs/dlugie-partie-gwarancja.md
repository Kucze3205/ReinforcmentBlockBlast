# Długie partie z gwarancją tacki (#241)

Pomiar polityki `lookahead-ntuple:ntuple/survival-adce-400k.json@beam=B,samples=0,complete=1` (gwarancja z #239,
[gwarancja-tacki.md](gwarancja-tacki.md)) na partiach do 20000 postawień (sufit benchmarku to 4000). Narzędzie:
`tools/measure_death_avoidability.py`, konfiguracja `docs/data/241-config-20k.json` (jak `bench/config.json`, `move_cap` = 20000),
16 pierwszych seedów stałych, `--jobs 4`. Dane: `docs/data/241-long-beam{8,32,128}.json`. Każdy przebieg zmieścił się
w jednym poleceniu (bez dzielenia na partie).

## Wynik

| B | śmierci | `n_capped` | średnia pkt | mediana pkt | min–max pkt | śr. postawień | pkt/postawienie | postawień/s (4 procesy) | `elapsed_s` |
|---|---|---|---|---|---|---|---|---|---|
| 8 | 0 | 16/16 | 2 109 700 | 2 123 985 | 1 972 675 – 2 291 510 | 20000 | 105,5 | 3791 | 84,4 |
| 32 | 0 | 16/16 | 2 603 193 | 2 606 987 | 2 391 242 – 2 917 115 | 20000 | 130,2 | 1694 | 188,9 |
| 128 | 0 | 16/16 | 2 818 480 | 2 821 041 | 2 531 350 – 3 335 579 | 20000 | 140,9 | 445 | 718,3 |

**Śmierci: zero na 48 partiach.** Wszystkie partie doszły do sufitu 20000, więc lista „dla każdej śmierci: `a_solvable`
i postawienie" jest pusta (`n_deaths = 0`, `a_search_miss = 0`). Przy `complete=1` polityka nie umarła ani razu w 960 000
postawień; droga do śmierci przez `REJECT_MAX_ATTEMPTS` w generatorze (tacka, której generator nie umiał dobrać) nie
wystąpiła. 48 partii nie wyklucza śmierci rzadszej niż ~1 na 300 000 postawień.

Postawień/s = suma postawień / `elapsed_s` (wall, 4 procesy). Dla B=128 jest to ~445 — zgodnie z ~425 z rekordu #234.

## Ekstrapolacja do 10 mln

Ponieważ partie nie umierają, średnia = sufit · pkt/postawienie. Na średnią 10 mln trzeba `1e7 / (pkt/postawienie)` postawień:

| B | potrzebne postawienia | najmniejszy sufit 4000·2^k | k | średnia przy tym suficie (szac.) |
|---|---|---|---|---|
| 8 | ~94 800 | 128 000 | 5 | ~13,5 mln |
| 32 | ~76 800 | 128 000 | 5 | ~16,7 mln |
| 128 | ~71 000 | 128 000 | 5 | ~18,0 mln |

Sufit 64 000 (k=4) dałby ~6,8 / 8,3 / 9,0 mln — za mało dla każdego B. Zakładam stałe pkt/postawienie; pomiar
dotyczy tylko pierwszych 20000 postawień, więc to założenie, nie pomiar.

Czas benchmarku 2×300 partii = 600 × 128 000 = 76,8 mln postawień, przy zmierzonej prędkości (4 procesy):

| B | bez kawałków | w 12 kawałkach |
|---|---|---|
| 8 | ~20 300 s ≈ 5,6 h | 12 × ~28 min |
| 32 | ~45 300 s ≈ 12,6 h | 12 × ~63 min |
| 128 | ~172 600 s ≈ 48 h | 12 × ~4,0 h |

Kawałki dzielą pracę po równo: łączny czas ten sam, gdy biegną kolejno na 4 procesach, krótszy, gdy równolegle na
osobnych runnerach. Sufit 128 000 przy B=128 nie mieści się w pojedynczym zadaniu; B=8 mieści się w kawałkach, kosztem
~25% mniej punktów na postawienie niż B=128 — i tak sięga 10 mln przy suficie 128 000.

Porównania z [ile-do-10-mln.md](ile-do-10-mln.md) (#119) nie przeliczałem w tym zadaniu.
