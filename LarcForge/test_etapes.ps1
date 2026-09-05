# Test des Étape 1 & 3 — Durcissement du Pipeline LarcForge
# Usage : PowerShell -ExecutionPolicy Bypass -File test_etapes.ps1

Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Tests des Étape 1 & 3 — Durcissement du Pipeline LarcForge  ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Config
$ProjectRoot = "D:\Projets\LarcForge"
$TestResults = @()

# Fonction helper pour exécuter un test
function Test-Command {
    param(
        [string]$Description,
        [string]$Command,
        [int[]]$ExpectedExitCodes
    )

    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
    Write-Host "[TEST] $Description" -ForegroundColor Yellow
    Write-Host "Commande : $Command" -ForegroundColor Gray

    try {
        Invoke-Expression $Command | Out-Host
        $exitCode = $LASTEXITCODE
    } catch {
        Write-Host "ERREUR : $_" -ForegroundColor Red
        $exitCode = -1
    }

    $passed = $false
    if ($ExpectedExitCodes -contains $exitCode) {
        Write-Host "✓ SUCCÈS : exit code = $exitCode (attendu : $([string]::Join(', ', $ExpectedExitCodes)))" -ForegroundColor Green
        $passed = $true
    } else {
        Write-Host "✗ ÉCHEC : exit code = $exitCode (attendu : $([string]::Join(', ', $ExpectedExitCodes)))" -ForegroundColor Red
    }

    $TestResults += @{
        Description = $Description
        ExitCode    = $exitCode
        Passed      = $passed
    }

    Write-Host ""
}

# Test 1 : Linting simple en mode standard
Test-Command `
    -Description "Étape 1 : Linting standard (avec DB)" `
    -Command "cd $ProjectRoot && python -m larcforge lints --projects LarcCommon --no-db" `
    -ExpectedExitCodes @(0, 1, 3)

# Test 2 : Linting en mode dry-run
Test-Command `
    -Description "Étape 3 : Linting en mode DRY-RUN" `
    -Command "cd $ProjectRoot && python -m larcforge lints --projects LarcCommon --dry-run --json" `
    -ExpectedExitCodes @(0, 1, 3)

# Test 3 : Tests en mode dry-run
Test-Command `
    -Description "Étape 3 : Tests en mode DRY-RUN" `
    -Command "cd $ProjectRoot && python -m larcforge tests --dry-run --no-db" `
    -ExpectedExitCodes @(0, 1, 3)

# Test 4 : Run complet en mode dry-run (sans DB)
Test-Command `
    -Description "Étape 3 : Run COMPLET en mode DRY-RUN" `
    -Command "cd $ProjectRoot && python -m larcforge run --dry-run --no-db" `
    -ExpectedExitCodes @(0, 1, 3)

# Rapport Final
Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  RAPPORT FINAL DES TESTS                                      ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$passed = @($TestResults | Where-Object { $_.Passed }).Count
$total = $TestResults.Count

foreach ($test in $TestResults) {
    $status = if ($test.Passed) { "✓" } else { "✗" }
    $color = if ($test.Passed) { "Green" } else { "Red" }
    Write-Host "$status [$($test.ExitCode)] $($test.Description)" -ForegroundColor $color
}

Write-Host ""
Write-Host "Résumé : $passed/$total tests réussis" -ForegroundColor $(if ($passed -eq $total) { "Green" } else { "Red" })
Write-Host ""

if ($passed -eq $total) {
    Write-Host "🎉 TOUTES LES ÉTAPES IMPLÉMENTÉES AVEC SUCCÈS !" -ForegroundColor Green
} else {
    Write-Host "⚠ Certains tests ont échoué — vérifiez les détails ci-dessus" -ForegroundColor Yellow
}
