#!/usr/bin/env python3
"""Odtwarza wynik partii z trajektorii mostu (bridge/runs/*/*.jsonl) dwoma wzorami:

- "main": nasz wzór zamrożony w scoring.py/game.py (#20/#31, bez zmian tutaj),
- "alt": drabinka U(combo) 10/15/20 z docs/rozjazd-punktacja-generator.md §1,
  z combo rosnącym o liczbę wyczyszczonych linii zamiast o 1 (nigdy niewdrożona,
  liczona tu wyłącznie jako druga kolumna do porównania z apką, issue #183).

Nie dotyka scoring.py ani game.py. Każdy wpis trajektorii niesie własny
zaobserwowany `board`/`tray` (nie różnicę względem poprzedniego), więc replay
pojedynczego ruchu nie wymaga ciągłości klatek - tylko ciągłość stanu combo
(`combo`, `combo_counter`), którego most nie obserwuje bezpośrednio. Dlatego
brakujące kawałki/ruchy są realną luką w wyniku (patrz `events`), nie tylko
kosmetyczną dziurą w numeracji.

Który zestaw kawałków należy do jednej partii jest wiedzą z narracji
`bridge/runs/<id>/pomiar.json` (most miesza prawdziwe końce partii z fałszywymi
zatrzymaniami - patrz #183, #164) - ten skrypt NIE zgaduje granic partii sam;
woła się go raz na partię, z jawną listą plików.
"""
import argparse
import glob
import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from board import Board
from pieces import Piece
from scoring import COMBO_COUNTER_BASE, FULL_CLEAR_BONUS, clear_points, placement_points


def combo_unit_alt(combo):
    """U(combo): drabinka 10/15/20 z docs/rozjazd-punktacja-generator.md §1."""
    if combo <= 5:
        return 10
    if combo <= 10:
        return 15
    return 20


def line_bonus_alt(combo, lines):
    if lines <= 0:
        return 0
    if lines == 1:
        return combo_unit_alt(combo)
    return combo_unit_alt(combo) * lines * (lines - 1)


def clear_points_alt(combo, lines):
    return combo * line_bonus_alt(combo, lines)


def _chunk_num(path):
    m = re.search(r"chunk[_]?(\d+)", os.path.basename(path), re.IGNORECASE)
    return int(m.group(1)) if m else None


def find_chunk_files(run_dir, first=None, last=None):
    """Pliki z ruchami w katalogu przebiegu, posortowane po numerze kawałka.

    Dwie znane konwencje nazw w bridge/runs/*: `chunkN_moves.jsonl` (np. c1819ed)
    i `moves_chunkN.jsonl` (np. 1402cff). `first`/`last` filtrują po numerze
    kawałka (obustronnie domknięte), gdy trzeba wyciąć jedną partię z przebiegu."""
    files = [
        f
        for f in glob.glob(os.path.join(run_dir, "*.jsonl"))
        if "chunk" in os.path.basename(f).lower()
    ]
    files = [f for f in files if _chunk_num(f) is not None]
    if first is not None:
        files = [f for f in files if _chunk_num(f) >= first]
    if last is not None:
        files = [f for f in files if _chunk_num(f) <= last]
    files.sort(key=_chunk_num)
    return files


def load_entries(files):
    entries = []
    for f in files:
        name = os.path.basename(f)
        with open(f) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                e = json.loads(line)
                e["_source"] = name
                e["_chunk_num"] = _chunk_num(f)
                entries.append(e)
    return entries


def replay(entries, expect_first_chunk=1):
    """Liczy oba wzory ruch po ruchu na jednej, ciągłej partii.

    Nie dzieli wejścia na partie - zakłada, że `entries` to już dokładnie jedna
    partia (patrz docstring modułu). Zdarzenia bez ruchu (`okno`, `end`,
    rozbieżności numeracji) trafiają do `events`, ale nie zerują stanu combo -
    tylko prawdziwy restart gry by to uzasadniał, a tego most nie odróżnia
    niezawodnie od fałszywych zatrzymań (#164/#183)."""
    combo = 0
    combo_alt = 0
    combo_counter = COMBO_COUNTER_BASE
    score = 0
    score_alt = 0
    moves = []
    events = []

    prev_chunk_num = None
    prev_source = None
    prev_move_n = None

    first_move_seen = False

    for e in entries:
        source = e["_source"]
        cnum = e.get("_chunk_num")

        if source != prev_source:
            if prev_chunk_num is None:
                if cnum is not None and cnum > expect_first_chunk:
                    events.append(
                        {
                            "typ": "brakujacy_kawalek_na_starcie",
                            "source": source,
                            "opis": "pierwszy dostepny kawalek to %d, oczekiwano %d - "
                            "wczesniejsze ruchy i stan combo na starcie sa nieznane, "
                            "przyjeto combo=0" % (cnum, expect_first_chunk),
                        }
                    )
            elif cnum is not None and cnum != prev_chunk_num + 1:
                events.append(
                    {
                        "typ": "brakujacy_kawalek",
                        "source": source,
                        "opis": "poprzedni kawalek %d, nastepny %d - %d kawalka(ow) brakuje"
                        % (prev_chunk_num, cnum, cnum - prev_chunk_num - 1),
                    }
                )
            prev_move_n = None
        prev_source = source
        if cnum is not None:
            prev_chunk_num = cnum

        if e.get("okno"):
            events.append({"typ": "okno", "source": source, "n": e.get("n"), "opis": e["okno"]})

        if e.get("end"):
            events.append({"typ": "end", "source": source, "n": e.get("n"), "opis": e["end"]})

        if "move" not in e:
            continue

        n = e.get("n")
        if prev_move_n is not None and n is not None and n != prev_move_n + 1:
            events.append(
                {
                    "typ": "przerwa_w_numeracji",
                    "source": source,
                    "n": n,
                    "opis": "poprzedni ruch w tym kawalku n=%d, ten n=%d" % (prev_move_n, n),
                }
            )
        prev_move_n = n
        first_move_seen = True

        if e.get("ok") is False:
            events.append(
                {
                    "typ": "rozbieznosc_odczytu",
                    "source": source,
                    "n": n,
                    "opis": "ok=False (observed nie zgadzal sie z expected po tym ruchu)",
                }
            )

        board = Board()
        board.grid = [row[:] for row in e["board"]]
        tray = e["tray"]
        slot = e["move"]["slot"]
        shape = tray[slot]
        piece = Piece(shape, "slot%d" % slot, -1)
        x, y = e["move"]["x"], e["move"]["y"]
        if not board.place_piece(piece, x, y):
            events.append(
                {
                    "typ": "niemozliwy_ruch",
                    "source": source,
                    "n": n,
                    "opis": "postawienie nielegalne wg odczytu - ruch pominiety w replayu",
                }
            )
            continue

        placement = placement_points(piece)
        rows, cols = board.check_full_lines()
        lines = len(rows) + len(cols)
        remaining = sum(1 for j, s in enumerate(tray) if s is not None and j != slot)

        gained = placement
        gained_alt = placement
        if lines > 0:
            combo += 1
            combo_alt += lines
            combo_counter = COMBO_COUNTER_BASE + remaining
            gained += clear_points(combo, lines)
            gained_alt += clear_points_alt(combo_alt, lines)
        elif combo_counter <= 1:
            combo = 0
            combo_alt = 0
            combo_counter = COMBO_COUNTER_BASE
        else:
            combo_counter -= 1

        board.clear_lines(rows, cols)
        if not any(any(row) for row in board.grid):
            gained += FULL_CLEAR_BONUS
            gained_alt += FULL_CLEAR_BONUS

        score += gained
        score_alt += gained_alt
        moves.append(
            {
                "source": source,
                "n": n,
                "placement": placement,
                "lines": lines,
                "combo": combo,
                "combo_alt": combo_alt,
                "gained": gained,
                "gained_alt": gained_alt,
                "score": score,
                "score_alt": score_alt,
                "apka_score_before_move": e.get("score"),
            }
        )

    return {"moves": moves, "events": events}


def _ocr_consistent(moves):
    """OCR licznika 'score' jest spojny, jesli niemalejacy przez cala partie
    (braki/None sa pomijane, nie licza sie jako spadek)."""
    seen = [m["apka_score_before_move"] for m in moves if m["apka_score_before_move"] is not None]
    return len(seen) >= 2 and all(b >= a for a, b in zip(seen, seen[1:]))


def summarize(trajectory, apka_final=None, apka_final_source=None):
    moves = trajectory["moves"]
    n_moves = len(moves)
    score = moves[-1]["score"] if moves else 0
    score_alt = moves[-1]["score_alt"] if moves else 0
    clear_main = sum(m["gained"] - m["placement"] for m in moves)
    clear_alt = sum(m["gained_alt"] - m["placement"] for m in moves)

    chains = []
    chain = 0
    for m in moves:
        if m["lines"] > 0:
            chain += 1
        else:
            if chain > 0:
                chains.append(chain)
            chain = 0
    if chain > 0:
        chains.append(chain)  # ucieta koncem danych/partii

    ocr_ok = _ocr_consistent(moves)
    move_by_move = []
    if ocr_ok:
        for cur, nxt in zip(moves, moves[1:]):
            if nxt["apka_score_before_move"] is None:
                continue
            move_by_move.append(
                {
                    "n": cur["n"],
                    "apka_po_ruchu": nxt["apka_score_before_move"],
                    "main_po_ruchu": cur["score"],
                    "alt_po_ruchu": cur["score_alt"],
                    "roznica_main": cur["score"] - nxt["apka_score_before_move"],
                    "roznica_alt": cur["score_alt"] - nxt["apka_score_before_move"],
                }
            )
        if apka_final is not None and moves:
            move_by_move.append(
                {
                    "n": moves[-1]["n"],
                    "apka_po_ruchu": apka_final,
                    "main_po_ruchu": score,
                    "alt_po_ruchu": score_alt,
                    "roznica_main": score - apka_final,
                    "roznica_alt": score_alt - apka_final,
                }
            )

    return {
        "postawien": n_moves,
        "wynik_main": score,
        "wynik_alt": score_alt,
        "apka_wynik_koncowy": apka_final,
        "apka_wynik_zrodlo": apka_final_source,
        "pkt_na_postawienie_main": (score / n_moves) if n_moves else None,
        "pkt_na_postawienie_alt": (score_alt / n_moves) if n_moves else None,
        "udzial_czyszczen_main_pct": (100.0 * clear_main / score) if score else None,
        "udzial_czyszczen_alt_pct": (100.0 * clear_alt / score_alt) if score_alt else None,
        "combo_max_main": max((m["combo"] for m in moves), default=0),
        "combo_max_alt": max((m["combo_alt"] for m in moves), default=0),
        "lancuchy_combo": sorted(chains, reverse=True),
        "ocr_spojny_w_partii": ocr_ok,
        "ruch_po_ruchu": move_by_move,
        "events": trajectory["events"],
    }


def analyze_game(files, apka_final=None, apka_final_source=None, expect_first_chunk=1):
    entries = load_entries(files)
    trajectory = replay(entries, expect_first_chunk=expect_first_chunk)
    return summarize(trajectory, apka_final=apka_final, apka_final_source=apka_final_source)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", help="katalog bridge/runs/<id>")
    parser.add_argument("--first-chunk", type=int, default=None, help="pierwszy kawalek partii (wlacznie)")
    parser.add_argument("--last-chunk", type=int, default=None, help="ostatni kawalek partii (wlacznie)")
    parser.add_argument("--apka-final", type=float, default=None, help="wynik koncowy apki (odczyt z ekranu konca gry)")
    parser.add_argument("--apka-final-source", default=None, help="skad wzieto wynik koncowy (np. nazwa zrzutu)")
    parser.add_argument(
        "--expect-first-chunk",
        type=int,
        default=1,
        help="oczekiwany numer pierwszego kawalka partii, do wykrycia brakujacych na starcie",
    )
    parser.add_argument("--moves", action="store_true", help="dolacz pelna liste ruchow (ruch_po_ruchu jest juz zawsze wliczony)")
    args = parser.parse_args()

    files = find_chunk_files(args.run_dir, first=args.first_chunk, last=args.last_chunk)
    if not files:
        print("Brak plikow *chunk*.jsonl w %s w podanym zakresie" % args.run_dir, file=sys.stderr)
        sys.exit(1)

    result = analyze_game(
        files,
        apka_final=args.apka_final,
        apka_final_source=args.apka_final_source,
        expect_first_chunk=args.expect_first_chunk,
    )
    result["pliki"] = [os.path.basename(f) for f in files]
    if not args.moves:
        result.pop("ruch_po_ruchu", None)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
