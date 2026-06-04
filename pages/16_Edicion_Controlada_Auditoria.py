from pathlib import Path
import sys

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
from ui.page_header import render_page_header
import db
from operators import etiqueta_operador
from schema import NUMERIC_COLUMNS
from ui.formatting import dataframe_visible, texto_visible
from utils import EXCEL_PATH


CAMPOS_EDITABLES = [
    "Fecha turno",
    "Turno",
    "Modelo equipo",
    "Número equipo",
    "Operador",
    "Código operador",
    "Área operacional",
    "Petróleo litros",
    "Horómetro inicial",
    "Horómetro final",
    "Diferencia horómetro",
    "Horas de motor",
    "Banco",
    "Malla",
    "Fase",
    "Tipo de perforación",
    "Número precorte",
    "Número serie Tricono/Bit",
    "Condición del terreno",
    "Tipo detención",
    "Horas detención mecánica",
    "Horas detención No efectivas",
    "Horas efectivas perforando",
    "Combustible",
    "Relleno de agua",
    "Colación",
    "Traslado",
    "Standby por falta de tajo/Patio",
    "Tronadura",
    "Mantención Programada",
    "Cambio de aceros",
    "Avería",
    "Cambio turno",
    "Falta operador",
    "Otros",
    "Total horas ingresadas",
    "Metros perforados",
    "Pozos perforados turno",
    "Rendimiento m/h",
    "Disponibilidad %",
    "Utilización",
    "Observaciones",
    "Estatus del Equipo",
]


def _filtros_edicion():
    with app.st.sidebar:
        app.st.header("Buscar registros")
        rango = app.st.date_input("Fecha", value=None, key="edicion_fecha")
        turno = app.st.multiselect(
            "Turno",
            db.obtener_valores_distintos_columna("Turno"),
            format_func=texto_visible,
            key="edicion_turno",
        )
        equipo = app.st.multiselect(
            "Equipo",
            db.obtener_valores_distintos_columna("Modelo equipo"),
            format_func=texto_visible,
            key="edicion_equipo",
        )
        operador = app.st.multiselect(
            "Operador",
            db.obtener_valores_distintos_columna("Operador"),
            format_func=lambda valor: texto_visible(etiqueta_operador(valor)),
            key="edicion_operador",
        )
        malla = app.st.multiselect(
            "Malla",
            db.obtener_valores_distintos_columna("Malla"),
            format_func=texto_visible,
            key="edicion_malla",
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
        "malla": malla,
    }


def _opcion_registro(fila):
    partes = [
        f"ID {fila.get('id', '')}",
        str(fila.get("Fecha turno", "")),
        texto_visible(fila.get("Turno", "")),
        texto_visible(fila.get("Modelo equipo", "")),
        texto_visible(fila.get("Número equipo", "")),
        texto_visible(fila.get("Operador", "")),
        texto_visible(fila.get("Malla", "")),
    ]
    return " | ".join(parte for parte in partes if str(parte).strip())


def _valor_inicial(registro, campo):
    valor = registro.get(campo, "")
    if pd.isna(valor):
        return 0.0 if campo in NUMERIC_COLUMNS else ""
    return valor


def _campo_editor(campo, valor):
    key = f"edicion_campo_{campo}"
    if campo in NUMERIC_COLUMNS:
        numero = pd.to_numeric(pd.Series([valor]), errors="coerce").fillna(0).iloc[0]
        return app.st.number_input(texto_visible(campo), value=float(numero), step=0.25, key=key)
    if campo == "Observaciones":
        return app.st.text_area(texto_visible(campo), value=texto_visible(valor), height=120, key=key)
    return app.st.text_input(texto_visible(campo), value=texto_visible(valor), key=key)


def _mostrar_formulario_edicion(registro):
    registro_id = int(registro["id"])
    app.st.subheader("Registro seleccionado")
    columnas_resumen = [
        "id",
        "Fecha turno",
        "Turno",
        "Modelo equipo",
        "Número equipo",
        "Operador",
        "Banco",
        "Malla",
        "Metros perforados",
        "Total horas ingresadas",
    ]
    disponibles = [col for col in columnas_resumen if col in registro]
    app.st.dataframe(dataframe_visible(pd.DataFrame([{col: registro.get(col) for col in disponibles}])), width="stretch", hide_index=True)

    with app.st.expander("Ver registro completo antes de editar", expanded=False):
        visible = {k: v for k, v in registro.items() if k not in {"created_at", "updated_at", "source", "source_row"}}
        app.st.dataframe(dataframe_visible(pd.DataFrame([visible])), width="stretch", hide_index=True)

    app.st.subheader("Editar campos operacionales")
    campos_presentes = [campo for campo in CAMPOS_EDITABLES if campo in registro]
    cambios = {}
    with app.st.form("form_edicion_auditada", clear_on_submit=False):
        columnas = app.st.columns(3)
        for indice, campo in enumerate(campos_presentes):
            with columnas[indice % 3]:
                cambios[campo] = _campo_editor(campo, _valor_inicial(registro, campo))

        motivo = app.st.text_area(
            "Motivo obligatorio de edición",
            height=110,
            placeholder="Describe por qué se corrige este registro.",
            key="edicion_motivo",
        )
        guardar = app.st.form_submit_button("Guardar edición auditada", type="primary")

    if not guardar:
        return

    if not str(motivo or "").strip():
        app.st.error("No se permite editar sin motivo de edición.")
        return

    try:
        resultado = db.actualizar_registro_auditado(
            registro_id,
            cambios,
            motivo,
            usuario="streamlit",
            sync_excel=True,
        )
    except Exception as exc:
        app.st.error(f"No fue posible guardar la edición: {texto_visible(exc)}")
        return

    if resultado["actualizados"] <= 0:
        app.st.info("No se detectaron cambios para guardar.")
        return

    try:
        app.limpiar_cache_reportes()
    except Exception:
        pass
    app.st.success(f"Edición guardada. Campos auditados: {resultado['auditoria']}.")
    app.st.rerun()


def _mostrar_auditoria(registro_id):
    app.st.subheader("Auditoría del registro")
    auditoria = db.leer_auditoria_ediciones(registro_id)
    if auditoria.empty:
        app.st.info("Este registro todavía no tiene ediciones auditadas.")
        return
    app.st.dataframe(dataframe_visible(auditoria), width="stretch", hide_index=True)


def main():
    if not app.requerir_acceso(admin=True):
        return
    render_page_header(app.st, "Edición Controlada")
    app.st.caption(
        f"Edición trazable de registros históricos | SQLite oficial y respaldo Excel: {EXCEL_PATH.name}"
    )

    filtros = _filtros_edicion()
    resultados = db.consultar_registros_edicion(**filtros)
    app.st.subheader("Resultados de búsqueda")
    if resultados.empty:
        app.st.info("No hay registros que coincidan con los filtros.")
        return

    columnas_resultado = [
        col
        for col in [
            "id",
            "Fecha turno",
            "Turno",
            "Modelo equipo",
            "Número equipo",
            "Operador",
            "Banco",
            "Malla",
            "Metros perforados",
            "Total horas ingresadas",
        ]
        if col in resultados.columns
    ]
    app.st.dataframe(dataframe_visible(resultados[columnas_resultado]), width="stretch", hide_index=True)

    opciones = {
        _opcion_registro(fila): int(fila["id"])
        for _, fila in resultados.iterrows()
        if "id" in fila and pd.notna(fila["id"])
    }
    if not opciones:
        app.st.error("Los resultados no incluyen ID de registro. No es posible editar.")
        return

    seleccion = app.st.selectbox("Registro a editar", list(opciones.keys()), key="edicion_registro_id")
    registro_id = opciones[seleccion]
    registro = db.obtener_registro_por_id(registro_id)
    if not registro:
        app.st.error("No fue posible cargar el registro seleccionado.")
        return

    _mostrar_formulario_edicion(registro)
    _mostrar_auditoria(registro_id)


main()

