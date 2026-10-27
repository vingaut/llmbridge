# Contribuer

Merci ! Ce projet est volontairement petit et sans dépendance : c'est ce qui le rend
portable. Deux règles priment sur les autres.

## Règles du projet

1. **Zéro dépendance à l'exécution.** `app.py` n'utilise que la bibliothèque standard.
   Une PR qui ajoute `requests`, `flask` ou `pyyaml` au runtime sera refusée ; ces
   outils sont acceptables pour *tester* (`uv run --with pyyaml python …`).
2. **Rien n'est écrit sans sauvegarde.** Toute écriture passe par `do_write()`
   (`.bak-<horodatage>` + fichier temporaire + `os.replace`) et par `guard()`
   (liste blanche issue du dernier scan). Ne contournez pas ces deux fonctions.

## Mise en route

```bash
python app.py --html web/index.html --no-browser   # Python 3.10+
```

L'interface est un fichier HTML unique : aucune compilation, aucune chaîne npm.

Pour l'exécutable :

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1   # Windows
./build.sh                                            # Linux
```

## Checklist avant une PR

- [ ] `python app.py --list` détecte les harnais et leurs versions ;
- [ ] un scan, un aperçu puis une écriture **sur une copie** de chaque fichier
      fonctionnent (jamais sur la configuration réelle) ;
- [ ] le fichier produit est relu par un parseur indépendant
      (`json.loads` après retrait des commentaires, `yaml.safe_load`) ;
- [ ] le diff ne touche que ce qui est annoncé dans l'aperçu ;
- [ ] l'interface reste utilisable dans les 8 langues (bascule + rechargement) ;
- [ ] `LLMBridge --list` fonctionne sur l'exécutable reconstruit.

## Style

- Python : PEP 8, annotations légères, messages d'erreur **en français dans l'API**
  (ils remontent tels quels dans l'interface), journal technique en anglais ;
- JavaScript : ES2018, pas de framework, pas de build ; les fonctions pures restent
  dans `CORE`/`YCORE` (testables sans DOM) ;
- commentaires : expliquer **pourquoi**, pas ce que fait la ligne.

## Ajouter une langue

Voir [docs/I18N.md](docs/I18N.md). Une traduction partielle est acceptée si `fr` et
`en` sont complets : les clés manquantes retombent sur l'anglais.

## Signaler un bug

Utilisez le modèle proposé. Ce qui aide vraiment :

- la version détectée des trois harnais (`LLMBridge --list`) ;
- le message exact (badge rouge, journal, sortie console) ;
- le diff de l'aperçu, ou le fichier anonymisé qui pose problème.

## Commits

`type(scope): résumé` — `fix(opencode)`, `feat(i18n)`, `docs`, `build`, `test`.

## Licence

En contribuant, vous acceptez que votre code soit publié sous MIT.
