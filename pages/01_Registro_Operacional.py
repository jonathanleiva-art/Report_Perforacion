from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from ui.page_header import render_page_header
from data import leer_reportes_sqlite as leer_reportes
from utils import EXCEL_PATH


def main():
    if not app.requerir_acceso():
        return
    render_page_header(app.st, 
        "Registro Operacional",
        f"Ingreso manual de reportes diarios, validación de turno y respaldo operativo | Fuente: Registros manuales SQLite",
    )
    app.st.info(
        "Este formulario crea registros manuales. "
        "Los Ciclos de Perforación Excel se administran desde la fuente de datos de Ciclos y no se mezclan con este ingreso."
    )

    if app.st.session_state.pop("reporte_guardado", False):
        app.st.success("Reporte guardado correctamente en SQLite y exportado a Excel.")

    df_reportes = leer_reportes()
    app.formulario_registro(df_reportes)


main()
