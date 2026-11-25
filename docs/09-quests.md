# 09 — Questy NPC z flagami zdarzeń (stan 2026-11-23)

Wynik: [`assets/data/quests.json`](../assets/data/quests.json) — **46 questów** (33 gra podstawowa, 13 DLC),
**139 kroków**, 368 różnych flag. Generator: [`tools/extract/build_quests.py`](../tools/extract/build_quests.py).

```powershell
python tools/extract/build_quests.py            # generuje quests.json (gra + cache TGA)
python tools/extract/build_quests.py --verify   # + sprawdza każdą flagę na 7 postaciach przez backend i ustawia confidence
```

Backend czyta dane z `backend/data/quests.json` — plik w `assets/data/` trzeba tam skopiować
(albo dopisać krok do `backend/tools/build_data.py`). Tego nie zrobiłem, bo `backend/` miał zostać bez zmian.

## Źródła i licencje

| Klucz (`sources`) | Co | Licencja / uwagi |
|---|---|---|
| `regulation` | `regulation.bin` z gry użytkownika: `ItemLotParam_map/_enemy`, pole `getItemFlagId` (flaga „przedmiot otrzymany”). Przedmioty dawane przez NPC mają loty 100000–119999 i flagi 400000–400999 | dane gry z lokalnej instalacji, czytane lokalnie, nic nie jest kopiowane do repo |
| `tga-ct` | [The-Grand-Archives/Elden-Ring-CT-TGA](https://github.com/The-Grand-Archives/Elden-Ring-CT-TGA) (plik `VERSION` = 1.140, `master` z 2026-10-22): *Event Flag Manager* (flagi pokonania 208 bossów) i *Event Flags/Deprecated/NPCs* (opisane flagi stanu ~25 NPC) | **brak pliku licencji** w repozytorium (domyślnie wszelkie prawa zastrzeżone). Bierzemy tylko numery flag (fakty techniczne), lokalnie, z podaniem źródła. Kopia: `assets/cache/community/tga/` (poza gitem) |
| `talk-esd` | skrypty rozmów (`/script/talk/*.talkesdbnd.dcx`) i `NpcName` z gry | dane gry; użyte tylko do przypisania bloku flag stanu do konkretnego NPC |
| `npc-block` | reguła „NPC opuścił stan początkowy” (patrz niżej) | wyprowadzone przeze mnie z TGA + porównania save'ów |
| `save-verified` | sprawdzenie na save'ach użytkownika (plik `co2`, 7 postaci) | — |
| `general-knowledge` | treść kroków, `where`, `next` — pisane własnymi słowami po polsku | do potwierdzenia w grze |

Pobrane, ale **nieużyte** w wyniku (licencje restrykcyjne lub dane niepewne):

| Repo | Licencja | Dlaczego nie |
|---|---|---|
| [thefifthmatt/SoulsRandomizers](https://github.com/thefifthmatt/SoulsRandomizers) (`diste/Base/itemevents.txt` …) | *SoulsRandomizers License 1.0* — wszelkie prawa zastrzeżone, zakaz rozpowszechniania utworów pochodnych | posłużyło tylko jako wskazówka, że ID eventu = koniec bloku NPC (np. 3619 „Blaidd quest”); żadne dane z niego nie trafiły do JSON |
| [Hapfel1/er-save-manager](https://github.com/Hapfel1/er-save-manager) (`event_flags.json`) | od 22.07.2026 *Source-Available*, zakaz użycia w innym projekcie bez zgody (wcześniej MIT) | nie ma flag questów NPC |
| [laszloprekop/ER-save-Reader](https://github.com/laszloprekop/ER-save-Reader) (`quest_chains.rs`, rosetta) | MIT / Apache-2.0 | flagi questów NPC oznaczone przez autora jako niezweryfikowane i niezgodne z naszymi save'ami |
| [imCioco/ER_QuestPath-Lang](https://github.com/imCioco/ER_QuestPath-Lang) | MIT | tylko tłumaczenia tekstów, bez flag |

Licencje zapisane w `assets/cache/community/<źródło>/LICENSE*`. Teksty z Fextralife/MapGenie/wiki nie były używane.

## Jak liczone są kroki

Krok ma `flags` i `mode`: `any` — wystarczy dowolna flaga (alternatywne zakończenia, np. Sellen: kris **albo**
dzwonek Sellen), `all` — wszystkie (Gurranq: komplet nagród). Każda flaga w JSON pochodzi z jednego ze źródeł:

1. **Przedmiot od NPC / z questa** (`regulation`) — najpewniejsze: flaga ustawia się, gdy gracz dostaje przedmiot
   (np. 400391 = Karyjski odwrócony posąg od Ranni, 9502 = Run naprawy Księcia Śmierci). Flagi te są trwałe.
2. **Boss pokonany** (`tga-ct`) — flaga `isDefeated` z TGA (np. 12040800 Astel, 21010800 Messmer).
3. **Blok stanu NPC** (`npc-block`). Każdy NPC ma 20 kolejnych flag: `+0` przyjazny, `+1` wrogi, `+3` martwy,
   `+5…+18` etap/położenie (dokładnie jedna naraz), `+19` techniczna. Blok przypisany po rozmowie NPC:
   `t<ID>.esd` ↔ `NpcName` `1<ID>00` (np. t106 = Ranni → 3740, t418 = Leda → 4440). Znaczenie pojedynczych
   etapów jest w większości nieopisane, więc używam tylko reguły „NPC opuścił stan początkowy” (dowolna z `+6…+17`
   albo `+3`), i to wyłącznie dla kroków „spotkaj NPC”. `+18` pomijam — u dwóch postaci jest ustawiona także w
   blokach bez NPC. Dla Yury `+6` jest stanem startowym (widać na nowej postaci), więc jest wyłączona.
4. **Kroki kumulatywne** (`"cumulative": true`) — krok „spotkaj NPC” zalicza się też, gdy zaliczony jest
   dowolny późniejszy krok (skoro jest zakończenie, było i spotkanie). Ich `flags` zawierają flagi kolejnych kroków.

Każdy krok ma `sources`; kroki z flagą opisaną w TGA mają dodatkowo `tga_labels`.
`locks[]`: `{boss_en, boss_id, boss_flag, step, warning}` — `boss_id` dopasowane do `backend/data/bosses.json`
po fladze pokonania (`boss-<flaga>`), `boss_flag` zostaje na wypadek zmiany identyfikatorów.

### Weryfikacja i `confidence`

`--verify` czyta wszystkie 368 flag na 7 postaciach z `ER0000.co2` (backend `/api/flags`) i dla każdej postaci
liczy wektor kroków. **Naruszenie** = zaliczony krok, przed którym jest niezaliczony.

| Poziom | Warunek |
|---|---|
| `verified` | 0 naruszeń na 7 postaciach, nowa postać (najniższy poziom) ma 0 kroków, ktoś ma ≥ 2 kroki, wszystkie flagi z `regulation`/`tga-ct` (bez reguły bloku NPC) |
| `high` | 0 naruszeń, nowa postać 0 kroków, zaobserwowany ≥ 1 krok (np. quest korzysta z reguły bloku NPC) |
| `medium` | ≤ 1 naruszenie |
| `low` | więcej naruszeń albo flagi nieczytelne z save'a |

Wynik: **30 `verified`, 16 `high`**, 0 `medium`/`low`. Na nowej postaci „chuj” (poz. 8) z 368 flag nie jest
ustawiona żadna; „finali” ma 148, „boink” 125. Dla „finali” i „boink” pliki `sl2` i `co2` dają identyczne wartości wszystkich 368 flag.
Wyniki dla każdej postaci są w JSON w `entries[].verification.chars`.

`verified` znaczy: flagi są prawdziwe i zachowują się spójnie na save'ach. **Nie** znaczy, że tekst kroku jest
sprawdzony w grze — opisy i podpowiedzi `next` pochodzą z wiedzy ogólnej.

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

Pozostałe postacie (grandes, prophet, Mokki, Ser Davick) też nie mają naruszeń — patrz `verification` w JSON.

Ikona questa = `icon` charakterystycznego przedmiotu z `items.json` (np. Ranni → Pierścień ciemnego księżyca 3050,
Alexander → Odłamek Alexandra 18871). Nazwy NPC, miejsc i przedmiotów w tekstach są z plików gry (`polpl`); żeby
uniknąć błędnej odmiany, miejsca występują jako „w lokacji X”, a przedmioty jako „przedmiot X”.

## Czego brakuje / problemy

1. **Kroki pośrednie bez flagi.** Wiele etapów to tylko rozmowa albo przejście NPC w inne miejsce (np. Ranni:
   przyjęcie służby w Wieży Ranni, Seluvis, Iji; Boc w Liurnii; Blaidd w więzieniu). Flagi etapów `+5…+18` istnieją,
   ale ich znaczenie (które miejsce) jest opisane tylko dla części NPC w TGA. Skan EMEVD map pokazał, że etapy są
   ustawiane głównie w `common.emevd`, więc samo „która mapa używa flagi” nie wystarcza. Następny krok: rozkodować
   eventy `30xx–45xx` z `common.emevd` (warunki → który etap) albo opisać etapy, porównując save przed i po rozmowie.
2. **Brak questów:** Rennala, Shabriri (wspomniany przy Yurze), Enia / Dwa Palce, Hewg, Ensha, Albus i medaliony
   Świętego Drzewa, Pidia, Miriel, Gostoc, Jerren (osobno), kupcy. Z DLC: Jolán pokryta tylko 2 krokami, St. Trina jest
   częścią questa Thiolliera, brak Logura, Lionela, Moonrithylla i questów „Ród poszukiwaczy” (dostawy Moore'a
   400750–400755 usunięte z kroków, bo zabicie Moore'a zamyka quest bez dostaw — wspomniane w notatkach).
3. **Kolejność i opisy z wiedzy ogólnej** — weryfikacja na save'ach sprawdza tylko kolejność i to, że nowa postać
   ma zero; nie potwierdza, że tekst kroku dokładnie opisuje zdarzenie (np. kiedy Fia daje Podniszczony sztylet,
   co dokładnie odpala 400394 Miniatura Ranni). Pewność `verified` dotyczy flag, nie tekstu.
4. **Ścieżki alternatywne.** Kroki „zakończenie” mają `mode:"any"` po wszystkich znanych wariantach (np. Millicenta:
   pomoc/zdrada). Jeśli gracz zabije NPC wcześnie, późniejsze kroki zostaną niezaliczone na zawsze — aplikacja
   pokaże to jako quest niedokończony. Flaga śmierci (`npc_block + 3`) jest dostępna, gdyby UI miało pokazać
   „quest przerwany”.
5. **Blokady (`locks`)** — 8 wpisów (Bestia Eldeńska dla trzech runów naprawy i Ranni, Rykard, Malenia, Messmer,
   Bayle). Treść ostrzeżeń jest z wiedzy ogólnej; „Messmer → Rogaty przybysz” jest sformułowane ostrożnie („może”).
6. **TGA bez licencji** — używamy tylko numerów flag. Gdyby dane miały trafić do publicznego repo, warto zapytać
   autorów TGA albo zostawić w JSON tylko flagi z `regulation.bin` (to dane z gry użytkownika, generowane lokalnie).
7. **Backend** czyta `backend/data/quests.json` (nadal pusty) — trzeba skopiować wynik albo zmienić
   `backend/tools/build_data.py`.

## Tryb bez spoilerów — teksty kroków (2026-11-23)

Część kroków zdradzała losy postaci („Iji ginie”, „Podejdź do ciała Rogiera”, nagrody typu „Dzwonek kulisty X”
po śmierci NPC, zwroty akcji jak Yura/Shabriri). `tools/extract/quest_spoilers.py` dodaje do takich kroków
`text_safe` / `next_safe` (podpowiedź bez rozstrzygnięcia) i do ostrzeżeń `warning_safe`; `build_quests.py` stosuje to
przy generowaniu, a `python tools/extract/quest_spoilers.py` — na gotowym `quests.json`. Frontend w trybie
„bez spoilerów” pokazuje wersję bezpieczną dla kroków jeszcze niezaliczonych i w „Co dalej”; po zaliczeniu kroku — pełny
tekst. Obecnie 28 kroków + 1 ostrzeżenie (Igon).
