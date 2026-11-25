# 04 — Otwarte pytania i następne kroki

## Rozwiązane (2026-11-23, research w internecie, patrz [05](05-istniejace-projekty.md))

- ~~Mapowanie ID flagi → offset~~ → **rozwiązane i zweryfikowane.** Pobrana
  `data/er-save-lib/eventflag_bst.txt` (commit `664ff9e8`, 11 920 bloków). Wszystkie 6 próbek
  z ER-Save-Editor się zgadzają, a 600 offsetów z CT daje sensowne ID (łaski DLC 768xx,
  osełki 656xx, areny 60350/60360/60370). Odczyt po ID i po offsecie dają 0 rozbieżności.
  ⚠️ Repo ER-Save-Lib **nie ma licencji**: używamy lokalnie, ale do publicznej wersji lepiej
  wygenerować tabelę samemu (zrzut drzewa z pamięci gry).
- ~~Pozycja gracza w save'ie~~ → PlayerCoordinates za 5 listami po flagach. Zweryfikowane.
- ~~Pola profilu i preambuła przed flagami~~ → zweryfikowane (śmierci, ostatnia łaska, czas gry).
- ~~Jak wykrywać zmiany save'a~~ → obserwować **folder**, nie plik (gra robi atomową podmianę
  pliku i rusza `.bak`). Debounce kilkaset ms (RingWatch: 400 ms).

## Wynik pomiaru zapisu (2026-11-23, 17:58–18:04, Seamless Coop, nowa postać)

- **Gra zapisuje save cyklicznie co ~60 s** (odstępy 60,0 / 62,3 / 74,7 / 60,8 s) plus dodatkowe
  zapisy przy zdarzeniach (wczytanie mapy, przejście samouczek → Limgrave): seria 1–4 s po zdarzeniu.
- **Opóźnienie pamięć → plik** dla 179 flag: min 1,3 s, **mediana 27,8 s**, max 71,3 s.
- Pamięć: zmiany flag i pozycja widoczne natychmiast (próbkowanie co 250 ms).
- Wniosek: tryb „tylko save” (oficjalne online z EAC) daje mapę **opóźnioną do ~1 minuty**.
  Tryb pamięci (Seamless/offline) jest naprawdę na żywo. Hybryda ma sens.
- Uwaga do etykiet: flaga 2200 włącza się przy wczytaniu gry i wyłącza przy przejściach; w CSV
  jest w grupie bossa Midry, ale to raczej flaga ogólna. Etykiety z CT przypisane do grup bossów
  nie zawsze znaczą „boss pokonany”.
- Rozmowa z NPC przy pierwszej łasce (18:04:11): `+3082`, `+1042369202`, `+1042369206`.

## Do ustalenia

1. ~~Jak często gra zapisuje save?~~ → zmierzone, patrz wyżej. Narzędzie:
   `scripts/live_watch.py` → `logs/live_watch.log`. Bez EAC czyta jednocześnie pamięć gry
   (co 250 ms) i plik, i dla każdej flagi loguje opóźnienie „pamięć → plik”. Przy działającym EAC
   nie otwiera procesu gry (sam sterownik EAC odbiera prawa do odczytu pamięci, a próby
   otwarcia procesu mogą być logowane), czyta tylko plik.
   Pierwsza obserwacja (oficjalna gra, 17:52): dwa zapisy w odstępie 8,8 s, drugi z 4 zmienionymi
   flagami (9800→9807 i para flag 2048429214/2048429215, to wygląda na zmianę stanu).
2. **Weryfikacja wskaźników z CT/SoulSplittera na żywym procesie** (Seamless Coop).
3. **Współrzędne globalne → piksele mapy.** Wzór `kafel*256+128+lokalna` z dokumentacji
   do sprawdzenia, potem kalibracja na obrazie mapy (2–3 punkty odniesienia, np. łaski).
4. **Lista przedmiotów z pozycjami.** Opcje: generować z `regulation.bin` + MSB map (jak RingWatch),
   albo użyć otwartego zbioru (Mjolniar, MIT; tabele z ER_DynamicOverlay, AGPL). Sprawdzić licencje.
5. Questy: skąd brać flagi etapów questów NPC i opisy „co dalej” (TGA CT, SaveForge).

## Proponowana kolejność

1. Watcher zapisu save'a (pytanie 1). Szybki pomiar.
2. Pobranie `eventflag_bst.txt` i weryfikacja kilku flag (łaski, bossowie).
3. Program pomocniczy: odczyt save'a → JSON → WebSocket do strony.
4. Tryb pamięci (Seamless Coop): AOB + `ReadEventFlag` + pozycja co ~250 ms.
5. Strona: Leaflet + kafle mapy + warstwy (łaski, bossowie, przedmioty, regiony).
