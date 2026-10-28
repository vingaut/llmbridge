# LLMBridge

**Brancher un endpoint local compatible OpenAI sur opencode, Hermes Agent et dsh — en un clic, sans éditer un fichier à la main.**

LLMBridge est un outil qui automatise à 90% la configuration des providers locaux dans les harnais:
-HERMES
-DeepSeek Harness
-OPENCODE V2 (CLI terminale et application desktop)
Je massacre regulierement mes workflows et j'en avais marre de tout retaper dans ces satanés cli !

Je voulais un outil sans dependance qu'on peut lancer sur n'importe quel poste dans un reseau local et qui fera la mise a jour des providers locaux dans les harnais les plus utilisés.

Ca ne sert probablement à rien, mais c'est cousu main ! Enfin ... hebergé et motorisé localement, pas un jeton ne vient de Chine ni des US !
---

## Démarrage — trois façons

### 1. Binaire (rien à installer)

Téléchargez `LLMBridge-vX.Y.Z-windows-x64.exe` (Windows) ou `LLMBridge-vX.Y.Z-linux-x64`
(Linux) dans les [Releases](../../releases) — le nom du fichier porte la version, et une
archive `LLMBridge-vX.Y.Z-source.zip` est publiée à côté — puis double-cliquez. Le
navigateur ouvre <http://127.0.0.1:8766/>.

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
| **opencode** (CLI terminale) | `0.0.0-beta-19271` | `providers.<id>` → `name`, `package`, `settings.baseURL/apiKey/headerTimeout/chunkTimeout`, `models.<alias>` → `modelID`, `name`, `capabilities`, `compatibility.reasoningField`, `limit.context/output` |
| **opencode** (application desktop) | `2.1.4` | même fichier, même schéma — les deux builds partagent `~/.config/opencode/opencode.jsonc` |
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
| opencode (terminale + desktop) | `~/.config/opencode/opencode.jsonc` | — (clé dans le JSON) |
| Hermes Agent | `~/.hermes/config.yaml` | `~/.hermes/.env` |
| dsh | `~/.dsh/cordis.patch.yml` | `~/.dsh/.env` |

Ce ne sont que des **premières** suppositions. Le scan essaie, dans cet ordre, et chaque
fichier trouvé est proposé dans une liste déroulante sur la carte :

1. **les variables d'environnement** — `OPENCODE_CONFIG`, `OPENCODE_CONFIG_DIR`,
   `XDG_CONFIG_HOME`, `HERMES_HOME`, `HERMES_CONFIG_PATH`, `HERMES_ENV_PATH`,
   `DSH_HOME`, `DSH_AGENTS_HOME`, `DSH_CONFIG`, `DSH_PATCH` ;
2. **ce que l'outil annonce lui-même** — `hermes config path`, `hermes config env-path`,
   `opencode debug paths` ;
3. **les conventions** (tableau ci-dessus) ;
4. **un parcours du profil entier**, dossiers masqués et `AppData` compris : tout
   `opencode.json(c)` dans un dossier `opencode`, `config.yaml` dans `.hermes` / `Hermes`,
   `cordis.patch.yml` dans `dsh`. Borné en profondeur, en nombre d'entrées et en durée ;
   `node_modules`, caches de navigateur et `Windows` sont ignorés.

dsh et la CLI opencode s'installent uniquement par npm : leur version est lue dans le
manifeste du paquet (`@deepseek-ai/dsh`, `@opencode-ai/cli`) au lieu d'exécuter un shim
`.cmd`.

Installé ailleurs ? **Dossier à scanner** (étape 1) rescanne n'importe quelle racine
(`C:\Users`, un autre profil, une installation déplacée) et 📁 sur une carte ouvre un
navigateur de dossiers pour pointer ce harnais au bon endroit — le choix est mémorisé.

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

## Mentions tierces

[NOTICE.md](NOTICE.md) : modèles utilisés pour écrire le code (aucun poids
redistribué, licence du modèle non contaminante), bundle de racines TLS embarqué,
marques citées à titre descriptif.
