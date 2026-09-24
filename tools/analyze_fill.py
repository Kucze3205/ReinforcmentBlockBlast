"""
Czy gra ratuje gracza przed niegrywalną tacką (#37): przeliczenie logu z polityką `fill`.

Wejście: jeden albo więcej `moves.jsonl` z przebiegów mostu z `POLICY=fill`. Dla każdej
tacki dobranej przez grę pyta o dwie rzeczy:

* **ile było niegrywalnych** — żywa: nic się nie mieści (koniec partii przy dobraniu);
  cała: trzech klocków nie da się postawić po kolei;
* **ile powinno być przy ślepym losowaniu** na tej samej planszy — suma
  `p_dead(plansza)` po wszystkich tackach, licząc z próbki ślepych tacek.

Gra, która pilnuje grywalności, da obserwowane ≪ oczekiwane. Ślepa da obserwowane ≈
oczekiwane. Poissona używamy tylko jako miary, jak bardzo zero jest zaskakujące.

Tacka jest *dobierana* na granicy trójek: po każdym trzecim postawieniu w partii.
Gdy dobrana tacka jest martwa, ekran końca zakrywa tackę, więc jej kształtów nie znamy —
wiemy tylko, że przy planszy z tego wpisu gra zakończyła partię na granicy. Dla „żywej"
to wystarcza (nic się nie mieści ⇒ koniec), dla „całej" tacka martwa-żywa jest też
martwa-cała.
"""
import collections
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playability import all_fit, any_fits, p_dead, sample_trays, to_mask

GAME_ENDS = ("koniec partii", "brak legalnego ruchu wg odczytu")


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def boundaries(rows):
    """Tacki dobrane przez grę: (plansza, tacka albo None, czy partia skończyła się od razu).

    Granica to wpis, przed którym partia ma za sobą 3k udanych postawień, k ≥ 1.
    Koniec partii w środku trójki (3k+1, 3k+2) osobno: to klocki, które nie weszły,
    a nie dobór gry.
    """
    out, mid_ends = [], []
    moves = collections.Counter()
    for row in rows:
        k = moves[row.get("partia", 0)]
        tray = row.get("tray") or []
        full = len(tray) == 3 and all(tray)
        if k and k % 3 == 0:
            if "end" in row:
                if row["end"] in GAME_ENDS:
                    out.append((row["board"], tray if full else None, True))
            elif full:
                out.append((row["board"], tray, False))
        elif k and row.get("end") in GAME_ENDS:
            mid_ends.append((row["board"], tray if full else None))
        if "move" in row:
            moves[row.get("partia", 0)] += 1
    return out, mid_ends


def empirical_trays(rows, n=300, seed=1):
    """Ślepe tacki z brzegowego rozkładu kształtów widzianych w tym biegu, sloty niezależnie."""
    shapes = [s for r in rows for s in (r.get("tray") or []) if s]
    if not shapes:
        return []
    rng = random.Random(seed)
    return [[rng.choice(shapes) for _ in range(3)] for _ in range(n)]


def poisson_cdf(k, mu):
    return sum(math.exp(-mu) * mu ** i / math.factorial(i) for i in range(k + 1))


def report(name, bounds, trays):
    e_any = e_all = 0.0
    o_any = o_all = 0
    for grid, tray, ended in bounds:
        mask = to_mask(grid)
        e_any += p_dead(mask, trays)
        e_all += p_dead(mask, trays, whole=True)
        if ended:
            o_any += 1  # koniec partii przy dobraniu: nic się nie zmieściło
            o_all += 1
        elif tray:
            o_any += not any_fits(mask, tray)
            o_all += not all_fit(mask, tray)
    print(f"\n   [{name}] tacek {len(bounds)}")
    for label, o, e in (("żywa (nic się nie mieści)", o_any, e_any), ("cała (nie wejdą wszystkie)", o_all, e_all)):
        print(f"     {label:28s} obserwowane {o:3d}  oczekiwane {e:6.2f}  "
              f"P(≤ obs | ślepe) = {poisson_cdf(o, e):.3g}")


def main(paths):
    rows = []
    for path in paths:
        run = load(path)
        print(f"== {path}: {len(run)} wpisów")
        rows += run
    bounds, mid_ends = boundaries(rows)
    fills = [sum(map(sum, b[0])) for b in bounds]
    ends = collections.Counter(r["end"] for r in rows if "end" in r)
    print(f"\n== tacki dobrane przez grę: {len(bounds)}, śr. zapełnienie planszy "
          f"{sum(fills) / max(1, len(fills)):.1f} z 64")
    print("   powody końca wpisu: " + ", ".join(f"{k}: {v}" for k, v in ends.items()))
    print(f"   koniec partii w środku trójki (klocki, które nie weszły): {len(mid_ends)}")
    report("ślepe losowanie z generatora symulatora", bounds, sample_trays(300, seed=7))
    emp = empirical_trays(rows)
    if emp:
        report("ślepe losowanie z kształtów widzianych w biegu", bounds, emp)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("użycie: python tools/analyze_fill.py <moves.jsonl> [...]")
    main(sys.argv[1:])
