# 06 — Kierunek wizualny i widoki (makieta)

## Cel

Aplikacja-towarzysz do Elden Ring z kilkoma widokami (bossowie, questy, przedmioty, mapa),
która **wygląda jak część świata gry**, a nie jak generyczny dashboard. Odświeża się sama
po każdym zapisie save'a (tryb online z EAC → opóźnienie do ~1 min, patrz [04](04-otwarte-pytania.md)).

## Badanie: co definiuje styl Elden Ring

Źródła: [UX/UI of Elden Ring (UX Collective)](https://uxdesign.cc/the-ux-and-ui-of-elden-ring-42036ad0e24c),
[Analysing the UX Design of Elden Ring (Superjump)](https://superjumpmagazine.com/analysing-the-ux-design-of-elden-ring),
[Kotaku o UI Elden Ring](https://kotaku.com/elden-ring-ui-ux-user-experience-interface-fromsoftware-1848637410),
[Stamen: kartografowie o mapie Elden Ring](https://stamen.com/cartographers-play-video-games-a-review-of-the-map-in-elden-ring/),
[Inverse o mapie](https://www.inverse.com/gaming/elden-ring-killed-the-map-game-good-riddance),
[Made Good Designs: fonty FromSoftware](https://madegooddesigns.com/fromsoftware-font/),
[Carter & Cone: Mantinia](https://carterandcone.com/font/mantinia/).

Obserwacje:
1. **Minimalizm i cisza.** Mało elementów na ekranie, dużo pustej, ciemnej przestrzeni.
   Informacja podawana obrazem, nie liczbami. Brak ikon zadań, brak krzykliwych kolorów.
2. **Ciemne, ciepłe tło + złoto stosowane oszczędnie.** Prawie czarne panele z lekką przezroczystością,
   tekst w kolorze kości/pergaminu, złoto tylko na akcentach (zaznaczenie, nagłówki, cienkie linie).
3. **Szeryfowa, klasyczna typografia.** Logo bazuje na Mantinii (inskrypcyjne kapitaliki, komercyjna),
   tekst UI zbliżony do Agmeny (komercyjna). Darmowe odpowiedniki: **Cinzel** (kapitaliki inskrypcyjne)
   i **Cormorant Garamond** (wysoki kontrast, elegancki) / EB Garamond (czytelność drobnego tekstu).
4. **Ornament z cienkich linii.** Poziome kreski zanikające na końcach, drobne romby jako węzły,
   narożniki-klamry zamiast pełnych ramek. Nic ciężkiego, nic z gradientem „glossy”.
5. **Światło łaski.** Złota, miękka poświata jako sygnał „tu jest coś ważnego / aktywne”.
6. **Mapa jak pergamin.** Ręcznie rysowana, kolor sepii, atrament, nieodkryte obszary jako pusty
   pergamin. Bardzo oszczędna ikonografia (łaski, budowle).

## Decyzje projektowe

### Paleta (tokeny CSS)

| Token | Kolor | Użycie |
|---|---|---|
| `--void` | `#0a0907` | tło aplikacji (ciepła czerń) |
| `--ash` | `#14120e` | panele |
| `--ash-2` | `#1c1913` | panele podniesione, hover |
| `--line` | `rgba(201,170,113,.22)` | cienkie linie ornamentu |
| `--gold` | `#c9aa71` | akcenty, nagłówki |
| `--gold-hi` | `#ecdcae` | zaznaczenie, liczby |
| `--bone` | `#d8cfbb` | tekst główny |
| `--muted` | `#8a8170` | tekst drugorzędny |
| `--grace` | `#f4d37c` | poświata „aktywne / na żywo” |
| `--blood` | `#9b3428` | pozostałe / niebezpieczne (oszczędnie) |
| `--parchment` | `#cbb88f` | mapa |
| `--ink` | `#3a2d1e` | atrament na mapie |

Tryb jasny nie jest planowany (gra jest ciemna, aplikacja działa obok gry, często na drugim ekranie).

### Typografia
- **Cinzel**: tytuły widoków, nazwy bossów, nawigacja. Wersaliki, duży odstęp liter (0.12–0.25em).
- **Cormorant Garamond**: opisy, wskazówki, tekst „lore”, liczby w dużym rozmiarze.
- Bez fontów bezszeryfowych w interfejsie (to najszybciej daje efekt „generycznego UI”).

### Ornament i faktura
- Linie: `linear-gradient(90deg, transparent, gold, transparent)` o grubości 1 px.
- Romby 5–7 px jako węzły linii, punkty osi czasu questa, znaczniki postępu.
- Narożniki-klamry na kartach zamiast pełnych obramowań.
- Winieta i delikatne ziarno (SVG `feTurbulence`) na tle, żeby czerń nie była płaska.
- Ikony: własne, liniowe SVG (pieczęcie / sigile), **żadnych grafik z gry** (prawa autorskie).

### Ruch
- Wolne przejścia 300–600 ms, `ease-out`, bez sprężyn i „podskoków”.
- Zdarzenie na żywo (np. boss pokonany po zapisie save'a): krótki złoty napis przez środek ekranu
  z rozszerzającym się odstępem liter, potem karta bossa przechodzi w stan „pokonany”.
- Wskaźnik „na żywo” w górnym pasku: pulsująca kropka łaski + „ostatni zapis 23 s temu”.

## Struktura aplikacji

```
┌──────────────────────────────────────────────────────────────────────┐
│ ◆ boink · poz. 180 · 77 h · ☠ 330          ● zapis 23 s temu (online) │  pasek postaci
├────────┬─────────────────────────────────────────────────────────────┤
│ MAPA   │                                                             │
│ BOSSOWIE│               treść widoku                    │ szuflada   │
│ QUESTY │                                                │ szczegółów │
│ PRZEDM.│                                                │ (po kliknięciu)
└────────┴─────────────────────────────────────────────────────────────┘
```

### Widoki
1. **Bossowie**: licznik `pokonani / wszyscy` z pierścieniem postępu, filtry (region, gra / DLC,
   tylko pozostali, obowiązkowi), siatka kart z sigilem, nazwą, regionem i stanem.
   Klik → szuflada: lokalizacja, **jak dotrzeć** (kroki), wymagania, nagrody, mini-mapa.
2. **Questy**: lista NPC z paskami postępu. Wybrany quest → oś czasu kroków (zrobione / bieżący /
   kolejne), wyróżniona karta **„Co dalej”** i ostrzeżenia o rzeczach, które można przegapić.
3. **Przedmioty**: kategorie (bronie, zbroje, talizmany, czary, popioły wojny, duchy…),
   siatka kolekcji: zdobyte w złocie, brakujące jako sylwetki. Klik → gdzie leży i jak zdobyć.
4. **Mapa**: pergamin, znaczniki wszystkich punktów (łaski, bossowie, przedmioty, questy) z filtrami,
   pozycja postaci z ostatniego zapisu, legenda, zoom i przesuwanie.

## Pomysły na dodatkowe funkcje (z danych save'a)

| # | Pomysł | Skąd dane | W makiecie |
|---|---|---|---|
| 1 | **Kronika**: automatyczna oś czasu zdarzeń (łaski, bossowie, questy) | diff flag między zapisami | ✅ widok |
| 2 | **Miejsca śmierci** (mapa cieplna) + liczba prób na bossa | pozycja plamy krwi (`blood_stain`) w każdym zapisie + licznik śmierci | ✅ warstwa mapy |
| 3 | **Tryb bez spoilerów**: nieodkryte rzeczy jako zamazane sylwetki | flagi odkrycia / regiony | ✅ przełącznik |
| 4 | Ostrzeżenia „zanim zabijesz X, dokończ Y” | flagi questów + bossów | ✅ w widoku questów |
| 5 | **Podsumowanie sesji** (karta do udostępnienia) | diff od startu sesji | ✅ |
| 6 | **Mgła wojny** z odblokowanych regionów | `unlocked_regions` | ✅ mapa |
| 7 | Postęp per region (%) | flagi pogrupowane po regionach | ✅ mapa / bossowie |
| 8 | Statystyki postaci, wykres poziomu w czasie | PlayerGameData, historia zapisów | – |
| 9 | Porównanie postaci / NG+ | profil USER_DATA010, `clear_count` | – |
| 10 | Osiągnięcia Steam z flag | flagi | – |
| 11 | Widok na telefon (QR w sieci LAN), nakładka OBS | backend HTTP | – |

## Makieta

`mockup/index.html`: jeden plik, dane przykładowe zgodne z kontraktem API backendu
([07-backend-api.md](07-backend-api.md), przygotowuje go równoległa sesja).
Mapa w makiecie to **abstrakcyjny, ręcznie narysowany w SVG ląd**: prawdziwą mapę świata
wyciągniemy później z plików gry zainstalowanej u użytkownika.

## Zachowanie widoków (stan na 2026-11-23, po dwóch audytach)

- **Nazewnictwo jak w grze**: PŻ / PS / Energia, atrybut Wytrzymałość, Wielki run, „runów”, Wieczne więzienia, Grobowce
  bohaterów, Dzwonki kuliste. Filtry wszędzie w tej samej kolejności: Wszystko / Gra podstawowa / DLC.
  Odmiana liczebników przez `plural()` / `pl()` w `app.js`.
- **Tryb bez spoilerów**: boss odsłania się po spotkaniu (łaska przy arenie, teren, próba walki); przedmioty ukryte tylko
  rzadkie i legendarne, których nie masz; „Odsłoń” działa na jeden boss / przedmiot (`state.revealed`), nie wyłącza trybu.
  Kroki questów niezaliczone pokazują wersję bez spoilerów.
- **Mapa**: wyszukiwanie pokazuje chip „Filtr: … ✕”, czyści się po wyjściu z mapy; „Wszystkie miejsca” z przedmiotu filtruje
  po dokładnej nazwie. Klik w mini-mapę w szczegółach → okienko „Pokazać na dużej mapie?”. NPC z questem: klik → quest.
- **Postacie**: ręczny wybór przypina postać; „Śledź automatycznie” wraca do postaci, której save zmienił się ostatnio.
- **Bossowie**: grupy wg rangi (domyślnie), kraina, status; panel krain po prawej z podkrainami; niepokonani przygaszeni.
- **Przedmioty**: grupy wg rzadkości (domyślnie), typu, skalowania, żywiołu; ramki rzadkość × żywioł; „Jak zdobyć”
  (bossowie, kupcy z ceną / wymiana / przeróbka odzienia, łup z przeciwników z szansą, nagrody ze zdarzeń).
