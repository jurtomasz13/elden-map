"""Pełne listy kroków questów: kroki z QuestPath (MIT, przetłumaczone na polski w `quest_steps_pl.json`) scalone
z naszymi krokami z flagami (`assets/data/quests.json` z build_quests.py).

- Krok QuestPath, który opisuje to samo co nasz krok (`match`), dostaje jego flagi i identyfikator (ostrzeżenia
  `locks` dalej wskazują właściwy krok); dodatkowe flagi zaliczenia z `flags`.
- `later` = flagi wszystkich późniejszych kroków (bez zakończeń alternatywnych `alt`): krok bez własnej flagi zalicza
  się, gdy zaliczony jest dowolny dalszy etap (skoro jest dalszy etap, ten był wcześniej).
- Nasze kroki z flagami, których nie dopasowano, zostają w swoim pierwotnym miejscu (sprawdzalny postęp).
- `here` = flagi położenia NPC z `quest_npc_states.json`: postać czeka przy tym kroku.
- Questy z `merge` (np. Ymir + Jolán) łączone w jeden; ich wątki podrzędne wskazują na wynikowy quest.

Źródło tekstów: QuestPath by imCioco (https://github.com/imCioco/ER_QuestPath-Lang, licencja MIT), tłumaczenie
na polski. Nazwy własne w znacznikach {p:…} {i:…} {n:…} zamieniane na oficjalne polskie nazwy z plików gry.

    python tools/extract/quest_steps.py      # po build_quests.py, przed quest_spoilers.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import build_quests as B  # noqa: E402

ROOT = B.ROOT
SRC = os.path.join(os.path.dirname(__file__), "quest_steps_pl.json")
OUT = os.path.join(ROOT, "assets", "data", "quests.json")
NEW = {"dragon-priestess": {"name": "Kapłanka Smoczej Komunii", "dlc": True}}
_BOSSES = os.path.join(ROOT, "assets", "data", "bosses_all.json")
BOSS_FLAGS = ({b["flag"] for b in json.load(open(_BOSSES, encoding="utf-8"))} |
              {f for b in json.load(open(_BOSSES, encoding="utf-8")) for f in b.get("alt_flags") or []}) if os.path.exists(_BOSSES) else set()
TALK_SRC = os.path.join(os.path.dirname(__file__), "quest_talk_flags.json")
TALK = json.load(open(TALK_SRC, encoding="utf-8")) if os.path.exists(TALK_SRC) else {}
STATES_SRC = os.path.join(os.path.dirname(__file__), "quest_npc_states.json")
STATES = json.load(open(STATES_SRC, encoding="utf-8")) if os.path.exists(STATES_SRC) else {}


def main():
    if not os.path.exists(OUT):
        print("quest_steps: brak assets/data/quests.json, pomijam")
        return
    data = json.load(open(OUT, encoding="utf-8"))
    ours = {q["id"]: q for q in data["entries"]}
    tr = json.load(open(SRC, encoding="utf-8"))
    names, _ = B.load_game()
    missing = set()
    fill = lambda t: B.fill(t, names, missing) if t else t  # noqa: E731
    removed, out = {}, []
    done_ids = set()
    for t in tr:
        base = ours.get(t["id"])
        merged = [ours[m] for m in t.get("merge", []) if m in ours]
        if base is None:
            meta = NEW.get(t["id"], {})
            base = {"id": t["id"], "name": meta.get("name") or t["name"], "npc": fill(t.get("npc")) or t["name"],
                    "dlc": meta.get("dlc", False), "icon": None, "parent": None, "locks": [], "missable": False,
                    "sources": [], "confidence": "low"}
        q = dict(base)
        q["npc"] = q.get("npc") or fill(t.get("npc"))
        by_step = {f"{o['id']}:{s['id']}": s for o in merged for s in o["steps"]}
        used, steps = set(), []
        for s in t["steps"]:
            mt = [by_step[m] for m in s.get("match") or [] if m in by_step]
            used |= {m for m in s.get("match") or [] if m in by_step}
            own = list(dict.fromkeys([f for m in mt for f in m.get("flags") or []] + list(s.get("flags") or [])))
            mode = "all" if len(mt) == 1 and mt[0].get("mode") == "all" and not s.get("flags") else "any"
            sid = mt[0]["id"] if len(mt) == 1 and mt[0]["id"] not in {x["id"] for x in steps} else f"p{s['qp']}"
            nxt = fill(s.get("next")) or ""
            if s.get("warn"):
                nxt = f"{nxt} ⚠ {fill(s['warn'])}".strip()
            steps.append({"id": sid, "text": fill(s["text"]), "where": fill(s.get("where")) or "", "next": nxt,
                          "text_safe": fill(s.get("safe")) or None, "flags": own, "mode": mode, "alt": bool(s.get("alt")) or s["qp"] >= 90,
                          "end": s["qp"] >= 90,                          # QuestPath s98/s99 = zakończenie (np. śmierć NPC)
                          "sources": ["questpath"] + (["regulation"] if mt else [])})
        # niedopasowany krok z flagą: zostaje (sprawdzalny postęp) w swoim pierwotnym miejscu — zaraz po kroku, do którego
        # dopasowano nasz poprzedni krok (albo na początku) — ale nie zalicza kroków przed sobą
        where_of = {m: i for i, s in enumerate(t["steps"]) for m in s.get("match") or []}
        inserts = []
        for o in merged:
            for k, s in enumerate(o["steps"]):
                if f"{o['id']}:{s['id']}" not in used and s.get("flags"):
                    prev = [where_of[f"{o['id']}:{x['id']}"] for x in o["steps"][:k] if f"{o['id']}:{x['id']}" in where_of]
                    inserts.append((max(prev) + 1 if prev else 0,
                                    {**s, "id": f"{o['id']}-{s['id']}" if o is not base else s["id"], "alt": False, "extra": True}))
        for pos, st in sorted(inserts, key=lambda x: -x[0]):
            steps.insert(pos, st)
        # flagi ze skryptów rozmów NPC (talk ESD, talk_quests.py) przypisane do kroków — quest_talk_flags.json
        for s in steps:
            add = TALK.get(q["id"], {}).get(s["id"], {}).get("flags") or []
            if add and not (s.get("mode") == "all" and s.get("flags")):   # krok „wszystkie flagi” (np. komplet nagród) bez zmian
                s["flags"] = list(dict.fromkeys(list(s.get("flags") or []) + add))
                s["mode"] = "any"
                s["sources"] = list(dict.fromkeys((s.get("sources") or []) + ["talk-esd"]))
        # flaga pokonania bossa wspólnego dla całej gry (np. Radahn) nie mówi nic o postępie questu: gdy krok ma inne
        # flagi (rozmowa, przedmiot), boss jest zbędny; i nigdy nie zalicza wcześniejszych kroków
        for s in steps:
            if any(f not in BOSS_FLAGS for f in s["flags"]):
                s["flags"] = [f for f in s["flags"] if f not in BOSS_FLAGS]
        for i, s in enumerate(steps):
            if not s["alt"]:
                s["later"] = list(dict.fromkeys(f for x in steps[i + 1:] if not x["alt"] and not x.get("extra")
                                                for f in x["flags"] if f not in BOSS_FLAGS))
            # krok zaliczany tylko flagą bossa (np. Darriwil, którego można pokonać bez Blaidda) liczy się dopiero,
            # gdy zaliczony jest poprzedni krok questu
            if i > 0 and s["flags"] and all(f in BOSS_FLAGS for f in s["flags"]):
                s["gated"] = True
        for s in steps:                                # zakończenia/alternatywy bez podpowiedzi — ogólny tekst bez szczegółów
            if not s.get("text_safe") and s.get("alt"):
                s["text_safe"] = ("Jedno z możliwych zakończeń wątku. Szczegóły ukryte." if s.get("end")
                                  else "Alternatywna ścieżka wątku. Szczegóły ukryte.")
        q["steps"] = steps
        q["sources"] = list(dict.fromkeys((q.get("sources") or []) + ["questpath"]))
        out.append(q)
        done_ids.add(q["id"])
        for o in merged:
            if o["id"] != q["id"]:
                removed[o["id"]] = q["id"]
    for q in data["entries"]:
        if q["id"] not in done_ids and q["id"] not in removed:
            out.append(q)
    for q in out:
        if q.get("parent") in removed:
            q["parent"] = removed[q["parent"]]
    # Block flags +5..+18 say where the NPC waits now. The game moves them on its own (Irina's death puts Hyetta at the
    # cliffs), so they mean "this is the current step, earlier ones are behind you", not "step done".
    by_id = {q["id"]: q for q in out}
    for qid, steps_states in STATES.items():
        q = by_id.get(qid)
        if not q or not q.get("npc_block"):
            raise SystemExit(f"quest_npc_states.json: quest {qid} nie istnieje albo nie ma bloku flag NPC")
        step_of = {s["id"]: s for s in q["steps"]}
        for sid, offsets in steps_states.items():
            if sid not in step_of:
                raise SystemExit(f"quest_npc_states.json: quest {qid} nie ma kroku {sid}")
            step_of[sid]["here"] = [q["npc_block"] + o for o in offsets]
    order = {q["id"]: i for i, q in enumerate(data["entries"])}
    out.sort(key=lambda q: order.get(q["id"], 10 ** 6))
    data["entries"] = out
    data.setdefault("sources", {})["questpath"] = {
        "title": "QuestPath (imCioco) — opisy kroków questów, tłumaczenie na polski",
        "url": "https://github.com/imCioco/ER_QuestPath-Lang", "license": "MIT"}
    json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    steps = sum(len(q["steps"]) for q in out)
    flagged = sum(1 for q in out for s in q["steps"] if s.get("flags"))
    print(f"quest_steps: {len(out)} questów, {steps} kroków ({flagged} z własną flagą), połączone: {removed or '—'}")
    if missing:
        print("  bez polskiej nazwy:", ", ".join(sorted(missing))[:600])


if __name__ == "__main__":
    main()
