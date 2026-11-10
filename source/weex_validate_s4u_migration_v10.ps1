$ErrorActionPreference='Stop'
$path='D:\FUNDSHOT\weex_alerts\weex_s4u_supervisor_migrate_admin_v10.ps1'
$tokens=$null;$errs=$null
[void][System.Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errs)
if($errs.Count -gt 0) {
 $errs|ForEach-Object {Write-Output ('PARSE_ERROR line '+$_.Extent.StartLineNumber+': '+$_.Message)}
 exit 2
}
Write-Output 'SUPERVISOR_ADMIN_MIGRATION_SCRIPT_SYNTAX_PASS'
