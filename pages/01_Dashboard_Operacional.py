from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from data import leer_reportes_sqlite as leer_reportes
from dashboard import dashboard as dashboard_view
from utils import EXCEL_PATH, limpiar_entero, ruta_imagen_equipo


def main():
    app.st.title("Sistema de Reporte de Perforación")
    app.st.caption(f"Dashboard operacional | Aplicación oficial: {EXCEL_PATH.parent} | Versión actual: {app.version_sistema()}")

    df_reportes = leer_reportes()
    dashboard_view(
        df_reportes,
        aplicar_filtros_fn=app.aplicar_filtros,
        mostrar_alerta_reportes_faltantes_fn=app.mostrar_alerta_reportes_faltantes,
        mostrar_alertas_operacionales_fn=app.mostrar_alertas_operacionales,
        seccion_reporte_pdf_fn=app.seccion_reporte_pdf,
        resumen_operacional_equipos_fn=app.resumen_operacional_equipos,
        equipos_esperados_fn=app.equipos_esperados,
        ruta_imagen_equipo_fn=ruta_imagen_equipo,
        limpiar_entero_fn=limpiar_entero,
        color_estado_operacional_fn=app.color_estado_operacional,
        color_texto_estado_operacional_fn=app.color_texto_estado_operacional,
        columnas_horas_turno_fn=app.columnas_horas_turno,
        etiqueta_hora_fn=app.etiqueta_hora,
    )


main()
