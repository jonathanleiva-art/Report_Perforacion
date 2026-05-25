from datetime import date, timedelta
from pathlib import Path
import sys

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
import db
from services import corrective_actions_service, data_quality_service
from ui.formatting import dataframe_visible, texto_visible


ESTADOS = ["Pendiente", "En revisión", "Corregido", "Cerrado"]
PRIORIDADES = ["Baja", "Media", "Alta", "Crítica"]


def _opciones_acciones(columna):
    try:
        return corrective_actions_service.obtener_valores_distintos_acciones(columna)
    except Exception:
        return []


def _filtros_sidebar():
    with app.st.sidebar:
        app.st.header("Filtros")
        equipos = _opciones_acciones("equipo")
        responsables = _opciones_acciones("responsable")
        estados = _opciones_acciones("estado") or ESTADOS
        prioridad = _opciones_acciones("prioridad") or PRIORIDADES

        equipo = app.st.multiselect(
            "Equipo",
            equipos,
            default=equipos,
            format_func=texto_visible,
            key="acciones_equipo",
        )
        estado = app.st.multiselect(
            "Estado",
            estados,
            default=estados,
            format_func=texto_visible,
            key="acciones_estado",
        )
        responsable = app.st.multiselect(
            "Responsable",
            responsables,
            default=responsables,
            format_func=texto_visible,
            key="acciones_responsable",
        )
        prioridad_filtrada = app.st.multiselect(
            "Prioridad",
            prioridad,
            default=prioridad,
            format_func=texto_visible,
            key="acciones_prioridad",
        )

    return {
        "equipo": equipo,
        "estado": estado,
        "responsable": responsable,
        "prioridad": prioridad_filtrada,
    }


def _kpis(resumen):
    c1, c2, c3, c4 = app.st.columns(4)
    c1.metric("Pendientes", resumen["pendientes"])
    c2.metric("Vencidas", resumen["vencidas"])
    c3.metric("Cerradas", resumen["cerradas"])
    c4.metric("Críticas", resumen["criticas"])


def _prioridad_semaforo(df):
    conteos = {prioridad: 0 for prioridad in PRIORIDADES}
    if not df.empty and "prioridad" in df.columns:
        for prioridad in PRIORIDADES:
            conteos[prioridad] = int((df["prioridad"].astype(str) == prioridad).sum())

    estilos = {
        "Baja": "#16A34A",
        "Media": "#2563EB",
        "Alta": "#D97706",
        "Crítica": "#DC2626",
    }
    cols = app.st.columns(4)
    for col, prioridad in zip(cols, PRIORIDADES):
        color = estilos[prioridad]
        col.markdown(
            f"""
            <div style="border-left: 6px solid {color}; padding: 0.65rem 0.9rem; background: #f8fafc; min-height: 76px;">
                <div style="font-size: 0.85rem; color: #64748b;">Prioridad</div>
                <div style="font-size: 1.15rem; font-weight: 700; color: #0f172a;">{prioridad}</div>
                <div style="font-size: 1.4rem; font-weight: 700; color: {color};">{conteos[prioridad]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _formulario_registro():
    with app.st.form("form_accion_correctiva", clear_on_submit=True):
        app.st.subheader("Registrar acción correctiva")
        col1, col2 = app.st.columns(2)
        with col1:
            fecha = app.st.date_input("Fecha", value=date.today(), key="accion_fecha")
            equipo = app.st.text_input("Equipo", key="accion_equipo_txt")
            operador = app.st.text_input("Operador", key="accion_operador_txt")
            tipo_problema = app.st.text_input("Tipo problema", key="accion_tipo_problema")
            responsable = app.st.text_input("Responsable", key="accion_responsable")
        with col2:
            prioridad = app.st.selectbox("Prioridad", PRIORIDADES, index=2, key="accion_prioridad")
            fecha_compromiso = app.st.date_input(
                "Fecha compromiso",
                value=date.today() + timedelta(days=3),
                key="accion_fecha_compromiso",
            )
            estado = app.st.selectbox("Estado", ESTADOS, index=0, key="accion_estado")
            descripcion_problema = app.st.text_area("Descripción problema", key="accion_descripcion", height=110)
            accion_correctiva = app.st.text_area("Acción correctiva", key="accion_correctiva", height=110)
        observacion_final = app.st.text_area("Observación final", key="accion_observacion_final", height=90)
        submitted = app.st.form_submit_button("Registrar acción")

    if submitted:
        try:
            accion = corrective_actions_service.registrar_accion_correctiva(
                {
                    "fecha": fecha,
                    "equipo": equipo,
                    "operador": operador,
                    "tipo_problema": tipo_problema,
                    "descripcion_problema": descripcion_problema,
                    "accion_correctiva": accion_correctiva,
                    "responsable": responsable,
                    "prioridad": prioridad,
                    "fecha_compromiso": fecha_compromiso,
                    "estado": estado,
                    "observacion_final": observacion_final,
                }
            )
            app.st.success(f"Acción registrada con ID {accion.get('id')}.")
            app.st.rerun()
        except Exception as exc:
            app.st.error(f"No fue posible registrar la acción: {exc}")


def _carga_observaciones_calidad():
    app.st.subheader("Generar acción desde Calidad de Datos")
    if app.st.button("Cargar observaciones de calidad", key="acciones_cargar_calidad"):
        df_base = db.consultar_historial_filtrado()
        resultado = data_quality_service.evaluar_calidad_datos(df=df_base)
        app.st.session_state["acciones_correctivas_observaciones_calidad"] = resultado.get("detalle", pd.DataFrame())
        app.st.success("Observaciones de calidad cargadas.")

    observaciones = app.st.session_state.get("acciones_correctivas_observaciones_calidad", pd.DataFrame())
    if observaciones is None or observaciones.empty:
        app.st.info("Carga observaciones de calidad para crear acciones desde hallazgos detectados.")
        return

    observaciones = observaciones.copy()
    observaciones = observaciones[observaciones["Estado"].astype(str).isin(["ERROR", "WARNING"])] if "Estado" in observaciones.columns else observaciones
    if observaciones.empty:
        app.st.info("No hay observaciones críticas o de advertencia disponibles.")
        return

    observaciones = observaciones.head(50).reset_index(drop=True)
    opciones = {
        f"{idx + 1}. {fila.get('Regla', '')} | {fila.get('Estado', '')} | {fila.get('Fecha turno', '')} | {fila.get('Modelo equipo', '')} | {fila.get('Operador', '')}": fila.to_dict()
        for idx, (_, fila) in enumerate(observaciones.iterrows())
    }
    seleccion = app.st.selectbox(
        "Observación detectada",
        list(opciones.keys()),
        key="acciones_observacion_calidad",
    )
    observacion = opciones[seleccion]
    app.st.dataframe(
        dataframe_visible(pd.DataFrame([observacion])),
        width="stretch",
        hide_index=True,
    )
    col1, col2 = app.st.columns(2)
    with col1:
        responsable = app.st.text_input("Responsable derivado", value=str(observacion.get("Operador", "")), key="acciones_resp_calidad")
    with col2:
        prioridad = app.st.selectbox("Prioridad derivada", PRIORIDADES, index=3 if observacion.get("Estado") == "ERROR" else 2, key="acciones_prio_calidad")

    if app.st.button("Crear acción desde observación", key="acciones_crear_desde_calidad"):
        try:
            accion = corrective_actions_service.crear_accion_desde_observacion(
                observacion,
                responsable=responsable,
                prioridad=prioridad,
            )
            app.st.success(f"Acción creada desde observación con ID {accion.get('id')}.")
            app.st.rerun()
        except Exception as exc:
            app.st.error(f"No fue posible crear la acción desde la observación: {exc}")


def _edicion_estado(df):
    app.st.subheader("Seguimiento y edición de estado")
    if df.empty:
        app.st.info("No hay acciones para editar.")
        return

    opciones = {
        f"#{int(fila['id'])} | {fila.get('equipo', '')} | {fila.get('tipo_problema', '')} | {fila.get('estado', '')}": int(fila["id"])
        for _, fila in df.iterrows()
        if "id" in fila
    }
    if not opciones:
        app.st.info("No se encontraron acciones editables.")
        return

    seleccion = app.st.selectbox("Acción a revisar", list(opciones.keys()), key="acciones_editar_select")
    accion = corrective_actions_service.obtener_accion_por_id(opciones[seleccion])
    if not accion:
        app.st.warning("No fue posible cargar la acción seleccionada.")
        return

    app.st.dataframe(dataframe_visible(pd.DataFrame([accion])), width="stretch", hide_index=True)
    col1, col2 = app.st.columns(2)
    with col1:
        nuevo_estado = app.st.selectbox("Nuevo estado", ESTADOS, index=ESTADOS.index(accion.get("estado", "Pendiente")) if accion.get("estado", "Pendiente") in ESTADOS else 0, key="acciones_editar_estado")
    with col2:
        observacion_final = app.st.text_area("Observación final", value=accion.get("observacion_final", ""), key="acciones_editar_obs", height=100)
    if app.st.button("Actualizar estado", key="acciones_actualizar_estado"):
        try:
            afectadas = corrective_actions_service.actualizar_estado_accion(
                accion["id"],
                nuevo_estado,
                observacion_final=observacion_final,
            )
            app.st.success(f"Acciones actualizadas: {afectadas}")
            app.st.rerun()
        except Exception as exc:
            app.st.error(f"No fue posible actualizar el estado: {exc}")


def _tabla_historial(df):
    app.st.subheader("Historial operativo")
    if df.empty:
        app.st.info("No hay acciones correctivas para los filtros seleccionados.")
        return

    columnas = [
        col
        for col in [
            "id",
            "fecha",
            "equipo",
            "operador",
            "tipo_problema",
            "descripcion_problema",
            "accion_correctiva",
            "responsable",
            "prioridad",
            "fecha_compromiso",
            "estado",
            "vencida",
            "dias_para_compromiso",
        ]
        if col in df.columns
    ]
    app.st.dataframe(
        dataframe_visible(df[columnas]),
        width="stretch",
        hide_index=True,
        column_config={
            "prioridad": app.st.column_config.TextColumn("prioridad", pinned=True),
            "estado": app.st.column_config.TextColumn("estado", pinned=True),
        },
    )


def main():
    app.st.title("Acciones correctivas operacionales")
    app.st.caption(
        f"Seguimiento de acciones derivadas de alertas operacionales y calidad de datos | Base SQLite: {db.DB_PATH.name}"
    )

    filtros = _filtros_sidebar()
    df = corrective_actions_service.listar_acciones_correctivas(
        equipo=filtros["equipo"],
        estado=filtros["estado"],
        responsable=filtros["responsable"],
        prioridad=filtros["prioridad"],
    )
    resumen = corrective_actions_service.resumen_acciones_correctivas()

    _kpis(resumen)
    app.st.divider()
    _prioridad_semaforo(df)
    app.st.divider()

    _formulario_registro()
    app.st.divider()
    _carga_observaciones_calidad()
    app.st.divider()

    _edicion_estado(df)
    app.st.divider()
    _tabla_historial(df)


main()
