"""Automatyczne portrety postaci: po zapisie gry, gdy zmienił się hełm albo wygląd (blok FACE), w tle uruchamiamy
tools/extract/render_character.py dla tego slotu i publikujemy zdarzenie SSE 'portrait'.

Render czyta pliki gry i save (tylko odczyt) i zapisuje PNG do assets/renders/ (lokalnie). Podpis ostatniego renderu
(id hełmu + skrót bloku FACE) trzymamy w backend/var/portraits.json, żeby nie renderować w kółko.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import queue
import subprocess
import sys
import threading

log = logging.getLogger("erbackend.portraits")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(ROOT, "tools", "extract", "render_character.py")
RENDERS = os.path.join(ROOT, "assets", "renders")
STATE = os.path.join(ROOT, "backend", "var", "portraits.json")


class Portraits:
    def __init__(self, service, python: str = sys.executable):
        self.service = service
        self.python = python
        self.enabled = os.path.exists(SCRIPT)
        try:
            self.done: dict[str, str] = json.load(open(STATE, encoding="utf-8"))
        except (OSError, ValueError):
            self.done = {}
        self.q: queue.Queue = queue.Queue()
        self.pending: set[str] = set()
        self.lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, name="portraits", daemon=True)
        self._thread.start()

    @staticmethod
    def signature(sf, slot: int) -> tuple[str, int | None]:
        s = sf.slot(slot)
        head = ((s.equipment or {}).get("head") or {}).get("id")
        e = sf.entries[slot]
        raw = sf.data[e.offset:e.offset + e.size]
        k = raw.find(b"FACE")
        face = hashlib.md5(raw[k:k + 0x120]).hexdigest()[:12] if k >= 0 else "-"
        return f"{head}:{face}", head

    def check(self, kind: str, slot: int, sf) -> None:
        """Wołane przez serwis po zmianie slotu (i przy starcie dla wszystkich postaci)."""
        if not self.enabled:
            return
        try:
            sig, head = self.signature(sf, slot)
        except Exception as e:                      # zepsuty slot nie może zatrzymać watchera
            log.debug("portret %s:%s — brak podpisu: %s", kind, slot, e)
            return
        key = f"{kind}:{slot}"
        png = os.path.join(RENDERS, f"char_{kind}_{slot}.png")
        if self.done.get(key) == sig and os.path.exists(png):
            return
        with self.lock:
            if key in self.pending:
                return
            self.pending.add(key)
        self.q.put((kind, slot, sig, head))

    def scan_all(self) -> None:
        for kind, sf in list(self.service.saves.items()):
            for i in sf.active_slots:
                self.check(kind, i, sf)

    def _run(self):
        while True:
            kind, slot, sig, head = self.q.get()
            key = f"{kind}:{slot}"
            try:
                r = subprocess.run([self.python, "-I", "-X", "utf8", SCRIPT, kind, str(slot)], cwd=ROOT,
                                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
                if r.returncode == 0:
                    self.done[key] = sig
                    os.makedirs(os.path.dirname(STATE), exist_ok=True)
                    with open(STATE, "w", encoding="utf-8") as f:
                        json.dump(self.done, f, indent=1)
                    log.info("portret %s odświeżony (hełm %s)", key, head)
                    self.service.publish("portrait", {"file": kind, "slot": slot, "head_id": head, "version": sig})
                else:
                    log.warning("portret %s: render nie powiódł się: %s", key, (r.stderr or r.stdout)[-400:])
            except Exception as e:
                log.warning("portret %s: %s", key, e)
            finally:
                with self.lock:
                    self.pending.discard(key)
