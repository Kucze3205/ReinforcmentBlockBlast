# Most: zapis ruchów bez nadpisywania, zrzut końca partii, stabilny odczyt wyniku (#198)

Sesja danych z cyklu 20 (#190) zebrała 3 całe partie, ale z trzech tylko jedna nadawała się
do pomiaru punktacji (#191) — z powodów mechanicznych mostu, nie gry:

1. `bridge.py` przy każdym wywołaniu nadpisywał `bridge-out/moves.jsonl` (otwarcie w trybie
   `"w"`). Verifier raz nie zdążył go skopiować przed kolejnym wywołaniem i cała trajektoria
   przepadła (sesja `cb91077`, `chunk3_moves.jsonl`).
2. Most czytał wynik z ekranu końca partii i od razu stukał „Play" — bez zrzutu ekranu, choć
   kryteria sesji danych go wymagają.
3. Pierwszy odczyt wyniku po wykryciu końca partii bywał błędny, bo licznik jeszcze się
   animuje (kawałek 12 z #190).

## Numeracja plików ruchów

`bridge.next_moves_path` daje pierwszemu wywołaniu w danym katalogu `moves.jsonl`, a każdemu
kolejnemu `moves.1.jsonl`, `moves.2.jsonl`, ... — żadne wywołanie nie nadpisuje pliku
poprzedniego, niezależnie od tego, jak szybko po sobie następują. Most wypisuje ścieżkę na
stdout (`log ruchów: bridge-out/moves.N.jsonl`).

**Polecenie dla verifiera:** po każdym wywołaniu `bridge.py` skopiuj/przenieś **wszystkie**
pliki pasujące do wzorca, nie tylko jeden:

```
cp bridge-out/moves*.jsonl <katalog_przebiegu>/
```

(dawniej wystarczał jeden `moves.jsonl` na wywołanie — teraz w `bridge-out/` mogą leżeć
pliki z kilku wywołań naraz, jeśli poprzednie kopiowanie nie zdążyło ich sprzątnąć; kopiowanie
całego wzorca jest nieszkodliwe nawet przy jednym pliku).

## Zrzut ekranu końca partii

Po wykryciu ekranu końca partii most zapisuje jego zrzut do `bridge-out/NNN_end.png` (NNN —
numer bieżącego ruchu w kawałku), **zanim** stuknie „Play". Nazwa pliku (bez katalogu) jest
w tym samym wpisie logu co `koniec_partii: true`, pod kluczem `zrzut_konca`.

## Stabilny odczyt wyniku końcowego

Zamiast pojedynczego odczytu, most czyta wynik końca partii (`bridge.stable_score`) aż dwa
kolejne odczyty będą równe, z limitem 6 prób. Wpis `koniec_partii` niesie:

- `wynik_koncowy` — ostatni (ustabilizowany, albo ostatni z limitu prób) odczyt,
- `wynik_koncowy_odczyty` — lista wszystkich odczytów po kolei, do wglądu, gdy się nie
  ustabilizował.
