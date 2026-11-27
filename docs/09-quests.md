# Questy NPC z flagami zdarzeń (stan 2026-11-23)

Wynik: [`assets/data/quests.json`](../assets/data/quests.json): 46 questów (33 gra podstawowa, 13 DLC),
139 kroków, 368 różnych flag. Generator: [`tools/extract/build_quests.py`](../tools/extract/build_quests.py).

```powershell
python tools/extract/build_quests.py            # generuje quests.json (gra + cache TGA)
python tools/extract/build_quests.py --verify   # + sprawdza każdą flagę na 7 postaciach przez backend i ustawia confidence
```

Backend czyta dane z `backend/data/quests.json`, więc plik z `assets/data/` trzeba tam skopiować
(albo dopisać krok do `backend/tools/build_data.py`). Tego nie zrobiłem, bo `backend/` miał zostać bez zmian.

## Źródła i licencje

| Klucz (`sources`) | Co | Licencja / uwagi |
|---|---|---|
| `regulation` | `regulation.bin` z gry użytkownika: `ItemLotParam_map/_enemy`, pole `getItemFlagId` (flaga „przedmiot otrzymany”). Przedmioty dawane przez NPC mają loty 100000–119999 i flagi 400000–400999 | dane gry z lokalnej instalacji, czytane lokalnie, nic nie jest kopiowane do repo |
| `tga-ct` | [The-Grand-Archives/Elden-Ring-CT-TGA](https://github.com/The-Grand-Archives/Elden-Ring-CT-TGA) (plik `VERSION` = 1.140, `master` z 2026-10-22): *Event Flag Manager* (flagi pokonania 208 bossów) i *Event Flags/Deprecated/NPCs* (opisane flagi stanu ~25 NPC) | brak pliku licencji w repozytorium (domyślnie wszelkie prawa zastrzeżone). Bierzemy tylko numery flag (fakty techniczne), lokalnie, z podaniem źródła. Kopia: `assets/cache/community/tga/` (poza gitem) |
| `talk-esd` | skrypty rozmów (`/script/talk/*.talkesdbnd.dcx`) i `NpcName` z gry | dane gry; użyte tylko do przypisania bloku flag stanu do konkretnego NPC |
| `npc-block` | reguła „NPC opuścił stan początkowy” (patrz niżej) | wyprowadzone przeze mnie z TGA + porównania save'ów |
| `save-verified` | sprawdzenie na save'ach użytkownika (plik `co2`, 7 postaci) | |
| `general-knowledge` | treść kroków, `where`, `next`, pisane własnymi słowami po polsku | do potwierdzenia w grze |

Pobrane, ale nieużyte w wyniku (licencje restrykcyjne lub dane niepewne):

| Repo | Licencja | Dlaczego nie |
|---|---|---|
| [thefifthmatt/SoulsRandomizers](https://github.com/thefifthmatt/SoulsRandomizers) (`diste/Base/itemevents.txt` …) | *SoulsRandomizers License 1.0*: wszelkie prawa zastrzeżone, zakaz rozpowszechniania utworów pochodnych | posłużyło tylko jako wskazówka, że ID eventu = koniec bloku NPC (np. 3619 „Blaidd quest”); żadne dane z niego nie trafiły do JSON |
| [Hapfel1/er-save-manager](https://github.com/Hapfel1/er-save-manager) (`event_flags.json`) | od 22.07.2026 *Source-Available*, zakaz użycia w innym projekcie bez zgody (wcześniej MIT) | nie ma flag questów NPC |
| [laszloprekop/ER-save-Reader](https://github.com/laszloprekop/ER-save-Reader) (`quest_chains.rs`, rosetta) | MIT / Apache-2.0 | flagi questów NPC oznaczone przez autora jako niezweryfikowane i niezgodne z naszymi save'ami |
| [imCioco/ER_QuestPath-Lang](https://github.com/imCioco/ER_QuestPath-Lang) | MIT | tylko tłumaczenia tekstów, bez flag |

Licencje zapisane w `assets/cache/community/<źródło>/LICENSE*`. Teksty z Fextralife/MapGenie/wiki nie były używane.

## Jak liczone są kroki

Krok ma `flags` i `mode`: `any` znaczy, że wystarczy dowolna flaga (alternatywne zakończenia, np. Sellen: kris albo
dzwonek Sellen), a `all`, że potrzebne są wszystkie (Gurranq: komplet nagród). Każda flaga w JSON pochodzi z jednego ze źródeł:

1. Przedmiot od NPC / z questa (`regulation`). Najpewniejsze źródło: flaga ustawia się, gdy gracz dostaje przedmiot
   (np. 400391 = Karyjski odwrócony posąg od Ranni, 9502 = Run naprawy Księcia Śmierci). Flagi te są trwałe.
2. Boss pokonany (`tga-ct`): flaga `isDefeated` z TGA (np. 12040800 Astel, 21010800 Messmer).
3. Blok stanu NPC (`npc-block`). Każdy NPC ma 20 kolejnych flag: `+0` przyjazny, `+1` wrogi, `+3` martwy,
   `+5…+18` etap/położenie (dokładnie jedna naraz), `+19` techniczna. Blok przypisany po rozmowie NPC:
   `t<ID>.esd` ↔ `NpcName` `1<ID>00` (np. t106 = Ranni → 3740, t418 = Leda → 4440). Znaczenie pojedynczych
   etapów jest w większości nieopisane, więc używam tylko reguły „NPC opuścił stan początkowy” (dowolna z `+6…+17`
   albo `+3`), i to wyłącznie dla kroków „spotkaj NPC”. `+18` pomijam, bo u dwóch postaci jest ustawiona także w
   blokach bez NPC. Dla Yury `+6` jest stanem startowym (widać na nowej postaci), więc jest wyłączona.
4. Kroki kumulatywne (`"cumulative": true`): krok „spotkaj NPC” zalicza się też, gdy zaliczony jest
   dowolny późniejszy krok (skoro jest zakończenie, było i spotkanie). Ich `flags` zawierają flagi kolejnych kroków.

Każdy krok ma `sources`; kroki z flagą opisaną w TGA mają dodatkowo `tga_labels`.
`locks[]`: `{boss_en, boss_flag, step, warning}`. Identyfikator bossa (`boss_id`) dopisuje dopiero
`backend/tools/build_data.py` po fladze pokonania, w danych backendu.

### Weryfikacja i `confidence`

`--verify` czyta wszystkie 368 flag na 7 postaciach z `ER0000.co2` (backend `/api/flags`) i dla każdej postaci
liczy wektor kroków. Naruszenie = zaliczony krok, przed którym jest niezaliczony.

| Poziom | Warunek |
|---|---|
| `verified` | 0 naruszeń na 7 postaciach, nowa postać (najniższy poziom) ma 0 kroków, ktoś ma ≥ 2 kroki, wszystkie flagi z `regulation`/`tga-ct` (bez reguły bloku NPC) |
| `high` | 0 naruszeń, nowa postać 0 kroków, zaobserwowany ≥ 1 krok (np. quest korzysta z reguły bloku NPC) |
| `medium` | ≤ 1 naruszenie |
| `low` | więcej naruszeń albo flagi nieczytelne z save'a |

Wynik: 30 `verified`, 16 `high`, 0 `medium`/`low`. Na nowej postaci „chuj” (poz. 8) z 368 flag nie jest
ustawiona żadna; „finali” ma 148, „boink” 125. Dla „finali” i „boink” pliki `sl2` i `co2` dają identyczne wartości wszystkich 368 flag.
Wyniki dla każdej postaci są w JSON w `entries[].verification.chars`.

`verified` znaczy: flagi są prawdziwe i zachowują się spójnie na save'ach. Nie znaczy, że tekst kroku jest
sprawdzony w grze. Opisy i podpowiedzi `next` pochodzą z wiedzy ogólnej.

Pierwsza wersja miała naruszenia, które pomogły poprawić dane:

- `L("Unalloyed Gold Needle")` łapało też naprawioną igłę (400321) → krok „igła od Gowry'ego” jest teraz na 400310.
- Kroki z bossami niezwiązanymi z NPC (Godrick u Kennetha, Rykard u Ryi) psuły kolejność u postaci, które questa
  nie robiły → usunięte albo zamienione na `locks` (Rykard u Tanith).
- Flaga 400357 (Ślad czarnego noża) jest ustawiona od startu na każdej postaci → nieużywana.
- Seluvis, Fia, Moore, Florissax: zabicie NPC wcześniej lub inna ścieżka → krok „spotkanie” jest kumulatywny.

## Tabela questów

Kolumny postaci: `x` = krok zaliczony, `.` = nie (kolejno s1, s2, …).

| id | Quest | Gra | Kroki | Pewność | finali (221) | boink (180) | chuj (8) | Źródła flag |
|---|---|---|---|---|---|---|---|---|
| ranni | Wiedźma Ranni i Era Gwiazd | baza | 8 | verified | `xxxxxxxx` | `xxxxxxxx` | `........` | regulation, tga-ct |
| blaidd | Blaidd, Półwilk | baza | 3 | verified | `xxx` | `xxx` | `...` | regulation, tga-ct |
| iji | Iji, mistrz kowalstwa | baza | 2 | high | `xx` | `xx` | `..` | npc-block, regulation |
| seluvis | Mistrz Seluvis | baza | 2 | verified | `xx` | `xx` | `..` | regulation |
| sellen | Czarodziejka Sellen | baza | 5 | verified | `xxxxx` | `xxxxx` | `.....` | regulation |
| rya | Rya i Wulkaniczny Dwór | baza | 2 | verified | `xx` | `xx` | `..` | regulation |
| tanith | Tanith i zlecenia Wulkanicznego Dworu | baza | 5 | verified | `xxxxx` | `xxxxx` | `.....` | regulation |
| bernahl | Rycerz Bernahl | baza | 3 | verified | `xxx` | `xxx` | `...` | regulation |
| varre | Białolicy Varré | baza | 4 | verified | `xxxx` | `xxx.` | `....` | regulation, tga-ct |
| alexander | Alexander, Wielki słojownik | baza | 4 | verified | `xxxx` | `xxxx` | `....` | regulation, tga-ct |
| millicent | Millicenta | baza | 4 | verified | `xxx.` | `xxxx` | `....` | regulation |
| gowry | Mędrzec Gowry | baza | 3 | verified | `xxx` | `xx.` | `...` | regulation |
| fia | Fia, Towarzyszka na Łożu Śmierci | baza | 4 | verified | `xxxx` | `xxxx` | `....` | regulation, tga-ct |
| d | D, Łowca Umarłych | baza | 3 | high | `xxx` | `xxx` | `...` | npc-block, regulation |
| rogier | Czarodziej Rogier | baza | 3 | high | `xxx` | `xxx` | `...` | npc-block, regulation |
| boc | Półczłowiek Boc | baza | 2 | verified | `xx` | `xx` | `..` | regulation |
| patches | Łata | baza | 3 | verified | `xxx` | `xxx` | `...` | regulation, tga-ct |
| diallos | Rycerz Diallos | baza | 2 | high | `x.` | `x.` | `..` | npc-block, regulation, tga-ct |
| jar-bairn | Słojątko | baza | 2 | high | `..` | `x.` | `..` | npc-block, regulation |
| kenneth | Kenneth Haight | baza | 2 | verified | `x.` | `xx` | `..` | regulation |
| irina-edgar | Irina i Edgar | baza | 4 | verified | `xxxx` | `xxxx` | `....` | regulation, tga-ct |
| hyetta | Hyetta i Trzy Palce | baza | 2 | high | `x.` | `xx` | `..` | npc-block, regulation |
| goldmask | Corhyn i Złota Maska | baza | 4 | high | `xxxx` | `xxxx` | `....` | npc-block, regulation |
| dung-eater | Łajnożerca | baza | 4 | verified | `xxxx` | `xxxx` | `....` | regulation |
| latenna | Latenna, albinauryka | baza | 2 | verified | `xx` | `xx` | `..` | regulation |
| nepheli | Nepheli Loux | baza | 2 | verified | `x.` | `xx` | `..` | regulation |
| thops | Czarodziej Thops | baza | 2 | high | `xx` | `xx` | `..` | npc-block, regulation |
| gideon | Sir Gideon Ofnir | baza | 2 | high | `xx` | `xx` | `..` | npc-block, regulation, tga-ct |
| roderika | Roderika | baza | 2 | verified | `xx` | `xx` | `..` | regulation |
| gurranq | Gurranq, Bestialski Duchowny | baza | 3 | verified | `xxx` | `xxx` | `...` | regulation |
| yura | Yura, Łowca krwawych palców | baza | 3 | high | `xxx` | `xxx` | `...` | npc-block, regulation |
| boggart | Szubrawiec Boggart | baza | 2 | verified | `xx` | `xx` | `..` | regulation |
| melina | Melina i Kuźnia Olbrzymów | baza | 4 | verified | `xxxx` | `xxxx` | `....` | regulation, tga-ct |
| leda | Leda, rycerz igły | DLC | 3 | high | `xxx` | `x..` | `...` | npc-block, regulation, talk-esd, tga-ct |
| ansbach | Pan Ansbach | DLC | 3 | high | `xxx` | `...` | `...` | npc-block, regulation |
| freyja | Freyja, Lwia Grzywa | DLC | 3 | high | `xxx` | `...` | `...` | npc-block, regulation |
| hornsent | Rogaty przybysz | DLC | 4 | verified | `xxxx` | `xx..` | `....` | regulation, talk-esd, tga-ct |
| hornsent-grandam | Starowina, rogata przybyszka | DLC | 2 | verified | `xx` | `xx` | `..` | regulation |
| moore | Moore i Ród poszukiwaczy | DLC | 2 | high | `xx` | `..` | `..` | npc-block, regulation |
| thiollier | Thiollier i św. Trina | DLC | 4 | high | `xxxx` | `....` | `....` | npc-block, regulation |
| ymir | Hrabia Ymir | DLC | 5 | verified | `xxxxx` | `.....` | `.....` | regulation, tga-ct |
| dane | Dane, Suchy Liść | DLC | 2 | verified | `xx` | `x.` | `..` | regulation |
| igon | Igon | DLC | 3 | verified | `xxx` | `...` | `...` | regulation, tga-ct |
| jolan | Jolán i Anna, szermierki nocy | DLC | 2 | verified | `xx` | `..` | `..` | regulation |
| queelign | Rycerz ognia Queelign | DLC | 2 | verified | `x.` | `xx` | `..` | regulation |
| florissax | Florissax, starożytna smoczyca | DLC | 2 | high | `xx` | `..` | `..` | npc-block, regulation |

Pozostałe postacie (grandes, prophet, Mokki, Ser Davick) też nie mają naruszeń, patrz `verification` w JSON.

Ikona questa = `icon` charakterystycznego przedmiotu z `items.json` (np. Ranni → Pierścień ciemnego księżyca 3050,
Alexander → Odłamek Alexandra 18871). Nazwy NPC, miejsc i przedmiotów w tekstach są z plików gry (`polpl`); żeby
uniknąć błędnej odmiany, miejsca występują jako „w lokacji X” albo „przy łasce X”, a przedmioty jako „przedmiot X”.
W `quest_steps_pl.json` znacznik (`{p:…}`, `{i:…}`, `{n:…}`) wstawia oficjalną nazwę w mianowniku, więc stoi tylko tam,
gdzie mianownik pasuje (podmiot, po dwukropku, w nawiasie); w innych przypadkach postać jest odmieniona zwykłym tekstem
(„z Blaiddem”, „Bocowi”). Klucz znacznika to angielska nazwa z plików gry; nieznany klucz przerywa `quest_steps.py`.
Teksty przejrzane w całości (2026-11-27): z angielskim oryginałem QuestPath i pod kątem odmiany po podstawieniu nazw;
podpowiedzi bez spoilerów (`safe`) mówią, dokąd iść albo z kim porozmawiać, bez zdradzania losów postaci.

## Czego brakuje / problemy

1. Kroki pośrednie bez flagi. Wiele etapów to tylko rozmowa albo przejście NPC w inne miejsce (np. Ranni:
   przyjęcie służby w Wieży Ranni, Seluvis, Iji; Boc w Liurnii; Blaidd w więzieniu). Takie kroki nie mają flagi
   zaliczenia, ale flaga położenia NPC (`+5…+18`, sekcja „Bieżący krok według położenia postaci”) pokazuje, przy
   którym z nich postać czeka. Nieprzypisane zostały stany sprawdzane w wielu mapach naraz (logika ogólna, głównie
   `common.emevd`) i stany po zakończeniu wątku.
2. Brak questów: Rennala, Shabriri (wspomniany przy Yurze), Enia / Dwa Palce, Hewg, Ensha, Albus i medaliony
   Świętego Drzewa, Pidia, Miriel, Gostoc, Jerren (osobno), kupcy. Z DLC: Jolán pokryta tylko 2 krokami, St. Trina jest
   częścią questa Thiolliera, brak Logura, Lionela, Moonrithylla i questów „Ród poszukiwaczy” (dostawy Moore'a
   400750–400755 usunięte z kroków, bo zabicie Moore'a zamyka quest bez dostaw; wspomniane w notatkach).
3. Kolejność i opisy z wiedzy ogólnej. Weryfikacja na save'ach sprawdza tylko kolejność i to, że nowa postać
   ma zero; nie potwierdza, że tekst kroku dokładnie opisuje zdarzenie (np. kiedy Fia daje Podniszczony sztylet,
   co dokładnie odpala 400394 Miniatura Ranni). Pewność `verified` dotyczy flag, nie tekstu.
4. Ścieżki alternatywne. Kroki „zakończenie” mają `mode:"any"` po wszystkich znanych wariantach (np. Millicenta:
   pomoc/zdrada). Jeśli gracz zabije NPC wcześnie, późniejsze kroki zostaną niezaliczone na zawsze, a aplikacja
   pokaże to jako quest niedokończony. Flaga śmierci (`npc_block + 3`) jest dostępna, gdyby UI miało pokazać
   „quest przerwany”.
5. Blokady (`locks`): 8 wpisów (Bestia Eldeńska dla trzech runów naprawy i Ranni, Rykard, Malenia, Messmer,
   Bayle). Treść ostrzeżeń jest z wiedzy ogólnej; „Messmer → Rogaty przybysz” jest sformułowane ostrożnie („może”).
6. TGA nie ma licencji. Używamy tylko numerów flag. Gdyby dane miały trafić do publicznego repo, warto zapytać
   autorów TGA albo zostawić w JSON tylko flagi z `regulation.bin` (to dane z gry użytkownika, generowane lokalnie).
7. Backend czyta `backend/data/quests.json` (nadal pusty), więc trzeba skopiować wynik albo zmienić
   `backend/tools/build_data.py`.

## Tryb bez spoilerów: teksty kroków (2026-11-23)

Część kroków zdradzała losy postaci („Iji ginie”, „Podejdź do ciała Rogiera”, nagrody typu „Dzwonek kulisty X”
po śmierci NPC, zwroty akcji jak Yura/Shabriri). `tools/extract/quest_spoilers.py` dodaje do takich kroków
`text_safe` / `next_safe` (podpowiedź bez rozstrzygnięcia) i do ostrzeżeń `warning_safe`; `build_quests.py` stosuje to
przy generowaniu, a `python tools/extract/quest_spoilers.py` na gotowym `quests.json`. Frontend w trybie
„bez spoilerów” pokazuje wersję bezpieczną dla kroków jeszcze niezaliczonych i w „Co dalej”, a po zaliczeniu kroku pełny
tekst. Obecnie 28 kroków + 1 ostrzeżenie (Igon).

## Wejście do Królestwa Cieni (2026-11-25)

Wątek dopisywany na stronie (`dlcEntryQuest` w `mockup/app.js`), bo w danych questów go nie ma:
Radahn (flaga pokonania + wariant 12…), dowolna łaska Pałacu Mohgwynów (m12_05), Mohg, Pan Krwi, a na koniec
obszar startowy DLC (flaga 62002) lub pierwsza łaska DLC „Cmentarna Równina”. Kroki mają wersje bez spoilerów.
Na mapie: znacznik „Wejście do DLC” przy łasce „Kokon Niebianina” (mapa podziemi) i „Początek Królestwa Cieni”
(mapa DLC); kliknięcie otwiera wątek.

## Pełne listy kroków (2026-11-25): `quest_steps.py` + `quest_steps_pl.json`

45 questów, 427 kroków (wcześniej 139), 160 z własną flagą. Opisy kroków z QuestPath (imCioco,
[ER_QuestPath-Lang](https://github.com/imCioco/ER_QuestPath-Lang), MIT, `tools/extract/LICENSE.questpath.txt`),
przetłumaczone na polski; nazwy własne w znacznikach `{p:}` `{i:}` `{n:}` → oficjalne polskie nazwy z gry
(nieznalezione zostają po angielsku). Podpowiedzi QuestPath (`hint`) = wersje bez spoilerów (`text_safe`).
- Kroki QuestPath dopasowane do naszych (`match`) przejmują flagi i identyfikatory (ostrzeżenia `locks` działają).
- Flagi położenia NPC z TGA: +5 w bloku to stan początkowy (ustawiony od startu gry, sprawdzone na nowej
  postaci) i nie oznacza spotkania; wykluczone, tak samo +6 u Yury.
- `later`: krok bez własnej flagi zalicza się, gdy zaliczony jest dalszy etap. Bez `alt` (wybory wykluczające się)
  i bez `extra` (nasze kroki z flagą bez odpowiednika, wstawiane za poprzednim dopasowanym krokiem).
- `end` (QuestPath s98/s99, np. śmierć NPC) kończy wątek. Krok oznaczony w `quest_steps_pl.json` jako `dead`
  („Millicent nie żyje”, 16 questów) zalicza flaga śmierci postaci: blok NPC + `build_quests.DEAD_FLAG` (3).
- `like`: krok dostaje też flagi wskazanych kroków innego questu. Wątek Gowry'ego to część historii Millicent, więc
  jego kroki od protezy do starcia z siostrami wskazują kroki Millicent (`millicent:p3`, `p5`, `p6`, `p8`); jego
  własna flaga rozmowy 1050389221 nie jest ustawiana u żadnej z 7 sprawdzonych postaci.
- Strona: quest ukończony, gdy zaliczone jest zakończenie albo wszystkie kroki poza alternatywnymi; cały wątek
  (z podwątkami) ukończony, gdy jest ukończony quest główny i każdy rozpoczęty podwątek. Ukończony quest z otwartym
  podwątkiem wskazuje go w „Co dalej”, a ostrzeżenia `locks` po ukończeniu znikają.
- Sprawdzone na 3 postaciach: nowa (poziom 13) ma 2 kroki (prawdziwe), średnia i ukończona nie mają luk poza
  Rogierem (śmierć na końcu, kroki pośrednie bez flag).

QuestPath (mod na Nexusie) trzyma logikę kroków w kodzie DLL, więc flag nie da się z niego odczytać (sprawdzone:
w zasobach są tylko tłumaczenia). Następny krok: flagi ze skryptów rozmów NPC w plikach gry (talk ESD,
`tools/extract/talk_flags.py`, na razie lista flag bloku NPC używanych przez skrypt, np. Boc 3941–3948).

## Flagi ze skryptów rozmów NPC (2026-11-25): `esd.py`, `talk_quests.py`, `quest_talk_flags.json`

Skrypty rozmów (`/script/talk/<mapa>.talkesdbnd.dcx` → `t<TalkID><wariant>.esd`, TalkID = cyfry 2–4 z NpcName
`1<ID>xx`) czytane własnym parserem `tools/extract/esd.py` (format „fsSL” 64-bit: grupy stanów, stany, warunki,
polecenia, argumenty, bajtkod wyrażeń). Polecenie 1/11 = ustaw flagę (numer, stan); argumenty `TalkParam`
(np. 22300100) → `TalkParam` +0x04 = id kwestii w `TalkMsg`; opcje wyboru: `EventTextForTalk`.
Rozmowa = grupa stanów: flagi ustawiane w niej + jej kwestie i opcje menu (`python tools/extract/talk_quests.py 223`).

Wniosek: skrypty rozmów nie ustawiają flag z bloku NPC (3940…), tylko flagi przypisane do miejsc
(np. Boc: 31159206 „Daj igłę do szycia” w Przybrzeżnej Jaskini, 1039519205 „Możesz mnie tak nazywać” w Liurnii,
11109805… spotkanie w Leyndell). Przypisanie rozmów do kroków (156 kroków w 38 questach, 210 flag) zrobione
na podstawie kwestii i sprawdzone stanem flag na 7 postaciach (`quest_talk_flags.json`: flaga + uzasadnienie).
Po dołączeniu: 255 kroków z własną flagą (wcześniej 160); postać nowa ma 2 kroki (prawdziwe), pozostałe nie mają luk
poza Rogierem (wątek kończy się śmiercią, kroki pośrednie bez flag).

## Bieżący krok według położenia postaci (2026-11-26)

Flagi z bloku NPC od +5 do +18 (opisy TGA) mówią, gdzie postać teraz czeka. Gra przestawia je sama, także bez
rozmowy (np. po śmierci Iriny Hyetta czeka przy klifach), więc nie znaczą „krok zrobiony”. Trafiają do pola `here`
kroku: jeśli postać czeka przy kroku N, to N jest bieżący, a wcześniejsze kroki bez dowodu są oznaczone „za tobą”
(zrobione albo pominięte, save tego nie rozróżnia, ale nie są już do zrobienia). Flagi +1 (wrogość) i +3 (śmierć)
zostają flagami zaliczenia.

Opisy TGA znają tylko część położeń, więc resztę ustalono z plików gry. `tools/extract/npc_states.py` dla każdej
flagi bloku podaje mapy, których skrypty zdarzeń (`/event/<mapa>.emevd.dcx`) ją sprawdzają, oraz kwestie, które postać
mówi w tym stanie (`talk_quests.state_lines`):

    python tools/extract/npc_states.py 220 3660    # TalkID postaci i początek jej bloku flag

Mapa, której skrypt sprawdza flagę stanu, to zwykle miejsce, gdzie gra wtedy stawia postać (Aleksander +6: tylne
wejście do tunelu Gael, +8: pole bitwy z Radahnem). Mapy wspólne dla wielu stanów naraz to logika ogólna, nie
położenie. Przypisanie stanu do kroku jest w `tools/extract/quest_npc_states.json` (id questu → id kroku → lista
przesunięć; 40 questów, 109 kroków, 113 stanów), a `quest_steps.py` dopisuje te flagi do `here`. Stany „odszedł”,
„nie żyje” i „quest skończony” nie są przypisane do zwykłych kroków. Stan początkowy (ustawiony już u nowej postaci)
może wskazywać tylko pierwszy krok questu: inaczej wcześniejsze kroki wyglądałyby na „za tobą”, choć gracz ich nie
zrobił. Tak było u Latenny (czeka w Szopie śpiącego wilka od początku gry, przed rozmową z Albusem) i Ansbacha;
oba przypisania usunięte. Sprawdzenie: flagi bloku NPC na prawie nowej postaci.

Sprawdzone na 7 postaciach: żadna nie ma bieżącego kroku przed krokiem potwierdzonym flagą rozmowy albo przedmiotu
w sposób, który zmieniłby widok. Zostają przypadki, gdzie flaga położenia jest starsza niż ostatnia potwierdzona
rozmowa (Boc, Patches, Szubrawiec, Moore, Florissax, Kenneth). Przyczyna nie jest ustalona. Wtedy bieżący jest pierwszy niezaliczony krok po potwierdzonych, tak jak bez `here`.
