# Dane świata: bossowie, miejsca, przedmioty na mapie, NPC

Generuje: `tools/extract/extract_world.py` (część `python tools/extract/run_all.py`). Wszystko z plików gry
użytkownika, poza nazwami części bossów z lokalnej tabeli Cheat Engine (zapas, gdy gra nie podaje nazwy).
Wyniki w `assets/data/` (lokalnie, poza repozytorium).

## Weryfikacja na save'ach (2026-11-23)

| Postać | Bossowie gra podst. | Bossowie DLC | Przedmioty z mapy | Łaski |
|---|---|---|---|---|
| finali (poz. 221) | 153 / 170 | 40 / 42 | 2840 / 3336 | 406 / 422 |
| boink (poz. 180) | 147 / 170 | 10 / 42 | 2061 / 3336 | 328 / 422 |
| Ser Davick (poz. 13) | 3 / 170 | 0 / 42 | 10 / 3336 | 8 / 422 |
| chuj (poz. 8) | 1 / 170 | 0 / 42 | 2 / 3336 | 3 / 422 |

## Źródła w plikach gry

### Bossowie: `GameAreaParam` (216 wierszy)
- ID wiersza = flaga pokonania bossa (np. 10000800 Godrick, 1043300800 boss polowy na `m60_43_30`).
- `+0x04` i32 runy (single), `+0x08` runy (multi), `+0x48` `float[3]` pozycja, `+0x54` bajty area/gx/gz
  (bywają mylące, np. Messmer → `m15`; dlatego pozycję bierzemy z pliku mapy: wróg o EntityID = flaga).
- Nazwy (polskie, z gry): skrypty zdarzeń EMEVD `/event/<mapa>.emevd.dcx`. Wspólne zdarzenie
  `90005870` = pasek życia bossa, argumenty `(encja, ID nazwy w NpcName, slot)`. Zapasowo: ID z `NpcName`
  (zakres 900000000–999999999) w pobliżu flagi w argumentach. Nazwy z tabeli CE są tylko zapasem, bo bywają
  błędne (pod flagą Rennali wpis „Night's Cavalry”).
- Nagrody (parser `tools/extract/emevd.py`): w `common_func.emevd` 16 funkcji przyznaje łup
  (`2003[4]` AwardItemLot / `2003[36]` AwardItemsIncludingClients z parametrem). Dla każdej znamy bajt
  argumentu z pulą (np. `90005860`: bajt 16). Bierzemy pulę z wywołań `2000[6]` w skryptach map tylko wtedy,
  gdy w tym samym wywołaniu jest flaga dokładnie jednego bossa, plus zdarzenia mapy z literalnym
  AwardItemLot sprawdzające flagę jednego bossa. Wcześniejsza heurystyka („dowolna pula obok flagi”) dawała
  błędne nagrody (Margit → Winogrono Shabririego) i została usunięta. Uwaga: `GameAreaParam` ma wiersz o ID 0,
  który trzeba pominąć przy szukaniu flag w argumentach.
- Nagrody bossów lochów: globalna flaga 9xxx (ustalone porównaniem save'ów: Ser Davick vs chuj):
  zdarzenie śmierci bossa w lochu (`2003[12]` HandleBossDefeat) ustawia globalną flagę „boss pokonany”
  9xxx (`2003[66] SetEventFlag(0, 9xxx, 1)`), a `common.emevd` w zdarzeniu startowym inicjuje zdarzenia
  `InitializeEvent(slot, 1200…, 9xxx, pula, 0, flaga_otrzymania)`, np. `(9202, 20020)` = Prochy
  szlacheckiego czarodzieja za Ogara grobowca z Katakumb Burzowego Frontu. Pule nagród lochów mają małe
  ID (20000+), stąd wcześniejszy próg `> 100000` je gubił. Zdarzenie z HandleBossDefeat ma pierwszeństwo,
  wywołania wspólnych funkcji z flagą 9xxx są zapasem.
- Ikona: wizerunek (remembrance) albo pierwszy przedmiot z nagrody (najpierw znaczące: broń, zbroja,
  talizman, czar…, potem dowolny poza złotymi runami; bez „gołych” zbroi `Głowa/Tułów…`, ID < 101000),
  a gdy boss nie ma własnej nagrody, ikona imiennika (kolejni Strażnicy Drzewa, Nocna Kawaleria).
  Ikonę ma 201 z 212 bossów, kolejnych 8 ma portret wyrenderowany z modelu 3D gry (pole `model`, `render`;
  `render_bosses.py`, opis w [08-assets](08-assets.md)). Ludzcy bossowie (Leda, Łata, Hrabia Ymir, model `c0000`) są składani z części wg CharaInitParam + FaceParam. Wszystkich 212 bossów ma obrazek.
- Popioły wojny i dzwonki kulisty mają w grze wspólne ikony według typu, to nie błąd danych.
- Region: kraina najbliższej łaski (PL). Łaski DLC nie mają krainy w danych gry, więc jest brana z danych backendu (EN → PL przez PlaceName).

### Pliki map: MSB (`/map/mapstudio/mAA_BB_CC_00.msb.dcx`, 944 pliki)
Parser: `tools/extract/msb.py` (zgodny z układem MSBE z SoulsFormats):
- części: wróg (typ 2) → dane typu `+0x08` ThinkParamID, `+0x0C` NpcParamID, `+0x10` TalkID, `+0x18` CharaInitID;
  EntityID w danych encji. (Wcześniej `+0x18` było błędnie traktowane jako TalkID i lista NPC zawierała najeźdźców zamiast
  postaci, z którymi się rozmawia; poprawione 2026-11-23: 304 NPC, m.in. kupcy, Blaidd, Hewg, Gurranq.)
- zdarzenia skarbu (typ 4) → dane typu `+0x08` indeks części (obiekt, przy którym leży), `+0x10` ItemLotID.

### Przedmioty: `ItemLotParam_map` (wiersz 0x98 B)
`+0x00` 8× i32 ID przedmiotu, `+0x20` 8× i32 kategoria (1 goods, 2 broń, 3 zbroja, 4 talizman, 5 popiół wojny),
`+0x80` u32 flaga podniesienia (getItemFlagId), `+0x8A` 8× u8 liczba. Kolejne ID puli (lot+1…) to
dodatkowe przedmioty z tego samego miejsca.

Kategorie na mapie: z kategorii przedmiotu + typ goods `EquipParamGoods +0x3E`:
0 użytkowe/multiplayer, 1 kluczowe, 2 materiały, 3 wizerunki, 5/17 czary, 7/8 prochy duchów, 10 kryształowe łzy,
12 notatki/listy, 14 ulepszenia (złote nasiona, święte łzy, kamienie kowalskie, DLC: odłamki Ostrodrzewa,
prochy czcigodnych duchów), 15 wielkie runy, 16/18 inkantacje. Dalszy podział po polskiej nazwie
(dzwony kupców, kamienie pamięci, osełki, klucze kamiennego miecza, fragmenty map, receptury).

### Miejsca: `WorldMapPointParam`
`+0x20` area/gx/gz, `+0x24` pozycja, `+0x04` flaga pokazania punktu (6001 = zawsze), `+0x0C` ikona `MENU_MAP_<id>`,
`+0x30 + 12·i` do 8 napisów (PlaceName, flaga włączenia, flaga wyłączenia; flaga < 10 = zawsze), `+0x90 + i` rodzaj
napisu (0 miejsce, 1 imię postaci) → 294 miejsca. Kategoria po nazwie (katakumby, jaskinie/pieczary, tunele,
wiekowięzienia, groby bohaterów, wieże, ruiny, kościoły, zamki, forty, szopy, pomniejsze Złote Drzewa, wioski).

Stany świata: grafika kafli mapy ich nie ma (wariant kafla to tylko bity fragmentów mapy). Zmieniają się napisy i ikony
miejsc: „Krater upadłej gwiazdy” po fladze 9417 (common.emevd po Radahnie, znika po wejściu do krateru, 1045360500),
„Leyndell, stolica popiołów” po fladze 118 (po Malikecie), Enir-Ilim (ikona 211) po fladze 62890. Ikona 62 (Leyndell
szary) nie ma wpisu w parametrach i strona jej nie używa, dopóki nie sprawdzimy w grze, kiedy się pojawia. Imion postaci
(118 napisów rodzaju 1) strona na razie nie pokazuje. Twierdza Okrągłego Stołu (m11_10) jest jednym znacznikiem z ikoną 48
w miejscu łaski Stołu Utraconej Łaski; jej postacie, najeźdźca i skarby są w liście po kliknięciu.

### NPC
Wrogowie z TalkID ≠ −1 w MSB + `NpcParam +0x0C` (nameId) → `NpcName` (PL). 304 postacie (z duplikatami
w różnych fazach questów).

### Najeźdźcy (czerwone fantomy NPC)
Inwazja to wywołanie wspólnego zdarzenia `90005790` (common_func) w skrypcie mapy przez `InitializeCommonEvent`:
argumenty po ID zdarzenia: warunek, flaga pokonania, obszar, obszar, encja części MSB. Nagrody: `90005792` (flaga, obszar,
obszar, encja, pula), `90005774` (flaga, pula, flaga otrzymania) i `90005768` (Queelign: flaga, pula, flaga, pula…,
zależne od etapu questu). Pula to łańcuch wierszy `ItemLotParam_map` (lot, lot+1…), tak jak skarby. `NpcParam +0x133`
(teamType 27) nie wystarcza, bo mają go też czerwone postacie z pojedynków. Moore (6 wywołań w DLC) jest pominięty,
dopóki nie sprawdzimy w grze, czy to prawdziwe inwazje.

### Lochy → mapa świata: `WorldMapLegacyConvParam` (196 wierszy, 48 B)
`+0x04` src area/gx/gz, `+0x08` src pozycja, `+0x14` dst area/gx/gz, `+0x18` dst pozycja, `+0x24` punkt bazowy.
Punkt `src` w lochu odpowiada `dst` na kaflu świata; łańcuchy (`m35`→`m11`→`m60`) rozwiązywane rekurencyjnie
(najpierw wiersze prowadzące wprost do m60/m61). Lochy legacy (Stormveil, Leyndell, Akademia, wieże)
przeliczane z przesunięciem; w małych lochach (katakumby m30, jaskinie m31, tunele m32, m39–m43)
cała zawartość ląduje przy wejściu (`approx: true`).

Wyjątki (2026-11-25):
- Podziemia m12 (Siofra, Ainsel, Głębiny, Pałac Mohgwynów) są przeliczane z przesunięciem jak lochy legacy
  i zapisywane na osobnej mapie gry `M01` (te same piksele co powierzchnia; wszystkie 339 skarbów trafia
  w teren mapy podziemi). Wcześniej wszystko lądowało w 6 punktach na powierzchni.
- Przeklęte Farum Azula m13: gra rysuje je w wirze burzy na wschód od Szczytów Olbrzymów. m13 ma cztery
  wiersze `WorldMapLegacyConvParam` z różnymi przesunięciami; najbliższy (10/132) prowadził na Szczyty.
  Właściwy jest wiersz 11 (punkt bazowy → m60_51_43): px = 8488,9 + x, py = 4803,7 − z, skala 1:1. Obiekty
  leżą wtedy na ruinach z grafiki mapy (arena Malikitha na okrągłej platformie, Wielki Most). Stała `FARUM`
  w `extract_world.py` i `backend/erbackend/worldmap.py`. Pozostałe lochy (Burzowy Całun, Leyndell, Akademia,
  Haligtree, Wulkaniczny Dwór, lochy DLC) i otwarty świat sprawdzone nakładką na grafikę mapy (2026-11-25).
- Łaski w lochach (194 z 422): `extract_data.py` liczy tylko m60/m61; `extract_world.py` przelicza resztę
  tym samym `World.to_map` co bossów i skarby i dopisuje do `graces.json`.
- Krainy: podkraina z menu podróży (Płaczący Półwysep, Nokron…; w DLC tylko w lochach m20–m28), kraina
  główna tylko dla otwartego świata DLC. Nazwy jak w grze („Cmentarna równina”, „Ziemie Wieży”).

## Pliki wynikowe

| Plik | Liczba | Pola |
|---|---|---|
| `bosses_all.json` | 212 | id/flag, name (PL), name_en, location, region_pl, runes, map_id, dlc, icon, remembrance, rewards[], map/px/py/approx, named_by |
| `item_locations.json` | 3401 | lot, flag, map_id, items[{cat,id,name,name_en,icon,count,kind}], kind, dlc, region_pl, map/px/py/approx |
| `pois.json` | 295 | id, name, category, map_id, dlc, pos, flag (pokazanie), icon, names[[napis, flaga włączenia, flaga wyłączenia]], region_pl, map/px/py |
| `npcs.json` | 326 | name, name_en, map_id, entity, talk, region_pl, map/px/py |
| `invaders.json` | 25 | id (encja), flag (pokonanie), name, name_en, map_id, dlc, pos, lots[], quest_rewards, rewards[], region_pl, map/px/py |
| `enemies.json` | 19 887 | [mapa, px, py] każdego przeciwnika z łupem (numery wierszy w `item_sources.json` → `at`) |

## Braki

- Ikony ~110 mniejszych bossów (nagrody z katakumb/jaskiń wymagają pełnego parsera EMEVD).
- Przedmioty zdobywane inaczej niż z ziemi (kupcy, wrogowie, questy), do pokrycia przez ekwipunek z save'a (backend).
- Podziemia DLC (`M11`) to w plikach gry tylko szczątkowy fragment, więc go nie używamy.

## Najbliższa łaska (frontend, 2026-11-23)

Wcześniej liczona po pikselach mapy świata, co dla lochów rzutowanych na mapę (Farum Azula, Leyndell, Akademia, jaskinie)
dawało to łaski „blisko na rysunku” (np. Placidusax → Pierwszy kościół Mariki). Teraz:
- `bosses_all.json`, `item_locations.json`, `pois.json` i `npcs.json` mają `pos` = pozycja lokalna w pliku mapy (`map_id`), łaski też (`graces.json`, BonfireWarpParam).
- Poza otwartym światem (m60/m61) szukamy łaski w tym samym pliku mapy po odległości 3D.
- Łaski w samej arenie (< 25 m od bossa, np. Eldeński Tron przy Morgocie, Kokon Niebianina przy Mohgu, Sala debat przy
  Rudym wilku) pojawiają się dopiero po walce, więc dla bossów są pomijane, podobnie łaska nazwana jak boss.
- Areny w osobnej przestrzeni (Placidusax, Maliketh, Rennala, Bestia Eldeńska): stała tabela `ARENA_ACCESS` w `app.js`
  z łaską, od której się tam idzie.

## Skąd zdobyć przedmiot: `item_sources.json` (2026-11-23)

Generuje `tools/extract/extract_sources.py` (krok w `run_all.py`). Klucz `"<kategoria>:<id>"` (broń: ID bazowe).
- Kupcy: `ShopLineupParam`: `+0x00` ID, `+0x04` cena, `+0x08` EquipMtrlSetParam (wymiana; `+0x00` → ID goods, np.
  wizerunek), `+0x17` typ (0 broń, 1 zbroja, 2 talizman, 3 goods, 4 popiół wojny). Który kupiec ma który zakres wierszy,
  wynika ze skryptów rozmów `/script/talk/<mapa>.talkesdbnd.dcx` (pliki `t<TalkID>.esd`; literał int w wyrażeniu ESD = `0x82` + i32,
  para kolejnych literałów = początek i koniec zakresu). Rozmowy otwartego świata są we wspólnych archiwach
  `m60_00_00_00`, `m61_00_00_00`, `m00_00_00_00`, nie per kafel. TalkID → część MSB (`+0x10`) → NpcParam → imię i miejsce.
  Wiersze z ceną 0–1 bez materiału to usługi (np. duplikowanie u kowala), pomijane.
- Przeciwnicy: `NpcParam +0x30` → `ItemLotParam_enemy` (łup losowy), `+0x34` → `ItemLotParam_map` (jednorazowy).
  Szansa = waga (`+0x40` 8×u16) / suma wag w wierszu. Zwykli przeciwnicy nie mają nazw w grze (NpcName ma tylko 466
  postaci i bossów), więc grupujemy po modelu. Grupa ma wszystkie miejsca (`at`: numery wierszy `enemies.json`),
  a `count` liczy każdą część raz, nawet gdy przedmiot jest w dwóch wierszach puli.
- Najeźdźcy: nagrody z `invaders.json` (`invaders`: lista encji); ich pule nie są liczone jako zdarzenia.
- Zdarzenia (questy, podarunki): `AwardItemLot` (`2003[4]`/`2003[36]`) w skryptach map i `common`, także
  z parametrem przez `InitializeEvent`/`InitializeCommonEvent` (bajt źródłowy z tablicy parametrów). Pomijamy pule skarbów
  leżących na mapie.
- Bossowie: nagrody z `bosses_all.json`.

Pokrycie: ekwipunek (broń, zbroje, talizmany, popioły) ma miejsce na mapie albo źródło dla 1440 z 1557. Brakuje m.in. łupu
ze zwłok przy obiektach (skarby przypięte do assetów), części wymian u Enii i podarunków postaci.

## Poprawki kategorii i krain po audycie (2026-11-23)

- Wiekowięzienia w grze to „Wieczne więzienie …” (wcześniej reguła nie łapała żadnego i lądowały w „Więzienia (DLC)”);
  DLC: „Loch …” → kategoria `gaol` („Lochy”); główne lochy (Leyndell, Farum Azula, Akademia, Elphael…) → `legacy`;
  „Grobowiec bohatera”, „Pieczara”, „Kryjówka”, „Smocza jama” dopisane.
- Osełki (`Żelazne/Rozżarzone/Uświęcone/Błyskamienne ostrze`) → `whetblade`; runy DLC („Run Królestwa Cieni [n]”) → `golden_rune`.
- Kategoria punktu na mapie = najcenniejszy przedmiot w nim (`KIND_PRIORITY`), nie pierwszy.
- Kraina obiektów w lochach = kraina najbliższej łaski z tego samego pliku mapy (w m12_07 są Nokron i studnia Siofry; Stormveil → „Zamek Burzowego Całunu”, a nie Liurnia);
  `PlaceName_dlc02` dołączone (krainy DLC). Opisy miejsc bossów z tabeli CE (po angielsku) nie są już pokazywane.
- Przedmioty bez nazwy w grze (atrapy) pomijane; nazwy przycinane (spacje na końcu).
