# elden-map — dokumentacja badań

Cel projektu: strona z interaktywną mapą Elden Ring, która **na żywo** pokazuje postęp
(zebrane przedmioty, pokonani bossowie, odkryte łaski, etapy questów, co dalej).

## Ustalenia architektoniczne (stan na 2026-11-23)

| Źródło danych | Opóźnienie | Działa z EAC (oficjalne online) | Działa w Seamless Coop / offline |
|---|---|---|---|
| **Pamięć procesu** (ReadProcessMemory, tylko odczyt) | < 1 s | ❌ EAC blokuje dostęp | ✅ |
| **Plik save** (`ER0000.sl2` / `.co2`) | zależy od autozapisu gry (do zmierzenia) | ✅ | ✅ |
| Mod w grze (DLL / zmiany `regulation.bin`) | — | ❌ (ryzyko bana) | ✅, ale dużo pracy |

Decyzja: **hybryda** — program pomocniczy czyta pamięć gry gdy EAC jest wyłączony
(Seamless Coop), a w pozostałych przypadkach plik save. Oba źródła mają **ten sam
układ bloku flag zdarzeń** (patrz niżej), więc logika mapy jest wspólna.

## Spis dokumentów

- [01-pliki-gry.md](01-pliki-gry.md) — gdzie jest gra, co jest w folderze, analiza DLL/EXE
- [02-pamiec-gry.md](02-pamiec-gry.md) — struktury w pamięci (z tabeli Cheat Engine): sygnatury AOB, flagi, pozycja gracza
- [03-format-save.md](03-format-save.md) — format pliku save, zweryfikowany na Twoich zapisach
- [04-otwarte-pytania.md](04-otwarte-pytania.md) — co jeszcze trzeba ustalić / następne kroki
- [05-istniejace-projekty.md](05-istniejace-projekty.md) — podobne narzędzia (RingWatch, Tarnished Chronicle,
  ER_DynamicOverlay, SoulSplitter, er-save-manager) i źródła danych

- [06-design.md](06-design.md) — badanie stylu Elden Ring, paleta, typografia, widoki, pomysły (Kronika,
  miejsca śmierci, tryb bez spoilerów, ostrzeżenia, podsumowanie sesji)
- [07-backend-api.md](07-backend-api.md) — API backendu (przygotowuje sesja backendu)
- [08-assets.md](08-assets.md) — prawdziwa mapa, ikony i dane wyciągnięte z plików gry, przeliczenie współrzędnych
- [09-quests.md](09-quests.md) — questy NPC: źródła, flagi kroków, weryfikacja
- [10-world-data.md](10-world-data.md) — wszyscy bossowie, miejsca/lochy, przedmioty na mapie, NPC (z plików gry)

**Decyzja 2026-11-23:** gramy online z EAC → jedynym źródłem danych jest plik save.

Makieta: `mockup/`. Najpierw wygeneruj zasoby z gry (`python tools/extract/run_all.py`, patrz
[08-assets.md](08-assets.md)), potem w katalogu projektu uruchom `python -m http.server 5180` i otwórz
http://localhost:5180/mockup/ (serwer musi widzieć też `assets/`).
Dane na żywo: w drugim terminalu `python backend\server.py` (port 8765). Makieta sama wykrywa backend
i pokazuje prawdziwy stan postaci (pasek „na żywo · plik · slot” w lewym dolnym rogu); bez backendu
działa w trybie demo z danymi przykładowymi. Na żywo są: postać, bossowie DLC, łaski na mapie (422,
flagi czytane przez `/api/flags`), pozycja, miejsca śmierci, kronika, sesja, popioły wojny.
Stan na 2026-11-23 (wieczór): na żywo są też wszyscy bossowie (212), 46 questów (zagnieżdżone, zwijane),
ekwipunek (posiadane przedmioty) i widok „Postać” z założonym ekwipunkiem. Na mapie: miejsca/lochy,
przedmioty w ~25 kategoriach z filtrami; klik w przedmiot podświetla go i pokazuje statystyki, opis z gry
i notkę „Do czego służy”.

## Dane i skrypty

- [data/ct_event_flags.csv](data/ct_event_flags.csv) — 600 flag (**ID flagi**, byte offset, bit) z tabeli
  Cheat Engine Hexinton v8.0.4 (bossowie, łaski DLC, Ashes of War, osełki…)
- [data/er-save-lib/eventflag_bst.txt](data/er-save-lib/eventflag_bst.txt) — mapa blok → pozycja
  (ClayAmore/ER-Save-Lib @ `664ff9e8`, repo bez licencji, tylko do użytku lokalnego)
- [scripts/save_watch.py](scripts/save_watch.py) — watcher: loguje każdy zapis save'a i zmienione flagi
- [scripts/live_watch.py](scripts/live_watch.py) — pamięć gry + plik naraz, mierzy opóźnienie zapisu
  (pamięć tylko bez EAC; przy EAC nie dotyka procesu gry)
- [scripts/er_save_probe.py](scripts/er_save_probe.py) — parser save'a (read-only):
  ```
  python docs/scripts/er_save_probe.py <kopia ER0000.sl2> docs/data/ct_event_flags.csv
  ```

## Najważniejsze odkrycie w jednym zdaniu

Wszystkie flagi zdarzeń gry (przedmiot podniesiony, boss zabity, łaska odkryta, etap questa)
to **jeden ciągły blok bitów o rozmiarze `0x1BF99F` bajtów** — w pamięci pod
`[[EventFlagMan]+0x28]`, a w save'ie pod `koniec_listy_regionów + 0x1CA5E` w każdym slocie.
Offsety z tabeli CE działają 1:1 na danych z save'a (zweryfikowane na 6 postaciach).
