#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLMBridge — pont local pour l'outil « Endpoint LLM -> opencode / Hermes / dsh »

Un seul exécutable, aucune dépendance à l'exécution : il sert l'interface web
embarquée sur http://127.0.0.1:8766 et fait ce que le navigateur ne peut pas
faire depuis une page file:// :

  • lire et écrire les fichiers de configuration sur le disque ;
  • interroger l'API d'inférence (http://ip:port/v1) sans passer par CORS.

Routes
------
  GET  /                  l'interface (embarquée dans l'exécutable)
  GET  /api/health        sonde de vie (sans authentification)
  GET  /api/state         {ok, home, port, version, platform, python, harnesses[], verified}
  GET  /api/versions      versions détectées des trois harnais + version vérifiée
  POST /api/scan          {root, deep, paths{id:{config,env}}} -> harnais + contenu
  POST /api/http          {url, method, headers, body, timeout}
  POST /api/ping          {host, port, timeout}
  POST /api/read          {path}
  POST /api/write         {path, text}   sauvegarde .bak + écriture atomique
  POST /api/reveal        {path}

Sécurité : écoute uniquement sur 127.0.0.1, cookie de session SameSite=Strict,
contrôle d'origine, et écriture limitée aux fichiers que le dernier scan a
réellement détectés (chemin par défaut ou chemin personnalisé déclaré par
l'utilisateur) — jamais un chemin arbitraire. Sauvegarde horodatée systématique.

Compilation : build.ps1 / build.sh (PyInstaller --onefile), voir README.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error as urlerr
from urllib import request as urlreq
from urllib.parse import urlsplit

APP = "llm-bridge"
VERSION = "3.0.0"
DEFAULT_PORT = 8766
MAX_HTTP_BODY = 8 * 1024 * 1024      # réponse max d'une requête proxifiée
MAX_REQ_BODY = 16 * 1024 * 1024      # corps max accepté par l'API
VERSION_CACHE_TTL = 60.0

# Versions contre lesquelles cette release a été testée (docs/VERIFIED-VERSIONS.md).
VERIFIED = {
    "opencode": "2.1.4",
    "hermes": "0.22.5",
    "dsh": "0.2.1-rc.2",
}

HARNESS = [
    {
        "id": "opencode", "label": "opencode", "format": "jsonc", "flavor": "opencode",
        "color": "#f7c948", "note": "providers (pluriel) + package openai-compatible",
        "config": [".config/opencode/opencode.jsonc", ".config/opencode/opencode.json"],
        "env": None, "envPrefix": None,
        "bins": ["opencode"],
        "probe_paths": [
            r"%LOCALAPPDATA%\Programs\@opencodedesktop\resources\opencode-cli.exe",
            r"%APPDATA%\npm\opencode.cmd",
            r"%APPDATA%\npm\opencode2.cmd",
            "/usr/local/bin/opencode", "/usr/bin/opencode",
        ],
    },
    {
        "id": "hermes", "label": "Hermes Agent", "format": "yaml", "flavor": "hermes",
        "color": "#c792ea", "note": "custom_providers[] + bloc model: pour le fournisseur actif",
        "config": [".hermes/config.yaml", ".hermes/config.yml"],
        "env": ".hermes/.env", "envPrefix": "HERMES_CUSTOM_",
        "bins": ["hermes"],
        "probe_paths": [
            r"%USERPROFILE%\.hermes\hermes-agent\.hermes\bin\hermes.cmd",
            r"%LOCALAPPDATA%\hermes\hermes.cmd",
        ],
    },
    {
        "id": "dsh", "label": "dsh (DeepSeek Harness)", "format": "yaml", "flavor": "dsh",
        "color": "#7fdbca", "note": "providers sous l'entrée llm-pi-ai + agent-default-model",
        "config": [".dsh/cordis.patch.yml"],
        "env": ".dsh/.env", "envPrefix": "",
        "bins": ["dsh"],
        "probe_paths": [r"%APPDATA%\npm\dsh.cmd"],
    },
]

# noms de fichiers qu'on accepte d'écrire — jamais autre chose
ALLOWED_NAMES = {
    "config.yaml", "config.yml", "opencode.jsonc", "opencode.json",
    "cordis.patch.yml", ".env",
}

SKIP_DIRS = {
    "node_modules", "appdata", "windows", "venv", ".venv", ".git", ".cache", "cache",
    "dist", "build", "__pycache__", "library", "site-packages", ".vscode", ".npm",
    ".cargo", ".rustup", ".gradle", ".m2", "locallow", "onedrivetemp",
}


class Ctx:
    root = os.path.expanduser("~")
    token = secrets.token_hex(16)
    port = DEFAULT_PORT
    ui_path = ""
    cafile = ""
    insecure = False
    allowed: set[str] = set()      # realpaths autorisés en écriture (rempli par /api/scan)


_VCACHE: dict = {"at": 0.0, "data": None}


# --------------------------------------------------------------------------
# ressources (mode source ou exécutable PyInstaller --onefile)
# --------------------------------------------------------------------------
def resource_path(*parts: str) -> str:
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, *parts)


# --------------------------------------------------------------------------
# fichiers
# --------------------------------------------------------------------------
def read_text(path: str) -> str:
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:3] == b"\xef\xbb\xbf":
        return raw.decode("utf-8-sig", "replace")
    return raw.decode("utf-8", "replace")


def expand_path(value: str) -> str:
    """Développe ~, %VARS%, $VARS, retire les guillemets, rend un chemin absolu."""
    p = str(value or "").strip().strip('"').strip("'")
    if not p:
        return ""
    p = os.path.expandvars(os.path.expanduser(p))
    return os.path.abspath(p)


def find_config(root: str, relpaths: list[str], deep: bool = True, budget: float = 4.0):
    """Chemin direct d'abord ; sinon recherche récursive bornée par le basename."""
    for rel in relpaths:
        p = os.path.join(root, *rel.split("/"))
        if os.path.isfile(p):
            return p, False
    if not deep:
        return None, False
    wanted = {os.path.basename(r).lower() for r in relpaths}
    base_depth = os.path.abspath(root).rstrip(os.sep).count(os.sep)
    deadline = time.monotonic() + budget
    for dirpath, dirnames, filenames in os.walk(root):
        if time.monotonic() > deadline:
            break
        depth = os.path.abspath(dirpath).rstrip(os.sep).count(os.sep) - base_depth
        if depth >= 4:
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS]
        for fn in filenames:
            if fn.lower() in wanted:
                return os.path.join(dirpath, fn), True
    return None, False


def harness_item(h: dict, root: str, deep: bool, overrides: dict | None = None) -> dict:
    """Décrit un harnais : chemins par défaut sous `root`, ou chemins imposés par l'UI."""
    ov = (overrides or {}).get(h["id"]) or {}
    item = {
        "id": h["id"], "label": h["label"], "format": h["format"], "flavor": h["flavor"],
        "color": h["color"], "note": h["note"], "envPrefix": h["envPrefix"],
        "exists": False, "path": None, "name": None, "size": 0, "mtime": None,
        "text": None, "deep": False, "custom": False, "env": None,
        "defaults": {
            "config": os.path.join(root, *h["config"][0].split("/")),
            "env": os.path.join(root, *h["env"].split("/")) if h["env"] else None,
        },
    }

    custom_cfg = expand_path(ov.get("config", "")) if ov.get("config") else ""
    cfg = None
    if custom_cfg:
        item["custom"] = True
        item["path"] = custom_cfg
        if os.path.isfile(custom_cfg):
            cfg = custom_cfg
    else:
        cfg, was_deep = find_config(root, h["config"], deep)
        item["deep"] = was_deep
        if cfg:
            item["path"] = cfg

    if cfg:
        st = os.stat(cfg)
        item.update(exists=True, path=os.path.abspath(cfg), name=os.path.basename(cfg),
                    size=st.st_size, mtime=st.st_mtime, text=read_text(cfg))

    if h["env"]:
        custom_env = expand_path(ov.get("env", "")) if ov.get("env") else ""
        if custom_env:
            env_path = custom_env
        elif item["custom"] and item["path"]:
            # un fichier de config imposé implique un .env voisin
            env_path = os.path.join(os.path.dirname(item["path"]), ".env")
        else:
            env_path = item["defaults"]["env"]
        if os.path.isfile(env_path):
            st = os.stat(env_path)
            item["env"] = {"exists": True, "path": env_path, "size": st.st_size,
                           "mtime": st.st_mtime, "text": read_text(env_path)}
        else:
            item["env"] = {"exists": False, "path": env_path}
    return item


def scan(root: str, deep: bool, overrides: dict | None = None) -> dict:
    items = [harness_item(h, root, deep, overrides) for h in HARNESS]
    allowed = set()
    for it in items:
        if it["exists"] and it["path"]:
            allowed.add(os.path.realpath(it["path"]).lower())
        if it["env"] and it["env"].get("exists"):
            allowed.add(os.path.realpath(it["env"]["path"]).lower())
    Ctx.allowed = allowed
    return {"ok": True, "root": root, "items": items, "version": VERSION}


def guard(path: str) -> str:
    """N'autorise en écriture que les fichiers de configuration détectés au dernier scan."""
    if not path:
        raise PermissionError("chemin vide")
    real = os.path.realpath(path)
    if os.path.basename(real).lower() not in ALLOWED_NAMES:
        raise PermissionError(f"« {os.path.basename(real)} » n'est pas un fichier de configuration géré")
    if real.lower() not in Ctx.allowed:
        raise PermissionError(
            f"{real} n'a pas été détecté par le dernier scan — relancez la détection "
            f"(chemin par défaut, ou chemin personnalisé déclaré)")
    return real


def do_write(path: str, text: str) -> dict:
    real = guard(path)
    backup = None
    if os.path.exists(real):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = f"{real}.bak-{stamp}"
        shutil.copy2(real, backup)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(real), prefix=".llmbridge-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, real)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return {"ok": True, "path": real, "bytes": len(text.encode("utf-8")), "backup": backup}


# --------------------------------------------------------------------------
# versions installées
# --------------------------------------------------------------------------
def _run_version(exe: str) -> str | None:
    args = ["--version"]
    if sys.platform == "win32" and exe.lower().endswith((".cmd", ".bat")):
        cmd = ["cmd", "/c", exe, *args]
    else:
        cmd = [exe, *args]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=4,
                           encoding="utf-8", errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        out = ((p.stdout or "") + "\n" + (p.stderr or "")).strip()
        for line in out.splitlines():
            line = line.strip()
            if line:
                return line[:120]
    except Exception:  # noqa: BLE001 — binaire absent, GUI, timeout…
        return None
    return None


def detect_version(h: dict) -> dict:
    for name in h.get("bins", []):
        exe = shutil.which(name)
        if exe:
            out = _run_version(exe)
            if out:
                return {"raw": out, "exe": exe, "source": "PATH",
                        "verified": VERIFIED.get(h["id"], "")}
    for candidate in h.get("probe_paths", []):
        exe = expand_path(candidate)
        if exe and os.path.isfile(exe):
            out = _run_version(exe)
            if out:
                return {"raw": out, "exe": exe, "source": "install",
                        "verified": VERIFIED.get(h["id"], "")}
    return {"raw": None, "exe": None, "source": None, "verified": VERIFIED.get(h["id"], "")}


def versions(force: bool = False) -> dict:
    now = time.time()
    if not force and _VCACHE["data"] and now - _VCACHE["at"] < VERSION_CACHE_TTL:
        return _VCACHE["data"]
    out = {"ok": True, "verified": VERIFIED, "detected": {}}
    for h in HARNESS:
        info = detect_version(h)
        info["match"] = bool(info["raw"] and info["verified"] and info["verified"] in info["raw"])
        out["detected"][h["id"]] = info
    _VCACHE.update(at=now, data=out)
    return out


# --------------------------------------------------------------------------
# réseau (côté serveur : pas de CORS, messages d'erreur réels)
# --------------------------------------------------------------------------
def ssl_context() -> ssl.SSLContext:
    """Contexte TLS pour les appels https.

    On ne dépend pas du magasin système : sur un binaire portable il peut être
    absent (Windows minimal) ou incomplet (CPython autonome). L'ensemble de
    racines certifi est embarqué ; `--insecure` le contourne pour les serveurs
    auto-signés du réseau local.
    """
    if Ctx.insecure:
        return ssl._create_unverified_context()
    if Ctx.cafile and os.path.isfile(Ctx.cafile):
        try:
            return ssl.create_default_context(cafile=Ctx.cafile)
        except Exception:  # noqa: BLE001 — on retombe sur le magasin système
            pass
    return ssl.create_default_context()


def do_http(payload: dict) -> dict:
    url = str(payload.get("url") or "")
    u = urlsplit(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise ValueError("URL http(s) attendue")
    method = str(payload.get("method") or "GET").upper()
    headers = {str(k): str(v) for k, v in (payload.get("headers") or {}).items()}
    body = payload.get("body")
    data = None
    if body is not None and method not in ("GET", "HEAD"):
        data = json.dumps(body).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    timeout = min(max(float(payload.get("timeout") or 20), 1.0), 120.0)
    req = urlreq.Request(url, data=data, method=method, headers=headers)
    ctx = ssl_context()
    t0 = time.perf_counter()

    def elapsed() -> int:
        return int((time.perf_counter() - t0) * 1000)

    try:
        with urlreq.urlopen(req, timeout=timeout, context=ctx) as r:
            raw = r.read(MAX_HTTP_BODY)
            return {"status": r.status, "ms": elapsed(), "text": raw.decode("utf-8", "replace"),
                    "headers": {k.lower(): v for k, v in r.headers.items()}, "error": None}
    except urlerr.HTTPError as e:
        raw = e.read(MAX_HTTP_BODY)
        return {"status": e.code, "ms": elapsed(), "text": raw.decode("utf-8", "replace"),
                "headers": {k.lower(): v for k, v in (e.headers or {}).items()}, "error": None}
    except Exception as e:  # noqa: BLE001 — on veut le message exact
        return {"status": 0, "ms": elapsed(), "text": "", "headers": {},
                "error": f"{type(e).__name__}: {e}", "error_name": type(e).__name__}


def do_ping(payload: dict) -> dict:
    host = str(payload.get("host") or "")
    port = int(payload.get("port") or 0)
    timeout = min(max(float(payload.get("timeout") or 5), 0.5), 30.0)
    if not host or not port:
        return {"reachable": False, "error": "hôte ou port manquant", "ms": 0}
    t0 = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"reachable": True, "ms": int((time.perf_counter() - t0) * 1000)}
    except Exception as e:  # noqa: BLE001
        return {"reachable": False, "ms": int((time.perf_counter() - t0) * 1000),
                "error": f"{type(e).__name__}: {e}"}


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------
class Api(BaseHTTPRequestHandler):
    server_version = f"{APP}/{VERSION}"
    protocol_version = "HTTP/1.1"

    # ---- utilitaires ----------------------------------------------------
    def _send(self, code: int, payload: dict, extra: dict | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, path: str) -> None:
        try:
            with open(path, "rb") as f:
                body = f.read()
        except OSError as e:
            self._send(500, {"ok": False, "error": f"interface introuvable ({e}) : {path}"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Set-Cookie", f"bridge={Ctx.token}; Path=/; HttpOnly; SameSite=Strict")
        self.end_headers()
        self.wfile.write(body)

    def _raw_body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return b""
        if n > MAX_REQ_BODY:
            raise ValueError(f"corps trop volumineux ({n} octets)")
        return self.rfile.read(n)

    @staticmethod
    def _json(raw: bytes) -> dict:
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"corps JSON illisible : {e}") from e

    def _authorized(self) -> bool:
        origin = self.headers.get("Origin")
        allowed = {f"http://127.0.0.1:{Ctx.port}", f"http://localhost:{Ctx.port}"}
        if origin and origin not in allowed:
            return False
        site = self.headers.get("Sec-Fetch-Site")
        if site and site not in ("same-origin", "none"):
            return False
        cookie = self.headers.get("Cookie") or ""
        return f"bridge={Ctx.token}" in cookie

    def log_message(self, fmt: str, *args) -> None:
        if "/api/" in (self.path or ""):
            sys.stderr.write("  %s %s\n" % (self.command, self.path))

    # ---- routage --------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path in ("/", "/index.html"):
            self._send_html(Ctx.ui_path)
            return
        if path == "/favicon.ico":
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path == "/api/health":
            self._send(200, {"ok": True, "app": APP, "version": VERSION})
            return
        if path == "/api/state":
            if not self._authorized():
                self._send(403, {"ok": False, "error": "session du pont absente ou invalide"})
                return
            self._send(200, {
                "ok": True, "home": Ctx.root, "port": Ctx.port, "version": VERSION,
                "platform": sys.platform, "python": sys.version.split()[0],
                "harnesses": [{"id": h["id"], "label": h["label"], "note": h["note"],
                               "config": h["config"][0], "env": h["env"]} for h in HARNESS],
                "verified": VERIFIED,
            })
            return
        if path == "/api/versions":
            if not self._authorized():
                self._send(403, {"ok": False, "error": "session du pont absente ou invalide"})
                return
            self._send(200, versions())
            return
        self._send(404, {"ok": False, "error": "route inconnue"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        try:
            raw = self._raw_body()          # lu avant le contrôle : pas de désync keep-alive
        except ValueError as e:
            self._send(400, {"ok": False, "error": str(e)})
            return
        if not self._authorized():
            self._send(403, {"ok": False, "error": "session du pont absente ou invalide"})
            return
        try:
            payload = self._json(raw)
            if path == "/api/scan":
                root = expand_path(str(payload.get("root") or Ctx.root))
                if not os.path.isdir(root):
                    raise ValueError(f"racine inexistante : {root}")
                self._send(200, scan(root, bool(payload.get("deep", True)),
                                     payload.get("paths") or {}))
            elif path == "/api/http":
                self._send(200, do_http(payload))
            elif path == "/api/ping":
                self._send(200, do_ping(payload))
            elif path == "/api/read":
                real = guard(str(payload.get("path") or ""))
                st = os.stat(real)
                self._send(200, {"ok": True, "path": real, "text": read_text(real),
                                 "size": st.st_size, "mtime": st.st_mtime})
            elif path == "/api/write":
                text = payload.get("text")
                if not isinstance(text, str):
                    raise ValueError("« text » manquant")
                self._send(200, do_write(str(payload.get("path") or ""), text))
            elif path == "/api/reveal":
                real = guard(str(payload.get("path") or ""))
                if sys.platform == "win32":
                    subprocess.Popen(["explorer", "/select,", real])
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", "-R", real])
                else:
                    subprocess.Popen(["xdg-open", os.path.dirname(real)])
                self._send(200, {"ok": True, "path": real})
            else:
                self._send(404, {"ok": False, "error": "route inconnue"})
        except PermissionError as e:
            self._send(403, {"ok": False, "error": str(e)})
        except (ValueError, OSError) as e:
            self._send(400, {"ok": False, "error": f"{type(e).__name__}: {e}"})
        except Exception as e:  # noqa: BLE001
            self._send(500, {"ok": False, "error": f"{type(e).__name__}: {e}"})


# --------------------------------------------------------------------------
# démarrage
# --------------------------------------------------------------------------
def running_port(port: int) -> bool:
    """Une instance de LLMBridge écoute-t-elle déjà sur ce port ?"""
    try:
        with urlreq.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.7) as r:
            return r.status == 200 and b"llm-bridge" in r.read(512)
    except Exception:  # noqa: BLE001
        return False


def list_harnesses(root: str) -> int:
    print(f"racine : {root}")
    data = scan(root, deep=True, overrides={})
    for item in data["items"]:
        if item["exists"]:
            extra = " (+ .env)" if item["env"] and item["env"]["exists"] else ""
            tail = "  [chemin personnalisé]" if item["custom"] else ""
            print(f"  [x] {item['label']:<24} {item['path']}  {item['size']} o{extra}{tail}")
        else:
            print(f"  [ ] {item['label']:<24} absent")
    print("\nversions :")
    for hid, info in versions().get("detected", {}).items():
        state = "vérifiée" if info.get("match") else ("non vérifiée" if info.get("raw") else "inconnue")
        print(f"  {hid:<10} {(info.get('raw') or '—'):<46} {state}")
    return 0


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

    ap = argparse.ArgumentParser(
        prog="LLMBridge",
        description="Pont local pour l'outil Endpoint LLM (opencode / Hermes / dsh).")
    ap.add_argument("--root", default=os.environ.get("LLM_BRIDGE_ROOT") or os.path.expanduser("~"),
                    help="dossier à scanner (défaut : dossier utilisateur)")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--html", default="", help="interface HTML de rechange (itération sans rebuild)")
    ap.add_argument("--no-browser", action="store_true", help="ne pas ouvrir le navigateur")
    ap.add_argument("--insecure", action="store_true",
                    help="ignorer les certificats TLS (API https auto-signée)")
    ap.add_argument("--list", action="store_true", help="harnais + versions détectés, puis quitter")
    ap.add_argument("--version", action="version", version=f"{APP} {VERSION}")
    args = ap.parse_args()

    Ctx.root = expand_path(args.root)
    Ctx.insecure = args.insecure
    Ctx.ui_path = args.html or resource_path("web", "index.html")
    Ctx.cafile = resource_path("assets", "cacert.pem")

    if not os.path.isdir(Ctx.root):
        print(f"racine inexistante : {Ctx.root}", file=sys.stderr)
        return 2
    if not os.path.isfile(Ctx.ui_path):
        print(f"interface introuvable : {Ctx.ui_path}", file=sys.stderr)
        print("(en mode source, lancez depuis le dossier du projet ; en exécutable, "
              "l'interface est embarquée — utilisez --html pour la remplacer)", file=sys.stderr)
        return 2

    if args.list:
        return list_harnesses(Ctx.root)

    if running_port(args.port):
        url = f"http://127.0.0.1:{args.port}/"
        print(f"Une instance répond déjà sur {url} — ouverture du navigateur.")
        if not args.no_browser:
            webbrowser.open(url)
        return 0

    httpd = None
    for port in range(args.port, args.port + 12):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", port), Api)
            Ctx.port = port
            break
        except OSError:
            continue
    if httpd is None:
        print(f"aucun port libre entre {args.port} et {args.port + 11}", file=sys.stderr)
        return 3

    url = f"http://127.0.0.1:{Ctx.port}/"
    print(f"LLMBridge {VERSION}  ·  {url}")
    print(f"  racine scannée : {Ctx.root}")
    print("  Ctrl+C pour arrêter (fermer cette fenêtre suffit).")
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\narrêt.")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
