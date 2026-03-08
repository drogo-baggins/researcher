<#
.SYNOPSIS
    Windows 開発環境 venv 初期化スクリプト
.DESCRIPTION
    sandbox-init.sh の Windows 版。
    プロジェクトルート直下の venv/ を作成・更新します。
    Windows ではホストファイルシステム上で動作するため、
    venv は自然に永続化されます。
.EXAMPLE
    .\scripts\sandbox-init.ps1
#>
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectDir = Split-Path -Parent $ScriptDir
$VENV_DIR = Join-Path $ProjectDir "venv"

# ─── venv setup ──────────────────────────────────────────────────────────────

$VenvPython = Join-Path $VENV_DIR "Scripts\python.exe"

if (Test-Path $VenvPython) {
    Write-Host "[sandbox-init] venv found at $VENV_DIR - updating editable install..." -ForegroundColor Cyan
    & $VenvPython -m pip install --quiet -e $ProjectDir
    & $VenvPython -m pip install --quiet -r (Join-Path $ProjectDir "requirements-dev.txt")
    Write-Host "[sandbox-init] venv ready." -ForegroundColor Green
}
else {
    Write-Host "[sandbox-init] Creating venv at $VENV_DIR ..." -ForegroundColor Cyan
    python -m venv $VENV_DIR
    $VenvPip = Join-Path $VENV_DIR "Scripts\pip.exe"
    & $VenvPip install --upgrade pip --quiet
    & $VenvPip install -e $ProjectDir --quiet
    & $VenvPip install -r (Join-Path $ProjectDir "requirements-dev.txt") --quiet
    Write-Host "[sandbox-init] venv created and packages installed." -ForegroundColor Green
}

# ─── Activation hint ─────────────────────────────────────────────────────────

Write-Host ""
Write-Host "venv を有効化するには:" -ForegroundColor Yellow
Write-Host "  & $VENV_DIR\Scripts\Activate.ps1"
