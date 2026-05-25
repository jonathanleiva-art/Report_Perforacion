from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from data import leer_reportes_sqlite as leer_reportes
from utils import EXCEL_PATH


def main():
    app.st.title("Sistema de Reporte de Perforación")
    app.st.caption(f"Formulario de registro | Aplicación oficial: {EXCEL_PATH.parent} | Versión actual: {app.version_sistema()}")

    if app.st.session_state.pop("reporte_guardado", False):
        app.st.success("Reporte guardado correctamente en SQLite y exportado a Excel.")

    df_reportes = leer_reportes()
    app.formulario_registro(df_reportes)


main()
