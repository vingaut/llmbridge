# LLMBridge

**Brancher un endpoint local compatible OpenAI sur opencode, Hermes Agent et dsh — en un clic, sans éditer un fichier à la main.**

LLMBridge est un outil de bureau en un seul fichier. Il sonde une API
compatible OpenAI sur votre réseau (`http://ip:port/v1`), en déduit la fenêtre de
contexte, les modalités et le modèle exposé, puis écrit un fournisseur prêt à
l'emploi dans les fichiers de configuration des harnais installés sur la machine —
avec une sauvegarde horodatée avant chaque écriture.

Il existe parce qu'une simple page HTML **ne peut pas** faire ce travail : en
`file://`, le navigateur bloque deux choses.

| Blocage | Ce qui se passe |
|---|---|
| **CORS** | `fetch()` envoie `Origin: null` ; le serveur répond `200` mais sans `Access-Control-Allow-Origin`, donc le navigateur jette la réponse. Beaucoup de serveurs refusent aussi le preflight `OPTIONS` (`403`). |
| **Accès disque** | File System Access exige une origine stable et une autorisation par dossier ; en `file://` l'origine est opaque, les handles ne sont pas persistables, et l'échec s'affiche comme « dossier refusé ». |

LLMBridge fait les deux côté serveur, sur `127.0.0.1` uniquement, et sert
l'interface depuis là.

---

## Démarrage — trois façons

### 1. Binaire (rien à installer)

Téléchargez `LLMBridge.exe` (Windows) ou `LLMBridge` (Linux) dans les
[Releases](../../releases) et double-cliquez. Le navigateur ouvre
<http://127.0.0.1:8766/>.

### 2. Script Python (sans compilation)

```bash
python app.py            # Python 3.10+
```

### 3. Développement (interface modifiable à chaud)

```bash
python app.py --html web/index.html --no-browser
```

Toute modification de `web/index.html` est servie immédiatement, sans rebuild.

> Dans les trois cas, une fenêtre de console affiche l'URL et la racine scannée.
> `Ctrl+C` ou la fermeture de la fenêtre arrête le pont.

---

## Ce que fait l'outil

1. **Détecte** — lit les fichiers de configuration des trois harnais (chemins par
   défaut, ou chemins fournis).
2. **Sonde** — `GET /v1/models`, `/props`, `/api/tags`, un vrai aller-retour
   `/v1/chat/completions`, et une requête `max_tokens` démesurée pour lire la
   fenêtre de contexte dans le message d'erreur du serveur.
3. **Remplit** — id du fournisseur, base URL, contexte, budget de sortie, ids des
   modèles, variable de clé, `reasoningField` si le serveur expose un chat template,
   vision si le modèle déclare l'entrée image.
4. **Écrit** — JSONC pour opencode (commentaires préservés), YAML pour Hermes et dsh
   (commentaires et clés voisines préservés), mise à jour du `.env` pour la clé.

Trois modes d'écriture par harnais : **ajouter/mettre à jour**, **remplacer les
fournisseurs**, **remettre le fichier à zéro**. L'aperçu montre le résultat exact et
le journal liste ce qui sera supprimé avant confirmation.

## Versions vérifiées

Cette version a été testée contre :

| Harnais | Version testée | Ce qui est écrit |
|---|---|---|
| **opencode** | `2.1.4` | `providers.<id>` → `name`, `package`, `settings.baseURL/apiKey/headerTimeout/chunkTimeout`, `models.<alias>` → `modelID`, `name`, `capabilities`, `compatibility.reasoningField`, `limit.context/output` |
| **Hermes Agent** | `0.22.5` (config `v51`) | entrée `custom_providers[]` (`name`, `base_url`, `key_env`, `model`, `models`, `models_discovered`) et, si demandé, le bloc `model:` |
| **dsh** (DeepSeek Harness) | `0.2.1-rc.2` | fournisseur sous `llm-pi-ai → config.providers`, plus `agent-default-model` |

L'interface affiche la version **réellement détectée** sur votre machine à côté de
chaque carte (vert = vérifiée, orange = non vérifiée). La forme du fichier compte
plus que le numéro de version : si un harnais change de schéma, l'aperçu le montre
avant toute écriture. Voir [docs/VERIFIED-VERSIONS.md](docs/VERIFIED-VERSIONS.md).

## Chemins

Emplacements par défaut, sous votre dossier utilisateur :

| Harnais | Configuration | Fichier de clé |
|---|---|---|
| opencode | `~/.config/opencode/opencode.jsonc` | — (clé dans le JSON) |
| Hermes Agent | `~/.hermes/config.yaml` | `~/.hermes/.env` |
| dsh | `~/.dsh/cordis.patch.yml` | `~/.dsh/.env` |

Installé ailleurs, ou second profil ? Ouvrez **⚙ Chemins** au-dessus des cartes et
donnez les fichiers exacts — `~`, `$VARS` et `%VARS%` sont développés, le `.env`
voisin est déduit, et le choix est mémorisé dans le navigateur.

## Garde-fous

- écoute sur `127.0.0.1` seulement, cookie `SameSite=Strict` et contrôle d'origine :
  une page web tierce ne peut pas déclencher d'écriture ;
- écriture limitée aux fichiers trouvés par le dernier scan, et à des noms connus ;
- chaque écriture crée `<fichier>.bak-<horodatage>` à côté ;
- rien n'est envoyé ailleurs qu'à l'endpoint sondé.

## Ligne de commande

| Option | Effet |
|---|---|
| `--root DIR` | dossier à scanner (défaut : dossier utilisateur ; env `LLM_BRIDGE_ROOT`) |
| `--port N` | port d'écoute (défaut `8766`, 12 ports suivants essayés) |
| `--html FILE` | sert une autre interface, sans reconstruire |
| `--no-browser` | n'ouvre pas le navigateur |
| `--insecure` | ignore la vérification TLS (serveur auto-signé) |
| `--list` | affiche harnais + versions détectés, puis quitte |

## Compiler

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1     # Windows
```

```bash
./build.sh                                              # Linux (pas de compilation croisée)
```

Les deux produisent un exécutable autonome (`dist/LLMBridge.exe` / `dist/LLMBridge`,
~8 Mo) avec l'interface et le magasin de racines TLS embarqués. Prérequis :
Python 3.10+, `pip install pyinstaller` (les scripts gèrent le venv).

## API HTTP

Le pont est une petite API JSON, pilotable depuis vos scripts :

```
GET  /api/health                     vie du service (sans authentification)
GET  /api/state                      racine, port, version, harnais
GET  /api/versions                   versions détectées + vérifiées
POST /api/scan    {root, deep, paths:{id:{config,env}}}
POST /api/http    {url, method, headers, body, timeout}
POST /api/ping    {host, port, timeout}
POST /api/read    {path}
POST /api/write   {path, text}
POST /api/reveal  {path}
```

Les `POST /api/*` exigent le cookie de session posé par `GET /`. Voir
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Langues

L'interface est traduite en **français, English, Deutsch, español, italiano,
português, Nederlands, polski** (sélecteur en haut, détection automatique depuis le
navigateur). La documentation intégrée existe en français et en anglais ; le journal
technique reste en anglais. Ajouter une langue = un objet dans `web/index.html` —
voir [docs/I18N.md](docs/I18N.md).

## Dépannage

| Symptôme | Cause / solution |
|---|---|
| `INJOIGNABLE` | mauvaise IP/port, serveur lié à `127.0.0.1` au lieu de `0.0.0.0`, ou pare-feu. Le message affiche l'erreur réelle. |
| tous les harnais `ABSENT` | mauvaise racine (autre compte, profil déplacé) : elle est affichée en haut. Utilisez **Chemins** ou `--root`. |
| écriture refusée `403` | fichier non vu par le dernier scan : rescannez, ou déclarez son chemin. |
| le harnais ignore le fournisseur | redémarrez-le : la configuration est lue au démarrage. |
| endpoint HTTPS en échec | certificat auto-signé : lancez avec `--insecure`. |

Plus de détails dans [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Crédits

Architecture et conception d'origine : **Vincent GAUTIER** ([@vingaut](https://github.com/vingaut)).
Code : **Hermes Agent** (Nous Research), modèle `deepseek-v4.1-flash`. Voir [docs/CREDITS.md](docs/CREDITS.md).

## Licence

MIT — voir [LICENSE](LICENSE).
