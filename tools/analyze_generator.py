"""
Model generatora klocków (#38): czy wagi + filtr grywalności tłumaczą cały rozjazd z #30.

Trzy kandydaci na model doboru tacki, dopasowani do tacek z logów mostu:

* **A: ślepe wagi** — trzy niezależne losowania z brzegowego rozkładu typów;
* **B: wagi + filtr** — jak A, ale tacka, której trzech klocków nie da się postawić
  po kolei (`playability.all_fit`), jest odrzucana i losowana od nowa;
* **C: wagi warunkowane zapełnieniem** — osobny rozkład typów na kubełek planszy.

Miara to log-wiarygodność *tacki przy jej planszy*. B wyliczane przez symulację
(Z(plansza) = prawdopodobieństwo, że losowa tacka przejdzie filtr), wagi B dopasowane
iteracyjnie do zgodności oczekiwanych liczności typów z obserwowanymi.

Pytanie do modelu: czy B odtwarza (1) zależność od planszy i (2) nadwyżkę tacek
z powtórzonym typem, których żaden model wag nie tłumaczy? Jeśli tak, tacka nie
potrzebuje własnego parametru powtórzenia.

Użycie: python tools/analyze_generator.py <moves.jsonl> [...]
"""
import collections
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pieces import PIECE_POOL, PIECE_TYPES
from playability import all_fit, to_mask
from analyze_bridge import load

N_TYPES = len(PIECE_TYPES)
TYPE_OF = {json.dumps(p.shape): p.type_index for p in PIECE_POOL}
POSES = [len(p) for p in PIECE_TYPES]
SHAPES_OF = [[PIECE_POOL[i].shape for i in poses] for poses in PIECE_TYPES]


def unique_trays(paths):
    """Tacki ze wszystkich logów, bez duplikatów (te same przebiegi leżą w kilku katalogach)."""
    seen, out = set(), []
    for path in paths:
        rows = load(path)
        for row in rows:
            tr = row.get("tray", [])
            if "end" in row or len(tr) != 3 or not all(tr):
                continue
            if not all(json.dumps(s) in TYPE_OF for s in tr):
                continue
            k = json.dumps([row["board"], tr])
            if k in seen:
                continue
            seen.add(k)
            out.append((to_mask(row["board"]), sum(map(sum, row["board"])),
                        tuple(TYPE_OF[json.dumps(s)] for s in tr), tr))
    return out


def draw_piece(rng, w):
    t = rng.choices(range(N_TYPES), w)[0]
    return t, rng.choice(SHAPES_OF[t])


def draw_tray(rng, w, mask, filtered):
    while True:
        tray = [draw_piece(rng, w) for _ in range(3)]
        if not filtered or all_fit(mask, [s for _, s in tray]):
            return tuple(t for t, _ in tray)


def accept_rate(rng, w, mask, n=60):
    ok = 0
    for _ in range(n):
        tr = [draw_piece(rng, w)[1] for _ in range(3)]
        ok += all_fit(mask, tr)
    return max(ok, 0.5) / n


def repeat_stats(tray_types):
    two = sum(len(set(t)) < 3 for t in tray_types)
    three = sum(len(set(t)) == 1 for t in tray_types)
    return two / len(tray_types), three


def fit_filtered(data, iters=10, per=12, seed=1):
    """Wagi typów modelu B: iteracyjne dopasowanie oczekiwanych liczności do obserwowanych."""
    rng = random.Random(seed)
    obs = collections.Counter(t for _, _, tt, _ in data for t in tt)
    total = sum(obs.values())
    target = [max(obs[t], 0.5) / total for t in range(N_TYPES)]
    w = list(target)
    for _ in range(iters):
        exp = collections.Counter()
        for mask, _, _, _ in data:
            for _ in range(per):
                exp.update(draw_tray(rng, w, mask, True))
        et = sum(exp.values())
        w = [w[t] * target[t] / max(exp[t] / et, 1e-4) for t in range(N_TYPES)]
        s = sum(w)
        w = [x / s for x in w]
    return w


def loglik_blind(data, w):
    ll = 0.0
    for _, _, tt, _ in data:
        ll += sum(math.log(w[t] / POSES[t]) for t in tt)
    return ll


def loglik_filtered(data, w, seed=2):
    rng = random.Random(seed)
    ll = 0.0
    for mask, _, tt, _ in data:
        ll += sum(math.log(w[t] / POSES[t]) for t in tt) - math.log(accept_rate(rng, w, mask))
    return ll


def fit_by_fill(data, buckets=(0, 16, 24, 32, 64)):
    """Model C: brzegowe wagi osobno na kubełek zapełnienia (z wygładzeniem +1)."""
    tables = {}
    for lo in buckets[:-1]:
        c = collections.Counter(t for _, f, tt, _ in data if max(b for b in buckets if b <= f) == lo for t in tt)
        n = sum(c.values()) + N_TYPES
        tables[lo] = [(c[t] + 1) / n for t in range(N_TYPES)]
    return tables, buckets


def loglik_by_fill(data, model):
    tables, buckets = model
    ll = 0.0
    for _, f, tt, _ in data:
        w = tables[max(b for b in buckets if b <= f)]
        ll += sum(math.log(w[t] / POSES[t]) for t in tt)
    return ll


def simulate(data, w, filtered, seed=3, per=20):
    rng = random.Random(seed)
    out = []
    for mask, _, _, _ in data:
        out += [draw_tray(rng, w, mask, filtered) for _ in range(per)]
    return out


def main(paths):
    data = unique_trays(paths)
    print(f"{len(data)} unikalnych tacek")
    marg = collections.Counter(t for _, _, tt, _ in data for t in tt)
    n = sum(marg.values())
    w_blind = [marg[t] / n for t in range(N_TYPES)]
    obs2, obs3 = repeat_stats([tt for _, _, tt, _ in data])
    print(f"obserwowane: powtórzony typ {100 * obs2:.1f}%, trzy te same {obs3}")

    w_f = fit_filtered(data)
    m_c = fit_by_fill(data)
    ll_a, ll_b, ll_c = loglik_blind(data, w_blind), loglik_filtered(data, w_f), loglik_by_fill(data, m_c)
    k_a, k_b, k_c = N_TYPES - 1, N_TYPES - 1, 4 * (N_TYPES - 1)
    print(f"\n{'model':32}{'param':>6}{'logL':>10}{'AIC':>10}")
    for name, ll, k in (("A ślepe wagi", ll_a, k_a), ("B wagi + filtr grywalności", ll_b, k_b),
                        ("C wagi na kubełek zapełnienia", ll_c, k_c)):
        print(f"{name:32}{k:>6}{ll:>10.1f}{2 * k - 2 * ll:>10.1f}")

    print("\npowtórzenia w symulacji (na planszach z logu):")
    for name, w, flt in (("A", w_blind, False), ("B", w_f, True)):
        sim = simulate(data, w, flt)
        s2, s3 = repeat_stats(sim)
        print(f"  {name}: powtórzony typ {100 * s2:.1f}%, trzy te same {s3 * len(data) / len(sim):.1f} (przeskalowane)")

    print("\ntypy: obserwowane vs B po filtrze (udział %)")
    sim = simulate(data, w_f, True)
    cs = collections.Counter(t for tt in sim for t in tt)
    ns = sum(cs.values())
    for t in sorted(range(N_TYPES), key=lambda t: -marg[t]):
        name = PIECE_POOL[PIECE_TYPES[t][0]].name.rsplit("_", 1)[0]
        print(f"  {name:8} obs {100 * marg[t] / n:5.1f}  waga B {100 * w_f[t]:5.1f}  po filtrze {100 * cs[t] / ns:5.1f}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("użycie: python tools/analyze_generator.py <moves.jsonl> [...]")
    main(sys.argv[1:])
