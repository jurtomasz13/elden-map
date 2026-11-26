# Istniejące projekty i źródła (research z 2026-11-23)

Podobne narzędzia już istnieją, ale żadne z nich nie jest interaktywną mapą z postępem na żywo. Można się od nich
uczyć i korzystać z ich danych, sprawdzając licencje.

## Narzędzia czytające save

| Projekt | Język / licencja | Co robi | Co z niego bierzemy |
|---|---|---|---|
| [Cidan/RingWatch](https://github.com/Cidan/RingWatch) | Go, licencja nieznana | TUI w terminalu: pozostali bossowie i przedmioty, powiadomienie, gdy padnie boss. Obsługuje `.sl2` i `.co2` | Sposób wykrywania zmian: `fsnotify` na folderze save'a (a nie na pliku), bo gra robi atomowy zapis/podmianę i ruszają się pliki `.bak`; debounce 400 ms. Mapowanie flag przez `eventflag_bst.txt`. Przedmioty generuje z `regulation.bin` |
| [RysanekDavid/The-Tarnished-Chronicle](https://github.com/RysanekDavid/The-Tarnished-Chronicle) | prawdopodobnie Python + Qt, MIT | Tracker bossów z save'a, śmierci, czas gry, eksport do OBS | Zbiór danych boss → flaga (RingWatch go używa) |
| [Hapfel1/er-save-manager](https://github.com/Hapfel1/er-save-manager) + [dokumentacja formatu](https://elden-ring-save-manager.readthedocs.io/en/main/technical/save-file-structure/) | Python | Menedżer i edytor save'ów | Najlepszy opis formatu save'a. Pełna kolejność pól slotu (wpisana do [03](03-format-save.md)) |
| [ClayAmore/ER-Save-Editor](https://github.com/ClayAmore/ER-Save-Editor), [ER-Save-Lib](https://github.com/ClayAmore/ER-Save-Lib) | Rust | Edytor save'ów | `eventflag_bst.txt` (mapa blok → pozycja) w ER-Save-Lib; `src/db/event_flags.rs` = mapa `flag_id → (byte, bit)` |
| [oisis/EldenRing-SaveForge](https://pkg.go.dev/github.com/oisis/EldenRing-SaveForge) | Go | Edytor `.sl2` | Flagi zakończenia questów (według RingWatch) |

## Narzędzia czytające pamięć (tylko bez EAC)

| Projekt | Język / licencja | Jak działa |
|---|---|---|
| [Sully-/ER_DynamicOverlay](https://github.com/Sully-/ER_DynamicOverlay) | Rust, AGPL-3.0 | DLL wstrzykiwany do gry offline, overlay. Czyta `GameDataMan`, `CSEventFlagMan`, `WorldChrMan` przez sygnatury bajtów. Odświeża co ok. 250 ms. Tabele `bosses.toml` (207 bossów z flagami) i `checks.toml` |
| [FrankvdStam/SoulSplitter](https://github.com/FrankvdStam/SoulSplitter) | C#, GPLv3 | Autosplitter LiveSplit. `src/SoulMemory/EldenRing/EldenRing.cs` → `ReadEventFlag` to port funkcji gry z Ghidry (patrz [02](02-pamiec-gry.md)) |
| Route Tracker ([Nexus 9294](https://www.nexusmods.com/eldenring/mods/9294)) | ? | Zapisuje pozycję gracza i wysyła do podglądu w przeglądarce. Wymaga obejścia EAC. Strona Nexusa zablokowała automatyczny odczyt, więc szczegółów nie znamy |
| Checklist Overlay ([Nexus 9953](https://www.nexusmods.com/eldenring/mods/9953)) | ? | Overlay w grze odświeżany przy zapisie save'a. Strony nie udało się odczytać |

## Źródła danych (flagi, przedmioty, lokalizacje)

- [The-Grand-Archives/Elden-Ring-CT-TGA](https://github.com/The-Grand-Archives/Elden-Ring-CT-TGA): tabela CE
  z opisanymi flagami (źródło dla er-save-manager)
- Paramdex: definicje pól parametrów `regulation.bin`
- Zbiór lokalizacji „Mjolniar” (MIT, według RingWatch), do odszukania
- SoulsRandomizers: flagi checków przedmiotów

## Na co internet nie odpowiedział

- Jak szybko gra zapisuje save po zabiciu bossa albo podniesieniu przedmiotu. Żadne źródło nie podaje liczb.
  RingWatch reklamuje powiadomienie „w momencie, gdy padnie boss”, co sugeruje szybki zapis, ale trzeba to zmierzyć
  samemu.
- Przeliczenie współrzędnych na piksele obrazka mapy. Wiemy tylko, jak liczyć współrzędne globalne (patrz
  [03](03-format-save.md)).
