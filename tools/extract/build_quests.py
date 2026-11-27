"""Questy NPC (gra podstawowa + DLC) z flagami zdarzeń -> assets/data/quests.json.

Źródła flag (każdy krok ma tylko prawdziwe flagi, nic nie jest zgadywane z numeracji):
  * regulation.bin z gry (ItemLotParam_map/_enemy: getItemFlagId): flaga „przedmiot otrzymany”.
    Przedmioty dawane przez NPC w rozmowie mają loty 100000–119999 i flagi 400000–400999.
  * The Grand Archives CT (cache: assets/cache/community/tga/): flagi pokonania bossów
    (Event Flag Manager) i opisane flagi stanu NPC (Event Flags/Deprecated/NPCs).
  * skrypty rozmów (talk ESD) z gry: tylko do przypisania bloku flag stanu NPC (20 flag: +0 przyjazny,
    +1 wrogi, +3 martwy, +5..+18 etap/położenie, +19 techniczna) do konkretnej postaci.
Teksty kroków są pisane własnymi słowami; nazwy przedmiotów/miejsc/postaci są brane z plików gry (polpl).

Użycie:
    python tools/extract/build_quests.py            # tylko generuje quests.json
    python tools/extract/build_quests.py --verify   # + sprawdza flagi na postaciach przez lokalny backend
                                                    #   (GET http://127.0.0.1:8765/api/flags) i ustawia confidence
Wymaga gry (regulation.bin, msgbnd) jak pozostałe skrypty w tools/extract oraz pobranej tabeli TGA w cache.
"""
import json
import os
import re
import struct
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
import archive as A  # noqa: E402
import params as P  # noqa: E402

ROOT = A.ROOT
TGA_DIR = os.path.join(ROOT, "assets", "cache", "community", "tga-flags")           # tools/fetch_community.py
if not os.path.isdir(TGA_DIR):                                                        # stary układ (pełne archiwum)
    TGA_DIR = os.path.join(ROOT, "assets", "cache", "community", "tga", "Elden-Ring-CT-TGA-master", "CheatTable",
                           "CheatEntries", "Open - The Grand Archives - Elden Ring", "Event Flags")
BST = os.path.join(ROOT, "docs", "data", "er-save-lib", "eventflag_bst.txt")
OUT = os.path.join(ROOT, "assets", "data", "quests.json")
BACKEND = "http://127.0.0.1:8765"
VERIFY_FILE = "co2"   # plik z wszystkimi 7 postaciami (w tym nowa „chuj”)

SOURCES = {
    "regulation": {"title": "regulation.bin z gry (ItemLotParam: getItemFlagId — flaga otrzymania przedmiotu)",
                   "url": None, "license": "dane gry z lokalnej instalacji użytkownika; czytane lokalnie, nie kopiowane"},
    "tga-ct": {"title": "The Grand Archives — Elden Ring CT (Event Flag Manager: flagi bossów; "
                        "Event Flags/Deprecated/NPCs: opisane flagi stanu NPC)",
               "url": "https://github.com/The-Grand-Archives/Elden-Ring-CT-TGA",
               "license": "brak pliku licencji w repozytorium (domyślnie wszelkie prawa zastrzeżone); "
                          "korzystamy tylko z numerów flag (fakty techniczne), lokalnie, z podaniem źródła"},
    "talk-esd": {"title": "Skrypty rozmów (talk ESD) i NpcName z plików gry — przypisanie bloku flag stanu do NPC",
                 "url": None, "license": "dane gry z lokalnej instalacji użytkownika"},
    "npc-block": {"title": "Blok flag stanu NPC (20 flag): krok „NPC opuścił stan początkowy” = dowolna z flag +6..+18",
                  "note": "Reguła wyprowadzona z TGA (opisane bloki) + porównania 7 postaci; znaczenie pojedynczych "
                          "etapów nieopisane — dlatego takie kroki obniżają pewność."},
    "save-verified": {"title": "Sprawdzone na save'ach użytkownika (7 postaci, plik co2)",
                      "note": "Kroki zaliczone w kolejności (brak późniejszego kroku bez wcześniejszego), nowa postać bez kroków."},
    "general-knowledge": {"title": "Wiedza ogólna o przebiegu questów (opisy kroków i wskazówki pisane własnymi słowami)",
                          "note": "Kolejność i opisy do potwierdzenia w grze."},
}


# ---------------------------------------------------------------------------- dane z gry
def load_game():
    en, pl = P.load_texts("engus"), P.load_texts("polpl")

    def pair(base):
        e2p = {}
        for suf in ("", "_dlc01", "_dlc02"):
            te, tp = en.get(base + suf, {}), pl.get(base + suf, {})
            for i, v in te.items():
                if tp.get(i):
                    e2p.setdefault(v.strip(), tp[i].strip())
        return e2p

    names = {"i": {}, "p": pair("PlaceName"), "n": pair("NpcName")}
    for b in ("GoodsName", "WeaponName", "ProtectorName", "AccessoryName", "GemName"):
        for k, v in pair(b).items():
            names["i"].setdefault(k, v)
    # przedmiot (kategoria, id) -> nazwa EN, do lotów
    cat_tbl = {1: "GoodsName", 2: "WeaponName", 3: "ProtectorName", 4: "AccessoryName", 5: "GemName"}
    en_by = {}
    for c, b in cat_tbl.items():
        t = {}
        for suf in ("", "_dlc01", "_dlc02"):
            t.update(en.get(b + suf, {}))
        en_by[c] = t

    def item_en(c, i):
        t = en_by.get(c, {})
        if c in (2, 3):
            return t.get(i) or t.get(i - i % 100)
        return t.get(i)

    lots = {"talk": {}, "world": {}}   # nazwa EN -> {flaga}
    prm = P.load_params()
    for pname in ("ItemLotParam_map", "ItemLotParam_enemy"):
        rows, _ = P.rows(prm[pname])
        for rid, r in rows:
            ids = struct.unpack_from("<8i", r, 0)
            cats = struct.unpack_from("<8i", r, 0x20)
            flag = struct.unpack_from("<I", r, 0x80)[0]
            if not flag:
                continue
            kind = "talk" if pname == "ItemLotParam_map" and 100000 <= rid < 120000 else "world"
            for c, i in zip(cats, ids):
                n = item_en(c, i) if i > 0 else None
                if n:
                    lots[kind].setdefault(n.strip(), set()).add(flag)
    return names, lots


def load_tga_bosses():
    """Event Flag Manager (.cea, Lua): {nazwa bossa EN: flaga isDefeated}."""
    path = os.path.join(TGA_DIR, "Event Flag Manager", ".cea")
    text = open(path, encoding="utf-8").read()
    out = {}
    for m in re.finditer(r'\{category = "Bosses", subcategory = "[^"]*", name = "([^"]*) \| Defeated", '
                         r'flags = \{(?:\s*--[^\n]*)*\s*FLAG\((\d+)\)', text):
        out.setdefault(m.group(1), int(m.group(2)))
    return out


def load_tga_npc_labels():
    """Deprecated/NPCs: opisane flagi stanu NPC (offset w bloku flag -> ID przez eventflag_bst)."""
    pos_to_block = {}
    for ln in open(BST, encoding="utf-8"):
        if ln.strip():
            b, p = ln.strip().split(",")
            pos_to_block[int(p)] = int(b)
    root = "\\\\?\\" + os.path.join(TGA_DIR, "Deprecated", "NPCs")
    labels = {}

    def parse(p):
        t = open(p, encoding="utf-8").read()
        g = lambda tag: (re.search(f"<{tag}>(.*?)</{tag}>", t, re.S) or [None, None])[1]  # noqa: E731
        return {"desc": (g("Description") or "").strip('"'), "addr": g("Address"), "bit": g("BitStart"),
                "offs": re.findall(r"<Offset>([0-9A-Fa-f]+)</Offset>", t)}

    def walk(d, base, who):
        hdr = os.path.join(d, ".xml")
        a = base
        if os.path.exists(hdr):
            h = parse(hdr)
            if h["addr"] and h["addr"].startswith("+"):
                a = base + int(h["addr"][1:], 16)
            elif h["offs"]:
                a = int(h["offs"][0], 16)
        for name in os.listdir(d):
            p = os.path.join(d, name)
            if os.path.isdir(p):
                walk(p, a, who or name)
            elif name.endswith(".xml") and name != ".xml":
                e = parse(p)
                if e["bit"] is None or not e["addr"] or not e["addr"].startswith("+"):
                    continue
                off = a + int(e["addr"][1:], 16)
                blk = pos_to_block.get(off // 125)
                if blk is not None and e["desc"] not in ("?", ""):
                    labels[blk * 1000 + (off % 125) * 8 + (7 - int(e["bit"]))] = f"{who}: {e['desc']}"

    if os.path.isdir(root):
        for name in os.listdir(root):
            if os.path.isdir(os.path.join(root, name)):
                walk(os.path.join(root, name), 0, name)
    return labels


def load_bst_blocks():
    blocks = set()
    for ln in open(BST, encoding="utf-8"):
        if ln.strip():
            blocks.add(int(ln.split(",")[0]))
    return blocks


# ---------------------------------------------------------------------------- DSL definicji
def L(*names):
    """Przedmiot dany przez NPC (lot rozmowy/śmierci NPC, flagi 400xxx)."""
    return ("talk", names)


def W(*names):
    """Przedmiot podniesiony w świecie / z bossa (lot mapy)."""
    return ("world", names)


def B(*names):
    """Boss pokonany (flaga isDefeated z TGA CT)."""
    return ("boss", names)


def F(*ids, src="tga-ct"):
    """Flaga podana wprost (z opisanym źródłem)."""
    return ("raw", ids, src)


DEAD_FLAG = 3       # offset in an NPC's flag block set when the character dies


def NPC(base, skip=(), dead=True):
    """NPC opuścił stan początkowy: dowolna flaga etapu +6..+17 z jego bloku (bez etapów startowych `skip`)
    albo (dead=True) flaga śmierci +3. +18 pomijamy — u części postaci jest ustawiona w blokach bez NPC."""
    ids = [base + k for k in range(6, 18) if k not in skip] + ([base + DEAD_FLAG] if dead else [])
    return ("raw", tuple(ids), "npc-block")


def S(text, *specs, where=None, next=None, mode="any", cumulative=False):  # noqa: A002
    """cumulative=True: krok zaliczony także wtedy, gdy zaliczony jest którykolwiek późniejszy krok
    (np. „spotkaj NPC” — skoro jest dalszy etap, to spotkanie było)."""
    return {"text": text, "specs": specs, "where": where, "next": next, "mode": mode, "cumulative": cumulative}


def Q(qid, name, npc, region, icon, steps, dlc=False, locks=(), missable=False, notes=None, npc_block=None):
    return {"id": qid, "name": name, "npc_en": npc, "region_en": region, "icon_en": icon, "steps": steps,
            "dlc": dlc, "locks": list(locks), "missable": missable, "notes": notes, "npc_block": npc_block}


def LOCK(boss_en, step, warning):
    return {"boss_en": boss_en, "step": step, "warning": warning}


QUESTS = [
    # ------------------------------------------------------------------ gra podstawowa
    Q("ranni", "Wiedźma Ranni i Era Gwiazd", "Ranni the Witch", "Liurnia of the Lakes", "Dark Moon Ring", [
        S("Spotkaj Rennę w lokacji {p:Church of Elleh} (nocą, po zdobyciu konia). Da przedmioty {i:Spirit Calling Bell} i {i:Lone Wolf Ashes}.",
          L("Spirit Calling Bell"), where="{p:Church of Elleh}",
          next="Odwiedź lokację {p:Church of Elleh} nocą, mając już przedmiot {i:Spectral Steed Whistle}."),
        S("Zdobądź przedmiot {i:Fingerslayer Blade} w lokacji {p:Nokron, Eternal City} (dostępne po pokonaniu Radahna).",
          W("Fingerslayer Blade"), where="{p:Nokron, Eternal City}",
          next="Zgłoś się do Ranni w lokacji {p:Ranni's Rise}, pokonaj Radahna i znajdź {i:Fingerslayer Blade} w Nokron."),
        S("Oddaj ostrze Ranni, a otrzymasz przedmiot {i:Carian Inverted Statue}.", L("Carian Inverted Statue"),
          where="{p:Ranni's Rise}", next="Zanieś przedmiot {i:Fingerslayer Blade} do Ranni w lokacji {p:Ranni's Rise}."),
        S("Odwróć bibliotekę ({p:Carian Study Hall}) i zdobądź przedmiot {i:Cursemark of Death} w lokacji {p:Divine Tower of Liurnia}.",
          W("Cursemark of Death"), where="{p:Divine Tower of Liurnia}",
          next="Użyj posągu w lokacji {p:Carian Study Hall} i wejdź na szczyt {p:Divine Tower of Liurnia}."),
        S("Przejdź lokację {p:Ainsel River} do Nokstelli, pokonaj Cień zguby i weź przedmiot {i:Miniature Ranni}.",
          L("Miniature Ranni"), where="{p:Ainsel River}",
          next="Zejdź do lokacji {p:Ainsel River} (przez skrzynię w lokacji {p:Ranni's Rise}) i dojdź do Nokstelli."),
        S("Pokonaj Astel w lokacji {p:Lake of Rot}.", B("Astel, Naturalborn of the Void"),
          where="{p:Lake of Rot}", next="Przejdź lokację {p:Lake of Rot} i pokonaj Astel, Zrodzoną z Pustki."),
        S("Zdobądź przedmiot {i:Dark Moon Ring} w lokacji {p:Cathedral of Manus Celes} i załóż go Ranni.", W("Dark Moon Ring"),
          where="{p:Cathedral of Manus Celes}",
          next="Za Astel dojdź do lokacji {p:Moonlight Altar}, weź pierścień z katedry i wróć do Ranni."),
        S("Odbierz przedmiot {i:Dark Moon Greatsword} od Ranni.", L("Dark Moon Greatsword"),
          where="{p:Cathedral of Manus Celes}", next="Porozmawiaj z Ranni po założeniu pierścienia."),
    ], locks=[LOCK("Elden Beast", "s7", "Zakończenie Ery Gwiazd wymaga pierścienia na Ranni przed walką z "
                                          "Bestią Eldeńską.")],
        notes="Zakończenie Ery Gwiazd wymaga tego questa. Kroki pośrednie (Wieża Ranni, Seluvis, Iji) nie mają tu flag.",
        npc_block=3740),

    Q("blaidd", "Blaidd, Półwilk", "Blaidd the Half-Wolf", "Limgrave", "Royal Greatsword", [
        S("Spotkaj Blaidda (wycie w lokacji {p:Mistwood}) i pomóż mu w lokacji {p:Forlorn Hound Evergaol}: pokonaj Darriwila.",
          B("Bloodhound Knight Darriwil"), where="{p:Forlorn Hound Evergaol}",
          next="Porozmawiaj z Blaiddem w lokacji {p:Mistwood Ruins}, potem pokonaj Darriwila w wiecznym więzieniu."),
        S("Pokonaj Radahna (Blaidd pomaga na festiwalu w lokacji {p:Redmane Castle}).", B("Starscourge Radahn"),
          where="{p:Redmane Castle}", next="Weź udział w festiwalu w lokacji {p:Redmane Castle} i pokonaj Radahna."),
        S("Po zakończeniu questa Ranni Blaidd szaleje. Pokonaj go w lokacji {p:Ranni's Rise} i weź jego ekwipunek.",
          L("Royal Greatsword"), F(3603, src="tga-ct"), where="{p:Ranni's Rise}",
          next="Po zakończeniu questa Ranni wróć do lokacji {p:Ranni's Rise}."),
    ], notes="Krok 3 zaliczony także, gdy Blaidd zginie (flaga 3603).", npc_block=3600),

    Q("iji", "Iji, mistrz kowalstwa", "Smithing Master Iji", "Liurnia of the Lakes", "Iji's Mirrorhelm", [
        # bez NPC(3760): spotkanie z rozmowy (quest_talk_flags.json) — stan bloku zmienia się też bez rozmowy
        S("Spotkaj Iji przy drodze do lokacji {p:Caria Manor} (pomaga w queście Ranni).", cumulative=True,
          where="{p:Liurnia of the Lakes}", next="Idź drogą do lokacji {p:Caria Manor} i porozmawiaj z kowalem Iji."),
        S("Po zakończeniu questa Ranni Iji ginie. Zabierz {i:Iji's Mirrorhelm} i {i:Iji's Bell Bearing}.",
          L("Iji's Mirrorhelm", "Iji's Bell Bearing"), where="{p:Liurnia of the Lakes}",
          next="Ukończ quest Ranni i wróć do miejsca, gdzie stał Iji."),
    ], npc_block=3760),

    Q("seluvis", "Mistrz Seluvis", "Preceptor Seluvis", "Liurnia of the Lakes", "Seluvis's Potion", [
        S("Porozmawiaj z Seluvisem w lokacji {p:Three Sisters}. Da przedmiot {i:Seluvis's Potion}.", L("Seluvis's Potion"),
          cumulative=True,
          where="{p:Three Sisters}", next="Po dołączeniu do Ranni zejdź do wieży Seluvisa w lokacji {p:Three Sisters}."),
        S("Zakończenie: Seluvis ginie (z ręki Ranni albo Twojej) i zostawia {i:Seluvis's Bell Bearing}.",
          L("Seluvis's Bell Bearing"), where="{p:Three Sisters}",
          next="Postęp w queście Ranni kończy historię Seluvisa."),
    ], missable=True, notes="Eliksir można podać Nepheli, Łajnożercy albo Ryi; sekretne marionetki = {i:Pidia's Bell Bearing}.",
        npc_block=3560),

    Q("sellen", "Czarodziejka Sellen", "Sorceress Sellen", "Limgrave", "Sellen's Primal Glintstone", [
        S("Spotkaj Sellen w lokacji {p:Waypoint Ruins} (piwnica). Da przedmiot {i:Sellen's Primal Glintstone}.",
          L("Sellen's Primal Glintstone"), where="{p:Waypoint Ruins}",
          next="Pokonaj bossa w piwnicy lokacji {p:Waypoint Ruins} i porozmawiaj z Sellen."),
        S("Znajdź Azura w lokacji {p:Hermit Village} i wróć do Sellen, a otrzymasz przedmiot {i:Sellian Sealbreaker}.",
          L("Sellian Sealbreaker"), where="{p:Waypoint Ruins}",
          next="Odszukaj pierwotnego czarodzieja Azura w lokacji {p:Mt. Gelmir} i opowiedz o nim Sellen."),
        S("Złam pieczęć w lokacji {p:Sellia Hideaway} i spotkaj Lusata ({i:Stars of Ruin}).", L("Stars of Ruin"),
          where="{p:Sellia Hideaway}", next="Użyj łamacza pieczęci w lokacji {p:Sellia Hideaway} (Caelid)."),
        S("Spotkaj Sellen w lokacji {p:Witchbane Ruins} ({i:Starlight Shards}).", L("Starlight Shards"),
          where="{p:Witchbane Ruins}", next="Wróć do Sellen; poprowadzi Cię do lokacji {p:Witchbane Ruins} w Pogrobnie."),
        S("Rozstrzygnij spór Sellen i Jerrena w lokacji {p:Academy of Raya Lucaria}: {i:Glintstone Kris} (strona Sellen) "
          "albo {i:Sellen's Bell Bearing} (strona Jerrena).",
          L("Glintstone Kris", "Sellen's Bell Bearing"), where="{p:Academy of Raya Lucaria}",
          next="Po Rennali idź do sali Rennali w Akademii i wybierz stronę."),
    ], missable=True, npc_block=3460),

    Q("rya", "Rya i Wulkaniczny Dwór", "Rya the Scout", "Liurnia of the Lakes", "Rya's Necklace", [
        S("Odkup {i:Rya's Necklace} od Boggarta i oddaj go Ryi.", L("Rya's Necklace"),
          where="{p:Liurnia of the Lakes}",
          next="Porozmawiaj z Ryą przy drodze w Liurnii, potem z Boggartem w chacie nad jeziorem."),
        S("Spotkaj Ryę (Zorayas) w lokacji {p:Volcano Manor} i zakończ jej historię: {i:Tonic of Forgetfulness} "
          "lub {i:Zorayas's Letter}.", L("Zorayas's Letter", "Tonic of Forgetfulness"), where="{p:Volcano Manor}",
          next="Weź od Ryi przedmiot {i:Volcano Manor Invitation}, odnajdź ją w Dworze i wykonaj prośbę Tanith o eliksir."),
    ], missable=True, npc_block=3420),

    Q("tanith", "Tanith i zlecenia Wulkanicznego Dworu", "Tanith, Volcano Manor Proprietress", "Mt. Gelmir",
      "Drawing-Room Key", [
          S("Przyjmij zaproszenie Tanith ({i:Drawing-Room Key}).", L("Drawing-Room Key"),
            where="{p:Volcano Manor}", next="Porozmawiaj z Tanith w lokacji {p:Volcano Manor}."),
          S("Pierwsze zlecenie: pokonaj Istvana (zlecenie z listu: {i:Letter from Volcano Manor}).",
            L("Magma Shot"), where="{p:Limgrave}",
            next="Weź list z pracowni i najedź Istvana w Pogrobnie."),
          S("Drugie zlecenie: pokonaj Rileigha.", L("Serpentbone Blade"), where="{p:Altus Plateau}",
            next="Weź kolejny list z pracowni i najedź Rileigha."),
          S("Trzecie zlecenie: {i:Red Letter}, pokonaj Juno Hoslow.", L("Red Letter"), where="{p:Altus Plateau}",
            next="Weź przedmiot {i:Red Letter} z pracowni Dworu."),
          S("Pokonaj Rykarda i wróć do Tanith ({i:Taker's Cameo}).", L("Taker's Cameo"), where="{p:Volcano Manor}",
            next="Udaj się przez świątynię Dworu do Rykarda, potem porozmawiaj z Tanith."),
      ], locks=[LOCK("Rykard, Lord of Blasphemy", "s4",
                     "Zabicie Rykarda przed wykonaniem zleceń Tanith zamknie dalsze zlecenia.")], missable=True,
      npc_block=3100),

    Q("bernahl", "Rycerz Bernahl", "Knight Bernahl", "Mt. Gelmir", "Gelmir's Fury", [
        S("Pomóż Bernahlowi w jego zleceniu w Wulkanicznym Dworze ({i:Gelmir's Fury}).", L("Gelmir's Fury"),
          where="{p:Volcano Manor}", next="Porozmawiaj z Bernahlem w lokacji {p:Volcano Manor}."),
        S("Po pokonaniu Rykarda odbierz od Bernahla {i:Blasphemous Claw}.", L("Blasphemous Claw"),
          where="{p:Volcano Manor}", next="Pokonaj Rykarda i porozmawiaj z Bernahlem."),
        S("Pokonaj Bernahla, gdy zaatakuje w lokacji {p:Crumbling Farum Azula} ({i:Devourer's Scepter}).",
          L("Devourer's Scepter", "Beast Champion Helm", "Bernahl's Bell Bearing"),
          where="{p:Crumbling Farum Azula}", next="W Farum Azula pokonaj najeźdźcę Bernahla."),
    ], npc_block=3880),

    Q("varre", "Białolicy Varré", "White Mask Varré", "Limgrave", "Varré's Bouquet", [
        S("Pokonaj Godricka i porozmawiaj z Varrém ({i:Festering Bloody Finger}).",
          L("Festering Bloody Finger"), where="{p:Limgrave}",
          next="Porozmawiaj z Varrém przy lokacji {p:Limgrave} (Pierwszy Krok) po pokonaniu Godricka."),
        S("Najedź trzech graczy i wróć do lokacji {p:Rose Church} ({i:Lord of Blood's Favor}).",
          L("Lord of Blood's Favor"), where="{p:Rose Church}",
          next="Odwiedź Varrégo w lokacji {p:Rose Church} (Liurnia) i wykonaj jego prośbę."),
        S("Nasącz chustę krwią służki i oddaj ją ({i:Pureblood Knight's Medal}).",
          L("Pureblood Knight's Medal"), where="{p:Rose Church}",
          next="Zanurz chustę we krwi martwej służki w lokacji {p:Church of Inhibition} i wróć do Varrégo."),
        S("Pokonaj Varrégo w lokacji {p:Mohgwyn Palace} ({i:Varré's Bouquet}).", L("Varré's Bouquet"),
          F(3183, src="tga-ct"), where="{p:Mohgwyn Palace}",
          next="Użyj medalu, by przenieść się do lokacji {p:Mohgwyn Palace}; Varré tam czeka."),
    ], missable=True, notes="Krok 4 zaliczony też, gdy Varré zginął (flaga 3183).", npc_block=3180),

    Q("alexander", "Alexander, Wielki słojownik", "Alexander, Warrior Jar", "Limgrave", "Shard of Alexander", [
        S("Wyciągnij Alexandra z ziemi w lokacji {p:Stormhill} ({i:Exalted Flesh}).", L("Exalted Flesh"),
          where="{p:Stormhill}", next="Uderz utkniętego Alexandra na północ od lokacji {p:Gatefront} (Burzowe Wzgórze)."),
        S("Spotkaj go na festiwalu i pokonaj Radahna.", B("Starscourge Radahn"), where="{p:Redmane Castle}",
          next="Weź udział w festiwalu w lokacji {p:Redmane Castle}."),
        S("Pomóż mu w gorących źródłach w lokacji {p:Mt. Gelmir} ({i:Jar}).", L("Jar"), where="{p:Mt. Gelmir}",
          next="Znajdź Alexandra w źródłach lawy w lokacji {p:Mt. Gelmir}."),
        S("Stocz z nim pojedynek w lokacji {p:Crumbling Farum Azula} ({i:Shard of Alexander}).",
          L("Shard of Alexander", "Warrior Jar Shard"), where="{p:Crumbling Farum Azula}",
          next="Odszukaj Alexandra w lokacji {p:Crumbling Farum Azula}."),
    ], npc_block=3660),

    Q("millicent", "Millicenta", "Millicent", "Caelid", "Prosthesis-Wearer Heirloom", [
        S("Weź przedmiot {i:Unalloyed Gold Needle} od Gowry'ego i ulecz Millicentę w lokacji {p:Church of the Plague}.",
          F(400310, src="regulation"), where="{p:Church of the Plague}",
          next="Odwiedź Gowry'ego w Caelid, potem Millicentę w lokacji {p:Church of the Plague}."),
        S("Porozmawiaj z uleczoną Millicentą ({i:Prosthesis-Wearer Heirloom}).", L("Prosthesis-Wearer Heirloom"),
          where="{p:Church of the Plague}", next="Wróć do Millicenty po uleczeniu."),
        S("W {p:Elphael, Brace of the Haligtree} pomóż jej ({i:Rotten Winged Sword Insignia}) "
          "albo ją zdradź ({i:Millicent's Prosthesis}).",
          L("Rotten Winged Sword Insignia", "Millicent's Prosthesis"), where="{p:Elphael, Brace of the Haligtree}",
          next="Przejdź przez lokację {p:Altus Plateau}, {p:Mt. Gelmir} i {p:Mountaintops of the Giants} śladami Millicenty, "
               "potem znajdź jej znak w Elphael."),
        S("Po Malenii oddaj igłę ciału Millicenty ({i:Miquella's Needle}).",
          F(400321, 400324, src="regulation"), where="{p:Elphael, Brace of the Haligtree}",
          next="Pokonaj Malenię i połóż igłę przy ciele Millicenty."),
    ], locks=[LOCK("Malenia, Blade of Miquella", "s3",
                   "Pokonanie Malenii przed spotkaniem z Millicentą w Elphael przerwie jej quest.")],
        missable=True, npc_block=4180),

    Q("gowry", "Mędrzec Gowry", "Sage Gowry", "Caelid", "Flock's Canvas Talisman", [
        S("Spotkaj Gowry'ego w jego chacie ({i:Unalloyed Gold Needle}).", F(400310, src="regulation"),
          where="{p:Caelid}", next="Znajdź chatę Gowry'ego w Caelid (na północ od Sellii)."),
        S("Odbierz przedmiot {i:Sellia's Secret}.", L("Sellia's Secret"), where="{p:Caelid}",
          next="Porozmawiaj z Gowrym po wyleczeniu Millicenty."),
        S("Zakończenie: Gowry ginie i zostawia {i:Flock's Canvas Talisman}.", L("Flock's Canvas Talisman"),
          where="{p:Caelid}", next="Po zdradzie/pomocy Millicencie w Elphael wróć do chaty Gowry'ego."),
    ], npc_block=4160),

    Q("fia", "Fia, Towarzyszka na Łożu Śmierci", "Fia, Deathbed Companion", "Roundtable Hold", "Weathered Dagger", [
        S("Porozmawiaj z Fią w lokacji {p:Roundtable Hold} (objęcie, {i:Weathered Dagger}).",
          L("Weathered Dagger", "Radiant Baldachin's Blessing"), F(400332, src="regulation"), cumulative=True,
          where="{p:Roundtable Hold}", next="Porozmawiaj z Fią w Twierdzy Okrągłego Stołu."),
        S("Zejdź za Fią do lokacji {p:Deeproot Depths} i pokonaj jej czempionów.", B("Fia's Champions"),
          where="{p:Deeproot Depths}", next="Ukończ wątek D i Rogiera, potem idź do lokacji {p:Deeproot Depths}."),
        S("Pokonaj Fortissaxa we śnie Fii.", B("Lichdragon Fortissax"), where="{p:Deeproot Depths}",
          next="Porozmawiaj ze śpiącą Fią w lokacji {p:Deeproot Depths}."),
        S("Weź przedmiot {i:Mending Rune of the Death-Prince}.", F(9502, src="regulation"), where="{p:Deeproot Depths}",
          next="Podnieś run przy Fii po walce."),
    ], locks=[LOCK("Elden Beast", "s4", "Run naprawy trzeba mieć przed walką z Bestią Eldeńską, "
                                         "żeby wybrać to zakończenie.")],
        notes="Flaga 9502 = lot runu naprawy (regulation.bin).", npc_block=4120),

    Q("d", "D, Łowca Umarłych", "D, Hunter of the Dead", "Roundtable Hold", "D's Bell Bearing", [
        S("Spotkaj D w lokacji {p:Summonwater Village} i w lokacji {p:Roundtable Hold}.", NPC(4040), cumulative=True,
          where="{p:Summonwater Village}", next="Porozmawiaj z D przy lokacji {p:Summonwater Village} w Pogrobnie."),
        S("Historia D kończy się w lokacji {p:Roundtable Hold} ({i:D's Bell Bearing}).", L("D's Bell Bearing"),
          where="{p:Roundtable Hold}", next="Postęp w queście Fii prowadzi do śmierci D."),
        S("Oddaj zbroję D jego bratu ({i:Inseparable Sword}).", L("Inseparable Sword"),
          where="{p:Roundtable Hold}", next="Daj ekwipunek D jego bratu w Twierdzy Okrągłego Stołu."),
    ], npc_block=4040),

    Q("rogier", "Czarodziej Rogier", "Sorcerer Rogier", "Stormveil Castle", "Rogier's Letter", [
        S("Spotkaj Rogiera w lokacji {p:Stormveil Castle}, potem w lokacji {p:Roundtable Hold}.", NPC(3900), cumulative=True,
          where="{p:Stormveil Castle}", next="Znajdź Rogiera na dziedzińcu Zamku Burzowego Całunu."),
        S("Po śledztwie (przedmiot {i:Black Knifeprint}) Rogier umiera i zostawia {i:Rogier's Letter}.", L("Rogier's Letter"),
          where="{p:Roundtable Hold}", next="Odnajdź zbroję zabójców i porozmawiaj z Rogierem oraz Fią."),
        S("Odbierz po nim {i:Rogier's Bell Bearing}.", L("Rogier's Bell Bearing"), where="{p:Roundtable Hold}",
          next="Podejdź do ciała Rogiera w Twierdzy."),
    ], npc_block=3900),

    Q("boc", "Półczłowiek Boc", "Demi-Human Boc", "Limgrave", "Tailoring Tools", [
        S("Uwolnij Boca w lokacji {p:Coastal Cave} ({i:Tailoring Tools}).", F(60140, src="regulation"),
          where="{p:Coastal Cave}", next="Pokonaj wodzów półludzi w lokacji {p:Coastal Cave}."),
        S("Daj mu przedmiot {i:Gold Sewing Needle}.", W("Gold Sewing Needle"), where="{p:Altus Plateau}",
          next="Znajdź złotą igłę (Caelid, sklep po Łowcy dzwonków) i oddaj Bocowi."),
    ], notes="Flaga 60140 = lot Przyborów krawieckich (regulation.bin). Krok 3 = podniesienie złotej igły.",
        npc_block=3940),

    Q("patches", "Łata", "Patches", "Limgrave", "Letter to Patches", [
        S("Oszczędź Łatę w lokacji {p:Murkwater Cave}.", L("Golden Rune [1]"), B("Patches"),
          where="{p:Murkwater Cave}", next="Pokonaj Łatę w lokacji {p:Murkwater Cave} i przyjmij jego kapitulację."),
        S("Spotkaj go w lokacji {p:Volcano Manor} ({i:Letter to Patches}).", L("Letter to Patches"),
          where="{p:Volcano Manor}", next="Po przenosinach do Liurnii znajdź Łatę w Wulkanicznym Dworze."),
        S("Łata opuszcza Dwór ({i:Magma Whip Candlestick}).", L("Magma Whip Candlestick"),
          where="{p:Volcano Manor}", next="Zakończ zlecenia Dworu i porozmawiaj z Łatą."),
    ], npc_block=3680),

    Q("diallos", "Rycerz Diallos", "Knight Diallos", "Roundtable Hold", "Hoslow's Petal Whip", [
        S("Spotkaj Diallosa w lokacji {p:Roundtable Hold}, potem w Liurnii.", NPC(3440), cumulative=True,
          where="{p:Roundtable Hold}", next="Porozmawiaj z Diallosem w Twierdzy Okrągłego Stołu."),
        S("Diallos ginie w lokacji {p:Jarburg} ({i:Hoslow's Petal Whip}).", L("Hoslow's Petal Whip"), F(3443, src="tga-ct"),
          where="{p:Jarburg}", next="Odwiedź Diallosa w lokacji {p:Jarburg} po walkach w Wulkanicznym Dworze."),
    ], npc_block=3440),

    Q("jar-bairn", "Słojątko", "Jar-Bairn", "Liurnia of the Lakes", "Companion Jar", [
        S("Porozmawiaj ze Słojątkiem w lokacji {p:Jarburg}.", NPC(3820), cumulative=True, where="{p:Jarburg}",
          next="Odwiedź lokację {p:Jarburg} we wschodniej Liurnii."),
        S("Gdy Słojątko dorośnie (po śmierci Diallosa), odbierz przedmiot {i:Companion Jar}.", L("Companion Jar"),
          where="{p:Jarburg}", next="Odwiedzaj lokację {p:Jarburg} w miarę postępów Diallosa."),
    ], npc_block=3820),

    Q("kenneth", "Kenneth Haight", "Kenneth Haight, Limgrave Heir", "Limgrave", "Erdsteel Dagger", [
        S("Oczyść {p:Fort Haight} dla Kennetha ({i:Erdsteel Dagger}).", L("Erdsteel Dagger"),
          where="{p:Fort Haight}", next="Porozmawiaj z Kennethem na wzgórzu w Pogrobnie i odbij {p:Fort Haight}."),
        S("Po pokonaniu Godricka Nepheli zostaje władczynią Zamku Burzowego Całunu (z Kennethem i Gostokiem).",
          F(400422, src="regulation"), where="{p:Stormveil Castle}",
          next="Przyprowadź Nepheli do zamku, by objęła władzę."),
    ], npc_block=3580),

    Q("irina-edgar", "Irina i Edgar", "Irina of Morne", "Weeping Peninsula", "Irina's Letter", [
        S("Spotkaj Irinę przy lokacji {p:Bridge of Sacrifice} ({i:Irina's Letter}).", L("Irina's Letter"),
          where="{p:Bridge of Sacrifice}", next="Porozmawiaj z Iriną na Płaczącym Półwyspie."),
        S("Oddaj list Edgarowi w lokacji {p:Castle Morne} ({i:Sacrificial Twig}).", L("Sacrificial Twig"),
          where="{p:Castle Morne}", next="Zanieś list do Edgara w lokacji {p:Castle Morne}."),
        S("Pokonaj Lwiego wynaturzeńca w lokacji {p:Castle Morne}.", B("Leonine Misbegotten"), where="{p:Castle Morne}",
          next="Przejdź zamek do bossa."),
        S("Pokonaj Edgara Mściciela podczas najazdu w Liurnii ({i:Shabriri Grape}).", L("Shabriri Grape"),
          where="{p:Liurnia of the Lakes}", next="Edgar najedzie Cię w Liurnii (przy chacie na zachodzie)."),
    ], missable=True, npc_block=3400),

    Q("hyetta", "Hyetta i Trzy Palce", "Lightseeker Hyetta", "Liurnia of the Lakes", "Frenzied Flame Seal", [
        # bez NPC(3380): blok 3380 to jeden slot postaci — najpierw Irina, po jej śmierci Hyetta; 3387 („Irina nie żyje /
        # Hyetta czeka przy klifach”) ustawia się przed spotkaniem Hyetty. Krok zalicza się po dalszych etapach Hyetty.
        S("Spotkaj Hyettę w Liurnii i dawaj jej przedmiot {i:Shabriri Grape}.", cumulative=True,
          where="{p:Lake-Facing Cliffs}", next="Znajdź Hyettę przy lokacji {p:Lake-Facing Cliffs}."),
        S("Koniec drogi: Hyetta przy Trzech Palcach w lokacji {p:Subterranean Shunning-Grounds} ({i:Frenzied Flame Seal}).",
          L("Frenzied Flame Seal"), where="{p:Subterranean Shunning-Grounds}",
          next="Po przyjęciu Oszalałego Płomienia odwiedź Hyettę przy Trzech Palcach."),
    ], missable=True, notes="Blok flag 3380 obejmuje też Irinę (TGA łączy je w jednej grupie).", npc_block=3380),

    Q("goldmask", "Corhyn i Złota Maska", "Brother Corhyn", "Altus Plateau", "Golden Order Principia", [
        S("Spotkaj Corhyna w lokacji {p:Roundtable Hold}, potem Złotą Maskę w lokacji {p:Altus Plateau}.", NPC(4200), cumulative=True,
          where="{p:Altus Plateau}", next="Corhyn opuszcza Twierdzę i szuka Złotej Maski na płaskowyżu."),
        S("Zdobądź przedmiot {i:Golden Order Principia} w Leyndell.", W("Golden Order Principia"),
          where="{p:Leyndell, Royal Capital}", next="Znajdź zasady w ruinach Leyndell."),
        S("Odbierz przedmiot {i:Mending Rune of Perfect Order} od Złotej Maski.", F(9500, src="regulation"),
          where="{p:Leyndell, Royal Capital}", next="Pokaż Złotej Masce zasady na moście w Leyndell, Stolicy Popiołu."),
        S("Zakończenie: {i:Corhyn's Robe} / {i:Goldmask's Rags}.", L("Corhyn's Robe", "Goldmask's Rags"),
          where="{p:Leyndell, Royal Capital}", next="Po zakończeniu gry (lub ich śmierci) zbierz ich ekwipunek."),
    ], locks=[LOCK("Elden Beast", "s3", "Run naprawy trzeba mieć przed walką z Bestią Eldeńską, "
                                        "żeby wybrać to zakończenie.")], npc_block=4200),

    Q("dung-eater", "Łajnożerca", "Dung Eater", "Roundtable Hold", "Mending Rune of the Fell Curse", [
        S("Uwolnij Łajnożercę ({i:Sewer-Gaol Key}).", L("Sewer-Gaol Key"), where="{p:Roundtable Hold}",
          next="Porozmawiaj z Łajnożercą w Twierdzy Okrągłego Stołu."),
        S("Otwórz celę w lokacji {p:Subterranean Shunning-Grounds} ({i:Sword of Milos}).", L("Sword of Milos"),
          where="{p:Subterranean Shunning-Grounds}", next="Użyj klucza w kanałach Leyndell."),
        S("Daj mu przedmiot {i:Seedbed Curse}, a dostaniesz {i:Mending Rune of the Fell Curse}.", F(9504, src="regulation"),
          where="{p:Subterranean Shunning-Grounds}", next="Zbierz 5 klątw i oddaj je Łajnożercy w celi."),
        S("Zakończenie: {i:Omen Helm} (ekwipunek po Łajnożercy).", L("Omen Helm"),
          where="{p:Subterranean Shunning-Grounds}", next="Po runie Łajnożerca umiera w celi."),
    ], locks=[LOCK("Elden Beast", "s3", "Run naprawy trzeba mieć przed walką z Bestią Eldeńską, "
                                        "żeby wybrać to zakończenie.")], npc_block=4240),

    Q("latenna", "Latenna, albinauryka", "Latenna the Albinauric", "Liurnia of the Lakes",
      "Latenna the Albinauric", [
          S("Pokaż Latennie medalion ({i:Latenna the Albinauric}).", L("Latenna the Albinauric"),
            where="{p:Liurnia of the Lakes}", next="Znajdź Latennę na północy Liurnii mając {i:Haligtree Secret Medallion (Right)}."),
          S("Zanieś jej prochy do lokacji {p:Consecrated Snowfield} ({i:Somber Ancient Dragon Smithing Stone}).",
            L("Somber Ancient Dragon Smithing Stone"), where="{p:Consecrated Snowfield}",
            next="Wezwij Latennę przy zrujnowanym kościele w lokacji {p:Consecrated Snowfield}."),
      ], npc_block=4100),

    Q("nepheli", "Nepheli Loux", "Nepheli Loux, Warrior", "Stormveil Castle", "Arsenal Charm", [
        S("Spotkaj Nepheli w lokacji {p:Stormveil Castle} i w Twierdzy ({i:Arsenal Charm}).", L("Arsenal Charm"),
          where="{p:Roundtable Hold}", next="Porozmawiaj z Nepheli po pokonaniu Godricka."),
        S("Nepheli zostaje władczynią zamku ({i:Ancient Dragon Smithing Stone}).", F(400422, src="regulation"),
          where="{p:Stormveil Castle}", next="Porozmawiaj z Kennethem i Gostokiem, potem z Nepheli."),
    ], missable=True, npc_block=4220),

    Q("thops", "Czarodziej Thops", "Sorcerer Thops", "Liurnia of the Lakes", "Thops's Barrier", [
        S("Spotkaj Thopsa w lokacji {p:Church of Irith} i daj mu przedmiot {i:Academy Glintstone Key}.", NPC(3800), cumulative=True,
          where="{p:Liurnia of the Lakes}", next="Znajdź Thopsa w Kościele Iritha (Liurnia)."),
        S("Zakończenie w Akademii: {i:Thops's Barrier} / {i:Academy Glintstone Staff}.",
          L("Thops's Barrier", "Academy Glintstone Staff"), where="{p:Academy of Raya Lucaria}",
          next="Odwiedź Thopsa w lokacji {p:Academy of Raya Lucaria}."),
    ], npc_block=3800),

    Q("gideon", "Sir Gideon Ofnir", "Sir Gideon Ofnir, the All-Knowing", "Roundtable Hold", "Law of Causality", [
        S("Porozmawiaj z Gideonem w lokacji {p:Roundtable Hold} (przenosi się do swojej komnaty).",
          # bez NPC(3960): 3967 („pokój — Godrick pokonany”) ustawia się po Godricku bez rozmowy z Gideonem;
          # rozmowy z Gideonem — z quest_talk_flags.json
          L("Black Flame's Protection", "Lord's Divine Fortification", "Law of Causality"),
          cumulative=True, where="{p:Roundtable Hold}", next="Zgłaszaj się do Gideona po każdym ważnym bossie."),
        S("Pokonaj Gideona w Leyndell, Stolicy Popiołu.", B("Sir Gideon Ofnir, the All-Knowing"),
          where="{p:Leyndell, Royal Capital}", next="Po Maliketh Gideon czeka przed Hoarah Louxem."),
    ], npc_block=3960),

    Q("roderika", "Roderika", "Roderika", "Stormhill", "Spirit Jellyfish Ashes", [
        S("Spotkaj Roderikę w chacie w lokacji {p:Stormhill} ({i:Spirit Jellyfish Ashes}).",
          L("Spirit Jellyfish Ashes"), where="{p:Stormhill}", next="Zajrzyj do chaty przy drodze na Burzowym Wzgórzu."),
        S("W Twierdzy zostań stroicielką duchów (Hewg), nagroda: {i:Golden Seed}.", L("Golden Seed"),
          where="{p:Roundtable Hold}", next="Porozmawiaj z Roderiką i Hewgiem w Twierdzy Okrągłego Stołu."),
    ], npc_block=3700),

    Q("gurranq", "Gurranq, Bestialski Duchowny", "Gurranq, Beast Clergyman", "Caelid", "Clawmark Seal", [
        S("Znajdź Gurranqa w lokacji {p:Bestial Sanctum}: {i:Beast Eye} i pierwsza nagroda {i:Clawmark Seal}.",
          L("Clawmark Seal"), where="{p:Bestial Sanctum}", next="Dotrzyj do lokacji {p:Bestial Sanctum} i oddaj pierwszy przedmiot {i:Deathroot}."),
        S("Oddaj 4 sztuki ({i:Deathroot}), nagroda: {i:Ash of War: Beast's Roar}.", L("Ash of War: Beast's Roar"),
          where="{p:Bestial Sanctum}", next="Zbieraj kolejne sztuki ({i:Deathroot}) i oddawaj je Gurranqowi."),
        S("Oddaj wszystkie 9, nagroda: {i:Ancient Dragon Smithing Stone}.", L("Gurranq's Beast Claw"),
          F(400230, src="regulation"), mode="all", where="{p:Bestial Sanctum}",
          next="Oddaj pozostałe sztuki ({i:Deathroot})."),
    ], npc_block=3640),

    Q("yura", "Yura, Łowca krwawych palców", "Yura, Hunter of Bloody Fingers", "Limgrave", "Ronin's Armor", [
        S("Spotkaj Yurę w Pogrobnie i w Liurnii.", NPC(3620, skip=(6,)), cumulative=True, where="{p:Limgrave}",
          next="Porozmawiaj z Yurą przy lokacji {p:Murkwater Cave}."),
        S("Pokonaj Eleonorę na płaskowyżu Altus ({i:Eleonora's Poleblade}).", L("Eleonora's Poleblade"),
          where="{p:Second Church of Marika}", next="Spotkaj Yurę przy lokacji {p:Second Church of Marika} i pokonaj Eleonorę."),
        S("Zakończenie: Yura / Shabriri ({i:Ronin's Armor}).", L("Ronin's Armor"),
          where="{p:Altus Plateau}", next="Spotkaj Yurę ponownie (Mt. Gelmir); jego koniec wiąże się z Shabririm."),
    ], missable=True, npc_block=3620),

    Q("boggart", "Szubrawiec Boggart", "Blackguard", "Liurnia of the Lakes", "Blackguard's Iron Mask", [
        S("Odkup od Boggarta przedmiot {i:Rya's Necklace}.", L("Rya's Necklace"), where="{p:Liurnia of the Lakes}",
          next="Odwiedź Boggarta w chacie nad jeziorem (Liurnia)."),
        S("Zakończenie: {i:Blackguard's Bell Bearing}.", L("Blackguard's Bell Bearing"),
          where="{p:Liurnia of the Lakes}", next="Spotkaj Boggarta w Twierdzy Okrągłego Stołu."),
    ], npc_block=4140),

    Q("melina", "Melina i Kuźnia Olbrzymów", "Melina", "Limgrave", "Spectral Steed Whistle", [
        S("Przyjmij propozycję Meliny ({i:Spectral Steed Whistle}).", L("Spectral Steed Whistle"),
          where="{p:Limgrave}", next="Odpocznij przy łasce przy lokacji {p:Gatefront} w Pogrobnie."),
        S("Melina zabiera Cię do lokacji {p:Roundtable Hold}.", F(71190, src="tga-ct"), where="{p:Roundtable Hold}",
          next="Odpocznij przy łasce po wejściu na Burzowe Wzgórze lub zamek."),
        S("Na płaskowyżu ({p:Altus Plateau}) Melina daje przedmiot {i:Rold Medallion}.", L("Rold Medallion"), where="{p:Altus Plateau}",
          next="Odpocznij przy łasce po pokonaniu Morgotta."),
        S("Pokonaj Maliketha. Melina rozpala Kuźnię.", B("Maliketh, the Black Blade"),
          where="{p:Crumbling Farum Azula}", next="Dotrzyj do lokacji {p:Mountaintops of the Giants} i Kuźni Olbrzymów."),
    ], npc_block=4680),

    # ------------------------------------------------------------------ DLC Shadow of the Erdtree
    Q("leda", "Leda, rycerz igły", "Needle Knight Leda", "Gravesite Plain", "Leda's Armor", [
        S("Spotkaj Ledę w lokacji {p:Gravesite Plain}.", NPC(4440), cumulative=True, where="{p:Gravesite Plain}",
          next="Porozmawiaj z Ledą przy kamiennym ołtarzu na początku DLC."),
        S("Pokonaj Messmera.", B("Messmer the Impaler"), where="{p:Shadow Keep}",
          next="Przejdź lokację {p:Shadow Keep} i pokonaj Messmera."),
        S("Zakończenie: walka z Ledą i sojusznikami w lokacji {p:Enir-Ilim} ({i:Leda's Armor}).",
          L("Leda's Armor"), F(4443, src="talk-esd"), where="{p:Enir-Ilim}",
          next="W {p:Enir-Ilim} zmierz się z Ledą (sojusznicy zależą od Twoich wyborów)."),
    ], dlc=True, missable=True, npc_block=4440),

    Q("ansbach", "Pan Ansbach", "Sir Ansbach", "Gravesite Plain", "Letter for Freyja", [
        S("Spotkaj Ansbacha ({p:Gravesite Plain}, {p:Belurat, Tower Settlement}).", NPC(4400), cumulative=True, where="{p:Gravesite Plain}",
          next="Porozmawiaj z Ansbachem przy łasce w lokacji {p:Gravesite Plain}."),
        S("Odbierz przedmiot {i:Letter for Freyja}.", L("Letter for Freyja"), where="{p:Scadu Altus}",
          next="Rozmawiaj z Ansbachem w lokacji {p:Scadu Altus}."),
        S("Zakończenie: Ansbach w lokacji {p:Enir-Ilim} i jego ekwipunek ({i:Obsidian Lamina} albo zbroja).",
          L("Wise Man's Mask", "Obsidian Lamina", "Ansbach's Longbow"), where="{p:Enir-Ilim}",
          next="Po pokonaniu Messmera spotkaj Ansbacha przed Enir-Ilim."),
    ], dlc=True, npc_block=4400),

    Q("freyja", "Freyja, Lwia Grzywa", "Redmane Freyja", "Gravesite Plain", "Freyja's Greatsword", [
        S("Spotkaj Freyję w lokacji {p:Gravesite Plain}.", NPC(4420), cumulative=True, where="{p:Gravesite Plain}",
          next="Porozmawiaj z Freyją przy lokacji {p:Castle Ensis}."),
        S("Pokonaj Rellanę z pomocą Freyi ({i:Golden Lion Shield}).", L("Golden Lion Shield"),
          where="{p:Castle Ensis}", next="Wezwij Freyję na bossa w lokacji {p:Castle Ensis}."),
        S("Zakończenie: Freyja ginie i zostawia {i:Freyja's Greatsword}.", L("Freyja's Greatsword"), where="{p:Enir-Ilim}",
          next="Jej los rozstrzyga się po walce z Messmerem."),
    ], dlc=True, npc_block=4420),

    Q("hornsent", "Rogaty przybysz", "Hornsent", "Gravesite Plain", "Cross Map", [
        S("Spotkaj Rogatego przybysza ({i:Cross Map}).", L("Cross Map"), where="{p:Gravesite Plain}",
          next="Porozmawiaj z nim przy lokacji {p:Gravesite Plain}."),
        S("Odbierz przedmiot {i:New Cross Map}.", L("New Cross Map"), where="{p:Highroad Cross}",
          next="Porozmawiaj z nim przy lokacji {p:Highroad Cross}."),
        S("Pokonaj Messmera.", B("Messmer the Impaler"), where="{p:Shadow Keep}",
          next="Przejdź lokację {p:Shadow Keep} i pokonaj Messmera."),
        S("Zakończenie: Rogaty przybysz w lokacji {p:Enir-Ilim} ({i:Falx}).", L("Falx"), F(4363, src="talk-esd"),
          where="{p:Enir-Ilim}", next="Spotkaj go w lokacji {p:Enir-Ilim} (lub w Donżonie Cienia)."),
    ], dlc=True, locks=[LOCK("Messmer the Impaler", "s2", "Porozmawiaj z Rogatym przybyszem przy Krzyżu przy "
                                                            "gościńcu przed pokonaniem Messmera, inaczej jego "
                                                            "wątek może się urwać.")],
        npc_block=4360),

    Q("hornsent-grandam", "Starowina, rogata przybyszka", "Hornsent Grandam", "Belurat, Tower Settlement",
      "Watchful Spirit", [
          S("Oddaj Starowinie zbroję rogatych ({i:Watchful Spirit}).", L("Watchful Spirit"),
            where="{p:Belurat, Tower Settlement}", next="Znajdź staruszkę w lokacji {p:Belurat, Tower Settlement}."),
          S("Wróć z gulaszem ({i:Gourmet Scorpion Stew} / {i:Scorpion Stew}).",
            L("Gourmet Scorpion Stew", "Scorpion Stew"), where="{p:Belurat, Tower Settlement}",
            next="Po Messmerze odwiedź ją ponownie."),
      ], dlc=True, npc_block=4480),

    Q("moore", "Moore i Ród poszukiwaczy", "Moore", "Gravesite Plain", "Verdigris Greatshield", [
        S("Spotkaj Moore'a w lokacji {p:Gravesite Plain}.", NPC(4380), cumulative=True, where="{p:Gravesite Plain}",
          next="Porozmawiaj z Moore'em przy wózku na Cmentarnej Równinie."),
        S("Zakończenie: {i:Verdigris Greatshield} / {i:Moore's Bell Bearing}.",
          L("Verdigris Greatshield", "Moore's Bell Bearing"), where="{p:Enir-Ilim}",
          next="Los Moore'a rozstrzyga się po walce z Messmerem."),
    ], dlc=True, notes="Dostawy dla Rodu poszukiwaczy (flagi 400750–400755) nie są osobnym krokiem: zabicie Moore'a "
                       "kończy quest bez nich.", npc_block=4380),

    Q("thiollier", "Thiollier i św. Trina", "Thiollier", "Gravesite Plain", "Thiollier's Hidden Needle", [
        S("Spotkaj Thiolliera w lokacji {p:Gravesite Plain}.", NPC(4460), cumulative=True, where="{p:Gravesite Plain}",
          next="Porozmawiaj z Thiollierem przy Pagodzie Gaola."),
        S("Odbierz przedmiot {i:St. Trina's Smile}.", L("St. Trina's Smile"), where="{p:Scadu Altus}",
          next="Rozmawiaj z Thiollierem w lokacji {p:Shadow Keep, Church District}."),
        S("Spotkaj św. Trinę we śnie ({i:St. Trina's Blossom}).", L("St. Trina's Blossom"),
          where="{p:Stone Coffin Fissure}", next="Zaśnij przy kwiatach św. Triny (np. w lokacji {p:Stone Coffin Fissure})."),
        S("Zakończenie w lokacji {p:Enir-Ilim} ({i:Thiollier's Hidden Needle}).", L("Thiollier's Hidden Needle"),
          where="{p:Enir-Ilim}", next="Spotkaj Thiolliera w Enir-Ilim."),
    ], dlc=True, npc_block=4460),

    Q("ymir", "Hrabia Ymir", "Count Ymir, High Priest", "Scadu Altus", "Hole-Laden Necklace", [
        S("Przyłącz się do Ymira ({i:Hole-Laden Necklace} i {i:Ruins Map}).", L("Hole-Laden Necklace"),
          where="{p:Cathedral of Manus Metyr}", next="Porozmawiaj z Ymirem w lokacji {p:Cathedral of Manus Metyr}."),
        S("Zabij pierwszy cel, nagroda: {i:Ruins Map (2nd)}.", L("Ruins Map (2nd)"), where="{p:Scadu Altus}",
          next="Wykonaj zlecenie Ymira (pierwsza mapa ruin)."),
        S("Zabij drugi cel, nagroda: {i:Ruins Map (3rd)}.", L("Ruins Map (3rd)"), where="{p:Scadu Altus}",
          next="Wykonaj kolejne zlecenie Ymira."),
        S("Pokonaj Metyr, Matkę Palców.", B("Metyr, Mother of Fingers"), where="{p:Cathedral of Manus Metyr}",
          next="Zejdź pod katedrę i pokonaj Metyr."),
        S("Zakończenie: walka z Ymirem ({i:Ymir's Bell Bearing}).", L("Ymir's Bell Bearing"),
          B("Count Ymir, Mother of Fingers"), where="{p:Cathedral of Manus Metyr}",
          next="Po Metyr wróć do Ymira."),
    ], dlc=True, npc_block=4500),

    Q("dane", "Dane, Suchy Liść", "Dryleaf Dane", "Scadu Altus", "Dane's Footwork", [
        S("Spotkaj Dane'a ({i:Dane's Hat}).", L("Dane's Hat"), where="{p:Scadu Altus}",
          next="Znajdź mnicha w lokacji {p:Moorth Ruins}."),
        S("Zakończenie: {i:Dane's Footwork}.", L("Dane's Footwork"), where="{p:Scadu Altus}",
          next="Spotkaj Dane'a ponownie (Enir-Ilim / Moorth)."),
    ], dlc=True, npc_block=4560),

    Q("igon", "Igon", "Igon", "Jagged Peak", "Igon's Furled Finger", [
        S("Spotkaj Igona przy lokacji {p:Grand Altar of Dragon Communion} ({i:Igon's Furled Finger}).",
          L("Igon's Furled Finger"), where="{p:Foot of the Jagged Peak}",
          next="Porozmawiaj z Igonem u podnóża Wyszczerbionego Szczytu."),
        S("Pokonaj Bayle'a (Igon pomaga).", B("Bayle, the Dread"), where="{p:Jagged Peak}",
          next="Wezwij Igona na Bayle'a na szczycie."),
        S("Zakończenie: {i:Igon's Greatbow} i zbroja Igona.", L("Igon's Greatbow", "Igon's Helm"),
          where="{p:Jagged Peak}", next="Po Bayle'u odbierz ekwipunek Igona."),
    ], dlc=True, locks=[LOCK("Bayle, the Dread", "s1", "Porozmawiaj z Igonem przed walką z Bayle'em. "
                                                         "Po jego śmierci wątek Igona się kończy.")],
        npc_block=4260),

    Q("jolan", "Jolán i Anna, szermierki nocy", "Swordhand of Night Jolán", "Scadu Altus",
      "Swordhand of Night Jolán", [
          S("Spotkaj Jolán ({i:Swordhand of Night Jolán}).", L("Swordhand of Night Jolán"),
            where="{p:Cerulean Coast}", next="Szukaj Jolán w okolicach lokacji {p:Cerulean Coast}."),
          S("Zakończenie: {i:Claws of Night} / {i:Sword of Night}.", L("Claws of Night", "Sword of Night"),
            where="{p:Scadu Altus}", next="Spotkaj Annę i zakończ wątek."),
      ], dlc=True, npc_block=4320),

    Q("queelign", "Rycerz ognia Queelign", "Fire Knight Queelign", "Scadu Altus", "Crusade Insignia", [
        S("Pokonaj Queeligna podczas najazdu ({i:Crusade Insignia}).", L("Crusade Insignia"), where="{p:Scadu Altus}",
          next="Queelign najedzie Cię w lokacji {p:Scadu Altus}."),
        S("Zakończenie: {i:Ash of War: Flame Skewer} / {i:Fire Knight Queelign}.",
          L("Ash of War: Flame Skewer", "Fire Knight Queelign", "Queelign's Greatsword"),
          where="{p:Scadu Altus}", next="Odszukaj Queeligna ponownie."),
    ], dlc=True, npc_block=4340),

    Q("florissax", "Florissax, starożytna smoczyca", "Ancient Dragon Florissax", "Jagged Peak", "Priestess Heart", [
        S("Porozmawiaj z kapłanką przy Wielkim Ołtarzu ({i:Dragonbolt of Florissax}).",
          L("Dragonbolt of Florissax"), NPC(4300), cumulative=True, where="{p:Grand Altar of Dragon Communion}",
          next="Porozmawiaj z kapłanką smoczej komunii przy lokacji {p:Grand Altar of Dragon Communion}."),
        S("Zakończenie: {i:Priestess Heart} / {i:Ancient Dragon Florissax}.",
          L("Priestess Heart", "Ancient Dragon Florissax"), where="{p:Jagged Peak}",
          next="Wróć do kapłanki po pokonaniu Bayle'a."),
    ], dlc=True, npc_block=4300),
]


# ---------------------------------------------------------------------------- budowanie
def fill(text, names, missing):
    if not text:
        return text

    def rep(m):
        kind, key = m.group(1), m.group(2)
        v = names[kind].get(key)
        if v is None:
            missing.add(f"{kind}:{key}")
            return key
        return v
    return re.sub(r"\{([ipn]):([^}]+)\}", rep, text)


# Questy zagnieżdżone: wątek poboczny → quest nadrzędny (na stronie zwijane drzewko)
QUEST_PARENT = {
    "blaidd": "ranni", "iji": "ranni", "seluvis": "ranni",
    "rya": "tanith", "bernahl": "tanith",
    "gowry": "millicent",
    "d": "fia",
    "ansbach": "leda", "freyja": "leda", "hornsent": "leda", "moore": "leda", "thiollier": "leda",
    "hornsent-grandam": "hornsent",
}


def build():
    names, lots = load_game()
    bosses = load_tga_bosses()
    labels = load_tga_npc_labels()
    blocks = load_bst_blocks()
    items = json.load(open(os.path.join(ROOT, "assets", "data", "items.json"), encoding="utf-8"))
    icon_by_en = {}
    for it in items:
        icon_by_en.setdefault(it["name_en"], it["icon"])
    missing, errors = set(), []
    entries = []
    for q in QUESTS:
        steps = []
        qsrc = {"general-knowledge"}
        for n, st in enumerate(q["steps"], 1):
            flags, srcs = [], set()
            for spec in st["specs"]:
                if spec[0] in ("talk", "world"):
                    for nm in spec[1]:
                        fs = lots[spec[0]].get(nm)
                        if not fs:
                            errors.append(f"{q['id']} s{n}: brak lotu '{nm}' ({spec[0]})")
                            continue
                        flags += sorted(fs)
                    srcs.add("regulation")
                elif spec[0] == "boss":
                    for nm in spec[1]:
                        if nm not in bosses:
                            errors.append(f"{q['id']} s{n}: brak bossa '{nm}' w TGA")
                            continue
                        flags.append(bosses[nm])
                    srcs.add("tga-ct")
                else:
                    flags += list(spec[1])
                    srcs.add(spec[2])
            flags = list(dict.fromkeys(flags))
            for f in flags:
                if f // 1000 not in blocks:
                    errors.append(f"{q['id']} s{n}: flaga {f} spoza tabeli bloków (nieczytelna z save'a)")
            qsrc |= srcs
            labeled = [f"{f}={labels[f]}" for f in flags if f in labels]
            steps.append({"id": f"s{n}", "text": fill(st["text"], names, missing), "flags": flags,
                          "mode": st["mode"], "where": fill(st["where"], names, missing),
                          "next": fill(st["next"], names, missing) or None,
                          "sources": sorted(srcs), **({"tga_labels": labeled} if labeled else {})})
        for n, st in enumerate(q["steps"]):
            if st["cumulative"]:
                later = [f for s2 in steps[n + 1:] for f in s2["flags"]]
                steps[n]["flags"] = list(dict.fromkeys(steps[n]["flags"] + later))
                steps[n]["mode"] = "any"
                steps[n]["cumulative"] = True
        locks = []
        for lk in q["locks"]:
            locks.append({"boss_en": lk["boss_en"], "boss_flag": bosses.get(lk["boss_en"]), "step": lk["step"], "warning": lk["warning"]})
        icon = icon_by_en.get(q["icon_en"])
        if icon is None:
            errors.append(f"{q['id']}: brak ikony dla '{q['icon_en']}'")
        npc_pl = names["n"].get(q["npc_en"])
        if npc_pl is None:
            missing.add(f"n:{q['npc_en']}")
        entries.append({
            "id": q["id"], "name": q["name"], "npc": npc_pl or q["npc_en"], "npc_en": q["npc_en"], "dlc": q["dlc"],
            "region": names["p"].get(q["region_en"], q["region_en"]), "icon": icon, "steps": steps,
            "locks": locks, "missable": q["missable"], "sources": sorted(qsrc), "confidence": "low",
            "npc_block": q["npc_block"], "notes": fill(q["notes"], names, missing),
            "parent": QUEST_PARENT.get(q["id"]),
        })
    return entries, missing, errors


# ---------------------------------------------------------------------------- weryfikacja na save'ach
def api(path):
    with urllib.request.urlopen(BACKEND + path, timeout=30) as r:
        return json.load(r)


def verify(entries):
    chars = []
    for f in api("/api/characters")["files"]:
        if f["file"] == VERIFY_FILE:
            chars = [(c["slot"], c["name"], c["level"]) for c in f["characters"]]
    all_flags = sorted({fl for e in entries for s in e["steps"] for fl in s["flags"]} |
                       {lk["boss_flag"] for e in entries for lk in e["locks"] if lk.get("boss_flag")})
    state = {}
    for slot, name, _ in chars:
        st = {}
        for i in range(0, len(all_flags), 900):
            chunk = all_flags[i:i + 900]
            res = api(f"/api/flags?ids={','.join(map(str, chunk))}&file={VERIFY_FILE}&slot={slot}")["flags"]
            st.update({int(k): v for k, v in res.items()})
        state[slot] = st
    newest = min(chars, key=lambda c: c[2])      # najniższy poziom = nowa postać
    report = []
    for e in entries:
        per_char, violations, nulls = {}, 0, 0
        for slot, name, lvl in chars:
            st = state[slot]
            done = []
            for s in e["steps"]:
                vals = [st.get(f) for f in s["flags"]]
                nulls += sum(v is None for v in vals)
                ok = all(vals) if s["mode"] == "all" else any(vals)
                done.append(bool(ok))
            first_gap = next((i for i, d in enumerate(done) if not d), len(done))
            if any(done[first_gap:]):
                violations += 1
            per_char[name] = "".join("x" if d else "." for d in done)
        new_done = per_char[newest[1]].count("x")
        max_done = max(v.count("x") for v in per_char.values())
        uses_derived = any("npc-block" in s["sources"] for s in e["steps"])
        if nulls:
            conf = "low"
        elif violations == 0 and new_done == 0 and max_done >= 2 and not uses_derived:
            conf = "verified"
        elif violations == 0 and new_done == 0 and max_done >= 1:
            conf = "high"
        elif violations <= 1 and new_done == 0:
            conf = "medium"
        else:
            conf = "low"
        e["confidence"] = conf
        if "save-verified" not in e["sources"] and violations == 0 and max_done >= 1:
            e["sources"].append("save-verified")
        e["verification"] = {"chars": per_char, "violations": violations, "unknown_flags": nulls}
        report.append((e, per_char, violations))
    return chars, report


def main():
    entries, missing, errors = build()
    for m in sorted(missing):
        print("brak nazwy PL:", m)
    for err in errors:
        print("BŁĄD:", err)
    chars = None
    if "--verify" in sys.argv:
        chars, report = verify(entries)
        print("postacie:", ", ".join(f"{n} (slot {s}, poz. {lv})" for s, n, lv in chars))
        for e, per, viol in report:
            print(f"{e['id']:<18} {len(e['steps'])} kroków  {e['confidence']:<8} naruszeń={viol}  " +
                  " ".join(f"{n}:{v}" for n, v in per.items()))
    conf = {}
    for e in entries:
        conf[e["confidence"]] = conf.get(e["confidence"], 0) + 1
    meta = {
        "schema_version": 1, "kind": "quests", "generated_by": "tools/extract/build_quests.py",
        "sources": SOURCES,
        "confidence_levels": {
            "verified": "flagi z regulation.bin/TGA, kroki zaliczone w kolejności na wszystkich postaciach, "
                        "nowa postać bez kroków, co najmniej 2 kroki zaobserwowane",
            "high": "jak verified, ale część kroków to reguła bloku NPC albo zaobserwowano tylko 1 krok",
            "medium": "pojedyncze naruszenie kolejności lub brak obserwacji",
            "low": "sprzeczności albo flagi nieczytelne"},
        "coverage": {"quests": len(entries), "steps": sum(len(e["steps"]) for e in entries),
                     "dlc_quests": sum(e["dlc"] for e in entries), "confidence": conf,
                     "verified_on": [n for _, n, _ in chars] if chars else None},
    }
    import quest_spoilers                                   # wersje kroków bez spoilerów (losy postaci)
    quest_spoilers.apply(entries)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"_meta": meta, "entries": entries}, f, ensure_ascii=False, indent=1)
    print(f"zapisano {OUT}: {len(entries)} questów, {meta['coverage']['steps']} kroków, pewność {conf}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
