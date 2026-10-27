#!/usr/bin/env bash
# Construit dist/LLMBridge : un seul fichier, aucune dépendance au runtime.
# Même spec que sous Windows (PyInstaller ne fait pas de compilation croisée :
# il faut builder sur la plateforme cible).
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
  echo "Création de l'environnement de build (.venv)…"
  python3 -m venv .venv
fi

echo "Installation de PyInstaller…"
./.venv/bin/python -m pip install --upgrade pip --quiet
./.venv/bin/python -m pip install --upgrade pyinstaller --quiet

echo "Compilation…"
./.venv/bin/pyinstaller --clean --noconfirm llm-bridge.spec

ls -lh dist/LLMBridge
echo
echo "OK -> dist/LLMBridge (./dist/LLMBridge --no-browser pour tester sans navigateur)"
