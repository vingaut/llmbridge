# Versions vérifiées

Cette release (**3.0.0**) a été testée sur Windows 11 avec les versions suivantes,
installées sur la machine de l'auteur. Les versions sont détectées à l'exécution
(`/api/versions`) et affichées sur chaque carte.

| Harnais | Version testée | Détection | État |
|---|---|---|---|
| opencode (terminal) | `0.0.0-beta-19271` | `opencode` / `opencode2` dans le PATH, sinon `%APPDATA%\npm\opencode2.cmd` | ✅ vérifiée |
| opencode (desktop) | `2.1.4` | `%LOCALAPPDATA%\Programs\@opencodedesktop\resources\opencode-cli.exe`, sinon `%LOCALAPPDATA%\Programs\opencode\…`, `%PROGRAMFILES%\opencode\…`, `/opt/opencode/resources/opencode-cli` | ✅ vérifiée |
| Hermes Agent | `0.22.5` (2026.9.24) | `hermes` dans le PATH, sinon `%USERPROFILE%\.hermes\hermes-agent\.hermes\bin\hermes.cmd` | ✅ vérifiée |
| dsh (`@deepseek-ai/dsh`) | `0.2.1-rc.2` | `dsh` dans le PATH, sinon `%APPDATA%\npm\dsh.cmd` | ✅ vérifiée |

## Ce que « vérifiée » veut dire

La **forme** écrite a été relue dans un fichier réel produit par l'outil, puis
validée par un parseur indépendant :

- opencode : `json.loads` après retrait des commentaires et virgules finales ;
  `providers = [unsloth, strataqwen, lan-170-8080]`, entrée nouvelle complète ;
- Hermes : `yaml.safe_load` ; `custom_providers` contient l'entrée ajoutée,
  `model.default` / `base_url` pointent sur le fournisseur choisi ;
- dsh : `yaml.safe_load` ; `llm-pi-ai.config.providers` contient le fournisseur,
  `agent-default-model.provider` mis à jour, entrées `compaction-basic` et
  `ui-settings-general` intactes.

Les trois modes (ajouter / remplacer / remettre à zéro) ont été exercés, y compris
sur des copies de fichiers réels, avec contrôle du diff avant/après.

## Versions non testées

Toute autre version est **non vérifiée** (badge orange), pas nécessairement
incompatible. L'aperçu reste la référence : si le schéma a changé, le diff le montre
avant écriture.

Signes qu'une version est trop différente :

| Harnais | Signe |
|---|---|
| opencode | le fichier n'a plus de bloc `providers` (pluriel) → l'outil le crée, mais le schéma a peut-être changé |
| Hermes | `custom_providers` n'existe plus dans `config.yaml` |
| dsh | plus d'entrée `- id: llm-pi-ai` dans `cordis.patch.yml` |

## Mettre à jour ce tableau

1. installer la nouvelle version du harnais ;
2. `LLMBridge --list` → vérifier la version détectée ;
3. faire un scan, un aperçu, une écriture **sur une copie** du fichier ;
4. valider avec un parseur indépendant ;
5. mettre à jour `VERIFIED` dans `app.py` et ce fichier.
