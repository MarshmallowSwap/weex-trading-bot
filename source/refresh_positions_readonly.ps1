$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$python=(Get-Command python -ErrorAction Stop).Source
$log=Join-Path $root 'read_only_position_refresh.log'
try {
 foreach($module in @('position_readonly_adapter.py','risk_review_readonly.py')){
  $output=& $python (Join-Path $root $module) 2>&1
  if($LASTEXITCODE -ne 0){throw "Module failed: $module"}
  $output | ForEach-Object { Add-Content -Path $log -Value "[$(Get-Date -Format o)] $module : $_" }
 }
}catch{
 Add-Content -Path $log -Value "[$(Get-Date -Format o)] ERROR $($_.Exception.Message)"
 exit 1
}
