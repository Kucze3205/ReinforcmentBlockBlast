# Raport pętli

**2026-09-24 · cykl 2**

**Czeka na ciebie:** [otwarte awarie](https://github.com/Kucze3205/ReinforcmentBlockBlast/labels/awaria)
— dziś jedna, [#48](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/48), i bez niej
pętla nie ruszy.

## Gdzie jesteśmy

Rekordu nie ma. `bench/record.json` nie istnieje, nie ma ani jednych wag. Najlepsze, co repo
dziś potrafi, to zachłanna heurystyka na jeden pół-ruch w przód: **704,79 punktu** średnio
i **34,99 postawień** na partię, na 300 stałych seedach. Losowa polityka dla skali: 59,15.
Cel to 10 000 000 średnio w symulatorze i jedna realna partia ≥ 1 mln w apce. Brakuje czterech
rzędów wielkości.

Przez dwa cykle ta liczba nie drgnęła i nie mogła, bo przez dwa cykle **żadna sesja nie
wykonała ani jednej linii pracy**.

## Co się wydarzyło

Cykl 1 był biegiem na sucho i zdał: znalazł dwie usterki, które zatrzymują pętlę. Naprawiłeś
pierwszą — zamek na issue, który uniemożliwiał sesji opublikowanie raportu. Ta naprawa
zadziałała w całości i to jest dobra wiadomość tego cyklu: raport publikuje się sam, etykieta
się nakłada, issue się zamyka, zadania zależne ruszają bez niczyjej ręki. Sesja, która pisze
ten raport, wstała dokładnie w ten sposób.

Druga usterka została nietknięta i to ona zjadła cały cykl. `agent.sh` sięga po treść zadania,
zanim ustawi token, więc plik z zadaniem nie powstaje **dla żadnej roli**. Wszystkie trzy
sesje robocze cyklu 1 wróciły z tym samym zdaniem: katalog jest pusty, nie wiem, co mam robić.
Pętla domyka więc cykl poprawnie i wykonuje w nim puste zadanie. Opis i gotowa poprawka są
w [#48](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/48), z uwagą, żeby nie
przesuwać eksportu tokenu globalnie — wyciekłby wtedy do ról, które celowo go nie mają.

Do tego doszła trzecia rzecz, której wcześniej nie było jak zobaczyć: **nic się nie scala**.
Epilog uruchamia testy po rebasie i przy czerwonych odrzuca scalenie, a testy są czerwone
przez jeden przypadkowy import w `model.py`, który ciągnie bibliotekę okienkową nieobecną
na runnerze. Skutek jest cichy: dziennik cyklu 1 i poprzednia wersja tego raportu leżą na
gałęzi zadaniowej i nigdy nie dojechały, a każdy kolejny orchestrator budzi się z pustą
pamięcią i uznaje, że jest pierwszy. Ta poprawka jest w zasięgu pętli i czeka jako
[#49](https://github.com/Kucze3205/ReinforcmentBlockBlast/issues/49) — ruszy sama, gdy
zamkniesz awarię.

Przy okazji wyszło na jaw, że poprzedni cykl źle odczytał sprawę punktacji. Nazwał ją
zaniedbanym długiem; w rzeczywistości jest to konflikt dwóch ustaleń. Punktacja symulatora
została przez ciebie **zamrożona** na pomiarze z mostu, zgodnym co do punktu w osiemnastu
ruchach z rzędu — a obok, na niescalonej gałęzi, leży sprzeczna z nią drabinka punktów,
filtr grywalności tacki i przepisany generator, każde z własnym pomiarem i własną linią
bazową. To jest prawdziwa niewiadoma tego projektu i dostała osobne zadanie.

## Co dalej

Linia pracy brzmi: najpierw uczciwy sygnał nagrody i uczciwy symulator, potem wybór metody.
Merytorycznie ona nadal rokuje — pomiar z cyklu przed nami pokazał, że uczenie sieci na
runnerze bez karty graficznej jest nierealne jako metoda główna, a sam symulator bez sieci
jest od niego dwa rzędy wielkości szybszy, co przesuwa ciężar na przeszukiwanie. Mapa cyklu 3
jest już zbudowana i czeka: dwa zadania badawcze mają dowieźć materiał pod decyzję o kształcie
nagrody i o kierunku algorytmicznym, trzy pomiarowe mają rozstrzygnąć rozjazdy, których nie
wolno rozstrzygać zgadywaniem.

Operacyjnie linia pracy nie rokuje wcale i nie da się tego obejść planowaniem. Nie mam sygnału,
że kierunek jest zły; mam sygnał, że maszyna nie jeździ. Wszystko wisi na jednej poprawce
w `agent.sh`. Po niej pętla ruszy sama.
