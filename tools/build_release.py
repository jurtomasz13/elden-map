"""Buduje paczki do pobrania (bez kompilacji): instalator Windows (Inno Setup) i archiwum Linux (.tar.gz).

    python tools/build_release.py 0.1.0            # oba
    python tools/build_release.py 0.1.0 --windows  # tylko instalator
    python tools/build_release.py 0.1.0 --linux    # tylko archiwum

Składniki pobierane z oficjalnych źródeł do build/dl (sumy SHA-256 sprawdzane):
- Windows: Python embeddable (python.org) + Node.js win-x64 (nodejs.org)
- Linux: Python z python-build-standalone (astral-sh) + Node.js linux-x64 + Python embeddable dla Wine (Oodle z gry)
Do paczek trafiają tylko pliki śledzone przez git, bez assets/, save'ów i danych z gry.
"""
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BUILD, DL, DIST = (os.path.join(ROOT, "build", d) for d in ("", "dl", "dist"))
DEPS = {
    "winpy": ("https://www.python.org/ftp/python/3.14.3/python-3.14.3-embed-amd64.zip",
              "ad4961a479dedbeb7c7d113253f8db1b1935586b73c27488712beec4f2c894e6"),
    "winnode": ("https://nodejs.org/dist/v24.14.1/node-v24.14.1-win-x64.zip",
                "6e50ce5498c0cebc20fd39ab3ff5df836ed2f8a31aa093cecad8497cff126d70"),
    "linpy": ("https://github.com/astral-sh/python-build-standalone/releases/download/20261026/"
              "cpython-3.14.10%2B20261026-x86_64-unknown-linux-gnu-install_only.tar.gz",
              "1b38024924eb7f4cf0cab45d7b871d1f1991354190fccd2625ac7529a43786e2"),
    "linnode": ("https://nodejs.org/dist/v24.14.1/node-v24.14.1-linux-x64.tar.xz",
                "84d38715d449447117d05c3e71acd78daa49d5b1bfa8aacf610303920c3322be"),
}
PTH = "python314.zip\n.\n..\\..\\app\n..\\..\\app\\tools\\extract\n..\\..\\app\\backend\n"


def dep(name):
    url, sha = DEPS[name]
    path = os.path.join(DL, url.rsplit("/", 1)[1].replace("%2B", "+"))
    if not os.path.exists(path):
        os.makedirs(DL, exist_ok=True)
        print("pobieram", url, flush=True)
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "elden-map-build"}), timeout=900) as r:
            open(path, "wb").write(r.read())
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if h != sha:
        sys.exit(f"Zła suma SHA-256 dla {path}: {h}")
    return path


def app_files():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout.decode()
    return [f for f in out.split("\0") if f and not f.startswith(".claude/")]


# ---------------- Windows ----------------
def build_windows(version):
    stage = os.path.join(BUILD, "windows", "EldenMap")
    shutil.rmtree(os.path.dirname(stage), ignore_errors=True)
    for f in app_files():
        dst = os.path.join(stage, "app", f)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(ROOT, f), dst)
    py = os.path.join(stage, "runtime", "python")
    zipfile.ZipFile(dep("winpy")).extractall(py)
    open(os.path.join(py, "python314._pth"), "w", newline="\r\n").write(PTH)   # ścieżki do modułów aplikacji
    with zipfile.ZipFile(dep("winnode")) as z:
        top = z.namelist()[0].split("/")[0]
        for m in z.namelist():
            rel = m[len(top) + 1:]
            if not rel or m.endswith("/"):
                continue
            if rel.startswith(("node_modules/", "npm", "npx", "corepack")):   # wystarczy sam node.exe
                continue
            dst = os.path.join(stage, "runtime", "node", rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, "wb").write(z.read(m))
    open(os.path.join(stage, "Elden Map.bat"), "w", newline="\r\n").write(
        '@echo off\r\ntitle Elden Map\r\n"%~dp0runtime\\python\\python.exe" -X utf8 "%~dp0app\\launcher.py" %*\r\n')
    iss = os.path.join(BUILD, "windows", "EldenMap.iss")
    open(iss, "w", encoding="utf-8-sig").write(ISS.format(version=version, src=stage, dist=DIST, root=ROOT))
    iscc = next((p for p in (os.path.expandvars(r"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"),
                             os.path.expandvars(r"%ProgramFiles%\Inno Setup 6\ISCC.exe"),
                             os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe")) if os.path.exists(p)), None)
    if not iscc:
        sys.exit("Brak Inno Setup 6 (ISCC.exe). Zainstaluj go poleceniem: winget install JRSoftware.InnoSetup")
    os.makedirs(DIST, exist_ok=True)
    subprocess.run([iscc, "/Q", iss], check=True)
    print("instalator:", os.path.join(DIST, f"EldenMap-Setup-{version}.exe"))


ISS = r'''; Instalator Elden Map — generowany przez tools/build_release.py
[Setup]
AppId=EldenMap-jurtomasz13
AppName=Elden Map
AppVersion={version}
AppPublisher=jurtomasz13
AppPublisherURL=https://github.com/jurtomasz13/elden-map
DefaultDirName={{localappdata}}\Programs\Elden Map
DefaultGroupName=Elden Map
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir={dist}
OutputBaseFilename=EldenMap-Setup-{version}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=Elden Map
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "polish"; MessagesFile: "compiler:Languages\Polish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"

[Files]
Source: "{src}\*"; DestDir: "{{app}}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{{group}}\Elden Map"; Filename: "{{app}}\runtime\python\python.exe"; Parameters: "-X utf8 ""{{app}}\app\launcher.py"""; WorkingDir: "{{app}}\app"
Name: "{{group}}\Elden Map — przygotuj dane od nowa"; Filename: "{{app}}\runtime\python\python.exe"; Parameters: "-X utf8 ""{{app}}\app\launcher.py"" --prepare"; WorkingDir: "{{app}}\app"
Name: "{{group}}\Odinstaluj Elden Map"; Filename: "{{uninstallexe}}"
Name: "{{userdesktop}}\Elden Map"; Filename: "{{app}}\runtime\python\python.exe"; Parameters: "-X utf8 ""{{app}}\app\launcher.py"""; WorkingDir: "{{app}}\app"; Tasks: desktopicon

[Run]
Filename: "{{app}}\runtime\python\python.exe"; Parameters: "-X utf8 ""{{app}}\app\launcher.py"""; WorkingDir: "{{app}}\app"; Description: "Uruchom Elden Map (pierwsze uruchomienie przygotuje dane z gry)"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; dane wyciągnięte z gry i historia — usuwane razem z programem
Type: filesandordirs; Name: "{{app}}\app\assets"
Type: filesandordirs; Name: "{{app}}\app\backend\var"
Type: filesandordirs; Name: "{{app}}\app\backend\data"
Type: filesandordirs; Name: "{{app}}\app\docs\data"
'''


# ---------------- Linux ----------------
def build_linux(version):
    name = f"elden-map-{version}-linux-x64"
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, name + ".tar.gz")

    def add_bytes(tf, path, data, mode=0o644):
        ti = tarfile.TarInfo(path)
        ti.size, ti.mode, ti.mtime = len(data), mode, 1764000000
        tf.addfile(ti, io.BytesIO(data))

    def copy_tar(tf, src, mode, prefix, strip):
        with tarfile.open(src, mode) as s:
            for m in s.getmembers():
                parts = m.name.split("/")[strip:]
                if not parts or not parts[0]:
                    continue
                m2 = m
                m2.name = prefix + "/".join(parts)
                if m.issym() or m.islnk():
                    tf.addfile(m2)
                elif m.isdir():
                    tf.addfile(m2)
                else:
                    tf.addfile(m2, s.extractfile(m))

    launcher = ('#!/bin/sh\n# Elden Map — uruchamia aplikację z dołączonym Pythonem\n'
                'HERE="$(cd "$(dirname "$0")" && pwd)"\n'
                'exec "$HERE/runtime/python/bin/python3" -X utf8 "$HERE/app/launcher.py" "$@"\n').encode()
    with tarfile.open(out, "w:gz", compresslevel=9) as tf:
        add_bytes(tf, f"{name}/elden-map", launcher, 0o755)
        for f in app_files():                                                    # z gita: końce linii LF
            data = subprocess.run(["git", "show", f"HEAD:{f}"], cwd=ROOT, capture_output=True, check=True).stdout
            add_bytes(tf, f"{name}/app/{f}", data, 0o755 if f.endswith(".sh") else 0o644)
        copy_tar(tf, dep("linpy"), "r:gz", f"{name}/runtime/python/", 1)          # python/… → runtime/python/…
        with tarfile.open(dep("linnode"), "r:xz") as s:                          # tylko bin/node
            m = next(x for x in s.getmembers() if x.name.endswith("/bin/node"))
            data = s.extractfile(m).read()
        add_bytes(tf, f"{name}/runtime/node/bin/node", data, 0o755)
        with zipfile.ZipFile(dep("winpy")) as z:                                  # Python dla Wine (Oodle z gry)
            for n in z.namelist():
                add_bytes(tf, f"{name}/runtime/winpython/{n}", z.read(n))
    print("archiwum Linux:", out, f"({os.path.getsize(out) // 2**20} MB)")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    version = args[0]
    both = not ({"--windows", "--linux"} & set(sys.argv))
    if both or "--windows" in sys.argv:
        build_windows(version)
    if both or "--linux" in sys.argv:
        build_linux(version)


if __name__ == "__main__":
    main()
