$ErrorActionPreference = "Stop"

Write-Host "== Git status =="
git status --short

Write-Host "== Compile active project =="
python -m compileall `
  app_perforacion.py `
  config.py `
  data.py `
  db.py `
  dashboard.py `
  charts.py `
  metrics.py `
  pdf_report.py `
  services `
  pages `
  ui `
  audit `
  validation `
  ml `
  tests

Write-Host "== Pytest =="
python -m pytest tests -v
