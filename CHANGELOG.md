# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) · versionnage
[SemVer](https://semver.org/lang/fr/).

## [3.4.0] — 2026-10-30

### Modifié
- **dsh : la cible d'écriture est le patch du profil**
  (`~/.dsh/profiles/<profil>/cordis.patch.yml`) — la couche que sa page Models
  réécrit. Écrire dans le patch home rendait ce réglage impossible : dsh refuse
  d'enregistrer avec « Configuration for "llm-pi-ai" is overridden by a home patch
  or command-line overlay », ce qui bloquait toute création de fournisseur.
- le profil visé est détecté (web en tête, puis headless/tui) et sélectionnable ;
  l'interface signale un patch home qui définirait encore `llm-pi-ai`.
- `agent-default-model` n'est plus détourné sans le dire : la case « activer » ne
  se coche d'elle-même que si aucun modèle par défaut n'existe, et le modèle
  courant est affiché au-dessus du formulaire.
- les modes « remplacer » et « remise à zéro » disparaissent de la carte dsh :
  ils supprimaient des entrées écrites à la main.

### Corrigé
- le `.env` de dsh reste `$DSH_HOME/.env` même quand le fichier visé est dans
  `profiles/<nom>/` (il était déduit du dossier du fichier de configuration).

## [3.3.3] — 2026-10-29

### Corrigé
- **dsh exige une référence de credential, même sans authentification.** `apiKeyEnv`
  est déclaré dans son schéma comme `credential-ref` : pi-ai lève
  `No API key for provider: <id>` dès que la référence est absente, avant toute
  requête (vérifié dans `pi-ai/dist/api/openai-completions.js`, `getClientApiKey`).
  Le retirer en 3.3.2 était donc une erreur : il est désormais **toujours** écrit,
  et `$DSH_HOME/.env` reçoit la valeur — la clé saisie, ou `none` pour un endpoint
  sans authentification (source de repli documentée du service de credentials).
- Hermes conserve la règle inverse (`key_env` seulement si une clé existe) : il
  tolère une variable absente, contrairement à dsh.

## [3.3.2] — 2026-10-29

### Corrigé
- **dsh réclamait une clé API alors que l'endpoint n'en demande pas.** on écrivait
  `apiKeyEnv: <VAR>` même sans clé ; dsh cherche alors la variable, ne la trouve pas
  et refuse la requête. Sans clé, la ligne n'est plus écrite — dsh garde un profil
  « reference-free » et n'exige rien (comportement documenté du harnais).
- même correction pour `key_env` côté Hermes.
- quand une clé **est** saisie, elle est désormais écrite automatiquement dans le
  `.env` du harnais (créé au besoin) au lieu de rester dans le formulaire.
- bloc `.env` de l'interface : il ne s'affichait plus du tout depuis le passage au
  pont local (chemin non transmis), donc la variable était invisible et non modifiable.
- l'identifiant automatique ne reçoit plus de suffixe `-2` quand on réécrit le même
  fournisseur, et la variable d'environnement suit l'identifiant retenu.

## [3.3.1] — 2026-10-28

### Corrigé
- un binaire qui n'est pas une image PE valide (fichier vide, texte renommé `.exe`,
  installation npm interrompue) n'est plus exécuté. Windows affichait sinon
  « Application 16 bits non prise en charge » au moindre `--version` de sondage.
  Les fichiers écartés apparaissent sous « ignoré » dans `--diagnose`.

## [3.3.0] — 2026-10-28

### Ajouté
- **Création de la configuration quand elle n'existe pas encore.** opencode ne crée
  `opencode.jsonc` qu'une fois un fournisseur ajouté : sur une installation neuve,
  l'outil disait « absent » alors que le harnais était installé. Il affiche maintenant
  « INSTALLÉ · config absente », propose la carte, et écrit le fichier (dossiers
  parents compris) au premier enregistrement.
- **Recherche du binaire par motifs** : `%LOCALAPPDATA%\Programs\*\resources\opencode-cli.exe`
  couvre `ai.opencode.desktop`, `@opencodedesktop`, `opencode`… sans énumérer chaque
  variante d'installeur.
- `--diagnose` : binaire retenu, candidats et origine de chaque chemin, mode de création.

### Corrigé
- le parcours du profil est maintenant en largeur et commence par les dossiers utiles :
  le budget de 8 s se consumait dans `AppData/Local` avant d'atteindre `AppData/Roaming`.
- après une sonde, les champs dérivés de l'endpoint (baseURL, identifiant automatique,
  nom affiché) sont rafraîchis au lieu de rester sur une valeur précédente.
- les assets de release portent la version (`LLMBridge-vX.Y.Z-windows-x64.exe`,
  `…-linux-x64`, `…-source.zip`).

## [3.2.1] — 2026-10-28

### Modifié
- variables d'environnement alignées sur celles réellement lues par les harnais :
  `HERMES_CONFIG_PATH` et `HERMES_ENV_PATH` (hermes_cli/config.py) remplacent la
  supposition `HERMES_CONFIG` ; `DSH_HOME` confirmé par la source de dsh
  (« the home-level user patch layer `$DSH_HOME/cordis.patch.yml` »).
- le `.env` peut être désigné directement par `HERMES_ENV_PATH`, avant toute déduction.

## [3.2.0] — 2026-10-28

### Ajouté
- **Parcours du profil complet** pour trouver les configurations là où elles sont
  réellement installées : dossiers masqués et `AppData` compris (ils étaient exclus),
  correspondance sur (dossier parent, nom de fichier), bornes de profondeur et de durée.
  C'est ce qui ratait sur une seconde machine Windows.
- **Variables d'environnement** prises en compte : `OPENCODE_CONFIG`,
  `OPENCODE_CONFIG_DIR`, `XDG_CONFIG_HOME`, `HERMES_HOME`, `HERMES_CONFIG`,
  `DSH_HOME`, `DSH_AGENTS_HOME`, `DSH_CONFIG`, `DSH_PATCH`.
- **Chemins annoncés par les outils** : `hermes config path`, `hermes config env-path`,
  `opencode debug paths`.
- **Versions npm** lues dans le manifeste (`@deepseek-ai/dsh`, `@opencode-ai/cli`) :
  plus de shim `.cmd` à exécuter, ce qui convient à dsh qui s'installe par npm uniquement.
- **Choix du dossier dans l'interface** : champ « Dossier à scanner » (n'importe quelle
  racine, `C:/Users` ou un autre profil), navigateur de dossiers, bouton dossier par
  harnais, liste des candidats avec leur origine (`$VAR`, `cli`, `debug paths`, `scan`).

### Corrigé
- un chemin annoncé par un binaire ou une variable d'environnement ne déborde plus hors
  de la racine scannée : scanner un autre profil ne renvoie plus le vôtre.

## [3.1.0] — 2026-10-28

### Ajouté
- **opencode desktop** est détecté comme un harnais à part entière, à côté de la CLI
  terminale : deux cartes, deux binaires, deux versions (`opencode2 v0.0.0-beta-…`
  et `opencode-cli.exe v2.1.4`), sans remplacer l'une par l'autre.
- Le dossier de configuration est demandé au binaire (`<cli> debug paths`) au lieu
  d'être supposé : une installation desktop hors `~/.config` est suivie correctement.
- Le badge de version affiche le binaire détecté en infobulle.

## [3.0.0] — 2026-10-27

Version publiable.

### Ajouté
- **Chemins personnalisés par harnais** : l'interface accepte un fichier de
  configuration et un `.env` explicites (`~`, `$VARS`, `%VARS%` développés), les
  mémorise et les applique au scan suivant ; le `.env` voisin est déduit.
- **Versions détectées** : `/api/versions` lit `--version` de chaque harnais
  (PATH puis emplacements d'installation connus) et compare à la version vérifiée ;
  badge vert/orange par carte.
- **Documentation intégrée** (bouton *Documentation*) : fonctionnement, trois modes
  de lancement, versions vérifiées, chemins, garde-fous, dépannage.
- **Interface en 8 langues** : fr, en, de, es, it, pt, nl, pl ; sélecteur, détection
  automatique, mémorisation. Astuces en survol (attributs `title`) sur les champs,
  les boutons et les badges.
- **Liste blanche d'écriture** : seuls les fichiers détectés par le dernier scan
  sont écrits (403 sinon), au lieu d'une simple vérification de racine.
- Dépôt publiable : README bilingue, `docs/`, workflows GitHub Actions (build
  Windows/Linux + release sur tag), modèle de rapport de bug.

### Modifié
- `/api/state` expose la liste des harnais et les versions vérifiées.
- Le journal technique et le panneau de sonde passent en anglais (diagnostic brut).

## [2.2.0] — 2026-10-27

### Ajouté
- Projet PyInstaller : `app.py` + spec, interface et racines TLS embarquées,
  builds Windows/Linux, `.vscode/`.

### Corrigé
- HTTPS en échec dans le binaire (`CERTIFICATE_VERIFY_FAILED`) : magasin de racines
  `certifi` embarqué.
- `previewTarget`/`envHtml`/`renderDetect` utilisaient `t` à la fois pour le harnais
  et pour le traducteur (masquage) — renommé.

## [2.1.0] — 2026-10-27

### Ajouté
- Pont local Python (`serve.py`) : scan disque, proxy HTTP sans CORS, écriture
  atomique avec sauvegarde `.bak-<horodatage>`, relecture de contrôle.
- Interface branchée sur `/api/*` avec repli sur le comportement `file://`.

### Corrigé
- `Content-Type: application/json` envoyé sur les GET → preflight `OPTIONS` refusé.
- `modalities` renvoyé en objet (`{"vision":true}`) → `.join()` levait une exception
  silencieuse qui vidait les cartes.
- Champ `model` de dsh jamais pré-rempli ; `keyEnv` dupliqué avec le bloc `.env`.
- Budget de sortie calculé à 687 % du contexte → plafonné à 32 768.
- `classify()` ne distinguait pas « bloqué par CORS » de « serveur injoignable ».

## [1.0.0] — 2026-10-27

Version d'origine (`config-endpoint-llm.html`), fournie par l'auteur : page HTML
autonome, sonde directe en `fetch()`, écriture via File System Access. N'a jamais pu
fonctionner en `file://` (CORS + origine opaque) — d'où la réécriture.
