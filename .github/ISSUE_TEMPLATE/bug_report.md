---
name: Rapport de bug
about: Quelque chose ne fonctionne pas comme prévu
title: "[bug] "
labels: bug
---

## Ce qui se passe

<!-- Message exact, badge affiché, extrait du journal (le journal est en anglais). -->

## Ce qui devrait se passer

## Environnement

- OS : <!-- Windows 11 / Ubuntu 24.04 … -->
- Version de LLMBridge : <!-- exe, `python app.py --version`, ou commit -->
- Mode de lancement : <!-- binaire / python app.py / --html -->
- Versions des harnais (sortie de `LLMBridge --list`) :

```
coller ici
```

## Endpoint sondé

- type de serveur : <!-- llama.cpp, vLLM, ollama, LM Studio, autre -->
- URL (anonymisée) : `http://192.168.x.x:8080/v1`
- le problème arrive-t-il aussi avec `curl http://…/v1/models` ? <!-- oui / non -->

## Fichier concerné

- harnais : <!-- opencode / hermes / dsh -->
- mode d'écriture : <!-- ajouter / remplacer / remettre à zéro -->
- si possible, un extrait **anonymisé** du fichier et le diff de l'aperçu
