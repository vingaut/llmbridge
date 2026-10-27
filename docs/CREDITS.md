# Crédits

## Projet

| Rôle | Nom |
|---|---|
| Architecture, conception d'origine, spécifications, recette | **vinga** |
| Code (v2.1 → v3.0), tests, documentation | **Hermes Agent** — Nous Research |

Le point de départ est l'outil `config-endpoint-llm.html` conçu et écrit par vinga :
une page HTML autonome qui sondait l'API en `fetch()` et écrivait via File System
Access. La v1 ne pouvait pas fonctionner en `file://` (CORS + origine opaque) ; la
réécriture conserve son interface, son vocabulaire et ses trois modes d'écriture, et
remplace la couche de transport par un pont local.

## Ce qui a servi à écrire la v3

| Ressource | Détail |
|---|---|
| Modèle | `deepseek-v4.1-flash`, servi par un moteur local `Strata ds4-0.1` (compatible OpenAI, fenêtre 1 048 576) |
| Agent | Hermes Agent (Nous Research) en session locale |
| Outils | terminal (git-bash), lecture/écriture de fichiers, navigateur piloté par CDP (tests d'interface), `curl` |
| Chaîne de build | Python 3.13.14 (géré par `uv`), PyInstaller 6.22.3, `certifi` (racines TLS) |
| Validation | PyYAML (relire les YAML produits), `json` (relire le JSONC), `diff` |
| Système | Windows 11, VS Code |

## Mesures de la session de développement

Relevées dans la base de session de Hermes en fin de travail (elles augmentent à
chaque échange supplémentaire) :

| Mesure | Valeur |
|---|---|
| Date | 2026-10-27 |
| Durée | ~4 h 40 (18:49 → 23:29, temps de build et d'attente inclus) |
| Messages | 328 |
| Appels d'outils | 176 |
| Appels API | 144 |
| Jetons d'entrée (frais) | 318 449 |
| Jetons de sortie | 201 632 |
| Jetons relus en cache | 29 818 617 |

Les « jetons relus en cache » correspondent au contexte renvoyé à chaque appel : le
coût réel en entrée est celui des 318 449 jetons frais.

## Ce qui a été vérifié, et ce qui ne l'a pas été

**Vérifié sur la machine de l'auteur** : scan des trois harnais, sonde d'un endpoint
réel (fenêtre, modalités, build), génération de test, écriture dans les trois formats
sur des copies, relecture et validation par des parseurs indépendants, modes
« remplacer » et « remettre à zéro », chemins personnalisés, refus d'écriture hors
liste blanche, interface dans les huit langues, binaire Windows compilé et testé.

**Non vérifié** : binaire Linux (aucune machine Linux disponible pendant la session ;
le spec et `build.sh` sont fournis et testés en logique, pas en exécution), versions
de harnais autres que celles listées dans `docs/VERIFIED-VERSIONS.md`, macOS.

## Remerciements

Les formats de configuration proviennent des projets eux-mêmes : opencode,
Hermes Agent (Nous Research) et dsh (DeepSeek). Les racines TLS embarquées viennent
de [certifi](https://github.com/certifi/python-certifi).
