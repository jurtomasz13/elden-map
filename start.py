"""Uruchamia backend (save → API na 127.0.0.1:8765) i stronę (127.0.0.1:5180), potem otwiera przeglądarkę.

    python start.py                      # folder save'a wykryty automatycznie (Windows / Linux + Proton)
    python start.py --save-dir ŚCIEŻKA   # albo zmienna ER_SAVE_DIR
    python start.py --no-browser

Ctrl+C zatrzymuje oba serwery. Wszystko nasłuchuje tylko lokalnie.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
API_PORT = 8765


def port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def elden_map_running() -> bool:
    """Czy na porcie API odpowiada już backend Elden Map (np. w innym oknie terminala)?"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{API_PORT}/api/health", timeout=2) as r:
            return "save_dir" in json.loads(r.read().decode("utf-8"))
    except (OSError, ValueError):
        return False


def busy_hint(port: int) -> str:
    if os.name == "nt":
        return f"  netstat -ano | findstr :{port}      (ostatnia kolumna = PID, zamknij go w Menedżerze zadań)"
    return f"  ss -ltnp | grep :{port}      (pokaże proces)      albo      fuser -k {port}/tcp      (zamknie go)"


def main():
    ap = argparse.ArgumentParser(description="Elden Map — backend + strona")
    ap.add_argument("--save-dir", help="folder z ER0000.sl2 / ER0000.co2")
    ap.add_argument("--port", type=int, default=5180, help="port strony (domyślnie 5180)")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    url = f"http://127.0.0.1:{a.port}/mockup/"

    if not os.path.exists(os.path.join(ROOT, "assets", "data", "bosses_all.json")):
        print("Brak danych z gry — najpierw uruchom:  python prepare.py")
    if port_busy(API_PORT) or port_busy(a.port):
        if elden_map_running() and port_busy(a.port):
            print(f"\nElden Map już działa (w innym oknie terminala): {url}\n"
                  "Żeby uruchomić od nowa, zamknij tamto okno albo naciśnij w nim Ctrl+C.\n")
            if not a.no_browser:
                webbrowser.open(url)
            return 0
        for port in (API_PORT, a.port):
            if port_busy(port):
                print(f"\nPort {port} jest zajęty przez inny program (albo poprzednie uruchomienie jeszcze się zamyka).\n"
                      f"Sprawdź, co go używa:\n{busy_hint(port)}\n")
        return 1

    be = [sys.executable, "-X", "utf8", os.path.join(ROOT, "backend", "server.py")]
    if a.save_dir:
        be += ["--save-dir", a.save_dir]
    procs = []
    try:
        procs.append(subprocess.Popen(be, cwd=ROOT))
        procs.append(subprocess.Popen([sys.executable, os.path.join(ROOT, "tools", "static_server.py"), str(a.port)],
                                      cwd=ROOT))
        for _ in range(60):                               # poczekaj, aż backend i strona odpowiedzą
            if any(p.poll() is not None for p in procs):
                break
            if port_busy(API_PORT) and port_busy(a.port):
                break
            time.sleep(0.25)
        if any(p.poll() is not None for p in procs):
            print("\nSerwer nie wystartował — szczegóły wyżej.")
            return 1
        print(f"\nElden Map: {url}   (API: http://127.0.0.1:{API_PORT}/api/health)   — Ctrl+C kończy\n")
        if not a.no_browser:
            webbrowser.open(url)
        while all(p.poll() is None for p in procs):
            time.sleep(0.5)
        return 1                                          # któryś serwer padł
    except KeyboardInterrupt:
        return 0
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
            except KeyboardInterrupt:
                p.kill()


if __name__ == "__main__":
    sys.exit(main())
