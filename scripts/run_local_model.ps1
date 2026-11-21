param([string]$OllamaPath)

$root = Split-Path -Parent $PSScriptRoot
if (-not $OllamaPath) {
    $command = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $command) {
        throw 'Install Ollama or pass its executable path with -OllamaPath.'
    }
    $OllamaPath = $command.Source
}
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_MAX_QUEUE = '1'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_MODELS = Join-Path $root '.local/ollama-models'

# Ollama writes routine server logs to stderr.
$ErrorActionPreference = 'Continue'
& $OllamaPath serve
exit $LASTEXITCODE
