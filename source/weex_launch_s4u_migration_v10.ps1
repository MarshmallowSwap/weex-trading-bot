$ErrorActionPreference='Stop'
$script='D:\FUNDSHOT\weex_alerts\weex_s4u_supervisor_migrate_admin_v10.ps1'
try {
 $p=Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"' + $script + '"')) -PassThru
 Write-Output ('ELEVATION_REQUESTED pid='+$p.Id)
} catch {
 Write-Output ('ELEVATION_NOT_STARTED '+$_.Exception.GetType().Name)
 exit 2
}
