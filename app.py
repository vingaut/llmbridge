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
import glob
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
from urllib.parse import parse_qs, urlsplit

APP = "llm-bridge"
VERSION = "3.2.0"
DEFAULT_PORT = 8766
MAX_HTTP_BODY = 8 * 1024 * 1024      # réponse max d'une requête proxifiée
MAX_REQ_BODY = 16 * 1024 * 1024      # corps max accepté par l'API
VERSION_CACHE_TTL = 60.0

# Versions contre lesquelles cette release a été testée (docs/VERIFIED-VERSIONS.md).
VERIFIED = {
    "opencode": "0.0.0-beta-19271",        # CLI terminale (npm @opencode-ai/cli)
    "opencode-desktop": "2.1.4",           # application desktop (Electron)
    "hermes": "0.22.5",
    "dsh": "0.2.1-rc.2",
}

HARNESS = [
    {
        "id": "opencode", "label": "opencode (terminal)", "format": "jsonc", "flavor": "opencode",
        "color": "#f7c948", "note": "CLI en terminal, partage ~/.config/opencode",
        "config": [".config/opencode/opencode.jsonc", ".config/opencode/opencode.json"],
        "env": None, "envPrefix": None, "discover": True,
        "pkg": "@opencode-ai/cli",
        "bins": ["opencode", "opencode2"],
        "probe_paths": [
            r"%APPDATA%\npm\opencode.cmd",
            r"%APPDATA%\npm\opencode2.cmd",
            "/usr/local/bin/opencode", "/usr/bin/opencode",
        ],
    },
    {
        "id": "opencode-desktop", "label": "opencode (desktop)", "format": "jsonc",
        "flavor": "opencode", "color": "#f0b429",
        "note": "application desktop (Electron), même config que la CLI",
        "config": [".config/opencode/opencode.jsonc", ".config/opencode/opencode.json"],
        "env": None, "envPrefix": None, "discover": True,
        "bins": [],
        "probe_paths": [
            r"%LOCALAPPDATA%\Programs\@opencodedesktop\resources\opencode-cli.exe",
            r"%LOCALAPPDATA%\Programs\opencode\resources\opencode-cli.exe",
            r"%PROGRAMFILES%\opencode\resources\opencode-cli.exe",
            "/opt/opencode/resources/opencode-cli",
        ],
    },
    {
        "id": "hermes", "label": "Hermes Agent", "format": "yaml", "flavor": "hermes",
        "color": "#c792ea", "note": "custom_providers[] + bloc model: pour le fournisseur actif",
        "config": [".hermes/config.yaml", ".hermes/config.yml"],
        "env": ".hermes/.env", "envPrefix": "HERMES_CUSTOM_",
        "path_cmd": ["config", "path"], "env_path_cmd": ["config", "env-path"],
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
        "pkg": "@deepseek-ai/dsh",
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
    "node_modules", "windows", "venv", ".venv", ".git", ".cache", "cache", "caches",
    "dist", "build", "__pycache__", "site-packages", ".npm", ".vscode",
    ".cargo", ".rustup", ".gradle", ".m2", "locallow", "onedrivetemp",
    # caches applicatifs (Electron & co) : volumineux, jamais de config dedans
    "code cache", "gpucache", "cachestorage", "service worker", "blob_storage",
    "dawncache", "shadercache", "webcache", "platformcache", "dictionaries",
    "logs", "crashes", "temp", "tmp", "windowsapps", "$recycle.bin",
    "system volume information", "program files", "program files (x86)", "programdata",
}

# Fichiers de configuration reconnus, par harnais : (dossier parent, nom de fichier).
# Le dossier est comparé sans le point initial : « .config/opencode », « AppData\Roaming\opencode »
# et « %APPDATA%\ai.opencode.desktop\opencode » sont donc tous acceptés.
MATCH = {
    "opencode": [("opencode", "opencode.jsonc"), ("opencode", "opencode.json")],
    "opencode-desktop": [("opencode", "opencode.jsonc"), ("opencode", "opencode.json")],
    "hermes": [("hermes", "config.yaml"), ("hermes", "config.yml")],
    "dsh": [("dsh", "cordis.patch.yml"), ("dsh", "cordis.patch.yaml")],
}

# Variables d'environnement qui déplacent la configuration d'un harnais.
#   "file" : chemin direct du fichier de configuration
#   "dir"  : dossier qui contient ce fichier
#   "xdg"  : base XDG (le harnais ajoute son propre sous-dossier : <base>/opencode/…)
ENV_HINTS = {
    "opencode": [("OPENCODE_CONFIG", "file"), ("OPENCODE_CONFIG_DIR", "dir"),
                 ("XDG_CONFIG_HOME", "xdg")],
    "opencode-desktop": [("OPENCODE_CONFIG", "file"), ("OPENCODE_CONFIG_DIR", "dir"),
                         ("XDG_CONFIG_HOME", "xdg")],
    "hermes": [("HERMES_CONFIG", "file"), ("HERMES_HOME", "dir"), ("HERMES_CONFIG_DIR", "dir")],
    "dsh": [("DSH_CONFIG", "file"), ("DSH_PATCH", "file"), ("DSH_HOME", "dir"),
            ("DSH_AGENTS_HOME", "dir"), ("XDG_CONFIG_HOME", "xdg")],
}

MAX_DEPTH = 9            # profondeur max sous la racine scannée
MAX_ENTRIES = 400_000    # nombre d'entrées max vues au total
MAX_CFG_BYTES = 4 * 1024 * 1024


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


def scan_tree(root: str, budget: float = 8.0) -> tuple[dict, dict]:
    """Un seul parcours du profil, AppData et dossiers masqués compris.

    Rend ``{harnais: [fichiers trouvés]}`` plus quelques statistiques pour l'UI.
    """
    rules: dict = {}
    for hid, pairs in MATCH.items():
        for parent, name in pairs:
            rules.setdefault(name.lower(), []).append((parent.lstrip(".").lower(), hid))

    found: dict = {hid: [] for hid in MATCH}
    deadline = time.monotonic() + budget
    started = time.monotonic()
    seen = 0
    root_abs = os.path.abspath(root)
    base = len(root_abs.rstrip(os.sep).split(os.sep))
    stack = [root_abs]
    truncated = False

    while stack:
        if time.monotonic() > deadline or seen > MAX_ENTRIES:
            truncated = True
            break
        current = stack.pop()
        if len(current.rstrip(os.sep).split(os.sep)) - base >= MAX_DEPTH:
            continue
        try:
            with os.scandir(current) as it:
                entries = list(it)
        except OSError:          # dossier d'un autre utilisateur, lien cassé, ACL…
            continue
        seen += len(entries)
        parent = os.path.basename(current).lstrip(".").lower()
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    if entry.name.lower() not in SKIP_DIRS:
                        stack.append(entry.path)
                elif entry.is_file(follow_symlinks=False):
                    for want_parent, hid in rules.get(entry.name.lower(), ()):
                        if want_parent != parent:
                            continue
                        st = entry.stat(follow_symlinks=False)
                        if st.st_size <= MAX_CFG_BYTES:
                            found[hid].append({"path": entry.path, "size": st.st_size,
                                               "mtime": st.st_mtime})
            except OSError:
                continue

    for hid, hits in found.items():
        uniq, known = [], set()
        for hit in sorted(hits, key=lambda m: m["mtime"], reverse=True):
            key = os.path.realpath(hit["path"]).lower()
            if key not in known:
                known.add(key)
                uniq.append(hit)
        found[hid] = uniq
    return found, {"entries": seen, "truncated": truncated,
                   "seconds": round(time.monotonic() - started, 2)}


def find_in_dir(dirpath: str, harness_id: str, depth: int = 6, budget: float = 4.0) -> list[str]:
    """Cherche les fichiers d'un harnais dans un dossier choisi par l'utilisateur."""
    pairs = MATCH.get(harness_id, [])
    parents = {p.lstrip(".").lower() for p, _ in pairs}
    names = {n.lower() for _, n in pairs}
    out: list[str] = []
    deadline = time.monotonic() + budget
    base = len(os.path.abspath(dirpath).rstrip(os.sep).split(os.sep))
    for current, dirnames, filenames in os.walk(dirpath):
        if time.monotonic() > deadline:
            break
        if len(os.path.abspath(current).rstrip(os.sep).split(os.sep)) - base >= depth:
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS]
        if os.path.basename(current).lstrip(".").lower() in parents:
            for name in filenames:
                if name.lower() in names:
                    out.append(os.path.join(current, name))
    return out


def _inside(path: str, root: str) -> bool:
    """Vrai si `path` est sous `root` (comparaison insensible à la casse sous Windows)."""
    try:
        p = os.path.realpath(path)
        r = os.path.realpath(root)
    except OSError:
        return False
    return p == r or p.startswith(r.rstrip(os.sep) + os.sep)


def harness_item(h: dict, root: str, tree: dict | None = None, overrides: dict | None = None) -> dict:
    """Décrit un harnais : tous les candidats trouvés, le chemin retenu, le contenu.

    Ordre des candidats : dossier imposé par l'utilisateur, chemins par défaut,
    dossier annoncé par le binaire lui-même, puis tout ce que le parcours a trouvé.
    """
    ov = (overrides or {}).get(h["id"]) or {}
    item = {
        "id": h["id"], "label": h["label"], "format": h["format"], "flavor": h["flavor"],
        "color": h["color"], "note": h["note"], "envPrefix": h["envPrefix"],
        "exists": False, "path": None, "name": None, "size": 0, "mtime": None,
        "text": None, "deep": False, "custom": False, "customDir": None, "env": None,
        "candidates": [],
        "defaults": {
            "config": os.path.join(root, *h["config"][0].split("/")),
            "env": os.path.join(root, *h["env"].split("/")) if h["env"] else None,
        },
    }

    exe, exe_source = find_exe(h) if h.get("bins") or h.get("probe_paths") else (None, None)
    item["binary"] = exe
    item["binary_source"] = exe_source

    cands: list[str] = []
    origins: dict = {}

    def add(path: str, origin: str = "") -> None:
        if not path or not os.path.isfile(path):
            return
        real = os.path.realpath(path)
        if all(os.path.realpath(c) != real for c in cands):
            cands.append(os.path.abspath(path))
            origins[os.path.abspath(path)] = origin

    custom = expand_path(ov.get("config", "")) if ov.get("config") else ""
    if custom:
        item["custom"] = True
        if os.path.isdir(custom):
            item["customDir"] = custom
            for hit in find_in_dir(custom, h["id"]):
                add(hit)
            item["defaults"]["config"] = os.path.join(custom, os.path.basename(h["config"][0]))
        else:
            item["path"] = custom
            add(custom)
            item["defaults"]["config"] = custom
    else:
        home = os.path.realpath(os.path.expanduser("~"))
        same_home = os.path.realpath(root).lower() == home.lower()
        # 1. variables d'environnement (OPENCODE_CONFIG, HERMES_HOME, DSH_HOME…)
        for path, label, _var in env_candidates(h):
            if same_home or _inside(path, root):
                add(path, label)
        # 2. chemin annoncé par le binaire (hermes config path / config env-path)
        if h.get("path_cmd") and exe:
            announced = cli_path_cmd(exe, h["path_cmd"])
            if announced and (same_home or _inside(announced, root)):
                add(announced, "cli")
            if h.get("env_path_cmd"):
                env_announced = cli_path_cmd(exe, h["env_path_cmd"])
                if env_announced and (same_home or _inside(env_announced, root)):
                    item["announced_env"] = env_announced
        # 3. conventions par défaut
        for rel in h["config"]:
            add(os.path.join(root, *rel.split("/")), "default")
        # 4. ce que le binaire dit de son dossier de config (opencode debug paths)
        if h.get("discover") and exe:
            cdir = cli_config_dir(exe)
            if cdir and _inside(cdir, root):
                for rel in h["config"]:
                    add(os.path.join(cdir, os.path.basename(rel)), "debug paths")
        # 5. tout ce que le parcours du profil a trouvé (AppData compris)
        if tree:
            for hit in tree.get(h["id"], []):
                add(hit["path"], "scan")

    item["candidates"] = [{"path": p, "size": os.path.getsize(p),
                           "mtime": os.path.getmtime(p), "origin": origins.get(p, "")}
                          for p in cands]
    cfg = cands[0] if cands else None
    if cfg is None and item["path"] and os.path.isfile(item["path"]):
        cfg = item["path"]
    item["deep"] = len(cands) > 1

    if cfg:
        st = os.stat(cfg)
        item.update(exists=True, path=os.path.abspath(cfg), name=os.path.basename(cfg),
                    size=st.st_size, mtime=st.st_mtime, text=read_text(cfg))

    if h["env"]:
        custom_env = expand_path(ov.get("env", "")) if ov.get("env") else ""
        if custom_env:
            env_path = custom_env
        elif item.get("announced_env"):
            env_path = item["announced_env"]
        elif item["exists"] and item["path"]:
            env_path = os.path.join(os.path.dirname(item["path"]), ".env")
        elif item["customDir"]:
            env_path = os.path.join(item["customDir"], ".env")
        else:
            env_path = item["defaults"]["env"]
        if env_path and os.path.isfile(env_path):
            st = os.stat(env_path)
            item["env"] = {"exists": True, "path": env_path, "size": st.st_size,
                           "mtime": st.st_mtime, "text": read_text(env_path)}
        else:
            item["env"] = {"exists": False, "path": env_path}
    return item


def scan(root: str, deep: bool, overrides: dict | None = None) -> dict:
    tree, stats = {}, {"entries": 0, "truncated": False, "seconds": 0.0}
    if deep:
        tree, stats = scan_tree(root)
    items = [harness_item(h, root, tree, overrides) for h in HARNESS]
    allowed = set()
    for it in items:
        if it["exists"] and it["path"]:
            allowed.add(os.path.realpath(it["path"]).lower())
        if it["env"] and it["env"].get("exists"):
            allowed.add(os.path.realpath(it["env"]["path"]).lower())
    Ctx.allowed = allowed
    return {"ok": True, "root": root, "items": items, "version": VERSION, "scan": stats}


def list_dir(path: str) -> dict:
    """Sous-dossiers d'un chemin, dossiers masqués compris (AppData, .config…)."""
    real = expand_path(path)
    if not os.path.isdir(real):
        raise ValueError(f"dossier introuvable : {real}")
    dirs, files = [], 0
    try:
        with os.scandir(real) as it:
            for entry in it:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        dirs.append({"name": entry.name, "path": entry.path,
                                     "hidden": entry.name.startswith(".")})
                    else:
                        files += 1
                except OSError:
                    continue
    except PermissionError as exc:
        raise PermissionError(f"accès refusé : {real}") from exc
    dirs.sort(key=lambda d: (not d["hidden"], d["name"].lower()))
    parent = os.path.dirname(real.rstrip(os.sep))
    return {"ok": True, "path": real, "parent": parent if parent != real else None,
            "dirs": dirs, "files": files}


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
def _run(exe: str, args: list[str], timeout: float = 4.0) -> str | None:
    """Exécute un binaire et rend toute sa sortie (jamais un GUI : timeout court)."""
    if sys.platform == "win32" and exe.lower().endswith((".cmd", ".bat")):
        cmd = ["cmd", "/c", exe, *args]
    else:
        cmd = [exe, *args]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return ((p.stdout or "") + "\n" + (p.stderr or "")).strip()
    except Exception:  # noqa: BLE001 — binaire absent, GUI, timeout…
        return None


def _run_version(exe: str) -> str | None:
    out = _run(exe, ["--version"])
    if out:
        for line in out.splitlines():
            line = line.strip()
            if line:
                return line[:120]
    return None


def find_exe(h: dict) -> tuple[str | None, str | None]:
    """Cherche le binaire d'un harnais : PATH d'abord, puis emplacements connus."""
    for name in h.get("bins", []):
        exe = shutil.which(name)
        if exe:
            return exe, "PATH"
    for candidate in h.get("probe_paths", []):
        exe = expand_path(candidate)
        if exe and os.path.isfile(exe):
            return exe, "install"
    return None, None


_PATHS_CACHE: dict = {}


def cli_config_dir(exe: str) -> str | None:
    """Demande au binaire où il lit sa configuration (`<cli> debug paths`).

    C'est ce qui permet de suivre l'application desktop d'opencode même si elle
    n'installe rien dans le PATH et n'écrit pas là où on l'attend.
    """
    if exe in _PATHS_CACHE:
        return _PATHS_CACHE[exe]
    found = None
    out = _run(exe, ["debug", "paths"], timeout=6)
    if out:
        for line in out.splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2 and parts[0].strip().lower() == "config":
                found = parts[1].strip().strip('"')
                break
    _PATHS_CACHE[exe] = found
    return found


def npm_roots() -> list[str]:
    """Dossiers `node_modules` globaux plausibles (npm, nvm, volta, Homebrew…)."""
    roots: list[str] = []

    def push(path: str) -> None:
        path = os.path.abspath(path)
        if os.path.isdir(path) and path not in roots:
            roots.append(path)

    for base in (os.environ.get("APPDATA"), os.environ.get("LOCALAPPDATA"),
                 os.environ.get("PREFIX"), os.path.expanduser("~/.npm-global"),
                 os.path.expanduser("~/npm"), "/usr/local", "/usr", "/opt/homebrew"):
        if not base:
            continue
        for tail in ("npm/node_modules", "lib/node_modules", "node_modules"):
            push(os.path.join(base, *tail.split("/")))
    for pattern in ("~/.nvm/versions/node/*/lib/node_modules",
                    "~/.volta/tools/image/node/*/lib/node_modules",
                    "~/AppData/Roaming/nvm/*/node_modules",
                    "~/scoop/apps/nodejs/current/node_modules",
                    "~/Library/pnpm/global/5/node_modules"):
        for path in glob.glob(os.path.expanduser(pattern)):
            push(path)
    return roots


def pkg_version(pkg: str) -> tuple[str, str] | None:
    """(version, dossier du paquet) d'un paquet npm global — sans lancer de binaire.

    dsh et la CLI opencode s'installent uniquement par npm : lire leur manifeste est
    plus sûr que d'exécuter un shim (« dsh.cmd ») qui peut rester bloqué.
    """
    for root in npm_roots():
        manifest = os.path.join(root, *pkg.split("/"), "package.json")
        try:
            with open(manifest, "r", encoding="utf-8", errors="replace") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        if data.get("version"):
            return str(data["version"]), os.path.dirname(manifest)
    return None


_PATH_CMD_CACHE: dict = {}


def cli_path_cmd(exe: str, args: list[str]) -> str:
    """Chemin que le binaire annonce lui-même (`hermes config path`, …)."""
    key = (exe, tuple(args))
    if key in _PATH_CMD_CACHE:
        return _PATH_CMD_CACHE[key]
    value = ""
    out = _run(exe, list(args), timeout=8)
    for line in (out or "").splitlines():
        candidate = line.strip().strip('"')
        if candidate and os.path.isabs(expand_path(candidate)):
            value = expand_path(candidate)
            break
    _PATH_CMD_CACHE[key] = value
    return value


def env_candidates(h: dict) -> list[tuple[str, str, str]]:
    """(chemin, origine, variable) proposés par l'environnement, pour ce harnais."""
    out: list[tuple[str, str, str]] = []
    sub = os.path.basename(h["config"][0].split("/")[0]).lstrip(".")
    names = [os.path.basename(rel) for rel in h["config"]]
    for var, kind in ENV_HINTS.get(h["id"], []):
        raw = os.environ.get(var)
        if not raw:
            continue
        base = expand_path(raw)
        label = f"${var}"
        if kind == "file":
            out.append((base, label, var))
        elif kind == "dir":
            out.extend((os.path.join(base, name), label, var) for name in names)
        else:
            out.extend((os.path.join(base, sub, name), label, var) for name in names)
    return out


def detect_version(h: dict) -> dict:
    pkg = h.get("pkg")
    if pkg:
        got = pkg_version(pkg)
        if got:
            return {"raw": f"{pkg.split('/')[-1]} v{got[0]}", "exe": got[1],
                    "source": "npm", "verified": VERIFIED.get(h["id"], "")}
    exe, source = find_exe(h)
    if exe:
        raw = _run_version(exe)
        if raw:
            return {"raw": raw, "exe": exe, "source": source,
                    "verified": VERIFIED.get(h["id"], "")}
    return {"raw": None, "exe": exe, "source": source, "verified": VERIFIED.get(h["id"], "")}


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
        if path == "/api/browse":
            if not self._authorized():
                self._send(403, {"ok": False, "error": "session du pont absente ou invalide"})
                return
            query = parse_qs(urlsplit(self.path).query)
            target = (query.get("path") or [Ctx.root])[0]
            try:
                self._send(200, list_dir(target))
            except (ValueError, PermissionError) as exc:
                self._send(400, {"ok": False, "error": str(exc)})
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
            elif path == "/api/find":
                target = expand_path(str(payload.get("path") or ""))
                if not os.path.isdir(target):
                    raise ValueError(f"dossier introuvable : {target}")
                hits = find_in_dir(target, str(payload.get("harness") or ""))
                self._send(200, {"ok": True, "path": target, "matches": [
                    {"path": h, "size": os.path.getsize(h), "mtime": os.path.getmtime(h)}
                    for h in hits]})
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
        print(f"  {hid:<18} {(info.get('raw') or '—'):<46} {state}")
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
