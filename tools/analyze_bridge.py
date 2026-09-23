"""
Analiza zalogowanych przebiegów mostu (#30): pula klocków, rozkład doboru, punktacja.

Wejście: jeden albo więcej `moves.jsonl` z artefaktów przebiegu mostu. Narzędzie
nie dotyka emulatora — liczy wyłącznie z logu, więc ten sam plik da się przeliczyć
po każdej zmianie symulatora.

Trzy rzeczy naraz:

* **Punktacja.** Odtwarza przewidywanie `advance()` ruch po ruchu i zestawia je
  z przyrostem wyniku odczytanym z ekranu. To ta sama droga, którą liczy most,
  więc stary log da się sprawdzić kodem, którego w chwili jego powstania nie było.
* **Z-5 — pula.** Zlicza unikalne kształty tacek i mówi, które z nich nie należą
  do 41 poz symulatora. Kształt spoza puli jest wynikiem, nie usterką.
* **Z-6 — rozkład.** Dwa testy, bo dwa założenia symulatora padają osobno: czy
  tacka to trzy **niezależne** losowania i czy rozkład zależy od **planszy**.
  Oba odpowiadają permutacją, nie wzorem — próbka jest mała i skorelowana.
* **Odczyt.** Każdy pomiar wyżej opiera się na tym, że most czyta tackę dobrze.
  `read_errors` sprawdza to różnicą plansz, czyli poza kodem odczytu.

Pomiar liczy **tacki**, nie sloty: gra dobiera trójkę naraz i dopiero po jej
opróżnieniu losuje następną, więc trzy kolejne wpisy logu niosą tę samą trójkę.
"""
import collections
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import Game, advance
from pieces import PIECE_POOL, PIECE_TYPES, plausible

POOL = {json.dumps(p.shape): p for p in PIECE_POOL}
TYPE_NAME = {t: PIECE_POOL[poses[0]].name.rsplit("_", 1)[0] for t, poses in enumerate(PIECE_TYPES)}


def load(path):
    """Wpisy przebiegu; wpis kończący (`end`) zostaje, bo niesie powód zatrzymania."""
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def trays(rows):
    """Tacki, czyli świeże trójki: (zapełnienie planszy w chwili doboru, trzy kształty).

    Tacka jest świeża, gdy wszystkie trzy sloty są pełne. Trójka z pierwszego wpisu
    przebiegu bywa niepełna (most wchodzi w partię w losowym momencie) i wtedy odpada.

    Wpis kończący przebieg odpada zawsze: gdy gra znika z pierwszego planu, segmentacja
    czyta launcher i zwraca blob, który bez tego filtra wszedłby do puli jako „kształt
    spoza puli" i unieważnił cały pomiar Z-5.
    """
    out = []
    for row in rows:
        tray = row.get("tray", [])
        if "end" in row or len(tray) != 3 or not all(s and plausible(s) for s in tray):
            continue
        fill = sum(sum(r) for r in row["board"])
        out.append((fill, tray))
    return out


def check_scoring(rows):
    """Przewidywany przyrost punktów vs odczytany z ekranu. Zwraca (zgodne, rozbieżne, ślepe).

    Jeden plik może nieść kilka partii (most gra dalej po przegranej), a combo nie
    przechodzi przez koniec partii — stąd reset symulatora na granicy.
    """
    game = Game()
    partia = 0
    ok = bad = blind = 0
    for row, nxt in zip(rows, rows[1:] + [{}]):
        if "move" not in row:
            continue
        if row.get("partia", 0) != partia:
            game = Game()  # nowa partia zaczyna z zerowym combo i zerowym licznikiem
            partia = row["partia"]
        m = row["move"]
        gain, _ = advance(game, row["board"], row["tray"], m["slot"], m["x"], m["y"])
        before = row.get("score")
        after = row.get("score_after", nxt.get("score"))
        if before is None or after is None or after < before:
            blind += 1  # wynik nie maleje: spadek to błąd OCR, nie rozbieżność punktacji
        elif after - before == gain:
            ok += 1
        else:
            bad += 1
            print(f"  ruch {row['n']}: ekran +{after - before}, symulator +{gain} "
                  f"(combo {game.combo}, linie {game.last_lines_cleared})")
    return ok, bad, blind


def lifetimes(rows):
    """#32: ile ruchów żyje partia i co ją kończy.

    Partię kończy przegrana albo śmierć procesu. Przy śmierci wpis niesie werdykt
    `wznowienie` — jedyne miejsce, które mówi, czy gra odtworzyła planszę, czy
    zaczęła od zera, a od tego zależy wykonalność łańcucha 1M z #9.
    """
    moves = collections.Counter(r.get("partia", 0) for r in rows if "move" in r)
    ends = [(r["n"], r["end"], r.get("wznowienie", "")) for r in rows if "end" in r]
    return moves, ends


def census(samples):
    """Z-5: ile unikalnych kształtów, które spoza puli symulatora."""
    counts = collections.Counter()
    for _, tray in samples:
        counts.update(json.dumps(s) for s in tray)
    unknown = {k: v for k, v in counts.items() if k not in POOL}
    return counts, unknown


def read_errors(rows):
    """Swiadek odczytu tacki: co gra dolozyla do planszy wobec tego, co most przeczytal.

    Gdy ruch nie wyczyscil zadnej linii, roznica plansz przed i po jest dokladnie
    postawionym klockiem — a plansze most weryfikuje osobno (pole `ok`). To jedyne
    miejsce, w ktorym pomiar generatora daje sie obronic przed zarzutem, ze mierzy
    wlasna usterke odczytu, a nie gre (#34 pokazalo, ze taki zarzut jest realny).
    """
    hits = misses = 0
    for row in rows:
        if "move" not in row or "observed" not in row:
            continue
        before, after = row["board"], row["observed"]
        added = [(y, x) for y in range(8) for x in range(8) if after[y][x] and not before[y][x]]
        cleared = any(before[y][x] and not after[y][x] for y in range(8) for x in range(8))
        read = row["tray"][row["move"]["slot"]]
        if cleared or not added or not read:
            continue  # linia znikla: roznica plansz nie jest juz samym klockiem
        y0 = min(y for y, _ in added)
        x0 = min(x for _, x in added)
        h = max(y for y, _ in added) - y0 + 1
        w = max(x for _, x in added) - x0 + 1
        truth = [[0] * w for _ in range(h)]
        for y, x in added:
            truth[y - y0][x - x0] = 1
        hits += truth == read
        misses += truth != read
    return hits, misses


def _pairs(counts):
    """Ile par identycznych elementow w trojce."""
    return sum(v * (v - 1) // 2 for v in counts.values())


def tray_repeats(samples, reps=4000, seed=7):
    """Czy tacka to trzy niezalezne losowania.

    Symulator losuje trzy klocki niezaleznie. Test zestawia obserwowany udzial tacek
    z powtorzonym typem z tym, co daje losowanie niezalezne **z tego samego rozkladu
    brzegowego** — wiec mierzy wylacznie strukture tacki, nie wagi typow.
    """
    trays_types = [tuple(POOL[json.dumps(s)].type_index for s in tray) for _, tray in samples
                   if all(json.dumps(s) in POOL for s in tray)]
    n = len(trays_types)
    obs = sum(1 for t in trays_types if _pairs(collections.Counter(t)))
    obs3 = sum(1 for t in trays_types if len(set(t)) == 1)
    urn = [t for tray in trays_types for t in tray]
    rng = random.Random(seed)
    null = null3 = ge = 0
    for _ in range(reps):
        d = d3 = 0
        for _ in range(n):
            s = (rng.choice(urn), rng.choice(urn), rng.choice(urn))
            d += bool(_pairs(collections.Counter(s)))
            d3 += len(set(s)) == 1
        null += d
        null3 += d3
        ge += d >= obs
    return n, obs, obs3, null / reps, null3 / reps, (ge + 1) / (reps + 1)


def _chi2_fill(fills, trays_types, buckets=8):
    table = collections.defaultdict(collections.Counter)
    for fill, types in zip(fills, trays_types):
        table[min(fill // buckets, 4)].update(types)
    grand = collections.Counter()
    for c in table.values():
        grand.update(c)
    total = sum(grand.values())
    chi = 0.0
    for t in range(len(PIECE_TYPES)):
        for c in table.values():
            e = grand[t] * sum(c.values()) / total
            if e:
                chi += (c[t] - e) ** 2 / e
    return chi, table, grand


def board_dependence(samples, window=8, reps=3000, seed=5):
    """Z-6, wlasciwe pytanie: czy apka podglada plansze, losujac tacke.

    Statystyka to chi2 typ x zapelnienie, a rozklad zerowy powstaje przez losowe
    parowanie **calych tacek** z plansami — dzieki temu test nie zalamuje sie na
    korelacji wewnatrz tacki, ktora mierzy `tray_repeats`.

    Parowanie miesza tylko tacki z okna `window` kolejnych dobran tej samej partii.
    Bez tego ograniczenia zapelnienie i dryf rozkladu w czasie daloby zwiazek, ktorego
    nie ma: obie wielkosci rosna z numerem ruchu.
    """
    keep = [(f, tray) for f, tray in samples if all(json.dumps(s) in POOL for s in tray)]
    fills = [f for f, _ in keep]
    trays_types = [tuple(POOL[json.dumps(s)].type_index for s in tray) for _, tray in keep]
    obs, table, grand = _chi2_fill(fills, trays_types)
    rng = random.Random(seed)
    perm = list(trays_types)
    null = ge = 0.0
    for _ in range(reps):
        for lo in range(0, len(perm), window):
            block = trays_types[lo:lo + window]
            rng.shuffle(block)
            perm[lo:lo + window] = block
        v, _, _ = _chi2_fill(fills, perm)
        null += v
        ge += v >= obs
    return obs, null / reps, (ge + 1) / (reps + 1), table, grand


def main(paths):
    rows = []
    for path in paths:
        run = load(path)
        print(f"\n== {path}: {len(run)} wpisów, koniec: {run[-1].get('end', 'wyczerpany limit ruchów')}")
        ok, bad, blind = check_scoring(run)
        print(f"   punktacja: {ok} zgodnych, {bad} rozbieżnych, {blind} bez odczytu wyniku")
        moves, ends = lifetimes(run)
        print("   długość partii: " + ", ".join(f"{p}: {c} ruchów" for p, c in sorted(moves.items())))
        for n, end, rev in ends:
            print(f"   ruch {n}: {end}" + (f" -> {rev}" if rev else ""))
        rows += run

    samples = trays(rows)
    counts, unknown = census(samples)
    print(f"\n== Z-5: {len(samples)} tacek = {3 * len(samples)} dobrań")
    print(f"   unikalnych kształtów: {len(counts)} z {len(PIECE_POOL)} poz symulatora")
    print(f"   niewidziane poz: {len(PIECE_POOL) - len([k for k in counts if k in POOL])}")
    if unknown:
        print("   KSZTAŁTY SPOZA PULI (wynik, nie usterka):")
        for shape, n in sorted(unknown.items(), key=lambda kv: -kv[1]):
            print(f"     {n:4d}x {shape}")

    hits, misses = read_errors(rows)
    print(f"   odczyt tacki potwierdzony planszą: {hits} zgodnych, {misses} błędnych")

    n, obs, obs3, null, null3, p = tray_repeats(samples)
    print(f"\n== Z-6a: tacka jako całość, {n} tacek")
    print(f"   z powtórzonym typem: {obs} ({100 * obs / n:.1f}%) wobec {null:.1f} ({100 * null / n:.1f}%) "
          f"przy trzech niezależnych losowaniach z tego samego rozkładu — p = {p:.4f}")
    print(f"   trzy te same typy: {obs3} wobec {null3:.1f}")

    chi, null_chi, p_fill, table, grand = board_dependence(samples)
    print("\n== Z-6b: czy apka podgląda planszę")
    print(f"   chi2 typ x zapełnienie = {chi:.1f} wobec {null_chi:.1f} przy losowym parowaniu "
          f"tacka<->plansza w oknie 8 tacek — p = {p_fill:.4f}")
    names = [TYPE_NAME[t] for t in range(len(PIECE_TYPES))]
    print("   zapełnienie | n   | " + " ".join(f"{x[:7]:>7}" for x in names))
    for lo in sorted(table):
        total = sum(table[lo].values())
        share = " ".join(f"{100 * table[lo][t] / total:6.1f}%" for t in range(len(PIECE_TYPES)))
        print(f"   {8 * lo:>7}-{8 * lo + 7:<3} | {total:<3} | {share}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("użycie: python tools/analyze_bridge.py <moves.jsonl> [...]")
    main(sys.argv[1:])
