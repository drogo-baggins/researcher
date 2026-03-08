# setenv.ps1 — Windows 版環境変数設定
# Usage: . .\setenv.ps1

$env:SEARXNG_URL = "http://localhost:8888"
$env:EMBEDDING_MODEL = "nomic-embed-text-v2-moe"
$env:RELEVANCE_THRESHOLD = "0.5"
$env:OLLAMA_MODEL = "gpt-oss:20b"
