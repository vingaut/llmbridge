# Construit dist\LLMBridge.exe : un seul fichier, aucune dépendance au runtime.
# Usage : clic droit > "Exécuter avec PowerShell", ou  powershell -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Creation de l'environnement de build (.venv)..."
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3 -m venv .venv
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        python -m venv .venv
    } else {
        throw "Python 3 introuvable. Installez-le depuis python.org en cochant 'Add python.exe to PATH'."
    }
}

Write-Host "Installation de PyInstaller..."
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pyinstaller --quiet

Write-Host "Compilation..."
& ".\.venv\Scripts\pyinstaller.exe" --clean --noconfirm llm-bridge.spec

if (-not (Test-Path ".\dist\LLMBridge.exe")) {
    throw "La compilation a echoue : dist\LLMBridge.exe absent."
}
$size = [math]::Round((Get-Item ".\dist\LLMBridge.exe").Length / 1MB, 1)
Write-Host ""
Write-Host "OK -> dist\LLMBridge.exe ($size Mo)"
Write-Host "Double-cliquez dessus : il ouvre http://127.0.0.1:8766/ dans le navigateur."
