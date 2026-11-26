# Plan zmian po wersji 0.1.6

Kolejność pracy: najpierw plan (ten plik), potem badanie każdego punktu, na końcu implementacja. Przy każdym punkcie
jest to, co już wiadomo, i to, co trzeba zbadać. Numery to proponowana kolejność.

## Błędy

1. Przygotowanie danych na Linuksie przerywa się na `extract_map_pieces.py`.
   Wiadomo: skrypt zapisuje `assets/data/map_pieces.json`, ale folder `assets/data` tworzy dopiero późniejszy
   `extract_data.py`. Na świeżej instalacji (bez starych danych) folderu jeszcze nie ma. Na Windowsie u nas tego nie
   widać, bo folder istnieje od dawna.
   Zbadane (2026-11-26, pełne przygotowanie danych na czystej kopii z `git archive`, Windows): ten sam błąd wychodzi
   też na Windowsie. Po ręcznym założeniu folderu całość przechodzi (ok. 4 min), ale wynik różni się od danych
   przygotowanych drugi raz. Oba błędy wynikają z kolejności kroków:
   - `build_quests.py` bierze identyfikatory bossów z `backend/data/bosses.json`, który powstaje dopiero w kroku
     „Dane backendu”. Na świeżej instalacji ostrzeżenia w questach („ten boss zamyka krok”) nie mają powiązanego
     bossa (`boss_id: null`).
   - Miejsca i przedmioty w lochach dostają nazwę krainy z łask tego samego lochu. Przy pierwszym przebiegu łaski
     lochów nie mają jeszcze pozycji, więc np. Nokron dostaje „Rzeka Siofra” zamiast „Nokron, Wieczne Miasto”.
   Poprawka: każdy skrypt sam zakłada swój folder wyjściowy, kroki w kolejności zależności. Test: dwa przebiegi od
   zera dają identyczne dane.

## Questy

2. Przy kroku oznaczonym „za tobą” strona mówi dlaczego. Na przykład: „Aleksander czeka już na polu bitwy po
   Radahnie, więc ten krok jest za tobą” albo „Zaliczony jest dalszy krok: …”.
   Wiadomo: powód znamy w chwili liczenia (flaga położenia postaci albo flaga dalszego kroku), trzeba go tylko
   przekazać do widoku.
   Zbadane: `questSteps` w `mockup/app.js` zna oba przypadki. „Za tobą” bierze się z indeksu kroku, przy którym
   postać czeka (`here`). Krok zaliczony flagą dalszego kroku (`later`) jest dziś pokazany jako zwykły zrobiony, bez
   żadnej informacji. Poprawka: `questSteps` zapisuje przy kroku powód (krok, przy którym postać czeka, albo dalszy
   zaliczony krok), a oś czasu pokazuje go pod krokiem. Kilkanaście linii.

## Mapa

3. Ograniczenie przesuwania do granic mapy z gry w zwykłym trybie (bez szarego tła poza mapą), tak jak w trybie
   „Mój postęp”.
   Zbadane: `viewMap` ustawia granice z zapasem 1500 px poza obrazem mapy, stąd szarość. Tryb „Mój postęp” robi to
   dobrze w `applyArea` (granice plus najmniejsze przybliżenie wypełniające okno). Poprawka: ten sam mechanizm dla
   całej mapy, z obszarem 0…10496.
4. Filtry i ukrywanie warstw w trybie „Mój postęp”. Działają tylko na tym, co zostało odwiedzone albo zebrane.
   Zbadane w przeglądarce: przełączniki warstw w tym trybie są i działają (wyłączenie bossów ukrywa 86 znaczników).
   Problem w tym, że lista pokazuje liczby całej gry („Miejsca łaski 211/284”, „Broń 52/119”), więc wygląda jak
   lista wszystkiego. Poprawka: w tym trybie liczby i wiersze tylko z tego, co zaliczone; wiersz bez niczego
   zaliczonego znika. Wchodzi w punkt 14.
5. Stany mapy. Gra zmienia wygląd mapy po zdarzeniach. Z pamięci, do potwierdzenia: krater po spadającej gwieździe
   po Radahnie, stolica w popiele po Farum Azuli. W DLC zmiana przy pałacu.
   Zachowanie: „Mój postęp” pokazuje mapę według stanu z save'a i zmienia się sama, gdy stan się zmieni. W zwykłym
   trybie jest wybór stanu (przed / po).
   Zbadane: grafika kafli mapy nie ma stanów świata. W `eldenring.exe` jest jeden wzór nazwy kafla, a jego wariant to
   tylko bity fragmentów mapy; pozostałe warianty to stare kafle deweloperskie. Gra pokazuje zmiany napisami
   i ikonami z `WorldMapPointParam`, które włączają i wyłączają flagi:
   - krater: napis „Krater upadłej gwiazdy” po fladze 9417 (ustawia ją `common.emevd` po Radahnie), znika po
     wejściu do krateru (flaga 1045360500);
   - Leyndell: po fladze 118 (po Malikecie) napis zmienia się na „Leyndell, stolica popiołów”;
   - Enir-Ilim: ikona 211 pokazywana po fladze 62890 (nazwa flagi z listy społeczności, niepotwierdzona skryptem);
     ikona Belurat ma czarną, ciernistą chmurę.
   W atlasie ikon są też nieużywane przez parametry wersje (Belurat bez chmury, Leyndell w popiele, Donżon Cienia).
   Jeśli gra je podmienia, robi to w kodzie programu; trzeba sprawdzić w grze. Do tego 118 napisów z imionami postaci
   (np. Blaidd, Ranni) z flagami pokaż/ukryj, czyli spoilery questów.
   Propozycja: dane napisów i ikon z flagami w `extract_world.py`, strona wybiera napis i ikonę według flag (w „Moim
   postępie” z save'a, w zwykłym trybie przełącznik przed/po). Ikony miejsc wycięte z atlasów gry.
6. Okrągły Stół. Miejsca i przedmioty z Okrągłego Stołu wisiały w pustym miejscu na mapie.
   Zbadane: 24 punkty (20 NPC, 3 skarby, łaska) leżą w morzu na zachód od Limgrave. To położenie jest z danych gry
   (`WorldMapLegacyConvParam`, m11_10 → m60_40_35) i gra pokazuje tam ikonę łaski Okrągłego Stołu (ikona 48).
   Propozycja: jeden znacznik z ikoną Okrągłego Stołu w tym miejscu, po kliknięciu lista postaci, skarbów i łaski.
   Osobnej mapki nie ma z czego zrobić (gra nie ma grafiki wnętrza).
7. Najazdy na mapie: miejsca, w których atakują postacie-najeźdźcy (czerwone fantomy), z bossem i przedmiotami,
   które z nich wypadają.
   Zbadane: każda inwazja NPC to wywołanie wspólnego zdarzenia 90005790 w skrypcie mapy (argumenty: flaga
   pokonania, część na mapie). Jest 32 wywołań, 31 najeźdźców (Nerijus ma dwa), wszyscy z pozycją na mapie. Nagrody
   z zdarzeń 90005792, 90005774 i 90005768 (Queelign, zależne od etapu questu). Pokonanie sprawdza zwykła flaga,
   którą strona już umie czytać. Teraz dane ich nie mają: nie ma ich wśród bossów, 12 jest wśród zwykłych postaci,
   a ich przedmioty mają źródło „zdarzenie” bez imienia najeźdźcy.
   Propozycja: nowy plik `assets/data/invaders.json`, osobna warstwa „Najeźdźcy” na mapie ze stanem pokonania,
   w karcie przedmiotu źródło „nagroda za najeźdźcę”. Wątpliwe: 6 wpisów Moore'a (nie wiadomo, czy to inwazje).
8. Przeciwnicy z losowym łupem (np. broń z szansą 1%): pokazać wszystkie miejsca, w których dany przeciwnik się
   pojawia, a nie tylko część.
   Zbadane, przyczyny są w kodzie:
   - `extract_sources.py` zapisuje najwyżej 4 miejsca na grupę przeciwników (`MAX_SPOTS`), zwykle z jednego
     fragmentu mapy, i najwyżej 6 modeli (`MAX_ENEMIES`). Dotyczy 283 z 421 elementów ekwipunku z przeciwników.
   - Strona pokazuje z każdej grupy tylko pierwsze miejsce.
   - Błąd: pula jednorazowego łupu NPC jest czytana z NpcParam +0x1C, a to waga postaci. Właściwe pole to +0x34
     (Paramdex i dane). Przez to 114 przedmiotów z NPC nie ma źródła (np. dzwonki kuliste Gostoca, Corhyna i Łaty).
   - Licznik egzemplarzy liczy przedmiot dwa razy, gdy jest w dwóch wierszach puli.
   Przykład: wielki miecz wypędzonego rycerza ma 20 rycerzy na 4 mapach, w danych 4 punkty, wszystkie w Burzowym
   Całunie (9 rycerzy z Farum Azula pominiętych).
   Propozycja: bez limitów, plik `enemies.json` z każdym przeciwnikiem raz (ok. 20 tys. wierszy), w źródłach
   przedmiotu tylko odwołania. W karcie przedmiotu przycisk „N miejsc” pokazuje wszystkie punkty na mapie.

## Przedmioty

9. Jedna karta przedmiotu we wszystkich zakładkach. Teraz zakładka „Postać” pokazuje mniej niż „Przedmioty”.
   Zbadane: są dwa szablony. `openItem` (Przedmioty, nagrody bossów, linki z questów) i `itemBlock` (mapa i Postać).
   `itemBlock` nie ma ukrytych statystyk, „Jak zdobyć”, „Gdzie leży”, mini-mapy ani informacji o posiadaniu,
   a nagrody za bossa bierze z innego źródła danych. Sprawdzone w przeglądarce: talizman otwarty z Postaci nie ma
   ukrytych statystyk. Przy okazji: rodzaj przedmiotu jest brany z mapy, więc inkantacje spoza mapy dostają notkę
   „Czar”, a 34 z 78 sprawdzonych prochów duchów nie ma notki „Do czego służy”. Postać nie przekazuje karcie poziomu
   ulepszenia ani nasycenia broni.
   Poprawka: jedna funkcja karty, jedno miejsce ustalania rodzaju; Postać i mapa dokładają tylko swój kontekst
   (egzemplarz z ekwipunku, skarb z mapy). Skarb z kilkoma przedmiotami: lista, klik otwiera pełną kartę.
10. Przedmioty z Seamless Coop (save `.co2`).
    Zbadane: mod dodaje 12 przedmiotów, identyfikatory 8380001–8380012 (ustalone z pliku `ersc.dll`, nie
    z dokumentacji moda): Tiny Great Pot, Effigy of Malenia, Challenger's Lynchpin, Separation Mist, Judicator's
    Rulebook, Rune Decanter, Rot Essence 1–5, Dried Fingers. Save `.co2` to potwierdza (postacie „boink” i „finali”).
    Nazwy i opisy są tylko po angielsku w `SeamlessCoop\locale\english.json`. Polskich tekstów moda nie ma ani
    w grze, ani w internecie. Ikon mod nie ma własnych, używa ikon z gry, nie wiadomo których. Backend już zwraca te
    przedmioty, ale strona ich nie pokazuje, bo nie ma ich w katalogu przedmiotów, a w Postaci wyglądają jak pusty slot.
    Propozycja: osobna grupa „Seamless Coop” poza licznikami kolekcji, nazwy i opisy czytane z pliku moda przy
    przygotowaniu danych.
    Przy okazji znaleziony błąd: `extract_icons.py` pomija przedmiot, gdy w tej samej kategorii jest już przedmiot
    o tej samej nazwie. Przez to w katalogu brakuje m.in. dwóch wielkich run, kilku łez do flaszki, jednej zbroi
    i tarczy, które są w save'ach, a na stronie ich nie widać.

## Kronika

11. Historia dzień po dniu: co danego dnia zostało zrobione (bossowie, łaski, przedmioty, questy, śmierci).
    Wiadomo: save nie zapisuje dat. Historię może zbierać tylko sama aplikacja, porównując kolejne stany save'a
    w czasie działania, i zapisywać ją lokalnie.
    Zbadane: większość już jest. Backend trzyma bazę `backend/var/history.sqlite` (`history.py`) z migawkami,
    zdarzeniami (bossowie, łaski, skarby, kroki questów, poziom, zmiana obszaru) i śmierciami. Kronika już grupuje
    po dniach, ale tylko z ostatnich 300 zdarzeń.
    Brakuje: podsumowania dnia (czas gry, śmierci, poziomy, runy), śmierci w widoku, przedmiotów zdobytych bez flagi
    (kupione, z przeciwników, wytworzone; migawka nie trzyma ekwipunku) i przewijania do starszych dni.
    Największy problem: baza leży w folderze programu. Na Linuksie każda wersja rozpakowuje się do nowego folderu,
    a na Windowsie odinstalowanie usuwa `backend\var`, więc aktualizacja gubi historię. Propozycja: baza w folderze
    danych użytkownika (`%LOCALAPPDATA%\Elden Map`, `~/.local/share/elden-map`), z przeniesieniem starej.
    Ograniczenie: zmiany zrobione, gdy aplikacja nie działała, dostają czas zapisu pliku save, więc mogą trafić do
    innego dnia.

## Tryb „Mój postęp” dla całej strony

14. Przełącznik „Mój postęp” u góry po prawej, obok „Wszystko / Podstawka / DLC”, działający we wszystkich
    zakładkach (dopisane 2026-11-26). Gdy jest włączony, widać tylko to, co gracz już ma albo zrobił:
    - Przedmioty: tylko zebrane, bez list tego, czego jeszcze nie ma.
    - Bossowie: tylko pokonani.
    - Questy: tylko odkryte wątki. Widać kroki zrobione i bieżący krok, ale nie widać, ile kroków zostało ani jakie są
      dalsze.
    - Mapa: obecny tryb „Mój postęp” (fragmenty mapy, odwiedzone miejsca). Przyciski „Cała mapa / Mój postęp” w panelu
      mapy znikają, bo zastępuje je przełącznik u góry.
    - Przełącznik spoilerów jest wtedy wyszarzony, bo nie ma czego ukrywać.
    - Quest jest odkryty od pierwszego zrobionego kroku.
    - Przejście „pokaż na mapie” do miejsca poza odkrytym terenem nie wyłącza trybu: zaznacza to miejsce, a granice
      widoku są na ten czas zdjęte.

## Wygląd

12. Ikona strony (favicon).
    Zbadane: strona nie ma ikony (przeglądarka dostaje 404 na /favicon.ico). Ikona z plików gry odpada, bo `assets/`
    nie trafia do repozytorium ani paczek. Propozycja: własny `mockup/favicon.svg` (złoty romb w stylu znaku postaci
    z nagłówka) i jedna linia w `index.html`. Ikony SVG obsługują aktualne Chrome, Edge, Firefox i Safari (caniuse).
13. Szerokie monitory (ultrawide). Teraz treść jest przyklejona do lewej, a prawa strona jest pusta, dopóki nie
    otworzy się karta szczegółów.
    Zbadane w przeglądarce: widok ma limit 1400 px bez wyśrodkowania. Przy 3440×1440 pusta jest ponad połowa ekranu,
    a po otwarciu karty zostaje 1230 px pustki między treścią a kartą. Przy 1920×1080 karta zasłania część treści
    (panel „Kolekcja”). Wzorce z internetu (Material 3, SAP Fiori): na szerokim oknie lista i szczegóły stoją obok
    siebie.
    Propozycja: treść wyśrodkowana, a od ok. 1800 px karta szczegółów staje się kolumną obok listy zamiast wysuwanej
    szuflady. Poniżej tej szerokości zostaje szuflada.

## Ustalenia z właścicielem (2026-11-26)

- Punkt 7: najazdy to najeźdźcy, czerwone fantomy NPC.
- Punkt 5: w DLC chodzi o Enir-Ilim (czarny obszar na mapie, walka z Radahnem i Miquellą).
- Punkt 11: historia zbierana od instalacji nowej wersji.

## Kolejność implementacji (propozycja po badaniu)

Zrobione 2026-11-26 (commit 2bd5bd7): krok 1 w całości. Zamiast kolejności kroków okazało się, że kraina w lochach
była wybierana losowo przy remisie; teraz dwa przebiegi od zera dają te same dane. Rekomendacje z pytań przyjęte
przez właściciela w całości.

Zrobione 2026-11-26: krok 2 (punkty 2, 3, 4, 14). Przełącznik „Mój postęp” w górnym pasku działa we wszystkich
zakładkach i zawsze jest bez spoilerów (przełącznik spoilerów wyszarzony). „Pokaż na mapie” do miejsca spoza
odkrytego terenu zdejmuje tylko granice widoku (`mapPeek`), mgła i znaczniki zostają, a w panelu jest przycisk
„Wróć do mojego postępu”. Kronika zostaje bez zmian (to i tak historia tego, co zrobione).

Zrobione 2026-11-26: krok 3 (punkty 9 i 10). Jedna karta przedmiotu (`openItem`) we wszystkich widokach; Postać
dokłada założony egzemplarz (ulepszenie, nasycenie), mapa dokłada sekcję „To miejsce”, skarb z kilkoma przedmiotami
pokazuje listę. Rodzaj przedmiotu jest w katalogu (`kind`), więc notki „Do czego służy” są poprawne dla czarów,
inkantacji i prochów spoza mapy. Przedmioty Seamless Coop: osobna zakładka poza licznikami kolekcji, polskie nazwy
nasze, opisy po angielsku z pliku moda, ikona zastępcza.

Zrobione 2026-11-26: krok 4 (punkty 7 i 8). Najeźdźcy (25, bez Moore'a) jako warstwa mapy z kartą i nagrodami,
w karcie przedmiotu źródło „Nagroda za najeźdźcę”. Łup z przeciwników: wszystkie miejsca bez limitów (`enemies.json`),
przycisk w karcie przedmiotu pokazuje je na mapie (filtr „Gdzie wypada”).

Zrobione 2026-11-26: krok 5 (punkty 5 i 6). Miejsca mają ikony z gry i napisy zależne od flag z save'a (krater,
Leyndell w popiele, Enir-Ilim). Przełącznik „Stan świata: przed / po” był w 0.1.7, ale usunięty na prośbę właściciela
(nic praktycznie nie dawał). Twierdza Okrągłego Stołu to jedna ikona z listą postaci, najeźdźcy i skarbów. Zostaje: imiona postaci z mapy gry
(118 napisów) i ikony bez wpisu w parametrach (Leyndell szary, Belurat i Donżon Cienia bez czarnej chmury), dopóki
nie sprawdzimy w grze, kiedy się pojawiają.

Zrobione 2026-11-26 (po 0.1.10): imiona postaci z mapy gry (118 napisów, 71 znaczników postaci z ikoną z gry) według
pytania 2, Rycerze wielkiego naczynia jako pojedynki ze znaku i szara ikona Leyndell po Malikecie (wiki.gg nazywa ją
„Capital of Ash”). Potem Belurat bez czarnych cierni po spaleniu Zapieczętowanego Drzewa (Donżon Cienia nie ma
wariantu ikony), usunięty nieużywany endpoint `/api/chronicle` i pole `gtype`. Z listy pytań nic nie zostało.

Zrobione 2026-11-26: krok 6 (punkt 11). Baza historii w folderze użytkownika (kopiowana ze starego miejsca),
przedmioty zdobyte bez flagi w kronice, `/api/days` z podsumowaniem dnia (od 4:00), widok Kroniki z kartami dni
i przyciskiem „Starsze dni”.

Zrobione 2026-11-26: krok 7 (punkty 12 i 13). Ikona strony (złoty romb, SVG), treść wyśrodkowana, od 1800 px karta
szczegółów jako kolumna obok treści, od 2400 px szersza treść. Wszystkie kroki planu są zrobione.

1. Błędy, osobne szybkie wydanie dla kolegi: kolejność kroków przygotowania danych (punkt 1), przedmioty pomijane
   przez `extract_icons.py` (punkt 10), pula łupu NPC z NpcParam +0x34 (punkt 8).
2. Globalny „Mój postęp” (14) razem z filtrami mapy (4), granicami mapy (3) i powodem „za tobą” (2).
3. Jedna karta przedmiotu (9) i przedmioty Seamless Coop (10).
4. Wszystkie miejsca przeciwników (8) i najeźdźcy (7).
5. Napisy i ikony mapy zależne od flag (5) i Okrągły Stół (6).
6. Kronika dzień po dniu (11).
7. Ikona strony (12) i szerokie monitory (13).

## Pytania do właściciela po badaniu

Przy każdym rekomendacja.

1. Stany mapy: grafika mapy w grze się nie zmienia, zmieniają się napisy i ikony (krater po Radahnie, Leyndell
   w popiele, Enir-Ilim). Czy o to chodziło? Rekomendacja: tak to robimy; jeśli pamiętasz inny wygląd, zrzut ekranu.
2. Imiona postaci na mapie (118 napisów z gry, np. gdzie teraz stoi Blaidd): rekomendacja pokazywać tylko przy
   wyłączonych spoilerach, a w „Moim postępie” tylko postacie już spotkane.
3. Okrągły Stół: rekomendacja jeden znacznik z listą.
4. Najeźdźcy: rekomendacja tylko prawdziwe inwazje (31), bez czerwonych postaci z pojedynków (Ensha, siostry przy
   Millicencie). Moore'a pominąć, dopóki nie sprawdzimy w grze.
5. Miejsca przeciwników: rekomendacja na żądanie z karty przedmiotu („N miejsc” pokazuje je na mapie), bez stałej
   warstwy 20 tysięcy punktów.
6. Nazwy zwykłych przeciwników (gra ich nie ma): rekomendacja zostać przy „przeciwnik · kraina”, bez list
   społeczności o niesprawdzonej licencji.
7. Przedmioty Seamless Coop: rekomendacja polskie nazwy 12 przedmiotów piszemy sami, osobna grupa poza licznikami
   kolekcji, ikony zastępcze, chyba że zrobisz zrzut ekranu z gry.
8. Kronika: rekomendacja baza historii w folderze danych użytkownika (przeżyje aktualizację), dzień kończy się
   o 4:00, postacie z `.sl2` i `.co2` osobno, przedmioty kupione i wytworzone też w historii.
9. Szerokie monitory: rekomendacja karta szczegółów jako kolumna od 1800 px szerokości okna.
10. Ikona strony: rekomendacja złoty romb.
11. Tryb bez spoilerów w karcie przedmiotu otwartej z bossa, questu albo mapy: rekomendacja działa tak samo jak
    w zakładce Przedmioty (jedna karta, jedno zachowanie).

## Plan 2: statystyki bossów, wizerunki, asortyment kupców (2026-11-26)

Prośba właściciela: wizerunki i przedmioty za nie, ile run dają, ukryte statystyki bossów (odporności, na co słabi,
czym ich bić) i asortyment kupców z tym, co jeszcze zostało do kupienia. Badanie zrobione, kodu jeszcze nie ma.

### Co już jest
- Karta bossa: runy za pokonanie i nazwa wizerunku.
- Wymiany u Enii: 101 przedmiotów ma źródło „za Wizerunek…”, ale tylko w karcie przedmiotu. Wizerunek i boss nie
  pokazują, co można za nie dostać.
- Kupcy: źródło „kupiec” w karcie przedmiotu. Nie ma listy towaru kupca.

### Zbadane (pliki gry, układ pól z Paramdex, sprawdzone na danych)
- `NpcParam` (0x2E0 B, zgodne z rozmiarem wiersza): `+0x24` PŻ, `+0x1A4..+0x1C0` mnożniki obrażeń (zwykłe, cięte,
  obuchowe, kłute, magia, ogień, błyskawice, święte), `+0x108..` odporności na statusy (trucizna, zgnilizna,
  krwotok, śmierć, odmrożenie `+0x1E0`, sen `+0x126`, szaleństwo `+0x128`; 999 = odporny), `+0x2A8` postawa,
  `+0x4C` i dalej efekty specjalne, `resistCorrectId_*` (wzrost odporności po każdym wywołaniu statusu,
  `ResistCorrectParam`).
- Skalowanie obszaru: jeden z efektów bossa (`SpEffectParam`, 0x390 B) mnoży PŻ (`+0x10`) i odporności
  (`+0x108..`, `+0x2B4`, `+0x340`, `+0x344`). Sprawdzone na Margicie: 2521 × 1,656 = 4174 PŻ, cięte −10, święte 40,
  statusy 154 × 2,053 = 316, sen i szaleństwo odporny, postawa 80. Wszystko zgodne z Fextralife.
- Wizerunki: `EquipParamGoods +0x14` to runy za użycie (Złota runa [1] = 200, zgodne z grą; Wizerunek Zszywańca
  20 000).
- Kupcy: `ShopLineupParam +0x0C` flaga wyprzedania, `+0x10` flaga odblokowania (np. po oddaniu dzwonka), `+0x14`
  liczba sztuk (−1 bez limitu). Flagi wyprzedania backend czyta z save'a.

### Proponowane kroki
1. Statystyki bossa w karcie bossa: PŻ, osiem rodzajów obrażeń z oznaczeniem „słaby / odporny”, statusy z progami
   po kolejnych wywołaniach albo „odporny”, postawa. Dane z `NpcParam` i efektu skalowania, w `bosses_all.json`.
   Bossowie z kilkoma postaciami (duety, dwie fazy) mają każdą postać osobno.
2. „Czym bić”: rodzaje obrażeń i statusy, na które boss jest najsłabszy, plus bronie z Twojego ekwipunku, które je
   zadają (rodzaj ataku i status broni są już w danych przedmiotów). Gra nie ma listy „najlepszych broni”.
3. Wizerunki: w karcie wizerunku i bossa runy za użycie i lista wymian u Enii z zaznaczeniem, co już masz.
4. Asortyment kupca: karta kupca (z mapy i ze źródła „kupiec” w karcie przedmiotu) z listą towaru, ceną albo
   wymianą, limitem sztuk i stanem z save'a: wyprzedane, jeszcze nie odblokowane, dostępne.

### Pytania do właściciela (z rekomendacją)
1. NG+: rekomendacja na razie wartości dla pierwszego przejścia (tak jak grasz), skalowanie NG+ później.
2. Bronie „czym bić”: rekomendacja tylko z Twojego ekwipunku, bez list społeczności (licencja, zgadywanie).
3. Kupcy: rekomendacja stan „wyprzedane / do kupienia / zablokowane”. Gra zapisuje flagę wyprzedania; czy pamięta
   też, ile sztuk z kilku już kupiłeś, sprawdzę przy implementacji na save'ach.
4. Tryb bez spoilerów: rekomendacja statystyki bossa widać zawsze, gdy boss jest odkryty (tak jak dziś jego karta);
   towar kupca zablokowany do odblokowania pokazujemy jako „???”.

### Stan prac nad Planem 2 (wersja 0.2.0, ustalona z właścicielem)

Właściciel chce, żeby mapa i karty pokazywały wszystko, co da się wyczytać z gry, także rzeczy, których nie
wymienił. Po każdej partii zmian: audyt kompletności od strony danych gry (każda jednorazowa nagroda, każdy obiekt
na mapie z unikatowymi danymi), z liczbami pokrycia.

Zrobione (commity na main, niewydane):
- Jednorazowe łupy przeciwników na mapie (90005300/90005301 i pula o numerze encji): 248 znaczników, 94 skarabeusze.
- Kaplica Oczekiwania i mapy bez własnego przejścia (odwrócony wiersz WorldMapLegacyConvParam), w tools i backendzie.
- Statystyki bossów na karcie bossa (punkt 1 planu), sprawdzone z Fextralife.
- Mapa: przycisk ukryj/pokaż wszystko, tryb skupienia po przejściu z innej strony.

Do zrobienia, w tej kolejności:
1. Wizerunki: runy za użycie (EquipParamGoods +0x14) i wymiany u Enii w karcie wizerunku i bossa.
2. Karta wroga: Twoje bronie i teoretyczna liczba ciosów (badanie wzoru obrażeń w toku).
3. Karta NPC zamiast przejścia do questu: ikona albo render, opis, sklep z asortymentem i stanem z save'a, usługi,
   powiązania (quest, łup, podarunki, gdzie bywa). Klik w NPC na mapie otwiera kartę, z niej przejście do questu.
4. Teleporty na mapie (Waygate'y, skrzynie-pułapki, inne): znacznik, karta z miejscem docelowym, przycisk do celu.
5. Pełny audyt kompletności i uzupełnienie braków.
6. Przegląd kodu, dokumentacja (docs/10-world-data.md, 06-design), wydanie 0.2.0 po zgodzie.
