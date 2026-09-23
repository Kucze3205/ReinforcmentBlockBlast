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
* **Z-6 — rozkład.** Rozkłada dobór na kubełki zapełnienia planszy. Jeśli rozkład
  zależy od stanu planszy, generator symulatora trzeba przepisać na warunkowy.

Pomiar liczy **tacki**, nie sloty: gra dobiera trójkę naraz i dopiero po jej
opróżnieniu losuje następną, więc trzy kolejne wpisy logu niosą tę samą trójkę.
"""
import collections
import json
import os
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
    """Przewidywany przyrost punktów vs odczytany z ekranu. Zwraca (zgodne, rozbieżne, ślepe)."""
    game = Game()
    ok = bad = blind = 0
    for row, nxt in zip(rows, rows[1:] + [{}]):
        if "move" not in row:
            continue
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


def census(samples):
    """Z-5: ile unikalnych kształtów, które spoza puli symulatora."""
    counts = collections.Counter()
    for _, tray in samples:
        counts.update(json.dumps(s) for s in tray)
    unknown = {k: v for k, v in counts.items() if k not in POOL}
    return counts, unknown


def by_fill(samples, buckets=(0, 8, 16, 24, 32, 64)):
    """Z-6: rozkład typów klocków w kubełkach zapełnienia planszy.

    Gdyby dobór był ślepy na planszę, każdy kubełek dałby ten sam rozkład.
    """
    table = collections.defaultdict(collections.Counter)
    for fill, tray in samples:
        lo = max(b for b in buckets if b <= fill)
        for shape in tray:
            piece = POOL.get(json.dumps(shape))
            table[lo][TYPE_NAME.get(piece.type_index, "?") if piece else "spoza puli"] += 1
    return table


def main(paths):
    rows = []
    for path in paths:
        run = load(path)
        print(f"\n== {path}: {len(run)} wpisów, koniec: {run[-1].get('end', 'wyczerpany limit ruchów')}")
        ok, bad, blind = check_scoring(run)
        print(f"   punktacja: {ok} zgodnych, {bad} rozbieżnych, {blind} bez odczytu wyniku")
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

    print("\n== Z-6: rozkład typów wg zapełnienia planszy")
    table = by_fill(samples)
    names = sorted({n for c in table.values() for n in c})
    print("   zapełnienie | n   | " + " ".join(f"{n[:7]:>7}" for n in names))
    for lo in sorted(table):
        total = sum(table[lo].values())
        share = " ".join(f"{100 * table[lo][n] / total:6.1f}%" for n in names)
        print(f"   {lo:>10}+ | {total:<3} | {share}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("użycie: python tools/analyze_bridge.py <moves.jsonl> [...]")
    main(sys.argv[1:])
