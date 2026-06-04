import pandas as pd
import streamlit as st

import db
from data import leer_reportes_sqlite
from services import ciclos_service, operational_excel_service


FUENTE_MANUAL = "Registros manuales SQLite"
FUENTE_CICLOS = "Ciclos de Perforacion Excel"
FUENTE_TODOS_EXCEL = "Todos los Excel importados"

CLAVES_FILTROS_DASHBOARD = [
    "dashboard_fecha",
    "dashboard_equipos",
    "dashboard_operadores",
    "dashboard_turnos",
    "dashboard_tipos_detencion",
    "dashboard_bancos",
    "dashboard_mallas",
    "dashboard_fases",
    "dashboard_tipos_perforacion",
    "dashboard_sql_filters",
    "dashboard_filter_diagnostics",
]


def _opciones_fuentes_excel():
    fuentes_excel = ciclos_service.listar_fuentes_datos(db_path=db.DB_PATH, solo_activas=True)
    fuentes_operacionales = operational_excel_service.listar_fuentes_operacionales(db_path=db.DB_PATH, solo_activas=True)
    opciones = [FUENTE_MANUAL, FUENTE_TODOS_EXCEL]
    ids_por_opcion = {FUENTE_MANUAL: None, FUENTE_TODOS_EXCEL: None}
    tipos_por_opcion = {FUENTE_MANUAL: "manual", FUENTE_TODOS_EXCEL: "ciclos"}
    if fuentes_excel.empty and fuentes_operacionales.empty:
        opciones.append(FUENTE_CICLOS)
        ids_por_opcion[FUENTE_CICLOS] = None
        tipos_por_opcion[FUENTE_CICLOS] = "ciclos"
        return opciones, ids_por_opcion, tipos_por_opcion

    fuentes_ciclos = fuentes_excel[fuentes_excel.get("tipo_fuente").astype(str).eq("excel_ciclos")] if not fuentes_excel.empty else fuentes_excel
    for _, fila in fuentes_ciclos.iterrows():
        nombre = str(fila.get("nombre_fuente") or "").strip()
        if not nombre:
            nombre = f"Ciclos de Perforacion Excel - {int(fila['id_fuente'])}"
        opciones.append(nombre)
        ids_por_opcion[nombre] = int(fila["id_fuente"])
        tipos_por_opcion[nombre] = "ciclos"

    if not fuentes_operacionales.empty:
        for _, fila in fuentes_operacionales.iterrows():
            nombre = str(fila.get("nombre_fuente") or "").strip()
            if not nombre:
                nombre = f"Excel operacional - {int(fila['id_fuente'])}"
            opciones.append(nombre)
            ids_por_opcion[nombre] = int(fila["id_fuente"])
            tipos_por_opcion[nombre] = "excel_operacional"
    return opciones, ids_por_opcion, tipos_por_opcion


def seleccionar_fuente_datos(st_module, *, key="fuente_datos_operacional"):
    opciones, ids_por_opcion, tipos_por_opcion = _opciones_fuentes_excel()
    fuente = st_module.sidebar.radio(
        "Fuente de datos",
        opciones,
        index=0,
        key=key,
        help="Manual usa registros_perforacion. Cada Excel importado queda registrado como fuente y puede analizarse por separado.",
    )
    id_fuente = ids_por_opcion.get(fuente)
    origen = tipos_por_opcion.get(fuente, "manual" if fuente == FUENTE_MANUAL else "ciclos")
    origen_anterior = st_module.session_state.get("dashboard_data_source")
    fuente_anterior = st_module.session_state.get("dashboard_data_source_id")
    if origen_anterior and (origen_anterior != origen or fuente_anterior != id_fuente):
        for clave in CLAVES_FILTROS_DASHBOARD:
            st_module.session_state.pop(clave, None)
    st_module.session_state["dashboard_data_source"] = origen
    st_module.session_state["dashboard_data_source_id"] = id_fuente
    st_module.session_state["dashboard_data_source_label"] = fuente
    return fuente


def cargar_dataframe_fuente(fuente):
    origen = st.session_state.get("dashboard_data_source")
    if origen == "excel_operacional":
        id_fuente = st.session_state.get("dashboard_data_source_id")
        return operational_excel_service.leer_operacional_dashboard(db_path=db.DB_PATH, id_fuente=id_fuente)
    if fuente != FUENTE_MANUAL:
        id_fuente = st.session_state.get("dashboard_data_source_id")
        solo_activas = id_fuente is None
        df = ciclos_service.leer_ciclos_operacional(
            db_path=db.DB_PATH,
            id_fuente=id_fuente,
            solo_activas=solo_activas,
        )
        if df.empty and fuente in {FUENTE_CICLOS, FUENTE_TODOS_EXCEL}:
            ciclos_service.importar_excel_ciclos(db_path=db.DB_PATH)
            df = ciclos_service.leer_ciclos_operacional(
                db_path=db.DB_PATH,
                id_fuente=id_fuente,
                solo_activas=solo_activas,
            )
        elif not df.empty:
            ciclos_service.sincronizar_operadores_ciclos(db_path=db.DB_PATH)
            df = ciclos_service.leer_ciclos_operacional(
                db_path=db.DB_PATH,
                id_fuente=id_fuente,
                solo_activas=solo_activas,
            )
        return df
    return leer_reportes_sqlite(db_path=db.DB_PATH)


def resumen_fuente(df):
    if df is None or df.empty:
        return {"registros": 0, "operadores": 0, "equipos": 0}
    operador_col = "operador_display" if "operador_display" in df.columns else "Operador"
    equipo_col = "Equipo" if "Equipo" in df.columns else "Numero equipo"
    return {
        "registros": int(len(df)),
        "operadores": int(pd.Series(df.get(operador_col, pd.Series(dtype=str))).dropna().astype(str).str.strip().loc[lambda s: s.ne("")].nunique()),
        "equipos": int(pd.Series(df.get(equipo_col, pd.Series(dtype=str))).dropna().astype(str).str.strip().loc[lambda s: s.ne("")].nunique()),
    }
