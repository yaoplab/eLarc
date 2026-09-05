# ============================================================================
# install_editable.ps1 — réinstalle les packages editables du monorepo LARC
# ============================================================================
# Usage (depuis n'importe où) :
#   powershell -ExecutionPolicy Bypass -File D:\projets\install_editable.ps1
#
# Après une réinitialisation de l'environnement Python, tout remettre en place
# en une commande. Les packages installés sont en mode "editable" (-e) :
# les modifications du code sont prises en compte immédiatement.
# ============================================================================

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$python = "python"

# Cibles : chemin du package (+ extra éventuel entre crochets)
$targets = @(
    "LarcCommon",
    "LarcForge[gui]"     # extra gui = PySide6 pour l'interface
)

foreach ($t in $targets) {
    Write-Host "==> pip install -e $t" -ForegroundColor Cyan
    python -m pip install -e (Join-Path $root $t)
}

Write-Host ""
Write-Host "Vérification des imports :" -ForegroundColor Cyan
python -c "import larccommon; import larcforge; import PySide6; print('OK : larccommon, larcforge, PySide6')"
Write-Host ""
Write-Host "Terminé. Relancer : python -m LarcForge ui" -ForegroundColor Green
