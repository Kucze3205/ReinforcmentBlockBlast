"""Buduje pomiar.json (#286) z plików ruchów i odczytów ze zrzutów (wpisanych ręcznie niżej)."""
import json, os, statistics, subprocess, shutil, tempfile
RUN = os.path.dirname(os.path.abspath(__file__))
POL = "lookahead-ntuple:ntuple/survival-adce-400k.json@beam=128,samples=0,complete=1,gain_weight=100000"

def rows(k):
    return [json.loads(l) for l in open(f"{RUN}/chunk{k}_moves.jsonl")]

def moves(k):
    return [r for r in rows(k) if "move" in r and "t" in r]

def grp(ks):
    n = bad = 0; span = 0.0; tms = []
    for k in ks:
        m = moves(k); n += len(m); bad += sum(1 for r in m if r.get("ok") is False)
        span += (m[-1]["t"] - m[0]["t"]) / 60 * len(m) / (len(m) - 1)
        tms += [sum(r["t_ms"].values()) for r in m if "t_ms" in r]
    return dict(kawalki=ks, postawienia=n, minuty=round(span, 2), postawien_na_minute=round(n / span, 2),
                mediana_t_ms=round(statistics.median(tms), 1), odsetek_ok_false=round(100 * bad / n, 1))

def wzor(last):
    out = subprocess.run(["python3", "tools/score_from_trajectory.py", RUN, "--first-chunk", "1", "--last-chunk", str(last)],
                         capture_output=True, text=True).stdout
    d = json.loads(out); return d["postawien"], d["wynik_main"]

# (kawalek, licznik ze zrzutu, zrzut, uwaga)
L = [(1, 26407, "chunk1_final.png"), (2, 75177, "chunk2_final.png"), (3, 138629, "chunk3_final.png"),
     (4, 157704, "chunk4_final.png"), (5, 170276, "chunk5_final.png"), (6, 202829, "chunk6_final.png"),
     (7, 267874, "chunk7_final.png"), (8, 371248, "chunk8_final.png"), (9, 513389, "chunk9_final.png"),
     (10, 684052, "chunk10_final.png"), (11, 881444, "chunk11_final.png"), (12, 1124408, "chunk12_final.png"),
     (13, 1399270, "chunk13_final.png"),
     (14, 1512468, "zrzut ręczny po próbie 1 (licznik_1.png miał 1509545 w animacji)"),
     (15, 1547434, "seria-proba2/licznik_1.png"),
     (16, 1887842, "chunk16_final.png"), (17, 1916865, "chunk17_final.png"), (18, 1967415, "chunk18_final.png")]
lw = []
for k, c, z in L:
    n, w = wzor(k)
    lw.append(dict(kawalek=k, postawienia=n, licznik_apki=c, zrzut=z, wynik_wzor=w, stosunek=round(c / w, 3)))
stare = grp([1]); nowe = grp([k for k in range(2, 14)] + [16, 17, 18])
last = lw[-1]
ratio = last["stosunek"]
pkt_marg = (lw[-1]["wynik_wzor"] - lw[10]["wynik_wzor"]) / (lw[-1]["postawienia"] - lw[10]["postawienia"])
# pomiar: przekroczenie 1 mln między kawałkiem 11 (1650) a 12 (1800), interpolacja liniowa po liczniku
c11, c12 = 881444, 1124408
post_1mln = round(1650 + 150 * (1_000_000 - c11) / (c12 - c11))
json.dump(dict(
    run=os.path.basename(RUN), cel="#286: tempo mostu stare/nowe, licznik apki vs wzór, próba skryptu serii",
    tempo_mostu=dict(
        polityka=POL, kawalki=18, postawienia=last["postawienia"], zakonczenie="czas",
        zakonczenie_uwaga="partia nie skończona (brak przegranej); przerwana po ~105 turach sesji, licznik apki 1 967 415 na zrzucie chunk18_final.png; kawałki 14 i 15 to ruchy prób skryptu (50 + 20 ruchów, zapisane w chunk14/15_moves.jsonl), kawałek 13→16 ciągły",
        minuty=round(stare["minuty"] + nowe["minuty"], 1),
        stare=stare, nowe=nowe,
        licznik_vs_wzor=lw,
        szacunek=dict(
            postawienia_do_1mln_pomiar=post_1mln,
            minuty_do_1mln_nowe_tempo=round(post_1mln / nowe["postawien_na_minute"], 1),
            z_ostatniego_stosunku=dict(stosunek=ratio, wzor_potrzebny=round(1e6 / ratio),
                                       pkt_wzor_na_postawienie_marginalnie_k11_18=round(pkt_marg, 1)),
            uwaga="1 mln licznika apki osiągnięty po ok. 1720 postawieniach (pomiar), nie ~3950 z #262; kawałek 17-18: przyrost licznika 29k/51k na 150 postawień, wyraźnie wolniejszy niż k12-13 (ok. 250k)."),
        proba_skryptu=dict(
            proba1=dict(komenda="--limit-minut 10 --kawalek 50", kod_wyjscia=0, zakonczenie="cel", przyczyna=None,
                        licznik_ze_skryptu=1519468, licznik_ze_zrzutu=1512468, zgodny=False,
                        postawien_na_minute=16.58, katalog="seria-proba",
                        uwaga="licznik już >1 mln przed startem, więc po jednym kawałku `cel`; zrzut licznika_1.png miał 1509545 (animacja), stabilny ekran po chwili 1512468"),
            proba2=dict(komenda="--limit-minut 1 --kawalek 20 --prog 100000000", kod_wyjscia=2, zakonczenie="przerwanie",
                        przyczyna="limit_minut", licznik_ze_skryptu=1549434, licznik_ze_zrzutu=1547434, zgodny=False,
                        postawien_na_minute=17.23, katalog="seria-proba2"),
            wniosek="read_score czyta 7-cyfrową wartość z błędem w 4. cyfrze (2→9, 7→9: pod żółtym rombem); dwa zgodne odczyty nie chronią, bo błąd jest powtarzalny"),
        read_7_cyfr=dict(zgodny_ze_zrzutem=False,
                         przyklady=["skrypt 1519468 / ekran 1512468 (seria-proba)", "skrypt 1549434 / ekran 1547434 (seria-proba2)",
                                    "licznik w trakcie ruchów: zgubione cyfry, np. 'wynik 15119' na ruchu 48 (seria-proba), 100261/110560 w chunk12"]),
        okna=[], okno="brak"),
), open(f"{RUN}/pomiar.json", "w"), indent=1, ensure_ascii=False)
print(json.dumps(stare)); print(json.dumps(nowe)); print(lw[-3:]); print(post_1mln, pkt_marg)
