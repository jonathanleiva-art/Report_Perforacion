$ErrorActionPreference = "Stop"

$project = "C:\Python_Proyectos\Report_Perforacion"
Set-Location -LiteralPath $project

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "Git no está instalado o no está disponible en PATH. Instala Git para Windows y vuelve a ejecutar este script."
}

git init
git add .
git commit -m "v1.0.5 - Dashboard KPI Profesional"
