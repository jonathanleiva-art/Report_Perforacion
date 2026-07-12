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
from services import catalog_service
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


def _opciones_filtro(columna):
    valores = db.obtener_valores_distintos_columna(columna)
    return ["Todos", *[valor for valor in valores if str(valor or "").strip()]]


def _valor_filtro(valor):
    return None if valor in (None, "", "Todos") else valor


def _limpiar_filtros_edicion():
    for key in [
        "edicion_fecha_desde",
        "edicion_fecha_hasta",
        "edicion_turno",
        "edicion_modelo_equipo",
        "edicion_numero_equipo",
        "edicion_operador",
        "edicion_banco",
        "edicion_malla",
        "edicion_buscar_id",
        "edicion_registro_id",
    ]:
        app.st.session_state.pop(key, None)


def _render_filtros_resultados():
    if app.st.button("Limpiar filtros", key="edicion_limpiar_filtros"):
        _limpiar_filtros_edicion()
        app.st.rerun()

    fila_1 = app.st.columns(4)
    with fila_1[0]:
        fecha_desde = app.st.date_input("Fecha turno desde", value=None, key="edicion_fecha_desde")
    with fila_1[1]:
        fecha_hasta = app.st.date_input("Fecha turno hasta", value=None, key="edicion_fecha_hasta")
    with fila_1[2]:
        turno = app.st.selectbox("Turno", ["Todos", "Día", "Noche"], key="edicion_turno")
    with fila_1[3]:
        buscar_id = app.st.text_input("Buscar por ID", key="edicion_buscar_id")

    fila_2 = app.st.columns(5)
    with fila_2[0]:
        modelo = app.st.selectbox("Modelo equipo", _opciones_filtro("Modelo equipo"), key="edicion_modelo_equipo")
    with fila_2[1]:
        numero = app.st.selectbox("Número equipo", _opciones_filtro("Número equipo"), key="edicion_numero_equipo")
    with fila_2[2]:
        operador = app.st.selectbox(
            "Operador",
            _opciones_filtro("Operador"),
            format_func=lambda valor: texto_visible(etiqueta_operador(valor)) if valor != "Todos" else "Todos",
            key="edicion_operador",
        )
    with fila_2[3]:
        banco = app.st.selectbox("Banco", _opciones_filtro("Banco"), key="edicion_banco")
    with fila_2[4]:
        malla = app.st.selectbox("Malla", _opciones_filtro("Malla"), key="edicion_malla")

    return {
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "turno": _valor_filtro(turno),
        "modelo_equipo": _valor_filtro(modelo),
        "numero_equipo": _valor_filtro(numero),
        "operador": _valor_filtro(operador),
        "banco": _valor_filtro(banco),
        "malla": _valor_filtro(malla),
        "registro_id": str(buscar_id or "").strip(),
    }


def _consultar_resultados_edicion(filtros, limit=500):
    path = Path(db.DB_PATH)
    if not path.exists():
        return pd.DataFrame()

    condiciones = ["1=1"]
    parametros = []

    def agregar_igual(columna, valor):
        if valor not in (None, ""):
            condiciones.append(f'"{columna}" = ?')
            parametros.append(str(valor))

    if filtros.get("fecha_desde") is not None:
        condiciones.append('date("Fecha turno") >= date(?)')
        parametros.append(str(filtros["fecha_desde"]))
    if filtros.get("fecha_hasta") is not None:
        condiciones.append('date("Fecha turno") <= date(?)')
        parametros.append(str(filtros["fecha_hasta"]))

    registro_id = filtros.get("registro_id")
    if registro_id:
        if registro_id.isdigit():
            condiciones.append("id = ?")
            parametros.append(int(registro_id))
        else:
            return pd.DataFrame()

    agregar_igual("Turno", filtros.get("turno"))
    agregar_igual("Modelo equipo", filtros.get("modelo_equipo"))
    agregar_igual("Número equipo", filtros.get("numero_equipo"))
    agregar_igual("Operador", filtros.get("operador"))
    agregar_igual("Banco", filtros.get("banco"))
    agregar_igual("Malla", filtros.get("malla"))

    try:
        with db.conectar_db(path) as connection:
            db.crear_tablas(db_path=path)
            columnas = db.columnas_tabla(connection)
            data_columns = [col for col in columnas if col not in db.TECHNICAL_COLUMNS]
            select_columns = ["id", *data_columns]
            query = (
                f"SELECT {', '.join(db.quote_identifier(col) for col in select_columns)} "
                f"FROM {db.quote_identifier(db.TABLA_REGISTROS)} "
                f"WHERE {' AND '.join(condiciones)} ORDER BY id DESC LIMIT ?"
            )
            df = pd.read_sql_query(query, connection, params=[*parametros, int(limit)])
    except Exception:
        return pd.DataFrame()

    from data import preparar_dataframe
    return preparar_dataframe(df)


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
    import datetime
    from operators import cargar_mapa_operadores
    key = f"edicion_campo_{campo}"

    # ── Fecha turno ──────────────────────────────
    if campo == "Fecha turno":
        ss_val = app.st.session_state.get(key)
        if isinstance(ss_val, str):
            try:
                parsed = pd.to_datetime(ss_val, errors="coerce")
                app.st.session_state[key] = parsed.date() if pd.notna(parsed) else datetime.date.today()
            except Exception:
                app.st.session_state[key] = datetime.date.today()
        try:
            fecha = pd.to_datetime(valor, errors="coerce")
            val_fecha = fecha.date() if pd.notna(fecha) else datetime.date.today()
        except Exception:
            val_fecha = datetime.date.today()
        return app.st.date_input(texto_visible(campo), value=val_fecha, key=key)

    # ── Turno ────────────────────────────────────
    if campo == "Turno":
        opciones = ["Día", "Noche"]
        val = texto_visible(str(valor or ""))
        idx = opciones.index(val) if val in opciones else 0
        return app.st.selectbox(texto_visible(campo), opciones, index=idx, key=key)

    # ── Modelo equipo ────────────────────────────
    if campo == "Modelo equipo":
        opciones = ["FlexiROC D65", "SmartROC D65", "Sandvik D75KS"]
        val = texto_visible(str(valor or ""))
        idx = opciones.index(val) if val in opciones else 0
        return app.st.selectbox(texto_visible(campo), opciones, index=idx, key=key)

    # ── Número equipo ────────────────────────────
    if campo == "Número equipo":
        opciones = catalog_service.FLOTA_EQUIPOS
        val = str(valor or "").strip()
        idx = opciones.index(val) if val in opciones else 0
        return app.st.selectbox(texto_visible(campo), opciones, index=idx, key=key)

    # ── Operador con autocompletado de código ────
    if campo == "Operador":
        mapa = cargar_mapa_operadores()
        nombres = sorted(set(mapa.values()))
        val = texto_visible(str(valor or ""))
        idx = nombres.index(val) if val in nombres else 0
        seleccionado = app.st.selectbox(texto_visible(campo), nombres, index=idx, key=key)
        codigo_auto = next((k for k, v in mapa.items() if v == seleccionado), "")
        app.st.session_state[f"codigo_auto_{key}"] = codigo_auto
        return seleccionado

    # ── Código operador (derivado del Operador seleccionado) ──
    if campo == "Código operador":
        operador_key = "codigo_auto_edicion_campo_Operador"
        codigo = app.st.session_state.get(operador_key, texto_visible(str(valor or "")))
        app.st.session_state[key] = codigo
        return app.st.text_input(texto_visible(campo), value=codigo, disabled=True, key=key)

    # ── Área operacional ─────────────────────────
    if campo == "Área operacional":
        raw = db.obtener_valores_distintos_columna("Área operacional")
        opciones = sorted({str(o).strip() for o in raw if str(o).strip()})
        if not opciones:
            return app.st.text_input(texto_visible(campo), value=str(valor or "").strip(), key=key)
        val = str(valor or "").strip()
        idx = opciones.index(val) if val in opciones else 0
        return app.st.selectbox(texto_visible(campo), opciones, index=idx, key=key)

    # ── Campos numéricos ─────────────────────────
    if campo in NUMERIC_COLUMNS:
        numero = pd.to_numeric(pd.Series([valor]), errors="coerce").fillna(0).iloc[0]
        return app.st.number_input(texto_visible(campo), value=float(numero), step=0.25, key=key)

    # ── Observaciones ────────────────────────────
    if campo == "Observaciones":
        return app.st.text_area(texto_visible(campo), value=texto_visible(valor), height=120, key=key)

    # ── Resto de campos ──────────────────────────
    return app.st.text_input(texto_visible(campo), value=texto_visible(valor), key=key)


def _mostrar_formulario_edicion(registro):
    registro_id = int(registro["id"])

    if app.st.session_state.get("_edit_id_cargado") != registro_id:
        for campo in CAMPOS_EDITABLES:
            if campo in registro:
                val = _valor_inicial(registro, campo)
                if campo in NUMERIC_COLUMNS:
                    app.st.session_state[f"edicion_campo_{campo}"] = float(
                        pd.to_numeric(pd.Series([val]), errors="coerce").fillna(0).iloc[0]
                    )
                else:
                    app.st.session_state[f"edicion_campo_{campo}"] = texto_visible(val)
        app.st.session_state["edicion_motivo"] = ""
        app.st.session_state["_edit_id_cargado"] = registro_id

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

    app.st.subheader("Resultados de búsqueda")
    filtros = _render_filtros_resultados()
    resultados = _consultar_resultados_edicion(filtros)

    if resultados.empty:
        app.st.info("No hay registros para los filtros seleccionados.")
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

    opciones_labels = list(opciones.keys())
    if app.st.session_state.get("edicion_registro_id") not in opciones_labels:
        app.st.session_state.pop("edicion_registro_id", None)

    seleccion = app.st.selectbox("Registro a editar", opciones_labels, key="edicion_registro_id")
    registro_id = opciones[seleccion]
    registro = db.obtener_registro_por_id(registro_id)
    if not registro:
        app.st.error("No fue posible cargar el registro seleccionado.")
        return

    _mostrar_formulario_edicion(registro)
    _mostrar_auditoria(registro_id)


main()

