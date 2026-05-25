param(
    [string]$ProjectPath = "C:\Python_Proyectos\Report_Perforacion"
)

$ErrorActionPreference = "Stop"

$project = Resolve-Path -LiteralPath $ProjectPath
$backupDir = Join-Path $project "backup_versions"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

$stamp = Get-Date -Format "yyyy_MM_dd_HHmm"
$zipPath = Join-Path $backupDir "backup_$stamp.zip"

$items = Get-ChildItem -LiteralPath $project -Force | Where-Object {
    $_.Name -ne "backup_versions" -and
    $_.Name -ne "__pycache__" -and
    $_.Name -ne "temp_charts"
}

Compress-Archive -LiteralPath $items.FullName -DestinationPath $zipPath -Force

Write-Output $zipPath
