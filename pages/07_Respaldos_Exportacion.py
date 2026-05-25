from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
import db
from config import BACKUP_DIR, EXCEL_PATH
from services import backup_service
from ui.formatting import dataframe_visible, texto_visible


def _filtros_exportacion():
    with app.st.sidebar:
        app.st.header("Filtros exportación")
        rango = app.st.date_input("Fecha", value=None, key="respaldo_fecha")
        turno = app.st.multiselect(
            "Turno",
            db.obtener_valores_distintos_columna("Turno"),
            format_func=texto_visible,
            key="respaldo_turno",
        )
        equipo = app.st.multiselect(
            "Equipo",
            db.obtener_valores_distintos_columna("Modelo equipo"),
            format_func=texto_visible,
            key="respaldo_equipo",
        )
        operador = app.st.multiselect(
            "Operador",
            db.obtener_valores_distintos_columna("Operador"),
            format_func=texto_visible,
            key="respaldo_operador",
        )
        banco = app.st.multiselect(
            "Banco",
            db.obtener_valores_distintos_columna("Banco"),
            format_func=texto_visible,
            key="respaldo_banco",
        )
        malla = app.st.multiselect(
            "Malla",
            db.obtener_valores_distintos_columna("Malla"),
            format_func=texto_visible,
            key="respaldo_malla",
        )

    fecha_desde = fecha_hasta = None
    if isinstance(rango, tuple) and len(rango) == 2:
        fecha_desde, fecha_hasta = rango

    return {
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "turno": turno,
        "equipo": equipo,
        "operador": operador,
        "banco": banco,
        "malla": malla,
    }


def _mostrar_integridad():
    app.st.subheader("Verificación de integridad")
    integridad = backup_service.verificar_integridad()
    app.st.dataframe(dataframe_visible(_dict_a_tabla(integridad)), width="stretch", hide_index=True)


def _dict_a_tabla(datos):
    import pandas as pd

    return pd.DataFrame(
        [{"criterio": clave, "valor": valor} for clave, valor in datos.items()]
    )


def _mostrar_respaldo_manual():
    app.st.subheader("Respaldo manual")
    col_sqlite, col_excel, col_pdf = app.st.columns(3)
    with col_sqlite:
        incluir_sqlite = app.st.checkbox("Base SQLite", value=True, key="backup_sqlite")
    with col_excel:
        incluir_excel = app.st.checkbox("Excel operacional", value=True, key="backup_excel")
    with col_pdf:
        incluir_pdf = app.st.checkbox("Reportes PDF", value=True, key="backup_pdf")

    if app.st.button("Generar respaldo", type="primary"):
        respaldos = backup_service.generar_respaldo_manual(
            incluir_sqlite=incluir_sqlite,
            incluir_excel=incluir_excel,
            incluir_pdf=incluir_pdf,
        )
        if not respaldos:
            app.st.warning("No se generó respaldo. Revisa que existan los archivos seleccionados.")
        else:
            app.st.success(f"Respaldo generado: {len(respaldos)} archivo(s).")
            app.st.dataframe(dataframe_visible(_dicts_a_tabla(respaldos)), width="stretch", hide_index=True)


def _dicts_a_tabla(registros):
    import pandas as pd

    return pd.DataFrame(
        [{"tipo": item["tipo"], "ruta": str(item["ruta"])} for item in registros]
    )


def _mostrar_exportaciones(filtros):
    app.st.subheader("Exportaciones")

    col_datos, col_auditoria, col_contrato = app.st.columns(3)
    with col_datos:
        if app.st.button("Exportar datos filtrados", key="exportar_datos_filtrados"):
            destino, df = backup_service.exportar_datos_filtrados_excel(filtros)
            app.st.session_state["export_datos_path"] = str(destino)
            app.st.session_state["export_datos_bytes"] = backup_service.dataframe_a_excel_bytes(df)
            app.st.session_state["export_datos_count"] = len(df)
        if "export_datos_bytes" in app.st.session_state:
            app.st.download_button(
                "Descargar datos filtrados",
                data=app.st.session_state["export_datos_bytes"],
                file_name=Path(app.st.session_state["export_datos_path"]).name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            app.st.caption(f"Registros exportados: {app.st.session_state.get('export_datos_count', 0)}")

    with col_auditoria:
        if app.st.button("Exportar auditoría", key="exportar_auditoria"):
            destino, df = backup_service.exportar_auditoria_ediciones_excel()
            app.st.session_state["export_auditoria_path"] = str(destino)
            app.st.session_state["export_auditoria_bytes"] = backup_service.dataframe_a_excel_bytes(df)
            app.st.session_state["export_auditoria_count"] = len(df)
        if "export_auditoria_bytes" in app.st.session_state:
            app.st.download_button(
                "Descargar auditoría",
                data=app.st.session_state["export_auditoria_bytes"],
                file_name=Path(app.st.session_state["export_auditoria_path"]).name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            app.st.caption(f"Auditorías exportadas: {app.st.session_state.get('export_auditoria_count', 0)}")

    with col_contrato:
        contrato = backup_service.leer_contrato_datos()
        if contrato:
            app.st.download_button(
                "Descargar contrato de datos",
                data=contrato,
                file_name="CONTRATO_DATOS.md",
                mime="text/markdown",
            )
        else:
            app.st.info("No se encontró CONTRATO_DATOS.md.")


def _mostrar_historial_respaldos():
    app.st.subheader("Historial de respaldos")
    respaldos = backup_service.listar_respaldos()
    if respaldos.empty:
        app.st.info("No hay respaldos disponibles en backup/.")
        return
    app.st.dataframe(dataframe_visible(respaldos), width="stretch", hide_index=True)


def main():
    app.st.title("Respaldos, exportación y recuperación")
    app.st.caption(
        f"Capa segura de respaldo operacional | Backup: {BACKUP_DIR} | Excel: {EXCEL_PATH.name}"
    )

    filtros = _filtros_exportacion()
    _mostrar_integridad()
    _mostrar_respaldo_manual()
    _mostrar_exportaciones(filtros)
    _mostrar_historial_respaldos()

    app.st.subheader("Recuperación")
    app.st.info("La estructura de recuperación queda preparada. La restauración automática todavía no está habilitada.")


main()
