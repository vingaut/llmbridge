# Architecture

```
┌──────────────────────────────────────────────┐
│  Navigateur  http://127.0.0.1:8766/          │
│  web/index.html  (UI + i18n + docs)          │
│    CORE   : JSONC à la ligne près            │
│    YCORE  : YAML à la ligne près             │
│    TARGETS: formes par harnais               │
└───────────────┬──────────────────────────────┘
                │  fetch same-origin (cookie de session)
┌───────────────▼──────────────────────────────┐
│  app.py  (ThreadingHTTPServer, 127.0.0.1)    │
│    /api/scan     disque → harnais + contenu  │
│    /api/http     proxy réseau (0 CORS)       │
│    /api/ping     TCP joignable ?             │
│    /api/write    .bak + écriture atomique    │
│    /api/versions --version des 3 harnais     │
└───────────────┬──────────────────────────────┘
                │
      fichiers de configuration     endpoint OpenAI-compatible
      (~/.hermes, ~/.dsh, ~/.config)      (http://ip:port/v1)
```

## Pourquoi cette séparation

Le navigateur ne peut pas, depuis une page `file://` :

- **lire/écrire le disque** de façon fiable : File System Access exige une origine
  stable et une autorisation par dossier ; en `file://` l'origine est opaque, les
  handles ne sont pas persistables, et toute erreur de persistance ressemble à un
  refus de dossier ;
- **appeler l'API** : `fetch()` envoie `Origin: null`, le serveur ne renvoie pas
  `Access-Control-Allow-Origin`, et répond souvent `403` au preflight `OPTIONS`.

Le pont fait ces deux choses côté serveur. L'interface reste un fichier HTML
ordinaire, mais elle est servie par le pont : même origine, cookie de session,
aucun CORS.

## Flux d'une écriture

1. l'UI construit les options depuis la carte (`cardOptions`) ;
2. `CORE.applyOpencode` / `YCORE.applyHermes` / `YCORE.applyDsh` produisent le
   nouveau texte **en mémoire**, en préservant commentaires, indentation et fins de
   ligne ; le résultat est validé (`CORE.validate`) avant tout I/O ;
3. l'aperçu affiche ce texte et la liste des éléments supprimés ;
4. `POST /api/write` vérifie que le chemin fait partie des fichiers détectés au
   dernier scan (`Ctx.allowed`), copie l'original en `.bak-<horodatage>`, écrit dans
   un fichier temporaire puis `os.replace()` (atomique) ;
5. l'UI relit le fichier via `POST /api/read`, re-parse et vérifie que le
   fournisseur est bien présent ; le résultat est journalisé en vert ou rouge.

## Pourquoi l'écriture se fait en JavaScript et pas en Python

Les transformations JSONC/YAML (préservation des commentaires, remplacement d'une
entrée, insertion dans un mapping) sont testables dans le navigateur, sans I/O, et
donnent l'aperçu exact avant écriture. Python ne fait que du disque et du réseau,
ce qui garde `app.py` petit et sans dépendance.

## Sécurité

| Mesure | Détail |
|---|---|
| Écoute | `127.0.0.1` uniquement, jamais `0.0.0.0` |
| Session | cookie `bridge=<aléatoire>` `HttpOnly; SameSite=Strict`, vérifié sur chaque `/api/*` |
| Origine | `Origin` doit être absent ou égal à `http://127.0.0.1:<port>` ; `Sec-Fetch-Site` doit valoir `same-origin`/`none` |
| Écriture | liste blanche issue du dernier scan + noms de fichiers connus (`config.yaml`, `opencode.jsonc`, `cordis.patch.yml`, `.env`…) |
| Sauvegarde | `.bak-<horodatage>` avant chaque remplacement, écriture atomique ensuite |
| Réseau | seules les URL `http(s)` sont proxifiées ; aucune requête hors de l'endpoint sondé |

## Compatibilité

`app.py` n'utilise que la bibliothèque standard (aucune dépendance à l'exécution).
`sys._MEIPASS` est pris en compte pour l'exécutable `--onefile`, et aucun chemin
Windows n'est codé en dur : la même source tourne sous Linux.
