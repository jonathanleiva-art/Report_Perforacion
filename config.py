from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
PLANOS_MALLA_DIR = DATA_DIR / "planos_malla"
PLANOS_MALLA_PREVIEW_DIR = PLANOS_MALLA_DIR / "preview"
REPORTES_OPERADORES_DIR = DATA_DIR / "reportes_operadores"
EXCEL_PATH = BASE_DIR / "reportes_perforacion.xlsx"
VERSION_PATH = BASE_DIR / "VERSION.txt"

REPORTES_PDF_DIR = BASE_DIR / "reportes_pdf"
BACKUP_DIR = BASE_DIR / "backup"
BACKUP_VERSIONS_DIR = BASE_DIR / "backup_versions"
TEMP_CHARTS_DIR = BASE_DIR / "temp_charts"
