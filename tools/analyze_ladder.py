"""
Drabinka punktow za linie (#33): jaka jednostka U(combo) i o ile rosnie combo.

Wejscie: `moves.jsonl` z przebiegow mostu. Dla kazdego postawienia liczy z logu
liczbe czyszczonych linii i reszte punktow po odjeciu komorek klocka, a potem
odtwarza combo gry hipoteza "combo rosnie o liczbe linii" i szuka drabinki
(granice schodkow, ich wysokosci), ktora zgadza sie z najwieksza liczba odczytow.

    python tools/analyze_ladder.py bridge-out/moves.jsonl [...]

Nie dotyka emulatora. Odczyty licznika psuje animacja przewijania, wiec dopasowanie
jest wieksze-lepsze, nie wszystko-albo-nic: ranking granic pokazuje, ktora wygrywa.
"""
import itertools
import json
import sys


def events(paths):
    """(combo gry po ruchu, linie, reszta punktow) dla kazdego czyszczacego postawienia."""
    out = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
        partia, combo, counter = None, 0, 3
        for r in rows:
            if "end" in r or r.get("move") is None:
                continue
            if r.get("partia", 0) != partia:
                partia, combo, counter = r.get("partia", 0), 0, 3
            piece = r["tray"][r["move"]["slot"]]
            if not piece:
                continue
            board = [row[:] for row in r["board"]]
            for dy, row in enumerate(piece):
                for dx, cell in enumerate(row):
                    if cell:
                        board[r["move"]["y"] + dy][r["move"]["x"] + dx] = 1
            lines = sum(all(row) for row in board) + sum(all(board[i][j] for i in range(8)) for j in range(8))
            remaining = sum(1 for s in r["tray"] if s) - 1
            if lines:
                combo += lines
                counter = 3 + remaining
                if r.get("score") is not None and r.get("score_after") is not None:
                    out.append((combo, lines, r["score_after"] - r["score"] - sum(map(sum, piece))))
            elif counter <= 1:
                combo, counter = 0, 3
            else:
                counter -= 1
    return out


def fit(evs, b1, b2, u2, u3):
    def unit(k):
        return 10 if k < b1 else (u2 if k < b2 else u3)
    return sum(1 for k, l, res in evs if res == k * unit(k) * (1 if l == 1 else l * (l - 1)))


def main(paths):
    evs = events(paths)
    ranking = sorted(((fit(evs, b1, b2, u2, u3), b1, b2, u2, u3)
                      for b1, b2 in itertools.combinations(range(2, 20), 2)
                      for u2, u3 in itertools.product((12, 15, 20), (15, 20, 25, 30))), reverse=True)
    print(f"czyszczen z odczytem: {len(evs)}; najwyzsze combo: {max(k for k, _, _ in evs)}")
    print("najlepsze drabinki (zgodnych, schodek2 od, schodek3 od, U2, U3):")
    for row in ranking[:5]:
        print("  ", row)


if __name__ == "__main__":
    main(sys.argv[1:])
