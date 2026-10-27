# Dépannage

## L'outil ne voit aucun harnais

1. Regardez la racine affichée en haut (badge `pont local · …`) : c'est le dossier
   réellement scanné. Un lancement « en tant qu'administrateur » avec un autre compte,
   ou une tâche planifiée sous `SYSTEM`, scanne un autre profil.
2. Chemins par défaut attendus : `~/.config/opencode/opencode.jsonc`,
   `~/.hermes/config.yaml`, `~/.dsh/cordis.patch.yml`.
3. Installé ailleurs : ouvrez **⚙ Chemins** et donnez le fichier exact.
4. En ligne de commande : `LLMBridge --list` affiche ce qui est trouvé, et où.

## L'endpoint est injoignable

- le message affiche l'erreur réelle : `ConnectionRefusedError` (rien n'écoute),
  timeout (pare-feu ou mauvaise IP), `SSL: WRONG_VERSION_NUMBER` (vous parlez https
  à un serveur http) ;
- le serveur doit écouter sur `0.0.0.0` (ou l'IP du réseau), pas seulement sur
  `127.0.0.1` ;
- testez d'abord depuis la machine du serveur : `curl http://127.0.0.1:8080/v1/models` ;
- réseau Windows marqué « public » : les connexions entrantes sont bloquées.

## Le serveur répond 200 mais l'outil dit injoignable

Impossible via le pont (il ne passe pas par le navigateur). Si vous voyez encore ce
message, vous utilisez l'ancienne page en `file://` : ouvrez l'URL
`http://127.0.0.1:8766/` fournie par le pont.

## « écriture refusée » / HTTP 403

Le fichier n'a pas été vu par le dernier scan. Deux causes :

- vous venez de changer un chemin : cliquez **Chemins → Rescanner** ;
- le fichier ne porte pas un nom géré (`config.yaml`, `config.yml`,
  `opencode.jsonc`, `opencode.json`, `cordis.patch.yml`, `.env`).

## Le harnais ignore le nouveau fournisseur

Redémarrez-le : les trois lisent leur configuration au démarrage. Vérifiez aussi que
la case « rendre actif » (ou `model:`) était cochée si vous attendiez un changement de
modèle par défaut.

## Port occupé

Le pont essaie les 12 ports suivants. Si aucun n'est libre :
`LLMBridge --port 8899`. Une instance déjà lancée sur le port est détectée : un
second lancement ouvre simplement le navigateur.

## HTTPS vers un serveur auto-signé

`LLMBridge --insecure` (ou lancez avec cette option depuis un raccourci). Les racines
publiques (`certifi`) sont embarquées, donc les endpoints publics fonctionnent sans
option.

## L'aperçu est vide / une erreur de validation apparaît

L'outil valide le résultat **avant** d'écrire : si le fichier d'entrée est exotique
(JSONC non standard, YAML avec ancres multiples), l'aperçu échoue et rien n'est
touché. Copiez le message d'erreur dans un rapport de bug avec la version du harnais.

## Antivirus / SmartScreen

L'exécutable n'est pas signé. Windows peut demander *Informations complémentaires →
Exécuter quand même* au premier lancement. Une compilation locale ne déclenche en
général rien. `--onefile` se décompresse dans `%TEMP%\_MEI…` à chaque démarrage
(~1 s) : c'est normal.

## Journal technique en anglais

Assumé : il contient des messages de bibliothèques (`urllib`, `ssl`, `socket`) qui
n'existent qu'en anglais. L'interface, elle, est traduite. Voir `docs/I18N.md`.
