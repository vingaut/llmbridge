# LLMBridge

**Point a local OpenAI-compatible endpoint at opencode, Hermes Agent and dsh — in one click, without touching a text editor.**

*Français : [README.fr.md](README.fr.md).*

LLMBridge is a tool that automates 90% of the configuration process for local providers within the following harnesses:
- HERMES
- DeepSeek Harness
- OPENCODE V2 (terminal CLI and desktop app)
I’m constantly breaking my own workflows, and I got tired of having to re-enter everything into those wretched CLIs!

I wanted a dependency-free tool that could be run on any machine on a local network to update the local providers used in the most common harnesses.

It’s probably entirely pointless, but it’s all hand-crafted! Well... it’s hosted and powered locally—not a single token comes from China or the US!

---

## Quick start — three ways

### 1. Binary (nothing to install)

Download `LLMBridge.exe` (Windows) or `LLMBridge` (Linux) from
[Releases](../../releases) and double-click it. Your browser opens
<http://127.0.0.1:8766/>.

### 2. Python script (no build step)

```bash
python app.py            # Python 3.10+
```

### 3. Development (edit the UI live)

```bash
python app.py --html web/index.html --no-browser
```

Changes to `web/index.html` are served immediately; no rebuild.

> In every mode a console window shows the URL and the scanned root.
> `Ctrl+C` or closing the window stops the bridge.

---

## What it does

1. **Detect** — reads the config files of the three harnesses (default paths, or
   paths you provide).
2. **Probe** — `GET /v1/models`, `/props`, `/api/tags`, a real `/v1/chat/completions`
   round-trip, and an optional oversized `max_tokens` request to read the context
   window out of the server's error message.
3. **Fill** — provider id, base URL, context, output budget, model ids, key variable,
   `reasoningField` when the server exposes a chat template, vision when the model
   declares image input.
4. **Write** — JSONC for opencode (comments preserved), YAML for Hermes and dsh
   (comments and neighbouring keys preserved), `.env` upsert for the API key.

Three write modes per harness: **add/update**, **replace all providers**, **reset the
file**. The preview shows the exact result, and the log lists what will be deleted
before you confirm.

## Verified harness versions

This release was tested against:

| Harness | Version tested | What is written |
|---|---|---|
| **opencode** (terminal CLI) | `0.0.0-beta-19271` | `providers.<id>` → `name`, `package`, `settings.baseURL/apiKey/headerTimeout/chunkTimeout`, `models.<alias>` → `modelID`, `name`, `capabilities`, `compatibility.reasoningField`, `limit.context/output` |
| **opencode** (desktop app) | `2.1.4` | same file, same schema — both builds share `~/.config/opencode/opencode.jsonc` |
| **Hermes Agent** | `0.22.5` (config `v51`) | `custom_providers[]` entry (`name`, `base_url`, `key_env`, `model`, `models`, `models_discovered`) and, if asked, the `model:` block (`default`, `provider`, `base_url`, `api_key`, `context_length`) |
| **dsh** (DeepSeek Harness) | `0.2.1-rc.2` | provider under `llm-pi-ai → config.providers`, plus `agent-default-model` (`provider`, `model`, `reasoningEffort`) |

The UI shows the version **actually detected** on your machine next to each card
(green = verified, orange = unverified). The file *shape* matters more than the
version number: if a harness changes its schema, the preview shows it before
anything is written. See [docs/VERIFIED-VERSIONS.md](docs/VERIFIED-VERSIONS.md).

## Paths

Default locations, under your home directory:

| Harness | Config | Key file |
|---|---|---|
| opencode (terminal + desktop) | `~/.config/opencode/opencode.jsonc` | — (key inline in the JSON) |
| Hermes Agent | `~/.hermes/config.yaml` | `~/.hermes/.env` |
| dsh | `~/.dsh/cordis.patch.yml` | `~/.dsh/.env` |

Those are only the *first* guess. The scan tries, in this order, and every file it finds
is offered in a dropdown on the card:

1. **environment variables** — `OPENCODE_CONFIG`, `OPENCODE_CONFIG_DIR`, `XDG_CONFIG_HOME`,
   `HERMES_HOME`, `HERMES_CONFIG_PATH`, `HERMES_ENV_PATH`, `DSH_HOME`,
   `DSH_AGENTS_HOME`, `DSH_CONFIG`, `DSH_PATCH`;
2. **what the tool announces itself** — `hermes config path`, `hermes config env-path`,
   `opencode debug paths`;
3. **the usual conventions** (table above);
4. **a walk of the whole profile**, hidden folders and `AppData` included: any
   `opencode.json(c)` inside a folder named `opencode`, `config.yaml` inside
   `.hermes` / `Hermes`, `cordis.patch.yml` inside `dsh`. Bounded by depth, entry count
   and a time budget; `node_modules`, browser caches and `Windows` are skipped.

dsh and the opencode CLI are npm-only: their version is read from the package manifest
(`@deepseek-ai/dsh`, `@opencode-ai/cli`) rather than by executing a `.cmd` shim.

Installed somewhere unusual? **Folder to scan** in step 1 rescans any root (`C:\Users`,
another profile, a moved install) and 📁 on a card opens a folder browser to point that
harness at the right directory — the choice is remembered in your browser.

## Safety

- listens on `127.0.0.1` only, `SameSite=Strict` session cookie and origin check:
  a third-party web page cannot trigger a write;
- writes are restricted to the files found by the last scan, and to known file names;
- every write creates `<file>.bak-<timestamp>` next to it;
- nothing is sent anywhere except the endpoint you probe.

## Command line

| Option | Effect |
|---|---|
| `--root DIR` | directory to scan (default: your home; env `LLM_BRIDGE_ROOT`) |
| `--port N` | listen port (default `8766`, next 12 tried if busy) |
| `--html FILE` | serve another UI file, without rebuilding |
| `--no-browser` | do not open the browser |
| `--insecure` | skip TLS verification (self-signed LAN servers) |
| `--list` | print detected harnesses and versions, then exit |

If an instance already listens on the port, a second launch just opens the browser.

## Build from source

```powershell
# Windows
powershell -ExecutionPolicy Bypass -File build.ps1
```

```bash
# Linux (PyInstaller cannot cross-compile: build on the target OS)
./build.sh
```

Both produce a single self-contained executable (`dist/LLMBridge.exe` /
`dist/LLMBridge`, ~8 MB) with the UI and the TLS root store embedded. Requirements:
Python 3.10+, `pip install pyinstaller` (the scripts handle the venv).

## HTTP API

The bridge is a small JSON API; you can drive it from your own scripts:

```
GET  /api/health                     liveness (no auth)
GET  /api/state                      root, port, version, harness list
GET  /api/versions                   detected + verified versions
POST /api/scan    {root, deep, paths:{id:{config,env}}}
POST /api/http    {url, method, headers, body, timeout}
POST /api/ping    {host, port, timeout}
POST /api/read    {path}
POST /api/write   {path, text}
POST /api/reveal  {path}
```

`POST /api/*` requires the session cookie set by `GET /`. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Languages

The interface is translated into **français, English, Deutsch, español, italiano,
português, Nederlands, polski** (selector in the header, auto-detected from the
browser). The embedded documentation is available in French and English; technical
logs stay in English. Adding a language is one object in `web/index.html` — see
[docs/I18N.md](docs/I18N.md).

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `UNREACHABLE` | wrong IP/port, server bound to `127.0.0.1` instead of `0.0.0.0`, or firewall. The message shows the real error (`ConnectionRefusedError`, timeout…). |
| all harnesses `MISSING` | wrong root (different account, moved profile). The scanned root is displayed at the top; use **Paths** or `--root`. |
| write refused `403` | the file was not seen by the last scan: rescan, or declare its path. |
| harness ignores the provider | restart it — configuration is read at startup. |
| HTTPS endpoint fails | self-signed certificate: start with `--insecure`. |

More in [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Credits

Architecture and original design: **Vincent GAUTIER** ([@vingaut](https://github.com/vingaut)).
Code: **Hermes Agent** (Nous Research), model `deepseek-v4.1-flash`. See [docs/CREDITS.md](docs/CREDITS.md).

## License

MIT — see [LICENSE](LICENSE). Third-party notices (models used to write the code, no
weights redistributed, embedded CA bundle): [NOTICE.md](NOTICE.md).
