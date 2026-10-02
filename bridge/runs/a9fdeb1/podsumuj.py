"""Podsumowanie #350: etykiety rodzaju napisu (wzrokowo z arkuszy zrzutów, klatka z największym rozrzutem w wierszach 3-5,
korekty: s8/s47 klatki na zrzutach pełnych) + napis-czas.md. python3 bridge/runs/a9fdeb1/podsumuj.py"""
import json
import statistics

RUN = "bridge/runs/a9fdeb1"
INNE = {1: "pasek_plus", 68: "pasek_plus", 8: "brak_napisu", 47: "brak_napisu", 58: "pochwala",
        43: "trofeum", 55: "trofeum"}
KAMIEN = {4, 7, 9, 12, 14, 18, 19, 21, 25, 28, 31, 36}
OPIS = {"combo": "napis „Combo N” (z „+N” albo bez)", "kamien_punktowy": "duża liczba 300…20000 (kamień punktowy)",
        "pochwala": "„Great!” / „Excellent!” (pochwała)", "trofeum": "puchar", "pasek_plus": "pasek „+10” z poświatą",
        "brak_napisu": "tylko poświata czyszczenia, bez napisu"}


def rodzaj(s):
    if s in INNE:
        return INNE[s]
    return "kamien_punktowy" if s in KAMIEN else "combo"


def p95(v):
    v = sorted(v)
    return v[min(len(v) - 1, int(round(0.95 * (len(v) - 1))))]


def stat(v):
    if not v:
        return "—"
    return f"{statistics.median(v):.2f} / {p95(v):.2f} / {max(v):.2f}"


def main():
    wszystkie = json.load(open(f"{RUN}/napis-czas.json"))
    serie = [x for x in wszystkie if "seria" in x]
    for x in serie:
        x["rodzaj"] = rodzaj(x["seria"])
        x["t_napis_wizualny_s"] = x.get("t_napis_wizualny_s")
    json.dump(wszystkie, open(f"{RUN}/napis-czas.json", "w"))
    rodzaje = sorted({x["rodzaj"] for x in serie}, key=lambda k: -sum(x["rodzaj"] == k for x in serie))
    L = ["# #350 — czas życia napisu po czyszczeniu linii", "",
         f"Serie: {len(serie)} (jedna na ruch czyszczący linię; polityka rekordu, beam=128). Klatki co ~0,2 s przez 6 s od końca "
         "przeciągnięcia (czas = środek między początkiem a końcem `screencap`; jeden `screencap` ≈ 0,2 s). "
         "Rodzaj napisu: wzrokowo z zrzutów (klatka z największym rozrzutem w wierszach 3–5); „Perfect!” i „Good!” — **zero trafień**.", "",
         "Metryki (mediana / p95 / max, s):",
         "- `t_zniknie` — pierwsza klatka, od której surowy `read_board` == ostatnia klatka serii (definicja z zadania);",
         "- `t_zniknie_trwale` — pierwsza klatka, od której wszystkie następne są równe ostatniej;",
         "- `t_wizualny` — ostatnia klatka z nakładką w wierszach 3–5 (`cell_flatness` ≥ `NAPIS_ROZRZUT`); baner poza wierszami 3–5 "
         "(np. seria 15, Combo 17 niżej) tego nie łapie;",
         "- `t_stable` — czas, po którym zwykły `stable_state()` zwróciłby wynik (dwie zgodne klatki).", "",
         "| rodzaj | n | t_zniknie | t_zniknie_trwale | t_wizualny | t_stable |", "|---|---|---|---|---|---|"]
    for k in rodzaje:
        g = [x for x in serie if x["rodzaj"] == k]
        wiz = [x["t_napis_wizualny_s"] for x in g if x["t_napis_wizualny_s"] is not None]
        L.append(f"| {OPIS[k]} | {len(g)} | {stat([x['t_zniknie_s'] for x in g])} | {stat([x['t_zniknie_trwale_s'] for x in g])} | "
                 f"{stat(wiz)} (n={len(wiz)}) | {stat([x['t_stable_s'] for x in g if x['t_stable_s'] is not None])} |")
    L += ["", "## Ile serii nadal miało napis po T s", "", "Warunek: ostatnia klatka z nakładką (`t_wizualny`) albo ostatnia klatka różna "
          "od końcowej (`t_zniknie_trwale`) później niż T.", "", "| rodzaj | n | >2 s | >3 s | >5 s | >6 s |", "|---|---|---|---|---|---|"]
    for k in rodzaje + ["wszystkie"]:
        g = serie if k == "wszystkie" else [x for x in serie if x["rodzaj"] == k]
        def po(T):
            return sum(1 for x in g if (x["t_napis_wizualny_s"] or 0) > T or x["t_zniknie_trwale_s"] > T)
        L.append(f"| {OPIS.get(k, k)} | {len(g)} | {po(2)} | {po(3)} | {po(5)} | {po(6)} |")
    ok = [x for x in serie if x.get("t_stable_s") is not None]
    L += ["", "## `stable_state()` i korekty `drop_banner_*`", "",
          f"- serie z wynikiem `stable_state()` (dwie zgodne klatki): {len(ok)}/{len(serie)};",
          f"- korekta (`drop_banner_ghosts` albo `drop_banner_text`) odpaliła na klatce `stable_state()`: {sum(x['korekta_odpalila'] for x in ok)};",
          f"- surowa klatka `stable_state()` == ostatnia klatka serii: {sum(x['stable_surowa_eq_ostatnia'] for x in ok)}/{len(ok)};",
          f"- po korekcjach plansza == ostatnia klatka: {sum(x['po_korekcji_eq_ostatnia'] for x in ok)}/{len(ok)};",
          f"- po korekcjach plansza == `expected` symulatora: {sum(x['po_korekcji_eq_expected'] for x in ok)}/{len(ok)};",
          f"- ostatnia klatka serii == `expected`: {sum(x['ostatnia_eq_expected'] for x in ok)}/{len(ok)}.", ""]
    zle = [x for x in ok if not x["po_korekcji_eq_ostatnia"]]
    L.append("Serie, w których po korekcjach plansza ≠ ostatnia klatka (stan po `stable_state()` byłby błędny): "
             + (", ".join(f"s{x['seria']} ({x['rodzaj']}, t_stable {x['t_stable_s']}, t_zniknie_trwale {x['t_zniknie_trwale_s']})" for x in zle) or "brak") + ".")
    open(f"{RUN}/napis-czas.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


main()
