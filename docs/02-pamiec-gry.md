# 02 — Struktury w pamięci gry

Źródło: tabela Cheat Engine `eldenring_all-in-one_Hexinton-v8.0.4.CT` (dla wersji gry 1.17.1 /
plik 2.7.1.0, zaktualizowana 2026-09-09). **Jeszcze nie zweryfikowane na żywym procesie** —
gra nie była uruchomiona podczas analizy (patrz [04-otwarte-pytania.md](04-otwarte-pytania.md)).

## Warunek: EAC musi być wyłączony

Tabela sama to sprawdza (`getProcessIDFromProcessName('EasyAntiCheat_EOS.exe')`). Przy działającym
EAC proces gry jest chroniony i `OpenProcess`/`ReadProcessMemory` nie zadziała.
Seamless Coop (`ersc_launcher.exe`) uruchamia grę bez EAC → odczyt pamięci działa.

## Weryfikacja wzorców na pliku eldenring.exe (2026-11-23, buildid 25827938)

Wzorce przeskanowane na pliku z dysku (sekcja `.text` nie jest zaszyfrowana na dysku):

| Manager | Trafień | RVA instrukcji | RVA wskaźnika (sekcja) |
|---|---|---|---|
| EventFlagMan (wzorzec SoulSplittera) | 1 | `0x1B7A76` | `0x3D6F4D8` (.data) |
| EventFlagMan (wzorzec CT) | 1 | `0xD470C9` | `0x3D6F4D8` (.data), **ten sam adres** |
| WorldChrMan | 1 | `0x3FFC86` | `0x3D6D018` (.data) |
| GameDataMan | 1 | `0x256560` | `0x3D64FB8` (.data) |
| GameMan | 1 | `0x67B050` | `0x3D709A8` (.data) |

Wzorce pasują do obecnej wersji gry. **Odczyt z działającego procesu (Seamless Coop) działa**
(2026-11-23 17:55): flagi czytane co 250 ms, ID flag sensowne (np. boss 2200 / 551 z tabeli CE).

⚠️ Gra ma wersję pliku **2.7.2.0**, a tabela CE jest dla 2.7.1.0. W `PlayerIns` pola przesunęły się
o `+0x10`: pozycja jest pod **`+0x6C0`** (CT: 0x6B0), MapID pod **`+0x6D0`** (CT: 0x6C0). Znalezione
skanem pamięci; `LocalPlayerOffset = 0x10EF8` się nie zmienił. Przy każdym patchu trzeba to
sprawdzić (np. szukając MapID obecnej mapy w okolicy `+0x600..0x700`).

## Jak znaleźć managery: sygnatury AOB

Każdy manager to globalny wskaźnik. Szukamy wzorca bajtów instrukcji, która go używa
(`mov rax, [rip+disp32]`), i liczymy adres:

```
adres_instrukcji = aob_scan(eldenring.exe, wzorzec)
adres_wskaźnika  = adres_instrukcji + offset + 4 + int32(adres_instrukcji + offset)
                 = adres_instrukcji + additional + int32(adres_instrukcji + offset)   # additional = offset + 4
```

| Manager | Wzorzec AOB | offset | additional |
|---|---|---|---|
| `WorldChrMan` | `48 8B 05 ?? ?? ?? ?? 48 85 C0 74 0F 48 39 88` | 3 | 7 |
| `GameDataMan` | `48 8B 05 ?? ?? ?? ?? 48 85 C0 74 05 48 8B 40 58 C3 C3` | 3 | 7 |
| `EventFlagMan` | `48 8B 3D ?? ?? ?? ?? 48 85 FF ?? ?? 32 C0 E9` | 3 | 7 |
| `EventFlagMan` (alternatywa z „Flags Logger” i SoulSplittera) | `44 89 7C 24 28 4C 8B 25 ?? ?? ?? ?? 4D 85 E4` | 8 | 12 |
| `GameMan` | `48 8B 05 ?? ?? ?? ?? 80 B8 ?? ?? ?? ?? 0D 0F 94 C0 C3` | 3 | 7 |
| `FieldArea` | `48 8B 0D ?? ?? ?? ?? 48 ?? ?? ?? 44 0F B6 61 ?? E8 ?? ?? ?? ?? 48 63 87 ?? ?? ?? ?? 48 ?? ?? ?? 48 85 C0` | 3 | 7 |
| `MapItemMan` | `48 8B 0D ?? ?? ?? ?? C7 44 24 50 FF FF FF FF C7 45 A0 FF FF FF FF 48 85 C9 75 2E` | 3 | 7 |
| `WorldMapMan` | `48 8B 0D ?? ?? ?? ?? E8 ?? ?? ?? ?? 0F B6 5D 90 84 C0 41 0F 44 DD` | 3 | 7 |
| `CSRegulationManagerImp` | `48 8B 0D ?? ?? ?? ?? 48 85 C9 74 0B 4C 8B C0 48 8B D7` | 3 | 7 |
| `CsDlc` | (długi wzorzec w CT) | 3 | 8 |

Pełna lista (35 managerów) jest w skrypcie `[ Enable ]` tabeli CT.

## Flagi zdarzeń (najważniejsze dla mapy)

```
flag_bytes = read_qword(read_qword(EventFlagMan) + 0x28)   # początek bloku bitów
rozmiar    = 0x1BF9A8 bajtów (wg „Flags Logger”; w save 0x1BF99F)
flaga      = (byte[flag_bytes + byte_offset] >> bit) & 1
```

- Tabela CE adresuje flagi **surowymi offsetami** `[[EventFlagMan]+28]+OFFSET`, bit `BitStart`.
  Wyeksportowane do [data/ct_event_flags.csv](data/ct_event_flags.csv) (600 flag).
- Ten sam układ bajtów jest w pliku save → [03-format-save.md](03-format-save.md). Zweryfikowane.
- „Flags Logger” w CT robi dokładnie to, czego potrzebujemy do wykrywania zmian: co 256 ms
  kopiuje cały blok i porównuje bit po bicie z poprzednim. To samo zrobi nasz program pomocniczy
  (1.8 MB co 250 ms to bez problemu).

### Mapowanie ID flagi → offset (do zrobienia)

Gra identyfikuje flagi numerami (np. ID z EMEVD / `ItemLotParam.getItemFlagId`), a blok jest
podzielony na **kawałki po 1000 flag = 125 bajtów**. Który kawałek leży pod którym indeksem
trzyma drzewo (`std::map`) w `EventFlagMan` (wg wiedzy społeczności: dzielnik pod `+0x1C`,
rozmiar kawałka pod `+0x20`, korzeń drzewa pod `+0x38`). Wtedy:

```
blok   = flag_id / 1000
reszta = flag_id % 1000
indeks = drzewo[blok]
offset = indeks * 125 + reszta / 8
bit    = 7 - (reszta % 8)
```

✅ **Potwierdzone w kodzie SoulSplittera** (`src/SoulMemory/EldenRing/EldenRing.cs`, funkcja
`ReadEventFlag`, port funkcji gry z Ghidry). Obiekt `CSFD4VirtualMemoryFlag` (= EventFlagMan):

| Pole | Co |
|---|---|
| `+0x1C` i32 | dzielnik (1000). 0 = jeszcze niezainicjalizowane, spróbuj później |
| `+0x20` i32 | rozmiar bloku w bajtach (125) |
| `+0x28` i64 | wskaźnik na początek bloku bitów |
| `+0x38` | głowa drzewa `std::map`; korzeń = `[głowa+0x08]` |
| węzeł `+0x00 / +0x10` | lewe / prawe dziecko |
| węzeł `+0x19` u8 | `_Isnil` (koniec drzewa) |
| węzeł `+0x20` i32 | klucz = numer bloku (`id / 1000`) |
| węzeł `+0x28` i32 | tryb: `1` → adres = `[+0x20] * [węzeł+0x30] + [+0x28]` (typowy przypadek) |
| węzeł `+0x30` | indeks bloku (i32) lub w innym trybie bezpośredni wskaźnik |

Bity: `maska = 1 << (7 - (reszta & 7))`, czyli najniższy numer flagi to najstarszy bit bajtu.
SoulSplitter szuka managera wzorcem `44 89 7C 24 28 4C 8B 25 ?? ?? ?? ?? 4D 85 E4` (ten sam,
co „Flags Logger” w CT).

**Dla save'a** to samo mapowanie (blok → indeks) jest gotowe jako plik `eventflag_bst.txt`
(linie `blok,pozycja`) w [ClayAmore/ER-Save-Lib](https://github.com/ClayAmore/ER-Save-Lib),
używany też przez RingWatch. Formuła: `byte = bst[id // 1000] * 125 + (id % 1000) // 8`,
`bit = 7 - (id % 1000) % 8`. Blok, którego nie ma w tabeli, nie ma miejsca w pamięci.
Alternatywnie możemy zrzucić drzewo sami z działającej gry.

## Pozycja gracza

`LocalPlayerOffset = 0x10EF8`

| Wartość | Łańcuch wskaźników | Typ |
|---|---|---|
| Globalne X / Y / Z | `[[WorldChrMan]+0x10EF8]` → `[+0]` → `+0x6B0 / +0x6B4 / +0x6B8` | float |
| Obrót (rad) | … `+0x6BC` | float |
| MapID | … `+0x6C0` | u32 |
| Lokalne X / Z / Y (w obrębie kafla mapy) | `[[[[[WorldChrMan]+0x10EF8]+0]+0x190]+0x68]+0x70 / 0x74 / 0x78` | float |
| Ostatnia „bezpieczna” pozycja | … `+0x6C4..0x6D4` | float ×4 + u32 |
| Plama krwi (runy po śmierci) | `[GameDataMan]+0x48` → `+0x0/4/8` XYZ, `+0x34` runy, `+0x38` mapa | |

Uwaga z CT: osie lokalne są w kolejności X, Z, Y (Y = wysokość).
„Globalne” współrzędne są tym, czego chcemy do mapy (świat otwarty = mapa `m60`/`m61`).

## Dane postaci

`[[GameDataMan]+0x08]` = PlayerGameData (ta sama struktura co w save, imię na `+0x94`).
