# Build do executável Windows do Frimapper (PyInstaller, onedir).
#
# Uso (PowerShell):
#   .\tools\build_windows.ps1 [-GraphvizHome "C:\Program Files\Graphviz"]
#
# Com -GraphvizHome (ou a env var GRAPHVIZ_HOME definida), o `dot` é
# empacotado dentro do bundle — o executável não depende de instalação
# do Graphviz na máquina de destino.

param(
    [string]$GraphvizHome = $env:GRAPHVIZ_HOME
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path ".venv-build")) {
    python -m venv .venv-build
}
& ".venv-build\Scripts\Activate.ps1"

pip install --upgrade pip
pip install -r requirements-build.txt

if ($GraphvizHome) {
    if (-not (Test-Path (Join-Path $GraphvizHome "bin\dot.exe"))) {
        throw "GRAPHVIZ_HOME inválido: não encontro bin\dot.exe em '$GraphvizHome'"
    }
    $env:GRAPHVIZ_HOME = $GraphvizHome
    Write-Host "A empacotar Graphviz de $GraphvizHome"
} else {
    Write-Host "GRAPHVIZ_HOME não definido — o executável usará o Graphviz do sistema."
}

pyinstaller frimapper.spec --noconfirm

Write-Host "`nValidação do bundle:"
& "dist\Frimapper\frimapper.exe" --selftest
if ($LASTEXITCODE -ne 0) { throw "Selftest do bundle falhou." }

Write-Host "`nBuild concluído: dist\Frimapper\"
