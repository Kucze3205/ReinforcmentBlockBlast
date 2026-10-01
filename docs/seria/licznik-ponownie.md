# Ponowna ocena licznika na materiale s1–s4 (#324)

Narzędzie: `python3 tools/licznik_ponownie.py --tabela docs/seria/s*/partia-*` (test: `tests/test_licznik_ponownie.py`). Czyta pole
`score` z `chunk*_moves.jsonl` (kawałki numerycznie) i szuka pierwszego wpisu (kawałek, `n`), od którego licznik ≥ 1 000 000 utrzymał
się przez ≥ 3 kolejne wpisy z odczytem (wpisy z `score: null` serii nie przerywają). Klasyfikacja to `zakonczenie` (i `przyczyna`)
z zapisanego `pomiar.json`; **nie została zmieniona**. „rozjazd” = tak, gdy ponowna ocena („≥ 1 mln utrzymany, bez `koniec_partii`
przed”) i `zakonczenie == cel` się różnią.

Wynik: jedyny rozjazd to **s4/1** — klasyfikacja `przerwanie (petla_bez_postepu)`, a licznik przekroczył 1 mln w kawałku 18
(`n` 71; wzrokowo ✔ na `kawalek_18/final.png`), bez końca partii, i doszedł do 1 285 808. Przyczyna: kotwica `counter_consistent`
utknęła na 25 662 (#324); poprawka reguły: `docs/seria-skrypt.md`. Pozostałe partie s1–s4 zgadzają się z klasyfikacją
(s1 nie ma odczytów licznika, `score` = `null`).

| partia | klasyfikacja (pomiar.json) | maksimum licznika | >= 1 mln utrzymany od | koniec_partii w materiale | rozjazd |
|---|---|---|---|---|---|
| s1/1 | przerwanie (limit_minut) | brak odczytów | nie | nie | nie |
| s1/2 | przerwanie (brak_legalnego_ruchu_wg_odczytu) | brak odczytów | nie | nie | nie |
| s1/3 | przerwanie (limit_minut) | brak odczytów | nie | nie | nie |
| s1/4 | przerwanie (petla_bez_postepu) | brak odczytów | nie | nie | nie |
| s1/5 | przerwanie (brak_legalnego_ruchu_wg_odczytu) | brak odczytów | nie | nie | nie |
| s1/6 | przerwanie (petla_bez_postepu) | brak odczytów | nie | nie | nie |
| s1/7 | przerwanie (brak_legalnego_ruchu_wg_odczytu) | brak odczytów | nie | nie | nie |
| s1/8 | przerwanie (brak_legalnego_ruchu_wg_odczytu) | brak odczytów | nie | nie | nie |
| s1/9 | przerwanie (brak_legalnego_ruchu_wg_odczytu) | brak odczytów | nie | nie | nie |
| s1/10 | przerwanie (brak_legalnego_ruchu_wg_odczytu) | brak odczytów | nie | nie | nie |
| s2/1 | przegrana | 59 932 | nie | tak | nie |
| s2/2 | przerwanie (petla_bez_postepu) | 146 484 | nie | nie | nie |
| s2/3 | przegrana | 55 567 | nie | tak | nie |
| s2/4 | przegrana | 32 690 | nie | tak | nie |
| s2/5 | cel | 1 258 214 | kawałek 6, n 126 | nie | nie |
| s2/6 | cel | 1 201 276 | kawałek 7, n 70 | nie | nie |
| s2/7 | cel | 1 222 688 | kawałek 9, n 58 | nie | nie |
| s2/8 | przerwanie (wyjatek: BrokenPipeError(32, 'Broken pipe')) | 694 797 | nie | nie | nie |
| s2/9 | przegrana | 31 319 | nie | tak | nie |
| s2/10 | przegrana | 89 137 | nie | tak | nie |
| s3/1 | przerwanie (petla_bez_postepu) | 18 893 | nie | nie | nie |
| s3/2 | przerwanie (petla_bez_postepu) | 13 218 | nie | nie | nie |
| s3/3 | przerwanie (petla_bez_postepu) | 856 524 | nie | nie | nie |
| s3/4 | cel | 1 205 087 | kawałek 7, n 78 | nie | nie |
| s3/5 | cel | 1 001 894 | kawałek 32, n 136 | nie | nie |
| s3/6 | cel | 1 122 372 | kawałek 10, n 92 | nie | nie |
| s3/7 | przerwanie (plansza_zawieszona) | 162 | nie | nie | nie |
| s3/8 | przerwanie (petla_bez_postepu) | 215 156 | nie | nie | nie |
| s3/9 | cel | 1 076 120 | kawałek 31, n 14 | nie | nie |
| s3/10 | przerwanie (petla_bez_postepu) | 1 972 | nie | nie | nie |
| s4/1 | przerwanie (petla_bez_postepu) | 1 285 808 | kawałek 18, n 71 | nie | tak |
| s4/2 | cel | 1 104 958 | kawałek 6, n 90 | nie | nie |
| s4/3 | cel | 1 009 525 | kawałek 18, n 131 | nie | nie |
| s4/4 | przerwanie (petla_bez_postepu) | 436 322 | nie | nie | nie |
| s4/5 | cel | 1 027 739 | kawałek 25, n 80 | nie | nie |
| s4/6 | przerwanie (petla_bez_postepu) | 236 443 | nie | nie | nie |
| s4/9 | cel | 1 009 327 | kawałek 16, n 135 | nie | nie |
| s4/10 | przerwanie (plansza_zawieszona) | 549 327 | nie | nie | nie |
