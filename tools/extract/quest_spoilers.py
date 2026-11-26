"""Wersje kroków questów bez spoilerów (losy postaci, zwroty akcji, nagrody zdradzające śmierć).

Frontend w trybie „bez spoilerów” pokazuje `text_safe` / `next_safe` dla kroków, których gracz jeszcze nie zaliczył;
po zaliczeniu kroku pełny tekst. Ostrzeżenia (locks) mają `warning_safe`.
Używane przez build_quests.py (przy generowaniu) i przez apply() na gotowym quests.json.
"""
import json
import os
import sys

# (quest, krok) -> {"text": …, "next": …}
SAFE = {
    ("iji", "s2"): {"text": "Po zakończeniu questa Ranni wróć do Ijiego. Jego wątek ma dalszy ciąg."},
    ("seluvis", "s2"): {"text": "Wątek Seluvisa ma swój finał w jego wieży. Wróć tam, gdy quest Ranni posunie się naprzód."},
    ("blaidd", "s3"): {"text": "Po zakończeniu questa Ranni odwiedź Blaidda w lokacji Wieża Ranni."},
    ("gowry", "s3"): {"text": "Po spotkaniu z Millicentą w Elphael wróć do chaty Gowry'ego. Jego historia ma tam finał.",
                      "next": "Po spotkaniu z Millicentą w Elphael wróć do chaty Gowry'ego."},
    ("millicent", "p8"): {"text": "W lokacji Elphael, Podpora Świętego Drzewa podejmij decyzję w sprawie Millicenty. Od niej zależy nagroda."},
    ("d", "s2"): {"text": "Historia D znajdzie swój finał w Twierdzy Okrągłego Stołu.",
                  "next": "Postępy w queście Fii wpływają na losy D, więc zaglądaj do Twierdzy Okrągłego Stołu."},
    ("rogier", "s2"): {"text": "Po śledztwie (przedmiot Ślad czarnego noża) wróć do Rogiera w Twierdzy Okrągłego Stołu. Coś na ciebie czeka."},
    ("rogier", "s3"): {"text": "Wróć do miejsca, w którym przesiadywał Rogier. Coś tam na ciebie czeka.",
                       "next": "Wróć do miejsca, w którym przesiadywał Rogier w Twierdzy Okrągłego Stołu."},
    ("sellen", "s5"): {"text": "Rozstrzygnij spór Sellen i Jerrena w lokacji Akademia Rai Lucarii. Wybór strony decyduje o nagrodzie."},
    ("dung-eater", "s4"): {"text": "Zakończenie wątku Łajnożercy: odwiedź go ponownie.",
                           "next": "Po oddaniu runy odwiedź Łajnożercę w jego celi."},
    ("jar-bairn", "s2"): {"text": "Gdy Słojątko dorośnie (po zakończeniu wątku Diallosa), odbierz przedmiot Towarzyszące naczynie."},
    ("goldmask", "p99"): {"text": "Zakończenie wątku Złotej Maski i Corhyna.",
                         "next": "Po zakończeniu ich wątku wróć do miejsca, w którym ich zostawiłeś."},
    ("leda", "s3"): {"text": "Zakończenie wątku Ledy rozegra się w lokacji Enir-Ilim."},
    ("ansbach", "p16"): {"text": "Zakończenie wątku Ansbacha w lokacji Enir-Ilim."},
    ("hornsent", "s4"): {"text": "Zakończenie wątku Rogatego przybysza w lokacji Enir-Ilim."},
    ("thiollier", "s4"): {"text": "Zakończenie wątku Thiolliera w lokacji Enir-Ilim."},
    ("moore", "s2"): {"text": "Zakończenie wątku Moore'a."},
    ("ymir", "s5"): {"text": "Zakończenie wątku Hrabiego Ymira."},
    ("dane", "s2"): {"text": "Zakończenie wątku Dane'a."},
    ("igon", "s3"): {"text": "Zakończenie wątku Igona."},
    ("ymir", "p11"): {"text": "Zakończenie wątku Jolán."},
    ("yura", "s3"): {"text": "Zakończenie wątku Yury."},
    ("rya", "s2"): {"text": "Spotkaj Ryę w lokacji Wulkaniczny Dwór i doprowadź jej historię do końca."},
    ("boggart", "s2"): {"text": "Zakończenie wątku Boggarta."},
    ("thops", "s2"): {"text": "Zakończenie wątku Thopsa w Akademii Rai Lucarii."},
    ("queelign", "s2"): {"text": "Zakończenie wątku Queeligna."},
    ("florissax", "s2"): {"text": "Zakończenie wątku Florissax."},
}
# ostrzeżenia: quest -> zamiennik (gdy zdradza los postaci)
SAFE_LOCKS = {
    "igon": "Porozmawiaj z Igonem przed walką z Bayle'em, inaczej jego wątek się zamknie.",
}


def apply(entries):
    n = 0
    for e in entries:
        for st in e.get("steps", []):
            s = SAFE.get((e["id"], st.get("id")))
            if s:
                if "text" in s:
                    st["text_safe"] = s["text"]
                if "next" in s:
                    st["next_safe"] = s["next"]
                n += 1
        if e["id"] in SAFE_LOCKS:
            for lk in e.get("locks") or []:
                lk["warning_safe"] = SAFE_LOCKS[e["id"]]
    return n


if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(__file__))
    import archive as A  # noqa: E402
    path = os.path.join(A.ROOT, "assets", "data", "quests.json")
    if not os.path.exists(path):                     # questy powstają w build_quests.py (prepare.py robi to w kolejności)
        sys.exit(print("quest_spoilers: brak assets/data/quests.json, pomijam"))
    d = json.load(open(path, encoding="utf-8"))
    known = {(e["id"], s.get("id")) for e in d["entries"] for s in e.get("steps", [])}
    missing = [k for k in SAFE if k not in known]
    n = apply(d["entries"])
    json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"quest_spoilers: {n} kroków z wersją bez spoilerów" + (f"; nieznane klucze: {missing}" if missing else ""))
