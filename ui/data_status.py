from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from openpyxl import load_workbook

from audit import audit_log
from data import limpiar_cache_reportes, preparar_dataframe
from ui.formatting import dataframe_visible
from config import BACKUPS_SQLITE_DIR
from services import backup_service
from utils import EXCEL_PATH


def _archivo_mtime(path):
    ruta = Path(path)
    return ruta.stat().st_mtime if ruta.exists() else 0


@st.cache_data(show_spinner=False)
def _contar_registros_excel_cached(path_text, mtime):
    path = Path(path_text)
    if not path.exists():
        return 0

    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
    except Exception:
        return 0

    try:
        hoja = workbook.active
        return max((hoja.max_row or 0) - 1, 0)
    finally:
        workbook.close()


def contar_registros_excel(path):
    ruta = Path(path)
    return _contar_registros_excel_cached(str(ruta.resolve()), _archivo_mtime(ruta))


def resumen_contrato_columnas(integridad):
    fuentes = [
        ("SQLite", integridad.get("columnas_no_canonicas_sqlite", []), integridad.get("columnas_extra_sqlite", [])),
        ("Excel", integridad.get("columnas_no_canonicas_excel", []), integridad.get("columnas_extra_excel", [])),
    ]
    filas = []
    for fuente, no_canonicas, extras in fuentes:
        for item in no_canonicas:
            filas.append({
                "Fuente": fuente,
                "Tipo": "No canónica",
                "Columna": item.get("columna", ""),
                "Corrección sugerida": item.get("columna_canonica", ""),
            })
        for columna in extras:
            filas.append({
                "Fuente": fuente,
                "Tipo": "Extra",
                "Columna": columna,
                "Corrección sugerida": "Revisar si debe agregarse al contrato",
            })
    return pd.DataFrame(filas, columns=["Fuente", "Tipo", "Columna", "Corrección sugerida"])


def renderizar_estado_contrato_columnas(st_module, integridad):
    resumen = resumen_contrato_columnas(integridad)
    if resumen.empty:
        st_module.caption("Contrato de columnas: OK, sin encabezados fuera de estándar.")
        return resumen

    st_module.warning("Se detectaron columnas fuera del contrato oficial.")
    st_module.dataframe(dataframe_visible(resumen), width="stretch", hide_index=True)
    return resumen


def mostrar_estado_datos(df_reportes):
    with st.expander("Estado de datos SQLite / Excel", expanded=True):
        try:
            import db

            existe_db = db.DB_PATH.exists()
            registros_excel = contar_registros_excel(EXCEL_PATH)
            registros_sqlite = db.contar_registros() if existe_db else 0
            duplicados_detectados = db.contar_duplicados_operacionales() if existe_db else 0
            integridad = backup_service.verificar_integridad(db_path=db.DB_PATH, excel_path=EXCEL_PATH)
            coincide = registros_excel == registros_sqlite

            st.caption(f"Ruta oficial del proyecto: {EXCEL_PATH.parent}")
            st.caption(f"Base SQLite conectada: {db.DB_PATH}")
            st.caption(f"Excel de respaldo/exportación: {EXCEL_PATH}")

            col_a, col_b, col_c, col_d, col_e, col_f = st.columns(6)
            col_a.metric("SQLite", "Conectada" if existe_db else "No existe")
            col_b.metric("Registros app", f"{len(df_reportes):,}")
            col_c.metric("Registros SQLite", f"{registros_sqlite:,}")
            col_d.metric("Registros Excel", f"{registros_excel:,}")
            col_e.metric("Estado", "OK" if coincide else "Revisar")
            col_f.metric("Duplicados", f"{duplicados_detectados:,}")

            if not coincide:
                st.warning("SQLite y Excel no tienen la misma cantidad de registros. No se borró nada; revisa antes de operar.")
            if duplicados_detectados:
                st.warning("Existen combinaciones duplicadas históricas. Nuevos duplicados quedan bloqueados; edición de registro será la opción futura.")
            else:
                st.caption("Bloqueo de duplicados activo para nuevos registros.")

            renderizar_estado_contrato_columnas(st, integridad)

            if not df_reportes.empty:
                columnas_ultimo = [
                    columna
                    for columna in ["Fecha turno", "Modelo equipo", "Número equipo", "Operador", "Turno", "Metros perforados", "Hora registro"]
                    if columna in df_reportes.columns
                ]
                st.caption("Último registro leído por la app")
                st.dataframe(dataframe_visible(df_reportes.tail(1)[columnas_ultimo]), width="stretch", hide_index=True)

            if st.button("Migrar/sincronizar Excel hacia SQLite"):
                df_actual = preparar_dataframe(pd.read_excel(EXCEL_PATH, engine="openpyxl"))
                registros = db.reemplazar_dataframe_reportes(df_actual, source="manual_excel_to_sqlite")
                audit_log.registrar_respaldo_sqlite(
                    resultado="ok",
                    detalle={"origen": "sincronizacion_manual", "registros": registros},
                )
                limpiar_cache_reportes()
                st.success(f"SQLite sincronizado correctamente: {registros:,} registros.")

            if st.button("Exportar SQLite a Excel respaldo"):
                df_sqlite = db.leer_registros()
                if df_sqlite.empty:
                    st.warning("SQLite no tiene registros para exportar.")
                else:
                    backup_dir = BACKUPS_SQLITE_DIR
                    backup_dir.mkdir(exist_ok=True)
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    export_path = backup_dir / f"respaldo_sqlite_exportado_{timestamp}.xlsx"
                    df_sqlite.to_excel(export_path, index=False)
                    st.success(f"SQLite exportado a {export_path.name}: {len(df_sqlite):,} registros.")

            backup_dir = BACKUPS_SQLITE_DIR
            st.caption("Aquí se guardan los respaldos exportados desde SQLite")
            st.code(str(backup_dir.resolve()), language=None)
            respaldos = sorted(
                backup_dir.glob("*.xlsx") if backup_dir.exists() else [],
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )[:5]
            if respaldos:
                st.dataframe(
                    dataframe_visible(pd.DataFrame(
                        [
                            {
                                "Archivo": path.name,
                                "Fecha modificación": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                                "Tamaño KB": round(path.stat().st_size / 1024, 2),
                            }
                            for path in respaldos
                        ]
                    )),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.info("No hay respaldos SQLite exportados.")
        except Exception as exc:
            st.warning(f"No se pudo verificar SQLite/Excel: {exc}")


def mostrar_estado_respaldo_sqlite(df_excel):
    mostrar_estado_datos(df_excel)
