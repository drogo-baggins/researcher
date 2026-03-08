<#
.SYNOPSIS
    Ollama コンテナ起動スクリプト (Windows PowerShell)
.DESCRIPTION
    ホストの Ollama モデルディレクトリをマウントして Ollama コンテナを起動します。
    Docker Desktop (推奨) または Podman を使用します。
.PARAMETER Force
    既に起動中でもコンテナを再作成します
.PARAMETER ModelsDir
    ホスト側のモデルディレクトリパス (デフォルト: $env:USERPROFILE\.ollama\models)
.EXAMPLE
    .\scripts\ollama-start.ps1
    .\scripts\ollama-start.ps1 -Force
    .\scripts\ollama-start.ps1 -ModelsDir "D:\ollama\models"
#>
param(
    [switch]$Force,
    [string]$ModelsDir = ""
)

$ErrorActionPreference = "Stop"

$OLLAMA_CONTAINER = "ollama"
$OLLAMA_PORT = "11434:11434"
$OLLAMA_IMAGE = "docker.io/ollama/ollama"
$MAX_WAIT = 30

# ─── Runtime Detection ────────────────────────────────────────────────────────

function Find-ContainerRuntime {
    foreach ($cmd in @("podman", "docker")) {
        if (Get-Command $cmd -ErrorAction SilentlyContinue) {
            & $cmd info *>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                return $cmd
            }
        }
    }
    return $null
}

$Runtime = Find-ContainerRuntime

if (-not $Runtime) {
    Write-Host "X podman も docker もインストールされていません" -ForegroundColor Red
    Write-Host "  https://docker.com または https://podman.io からインストールしてください"
    exit 1
}

Write-Host "Ollama 起動スクリプト (runtime: $Runtime)" -ForegroundColor Cyan
Write-Host ("=" * 56)

# ─── Model Directory Detection ────────────────────────────────────────────────

if (-not $ModelsDir) {
    if ($env:OLLAMA_MODELS) {
        $ModelsDir = $env:OLLAMA_MODELS
    } else {
        $ModelsDir = Join-Path $env:USERPROFILE ".ollama\models"
    }
}

if (-not (Test-Path $ModelsDir)) {
    Write-Host "WARNING: モデルディレクトリが見つかりません: $ModelsDir" -ForegroundColor Yellow
    Write-Host "  -ModelsDir パラメータまたは OLLAMA_MODELS 環境変数で指定できます"
    Write-Host "  ディレクトリを作成して続行します..."
    New-Item -ItemType Directory -Path $ModelsDir -Force | Out-Null
}

Write-Host "[OK] モデルディレクトリ: $ModelsDir" -ForegroundColor Green

# ─── Container Helper Functions ───────────────────────────────────────────────

function Test-ContainerExists {
    $names = & $Runtime ps -a --format '{{.Names}}' 2>$null
    return ($names -split "`n" | Where-Object { $_.Trim() -eq $OLLAMA_CONTAINER }).Count -gt 0
}

function Test-ContainerRunning {
    $names = & $Runtime ps --format '{{.Names}}' 2>$null
    return ($names -split "`n" | Where-Object { $_.Trim() -eq $OLLAMA_CONTAINER }).Count -gt 0
}

# ─── Existing Container Handling ──────────────────────────────────────────────

if ((Test-ContainerRunning) -and (-not $Force)) {
    Write-Host "[OK] Ollama コンテナは既に起動中です" -ForegroundColor Green
    Write-Host "  再作成するには: $($MyInvocation.MyCommand.Definition) -Force"

    Write-Host ""
    Write-Host "API 確認中..." -ForegroundColor Cyan
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        Write-Host "[OK] Ollama API 正常動作中" -ForegroundColor Green
        exit 0
    }
    catch {
        Write-Host "WARNING: Ollama API が応答しません。-Force で再作成を推奨します" -ForegroundColor Yellow
        exit 1
    }
}

if (Test-ContainerExists) {
    Write-Host ""
    Write-Host "既存コンテナをクリーンアップ..." -ForegroundColor Yellow
    & $Runtime stop $OLLAMA_CONTAINER 2>$null | Out-Null
    & $Runtime rm $OLLAMA_CONTAINER 2>$null | Out-Null
    Write-Host "[OK] クリーンアップ完了" -ForegroundColor Green
}

# ─── Start Container ──────────────────────────────────────────────────────────

Write-Host ""
Write-Host "Ollama コンテナを起動中..." -ForegroundColor Cyan

$ModelsMount = "${ModelsDir}:/root/.ollama/models"

& $Runtime run -d `
    --name $OLLAMA_CONTAINER `
    -p $OLLAMA_PORT `
    -v $ModelsMount `
    $OLLAMA_IMAGE

if ($LASTEXITCODE -ne 0) {
    Write-Host "X コンテナの起動に失敗しました" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] コンテナ作成完了" -ForegroundColor Green

# ─── Health Check ─────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "起動待機中..." -ForegroundColor Cyan

$ready = $false
for ($i = 1; $i -le $MAX_WAIT; $i++) {
    try {
        Invoke-WebRequest -Uri "http://localhost:11434/" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop | Out-Null
        $ready = $true
        break
    }
    catch {
        Write-Host "  待機中... ($i/$MAX_WAIT)" -NoNewline
        Write-Host "`r" -NoNewline
        Start-Sleep -Seconds 1
    }
}

if (-not $ready) {
    Write-Host ""
    Write-Host "X Ollama の起動がタイムアウトしました (${MAX_WAIT}秒)" -ForegroundColor Red
    Write-Host ""
    Write-Host "ログ:"
    & $Runtime logs $OLLAMA_CONTAINER 2>&1 | Select-Object -Last 20
    exit 1
}

Write-Host "[OK] Ollama が応答しています" -ForegroundColor Green

# ─── API Verification ─────────────────────────────────────────────────────────

Write-Host ""
Write-Host "API を検証中..." -ForegroundColor Cyan

try {
    $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
    $body = $response.Content

    if ($body -match '"models"') {
        Write-Host "[OK] Ollama API 正常動作" -ForegroundColor Green
        Write-Host ""
        Write-Host ("=" * 56)
        Write-Host "Ollama 起動完了" -ForegroundColor Green
        Write-Host ""
        Write-Host "  URL:    http://localhost:11434"
        Write-Host "  API:    http://localhost:11434/api/tags"
        Write-Host "  モデル: $ModelsDir"
        Write-Host "  停止:   .\scripts\ollama-stop.ps1"
    }
    else {
        Write-Host "WARNING: Ollama API が正常に応答していません" -ForegroundColor Yellow
        Write-Host "  レスポンス: $($body.Substring(0, [Math]::Min(200, $body.Length)))"
        exit 1
    }
}
catch {
    Write-Host "WARNING: Ollama API に接続できません: $_" -ForegroundColor Yellow
    exit 1
}
