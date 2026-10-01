#!/usr/bin/env python3
"""Partia serii weryfikacyjnej bez agenta (#283): gra jedną partię do końca kawałkami mostu.

Dostaje emulator z apką na planszy (start apki robi job, jak `tools/bridge.sh`); nie woła `git`.
Zakończenie (pole `zakonczenie` w `pomiar.json`, kod wyjścia):
  cel        0  licznik apki >= progu na stabilnej klatce (dwa zgodne odczyty, spójne z poprzednimi)
  przegrana  1  ekran końca partii (nie stuka „Play”)
  przerwanie 2  nieznane okno, petla_bez_postepu, plansza_zawieszona, restart_utracil_partie (#318), apka nie wraca, limit minut, wyjątek
  (błąd argumentów: 3)
Opis interfejsu: docs/seria-skrypt.md.
"""
import argparse
import json
import os
import statistics
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (REPO_ROOT, os.path.join(REPO_ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import bridge
import score_from_trajectory

EXIT = {"cel": 0, "przegrana": 1, "przerwanie": 2}
STABLE_TRIES = 6
LAST_MOVES = 5


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"{self.prog}: błąd: {message}", file=sys.stderr)
        sys.exit(3)


def build_parser():
    p = _Parser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("polityka", help="napis specyfikacji polityki, jak argv[2] mostu (np. greedy)")
    p.add_argument("katalog", help="katalog wyjściowy (pomiar.json, chunkN_moves.jsonl, zrzuty)")
    p.add_argument("--limit-minut", type=float, default=300.0, help="limit czasu partii w minutach (domyślnie 300)")
    p.add_argument("--prog", type=int, default=1_000_000, help="próg licznika apki (domyślnie 1000000)")
    p.add_argument("--kawalek", type=int, default=150, help="ruchów w kawałku (domyślnie 150)")
    return p


def write_atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_rows(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def classify_end(end, row):
    """(przyczyna, okno) dla wpisu `end` mostu, który nie jest końcem partii."""
    okno = row.get("okno")
    if end == "gra nie jest na pierwszym planie":
        return "apka_nie_wraca", okno
    if end.startswith("okno: "):
        name = end[len("okno: "):]
        if name in ("petla_bez_postepu", "plansza_zawieszona", "restart_utracil_partie"):
            return name, okno or name
        return "nieznane_okno", okno or name
    return end.replace(" ", "_"), okno


def percentile(values, q):
    v = sorted(values)
    return v[min(len(v) - 1, int(round(q * (len(v) - 1))))]


def counter_consistent(prev, value):
    """Czy odczyt licznika pasuje do poprzedniego zaakceptowanego (#290): nie maleje i nie skacze o rząd wielkości
    (zgubiona albo dopisana cyfra). Bez poprzedniego odczytu każdy jest spójny."""
    return prev is None or prev <= value < 10 * max(prev, 1)


def read_stable_counter():
    """Licznik apki: (wartość|None, odczyty, stabilny, obraz). Stabilny = dwa ostatnie odczyty zgodne.

    Obraz to klatka, z której pochodzi zwrócona wartość (ostatni odczyt), nie pierwszy zrzut (#290)."""
    frames = [bridge.screenshot()]
    shot = bridge.screenshot

    def recording():
        frames.append(shot())
        return frames[-1]

    bridge.screenshot = recording
    try:
        value, reads = bridge.stable_score(frames[0], bridge.SCORE_BOX, tries=STABLE_TRIES)
    finally:
        bridge.screenshot = shot
    stable = len(reads) >= 2 and reads[-1] == reads[-2] and value is not None
    return value, reads, stable, frames[-1]


def save_png(img, path):
    import numpy as np
    from PIL import Image
    Image.fromarray(img.astype(np.uint8)).save(path)


def run(args, now=time.time):
    out = args.katalog
    os.makedirs(out, exist_ok=True)
    pomiar_path = os.path.join(out, "pomiar.json")
    start = now()
    pomiar = {"polityka": args.polityka, "zakonczenie": "w_toku", "przyczyna": None, "okno": None,
              "licznik_apki": None, "licznik_odrzucone": [], "wynik_wzor": None, "postawienia": 0, "minuty": 0.0,
              "postawien_na_minute": None, "decision_ms": None, "okna": [], "kawalki": []}
    files, rows = [], []

    def refresh():
        moves = [r for r in rows if "move" in r]
        pomiar["postawienia"] = len(moves)
        ts = [r["t"] for r in rows if "t" in r]
        pomiar["minuty"] = round((max(ts) - min(ts)) / 60, 3) if len(ts) >= 2 else 0.0
        move_ts = [r["t"] for r in moves if "t" in r]
        span = (max(move_ts) - min(move_ts)) / 60 if len(move_ts) >= 2 else 0
        pomiar["postawien_na_minute"] = round(len(moves) / span, 2) if span > 0 else None
        dec = [r["decision_ms"] for r in moves if "decision_ms" in r]
        pomiar["decision_ms"] = ({"mediana": round(statistics.median(dec), 2),
                                  "p95": round(percentile(dec, 0.95), 2), "max": round(max(dec), 2)}
                                 if dec else None)
        pomiar["okna"] = [{"kawalek": r["_kawalek"], "n": r.get("n"), "okno": r.get("okno") or "restart",
                           "t": r.get("t")} for r in rows if r.get("okno") or r.get("restart")]
        pomiar["kawalki"] = [os.path.basename(f) for f in files]
        if files:
            try:
                pomiar["wynik_wzor"] = score_from_trajectory.analyze_game(files)["wynik_main"]
            except Exception as e:  # checkpoint ma przetrwać dziwny plik ruchów
                pomiar["wynik_wzor"] = None
                pomiar["wynik_wzor_blad"] = repr(e)

    def checkpoint():
        refresh()
        write_atomic(pomiar_path, pomiar)

    def finish(zakonczenie, przyczyna=None):
        pomiar["zakonczenie"] = zakonczenie
        pomiar["przyczyna"] = przyczyna
        checkpoint()
        print(f"zakonczenie: {zakonczenie}" + (f" ({przyczyna})" if przyczyna else ""), flush=True)
        return EXIT[zakonczenie]

    accepted = None  # ostatni stabilny i spójny odczyt licznika
    k = 0
    while True:
        if (now() - start) / 60 >= args.limit_minut:
            return finish("przerwanie", "limit_minut")
        k += 1
        chunk_dir = os.path.join(out, f"kawalek_{k}")
        os.makedirs(chunk_dir, exist_ok=True)
        bridge.OUT = chunk_dir
        bridge.main(args.kawalek, args.polityka, "argv", seria=True)
        src = os.path.join(chunk_dir, "moves.jsonl")
        dst = os.path.join(out, f"chunk{k}_moves.jsonl")
        if not os.path.exists(src):
            return finish("przerwanie", "brak_pliku_ruchow")
        os.replace(src, dst)
        files.append(dst)
        new = load_rows(dst)
        for r in new:
            r["_kawalek"] = k
        rows.extend(new)
        last = new[-1] if new else {}
        end = last.get("end")
        if end == "koniec_partii":
            moves = [r for r in rows if "move" in r][-LAST_MOVES:]
            pomiar["ostatnie_ruchy"] = [{"n": r.get("n"), "board": r["board"], "tray": r["tray"]} for r in moves]
            pomiar["wynik_koncowy"] = last.get("wynik_koncowy")
            pomiar["zrzut_konca"] = os.path.join(f"kawalek_{k}", last.get("zrzut_konca", ""))
            return finish("przegrana")
        if end:
            przyczyna, okno = classify_end(end, last)
            pomiar["okno"] = okno
            return finish("przerwanie", przyczyna)
        if not new:
            return finish("przerwanie", "pusty_plik_ruchow")
        value, reads, stable, img = read_stable_counter()
        if value is not None and not counter_consistent(accepted, value):
            pomiar["licznik_odrzucone"].append({"kawalek": k, "wartosc": value, "odczyty": reads, "poprzedni": accepted})
            value = None  # niespójny odczyt to brak odczytu
        if value is not None:
            zrzut = f"licznik_{k}.png"
            pomiar["licznik_apki"] = {"wartosc": value, "odczyty": reads, "stabilny": stable, "zrzut": zrzut}
            save_png(img, os.path.join(out, zrzut))
            if stable:
                accepted = value
                if value >= args.prog:
                    return finish("cel")
        checkpoint()


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.kawalek < 1 or args.limit_minut <= 0 or args.prog < 1:
        print("błąd: --kawalek, --limit-minut i --prog muszą być dodatnie", file=sys.stderr)
        return 3
    try:
        return run(args)
    except Exception as e:  # jakikolwiek wyjątek to przerwanie, nie przegrana
        path = os.path.join(args.katalog, "pomiar.json")
        try:
            data = {"polityka": args.polityka}
            if os.path.exists(path):
                with open(path) as f:
                    data = json.load(f)
            data.update(zakonczenie="przerwanie", przyczyna=f"wyjatek: {e!r}")
            write_atomic(path, data)
        except Exception:
            pass
        print(f"wyjątek: {e!r}", file=sys.stderr)
        return EXIT["przerwanie"]


if __name__ == "__main__":
    sys.exit(main())
