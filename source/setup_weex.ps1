$ErrorActionPreference='Stop'
$base=Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host 'WEEX - configurazione SOLO LETTURA' -ForegroundColor Cyan
Write-Host 'Crea una chiave API WEEX con permesso Read Only, senza Trade o Withdraw.'
function AskSecret([string]$label) {
 $s=Read-Host $label -AsSecureString
 $p=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
 try {return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($p)}
 finally {[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($p)}
}
$key=AskSecret 'WEEX API Key'
$secret=AskSecret 'WEEX Secret Key'
$pass=AskSecret 'WEEX API Passphrase'
if (-not $key -or -not $secret -or -not $pass) {throw 'Campi mancanti'}
$path=Join-Path $base 'weex_credentials.json'
[System.IO.File]::WriteAllText($path,(@{api_key=$key;secret_key=$secret;passphrase=$pass}|ConvertTo-Json -Compress),[System.Text.UTF8Encoding]::new($false))
try {
 $acl=Get-Acl $path
 $acl.SetAccessRuleProtection($true,$false)
 $rule=New-Object System.Security.AccessControl.FileSystemAccessRule([Security.Principal.WindowsIdentity]::GetCurrent().Name,'FullControl','Allow')
 $acl.AddAccessRule($rule)
 Set-Acl $path $acl
} catch {Write-Host 'Attenzione: impossibile restringere permessi NTFS' -ForegroundColor Yellow}
$key=$null;$secret=$null;$pass=$null
Write-Host 'Credenziali salvate localmente; ora verifico soltanto le posizioni in lettura.'
python (Join-Path $base 'test_readonly.py')
Read-Host 'Premi Invio per chiudere'
