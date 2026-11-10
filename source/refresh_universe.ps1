$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $root 'weex_universe_refresh.log'
$python = (Get-Command python -ErrorAction Stop).Source
try {
  $output = & $python (Join-Path $root 'weex_ai_universe.py') 2>&1
  $output | ForEach-Object { Add-Content -Path $log -Value "[$(Get-Date -Format o)] $_" }
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} catch {
  Add-Content -Path $log -Value "[$(Get-Date -Format o)] ERROR $($_.Exception.Message)"
  exit 1
}
