"""Punkt startowy paczek (instalator Windows, archiwum Linux): przy pierwszym uruchomieniu przygotowuje dane
z gry (prepare.py), potem uruchamia backend + stronę (start.py). Python i Node są w katalogu runtime/ obok app/.
"""
import os
import subprocess
import sys

APP = os.path.dirname(os.path.abspath(__file__))
RUNTIME = os.path.join(os.path.dirname(APP), "runtime")


def banner(text):
    print("\n" + "=" * 70 + "\n  " + text + "\n" + "=" * 70, flush=True)


def pause_on_error(msg):
    print("\n" + msg, flush=True)
    if sys.stdin and sys.stdin.isatty():
        try:
            input("\nNaciśnij Enter, aby zamknąć…")
        except EOFError:
            pass
    sys.exit(1)


def main():
    node = os.path.join(RUNTIME, "node") if os.name == "nt" else os.path.join(RUNTIME, "node", "bin")
    if os.path.isdir(node):                               # Node z paczki (kafle mapy, ikony, portrety 3D)
        os.environ["PATH"] = node + os.pathsep + os.environ.get("PATH", "")
    os.environ.setdefault("PYTHONUTF8", "1")
    py = [sys.executable, "-X", "utf8"]
    ready = os.path.exists(os.path.join(APP, "assets", "data", "bosses_all.json")) and \
        os.path.exists(os.path.join(APP, "backend", "data", "bosses.json"))
    if not ready or "--prepare" in sys.argv:
        banner("Elden Map, pierwsze uruchomienie: przygotowuję dane z twojej gry (kilkanaście minut)")
        print("Gra musi być zainstalowana (Steam). Pliki gry są tylko czytane.", flush=True)
        if subprocess.run(py + [os.path.join(APP, "prepare.py")], cwd=APP).returncode:
            pause_on_error("Przygotowanie danych nie powiodło się, szczegóły wyżej. "
                           "Jeśli gra jest w nietypowym miejscu, ustaw zmienną ER_GAME_DIR.")
    banner("Elden Map działa: http://127.0.0.1:5180/mockup/   (zamknij to okno, aby zakończyć)")
    args = [a for a in sys.argv[1:] if a != "--prepare"]
    r = subprocess.run(py + [os.path.join(APP, "start.py")] + args, cwd=APP)
    if r.returncode not in (0, -2, 130, 3221225786):     # 3221225786 = zamknięcie okna konsoli (Ctrl+C) na Windows
        pause_on_error("Serwer zakończył się błędem, szczegóły wyżej.")


if __name__ == "__main__":
    main()
