$ErrorActionPreference='Stop'
$script='D:\FUNDSHOT\weex_alerts\weex_s4u_supervisor_crash_drill_v10.py'
$python='D:\FUNDSHOT\weex_alerts\.venv_weex_live\Scripts\python.exe'
try {
 $p=Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList @('-NoProfile','-Command',('"' + $python + '" -B "' + $script + '"')) -PassThru
 Write-Output ('CONTROLLED_S4U_CRASH_ELEVATION_REQUESTED pid='+$p.Id)
} catch {
 Write-Output ('CONTROLLED_S4U_CRASH_ELEVATION_DENIED '+$_.Exception.GetType().Name)
 exit 2
}
