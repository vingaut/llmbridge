# Changelog

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) · versionnage
[SemVer](https://semver.org/lang/fr/).

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
