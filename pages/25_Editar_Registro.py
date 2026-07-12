# -*- coding: utf-8 -*-
from datetime import date, timedelta
from pathlib import Path
import sys
import sqlite3

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import app_perforacion as app
import db
from schema import NUMERIC_COLUMNS
from ui.page_header import render_page_header
from ui.formatting import texto_visible
from services import catalog_service
from services.kpi_service import calcular_kpi_operacional_productivo

_EQUIPOS = catalog_service.FLOTA_EQUIPOS
_TURNOS = ["Día", "Noche"]

# Campos numéricos que no están en NUMERIC_COLUMNS del schema
_NUMERICOS_EXTRA = {
    "Metros perforados", "Horas efectivas perforando", "Avería",
    "Disponibilidad %", "Utilización", "Rendimiento m/h",
    "Horas de motor", "Horómetro inicial", "Horómetro final", "Diferencia horómetro",
    "Horas detención mecánica", "Horas detención No efectivas", "Mantención Programada",
    "Traslado", "Relleno de agua", "Colación", "Tronadura", "Cambio de aceros",
    "Cambio turno", "Falta operador", "Standby por falta de tajo/Patio",
    "Otros", "Total horas ingresadas", "Pozos perforados turno",
    "Petróleo litros", "Aceite litros", "Combustible", "Número precorte",
}
_NUMERICOS_INT = {"Pozos perforados turno", "Número precorte"}

# Campos KPI calculados automáticamente — no se muestran en el formulario
_CAMPOS_KPI_AUTO = {"Disponibilidad %", "Utilización", "Rendimiento m/h"}

# Grupos de campos para el formulario
_GRUPOS = {
    "🗓 Identificación": [
        "Fecha turno", "Turno", "Modelo equipo", "Número equipo",
        "Operador", "Código operador", "Área operacional",
    ],
    "⛏ Producción y perforación": [
        "Metros perforados", "Pozos perforados turno", "Horas efectivas perforando",
        "Horómetro inicial", "Horómetro final", "Diferencia horómetro", "Horas de motor",
    ],
    "⏱ Distribución de horas": [
        "Avería", "Horas detención mecánica", "Horas detención No efectivas",
        "Mantención Programada", "Traslado", "Relleno de agua", "Colación",
        "Tronadura", "Cambio de aceros", "Cambio turno", "Falta operador",
        "Standby por falta de tajo/Patio", "Otros", "Total horas ingresadas",
    ],
    "📍 Ubicación": [
        "Banco", "Malla", "Fase",
        "Tipo de perforación", "Número serie Tricono/Bit",
        "Condición del terreno", "Tipo detención",
    ],
    "⚙️ Equipo y estado": [
        "Estatus del Equipo", "Petróleo litros", "Aceite litros", "Combustible",
    ],
    "📝 Observaciones": ["Observaciones"],
}

# Columnas para la tabla de resultados
_COLS_RESULTADO = [
    ("id", "ID"),
    ("Fecha turno", "Fecha"),
    ("Turno", "Turno"),
    ("Número equipo", "Equipo"),
    ("Operador", "Operador"),
    ("Metros perforados", "Metros"),
    ("Horas efectivas perforando", "H.Ef."),
    ("Avería", "H.Av."),
    ("Disponibilidad %", "Disp%"),
    ("Utilización", "Util%"),
    ("Rendimiento m/h", "Rend."),
]

_KEY_PREFIX = "er"

# Slug por grupo — garantiza keys únicas aunque un campo repita entre grupos
_GRUPO_SLUGS = {
    "🗓 Identificación": "ident",
    "⛏ Producción y perforación": "prod",
    "⏱ Distribución de horas": "horas",
    "📍 Ubicación": "ubic",
    "⚙️ Equipo y estado": "equip",
    "📝 Observaciones": "obs",
}


# ─── UTILIDADES ───────────────────────────────────────────────────────────────

def _n(val, default=0.0):
    try:
        return float(pd.to_numeric(pd.Series([val]), errors="coerce").fillna(default).iloc[0])
    except Exception:
        return default


def _s(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return texto_visible(str(val))


def _is_numeric(campo):
    return campo in NUMERIC_COLUMNS or campo in _NUMERICOS_EXTRA


def _fkey(campo, grupo=""):
    slug = _GRUPO_SLUGS.get(grupo, grupo[:6] if grupo else "g")
    return f"{_KEY_PREFIX}_f_{slug}_{campo}"


def _get_usuario():
    try:
        info = st.session_state.get("usuario_actual", {})
        return info.get("nombre") or st.session_state.get("usuario", "ProyectoDES")
    except Exception:
        return "ProyectoDES"


def _limpiar_estado_edicion():
    from ui.sectores_widget import limpiar_sectores
    slugs = set(_GRUPO_SLUGS.values())
    fijos = {
        f"{_KEY_PREFIX}_editing_id",
        f"{_KEY_PREFIX}_edit_loaded",
        f"{_KEY_PREFIX}_motivo",
    }
    for k in list(st.session_state.keys()):
        if k in fijos:
            st.session_state.pop(k, None)
            continue
        # er_f_{slug}_... — claves de campos del formulario
        if k.startswith(f"{_KEY_PREFIX}_f_"):
            partes = k.split("_", 3)   # ["er", "f", slug, campo]
            if len(partes) >= 3 and partes[2] in slugs:
                st.session_state.pop(k, None)
    # er_sec_... — claves del widget multi-sector
    limpiar_sectores(_sec_kf)


# ─── BÚSQUEDA ─────────────────────────────────────────────────────────────────

def _buscar_registros(fecha_desde, fecha_hasta, turno, equipo, operador):
    path = Path(db.DB_PATH)
    if not path.exists():
        return pd.DataFrame()

    conditions, params = ["1=1"], []
    if fecha_desde:
        conditions.append('"Fecha turno" >= ?')
        params.append(str(fecha_desde))
    if fecha_hasta:
        conditions.append('"Fecha turno" <= ?')
        params.append(str(fecha_hasta))
    if turno:
        conditions.append('"Turno" = ?')
        params.append(str(turno))
    if equipo:
        conditions.append('"Número equipo" = ?')
        params.append(str(equipo))
    if operador and operador.strip():
        conditions.append('"Operador" LIKE ?')
        params.append(f"%{operador.strip()}%")

    cols_needed = [col for col, _ in _COLS_RESULTADO]
    try:
        with sqlite3.connect(path) as conn:
            existing = {r[1] for r in conn.execute("PRAGMA table_info(registros_perforacion)").fetchall()}
            cols = [c for c in cols_needed if c in existing]
            cols_sql = ", ".join(f'"{c}"' for c in cols)
            where = " AND ".join(conditions)
            return pd.read_sql_query(
                f'SELECT {cols_sql} FROM registros_perforacion '
                f'WHERE {where} ORDER BY "Fecha turno" DESC, id DESC LIMIT 500',
                conn, params=params,
            )
    except Exception:
        return pd.DataFrame()


def _existe_duplicado(fecha, turno, equipo, excluir_id):
    try:
        path = Path(db.DB_PATH)
        if not path.exists():
            return False, None
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                'SELECT id, "Operador" FROM registros_perforacion '
                'WHERE "Fecha turno"=? AND "Turno"=? AND "Número equipo"=? AND id!=? LIMIT 1',
                (str(fecha), str(turno), str(equipo), int(excluir_id)),
            ).fetchone()
            if row:
                return True, _s(row["Operador"])
            return False, None
    except Exception:
        return False, None


# ─── RENDERIZADO BUSCADOR ─────────────────────────────────────────────────────

def _render_buscador():
    st.markdown(
        '<div style="background:#111318;border:1px solid #222;border-radius:10px;'
        'padding:18px 20px 14px;">',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="color:#E67E22;font-size:0.88rem;font-weight:700;margin:0 0 14px;">'
        '🔍 Filtros de búsqueda</p>',
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns([1.8, 1.8, 1.2, 1.2])
    with c1:
        fecha_desde = st.date_input("Desde", value=date.today() - timedelta(days=30), key=f"{_KEY_PREFIX}_fd")
    with c2:
        fecha_hasta = st.date_input("Hasta", value=date.today(), key=f"{_KEY_PREFIX}_fh")
    with c3:
        turno_sel = st.selectbox("Turno", ["(todos)", "Día", "Noche"], key=f"{_KEY_PREFIX}_turno")
    with c4:
        equipo_sel = st.selectbox("Equipo", ["(todos)"] + _EQUIPOS, key=f"{_KEY_PREFIX}_equipo")

    c5, c6 = st.columns([3, 1])
    with c5:
        operador_txt = st.text_input("Operador", placeholder="Nombre parcial del operador…", key=f"{_KEY_PREFIX}_op")
    with c6:
        st.write("")
        st.write("")
        buscar = st.button("🔍 Buscar Registros", type="primary", width="stretch", key=f"{_KEY_PREFIX}_buscar")

    st.markdown("</div>", unsafe_allow_html=True)

    return (
        fecha_desde,
        fecha_hasta,
        None if turno_sel == "(todos)" else turno_sel,
        None if equipo_sel == "(todos)" else equipo_sel,
        operador_txt,
        buscar,
    )


# ─── TABLA DE RESULTADOS ──────────────────────────────────────────────────────

def _fmt_cell(val, dec=1, suffix=""):
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return "—"
        return f"{float(val):.{dec}f}{suffix}"
    except Exception:
        return _s(val) or "—"


def _render_tabla(df):
    n = len(df)
    st.markdown(
        f'<p style="color:#888;font-size:0.8rem;margin:14px 0 8px;">'
        f'{n} registro{"s" if n != 1 else ""} encontrado{"s" if n != 1 else ""}'
        f'<span style="color:#555;"> · máx. 500 resultados</span></p>',
        unsafe_allow_html=True,
    )

    widths = [0.38, 0.9, 0.58, 0.58, 2.0, 0.62, 0.58, 0.58, 0.58, 0.58, 0.62, 0.72]
    headers = ["ID", "Fecha", "Turno", "Equipo", "Operador",
               "Metros", "H.Ef.", "H.Av.", "Disp%", "Util%", "Rend.", ""]

    # Header row
    hcols = st.columns(widths)
    for hc, lbl in zip(hcols, headers):
        hc.markdown(
            f'<p style="color:#E67E22;font-size:0.7rem;font-weight:700;margin:0;padding:3px 0;">{lbl}</p>',
            unsafe_allow_html=True,
        )
    st.markdown('<hr style="margin:4px 0 6px;border-color:#222;">', unsafe_allow_html=True)

    cell = 'style="font-size:0.78rem;color:#D0D0D0;margin:0;padding:3px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"'

    for _, row in df.iterrows():
        rid = int(row.get("id", 0))
        dcols = st.columns(widths)
        dcols[0].markdown(f'<p {cell}>{rid}</p>', unsafe_allow_html=True)
        dcols[1].markdown(f'<p {cell}>{_s(str(row.get("Fecha turno", ""))[:10])}</p>', unsafe_allow_html=True)
        dcols[2].markdown(f'<p {cell}>{_s(row.get("Turno", ""))}</p>', unsafe_allow_html=True)
        dcols[3].markdown(f'<p {cell}>{_s(row.get("Número equipo", ""))}</p>', unsafe_allow_html=True)
        dcols[4].markdown(f'<p {cell}>{_s(row.get("Operador", ""))}</p>', unsafe_allow_html=True)
        dcols[5].markdown(f'<p {cell}>{_fmt_cell(row.get("Metros perforados"))}</p>', unsafe_allow_html=True)
        dcols[6].markdown(f'<p {cell}>{_fmt_cell(row.get("Horas efectivas perforando"))}</p>', unsafe_allow_html=True)
        dcols[7].markdown(f'<p {cell}>{_fmt_cell(row.get("Avería"))}</p>', unsafe_allow_html=True)
        dcols[8].markdown(f'<p {cell}>{_fmt_cell(row.get("Disponibilidad %"))}%</p>', unsafe_allow_html=True)
        dcols[9].markdown(f'<p {cell}>{_fmt_cell(row.get("Utilización"))}%</p>', unsafe_allow_html=True)
        dcols[10].markdown(f'<p {cell}>{_fmt_cell(row.get("Rendimiento m/h"), dec=2)}</p>', unsafe_allow_html=True)
        with dcols[11]:
            if st.button("✏️ Editar", key=f"{_KEY_PREFIX}_btn_{rid}", width="stretch"):
                st.session_state[f"{_KEY_PREFIX}_editing_id"] = rid
                st.session_state.pop(f"{_KEY_PREFIX}_edit_loaded", None)
                st.rerun()


# ─── FORMULARIO DE EDICIÓN ────────────────────────────────────────────────────

def _sec_kf(name):
    return f"{_KEY_PREFIX}_sec_{name}"


def _inicializar_form(registro_id, registro):
    """Carga valores del registro en session_state una sola vez."""
    from ui.sectores_widget import init_sectores, json_a_sectores, TIPOS_SECTOR

    for titulo, campos in _GRUPOS.items():
        for campo in campos:
            if campo not in registro or campo in _CAMPOS_KPI_AUTO:
                continue
            key = _fkey(campo, titulo)
            raw = registro.get(campo)
            if campo == "Fecha turno":
                try:
                    val = pd.to_datetime(raw).date()
                except Exception:
                    val = date.today()
            elif campo == "Turno":
                val = str(raw) if str(raw) in _TURNOS else _TURNOS[0]
            elif campo == "Número equipo":
                val = str(raw).split(".")[0] if raw else _EQUIPOS[0]
            elif _is_numeric(campo):
                val = float(pd.to_numeric(pd.Series([raw]), errors="coerce").fillna(0).iloc[0])
            else:
                val = _s(raw)
            st.session_state[key] = val

    # Inicializar sectores desde sectores_json o campos legacy
    sectores_init = json_a_sectores(registro.get("sectores_json"))
    if sectores_init is None:
        ts = _s(registro.get("tipo_sector", "Producción"))
        if ts not in TIPOS_SECTOR:
            ts = "Producción"
        nu = _s(registro.get("numero_precorte", ""))
        sectores_init = [{"tipo": ts, "numero": nu}]
    init_sectores(_sec_kf, sectores_init)

    st.session_state[f"{_KEY_PREFIX}_motivo"] = ""
    st.session_state[f"{_KEY_PREFIX}_edit_loaded"] = registro_id


def _widget(campo, registro, grupo=""):
    """Renderiza el widget correspondiente al campo; devuelve su valor."""
    key = _fkey(campo, grupo)
    raw = registro.get(campo, "")

    if campo == "Turno":
        opts = _TURNOS
        return st.selectbox(texto_visible(campo), opts, key=key)

    if campo == "Número equipo":
        opts = list(_EQUIPOS)
        val_actual = _s(raw).split(".")[0]
        if val_actual and val_actual not in opts:
            opts = opts + [val_actual]
        return st.selectbox(texto_visible(campo), opts, key=key)

    if campo == "Fecha turno":
        return st.date_input(texto_visible(campo), key=key)

    if _is_numeric(campo):
        es_int = campo in _NUMERICOS_INT
        return st.number_input(
            texto_visible(campo),
            min_value=0.0,
            step=1.0 if es_int else 0.25,
            format="%.0f" if es_int else "%.2f",
            key=key,
        )

    if campo == "Observaciones":
        return st.text_area(texto_visible(campo), height=110, key=key)

    return st.text_input(texto_visible(campo), key=key)


def _leer(campo):
    """Lee el valor del campo desde session_state buscando en todos los grupos."""
    for titulo in _GRUPOS:
        key = _fkey(campo, titulo)
        if key in st.session_state:
            return st.session_state[key]
    return ""


def _render_kpi_preview():
    """Calcula y muestra KPIs en tiempo real con los valores actuales del form."""
    metros   = _n(_leer("Metros perforados"))
    pozos    = _n(_leer("Pozos perforados turno"))
    horas_ef = _n(_leer("Horas efectivas perforando"))
    h_total  = max(_n(_leer("Total horas ingresadas"), 12.0), 1.0)
    h_av     = _n(_leer("Avería"))
    h_mant   = _n(_leer("Mantención Programada"))
    h_no_ef  = _n(_leer("Horas detención No efectivas"))
    h_trasl  = _n(_leer("Traslado"))
    h_otros  = _n(_leer("Otros"))
    h_std    = _n(_leer("Standby por falta de tajo/Patio"))
    estatus  = _s(_leer("Estatus del Equipo"))

    kpi = calcular_kpi_operacional_productivo(
        metros=metros, pozos=pozos, horas_efectivas=horas_ef,
        horas_turno=h_total, horas_averia=h_av, horas_mantencion=h_mant,
        horas_no_efectivas=h_no_ef, horas_traslado=h_trasl,
        horas_otros=h_otros, horas_standby=h_std, estatus_equipo=estatus,
    )

    util = kpi["utilizacion_productiva"]
    rend = kpi["rendimiento"]
    disp = kpi["disponibilidad"]
    alertas = kpi["alertas_coherencia"]

    c_util = "#2ECC71" if util >= 50 else "#E67E22" if util >= 30 else "#E74C3C"
    c_rend = "#2ECC71" if rend >= 15 else "#E67E22" if rend >= 8  else "#E74C3C"
    c_disp = "#2ECC71" if disp >= 70 else "#E67E22" if disp >= 50 else "#E74C3C"

    alertas_html = "".join(
        f'<div style="color:#F39C12;font-size:0.73rem;margin-top:6px;">⚠ {_s(a)}</div>'
        for a in alertas
    )

    st.markdown(
        f'<div style="background:#0d0e10;border:1px solid #E67E22;border-radius:10px;'
        f'padding:16px 22px;margin:4px 0 12px;">'
        f'<p style="color:#E67E22;font-weight:700;font-size:0.87rem;margin:0 0 14px;">'
        f'📊 KPIs recalculados — actualización en tiempo real</p>'
        f'<div style="display:flex;gap:36px;align-items:flex-end;flex-wrap:wrap;">'
        f'<div><p style="color:#666;font-size:0.7rem;margin:0 0 2px;text-transform:uppercase;letter-spacing:1px;">Disponibilidad</p>'
        f'<p style="color:{c_disp};font-size:1.8rem;font-weight:700;margin:0;font-family:\'Barlow Condensed\',sans-serif;">{disp:.1f}%</p></div>'
        f'<div><p style="color:#666;font-size:0.7rem;margin:0 0 2px;text-transform:uppercase;letter-spacing:1px;">Utilización</p>'
        f'<p style="color:{c_util};font-size:1.8rem;font-weight:700;margin:0;font-family:\'Barlow Condensed\',sans-serif;">{util:.1f}%</p></div>'
        f'<div><p style="color:#666;font-size:0.7rem;margin:0 0 2px;text-transform:uppercase;letter-spacing:1px;">Rendimiento</p>'
        f'<p style="color:{c_rend};font-size:1.8rem;font-weight:700;margin:0;font-family:\'Barlow Condensed\',sans-serif;">{rend:.2f} m/h</p></div>'
        f'</div>{alertas_html}</div>',
        unsafe_allow_html=True,
    )
    return kpi


def _render_formulario(registro_id):
    registro = db.obtener_registro_por_id(registro_id)
    if not registro:
        st.error(f"No se pudo cargar el registro ID {registro_id}.")
        return

    # Inicializar estado solo al abrir un registro nuevo
    if st.session_state.get(f"{_KEY_PREFIX}_edit_loaded") != registro_id:
        _inicializar_form(registro_id, registro)

    # Cabecera del formulario
    fecha_r  = _s(str(registro.get("Fecha turno", ""))[:10])
    turno_r  = _s(registro.get("Turno", ""))
    equipo_r = _s(registro.get("Número equipo", ""))
    op_r     = _s(registro.get("Operador", ""))

    st.markdown(
        f'<div style="background:#111318;border-left:4px solid #E67E22;border-radius:8px;'
        f'padding:12px 18px;margin:16px 0;">'
        f'<p style="color:#E67E22;font-weight:700;font-size:0.92rem;margin:0;">✏️ Editando registro ID {registro_id}</p>'
        f'<p style="color:#BDC3C7;font-size:0.82rem;margin:5px 0 0;">'
        f'{fecha_r} · Turno {turno_r} · Equipo {equipo_r} · {op_r}</p></div>',
        unsafe_allow_html=True,
    )

    # Campos del formulario agrupados en expanders
    from ui.sectores_widget import render_sectores, sectores_a_json
    sectores_editados = [{"tipo": "Producción", "numero": ""}]

    for titulo, campos in _GRUPOS.items():
        campos_presentes = [
            c for c in campos
            if c in registro and c not in _CAMPOS_KPI_AUTO
        ]
        has_content = bool(campos_presentes) or titulo == "📍 Ubicación"
        if not has_content:
            continue
        expanded = titulo.startswith(("🗓", "⛏", "⏱"))
        with st.expander(titulo, expanded=expanded):
            n_cols = 1 if titulo.startswith("📝") else 3
            for i in range(0, len(campos_presentes), n_cols):
                fila = campos_presentes[i:i + n_cols]
                cols = st.columns(n_cols)
                for j, campo in enumerate(fila):
                    with cols[j]:
                        _widget(campo, registro, titulo)
            if titulo == "📍 Ubicación":
                st.divider()
                sectores_editados = render_sectores(_sec_kf)

    # KPI preview (lee session_state actualizado)
    st.divider()
    kpi = _render_kpi_preview()

    # Validación duplicado
    fecha_nueva  = str(_leer("Fecha turno"))
    turno_nuevo  = _s(_leer("Turno"))
    equipo_nuevo = _s(_leer("Número equipo"))
    duplicado, op_dup = _existe_duplicado(fecha_nueva, turno_nuevo, equipo_nuevo, registro_id)

    if duplicado:
        st.error(
            f"🚫 Ya existe otro registro para Equipo **{equipo_nuevo}** · "
            f"Turno **{turno_nuevo}** · {fecha_nueva}  \n"
            f"Operador registrado: **{op_dup}**  \n"
            f"Cambia equipo / turno / fecha antes de guardar."
        )

    # Motivo y botones de acción
    st.divider()
    motivo = st.text_area(
        "Motivo de edición (obligatorio)",
        placeholder="Describe brevemente el motivo de esta corrección…",
        key=f"{_KEY_PREFIX}_motivo",
        height=80,
    )

    btn1, btn2, btn3 = st.columns([3, 1, 1.2])
    with btn2:
        cancelar = st.button("✕ Cancelar", key=f"{_KEY_PREFIX}_cancel", width="stretch")
    with btn3:
        confirmar = st.button(
            "✅ Confirmar cambios",
            key=f"{_KEY_PREFIX}_confirm",
            type="primary",
            width="stretch",
            disabled=bool(duplicado),
        )

    if cancelar:
        _limpiar_estado_edicion()
        st.rerun()

    if confirmar and not duplicado:
        if not str(motivo or "").strip():
            st.error("El motivo de edición es obligatorio antes de guardar.")
            return
        _guardar_cambios(registro_id, registro, kpi, motivo, sectores_editados)


def _guardar_cambios(registro_id, registro, kpi, motivo, sectores):
    """Construye el dict de cambios y llama a actualizar_registro_auditado."""
    from ui.sectores_widget import sectores_a_json, TIPOS_SECTOR
    cambios = {}
    for campos in _GRUPOS.values():
        for campo in campos:
            if campo not in registro or campo in _CAMPOS_KPI_AUTO:
                continue
            if campo in cambios:
                continue  # primer grupo que defina el campo gana
            val = _leer(campo)
            if isinstance(val, date):
                val = str(val)
            cambios[campo] = val

    # Sectores JSON + campos legacy para compatibilidad con otros módulos
    cambios["sectores_json"] = sectores_a_json(sectores)
    if sectores:
        cambios["tipo_sector"] = sectores[0].get("tipo", "Producción")
        cambios["numero_precorte"] = (
            sectores[0].get("numero", "") or sectores[0].get("numero_precorte", "")
            if sectores[0].get("tipo") == "Precorte" else ""
        )

    # KPIs recalculados siempre sobrescriben los valores almacenados
    cambios["Disponibilidad %"] = round(kpi["disponibilidad"], 2)
    cambios["Utilización"]      = round(kpi["utilizacion_productiva"], 2)
    cambios["Rendimiento m/h"]  = round(kpi["rendimiento"], 2)

    try:
        resultado = db.actualizar_registro_auditado(
            registro_id,
            cambios,
            motivo=str(motivo).strip(),
            usuario=_get_usuario(),
            sync_excel=False,
        )
    except Exception as exc:
        st.error(f"Error al guardar: {_s(str(exc))}")
        return

    n_act = resultado.get("actualizados", 0)
    n_aud = resultado.get("auditoria", 0)

    if n_act <= 0 and n_aud <= 0:
        st.info("No se detectaron cambios respecto al registro original.")
        return

    db.limpiar_cache_consultas()
    try:
        app.limpiar_cache_reportes()
    except Exception:
        pass

    campos_mod = resultado.get("campos", [])
    st.success(
        f"✅ **Registro {registro_id} actualizado** — "
        f"{len(campos_mod)} campo(s) modificado(s) · {n_aud} entrada(s) de auditoría  \n"
        f"**Disponibilidad:** {kpi['disponibilidad']:.1f}% · "
        f"**Utilización:** {kpi['utilizacion_productiva']:.1f}% · "
        f"**Rendimiento:** {kpi['rendimiento']:.2f} m/h"
    )
    _limpiar_estado_edicion()
    # Invalida la tabla de búsqueda para que muestre valores actualizados
    st.session_state.pop(f"{_KEY_PREFIX}_results", None)


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    if not app.requerir_acceso():
        return

    render_page_header(
        st,
        "Editar Registro",
        "Búsqueda · Edición auditada · Recálculo automático de KPIs",
    )

    fecha_desde, fecha_hasta, turno, equipo, operador, buscar = _render_buscador()

    if buscar:
        with st.spinner("Buscando registros…"):
            df = _buscar_registros(fecha_desde, fecha_hasta, turno, equipo, operador)
        st.session_state[f"{_KEY_PREFIX}_results"] = df
        _limpiar_estado_edicion()

    editing_id = st.session_state.get(f"{_KEY_PREFIX}_editing_id")
    df_results = st.session_state.get(f"{_KEY_PREFIX}_results")

    if not editing_id:
        if df_results is not None:
            st.divider()
            if df_results.empty:
                st.info("No se encontraron registros con los filtros aplicados.")
            else:
                _render_tabla(df_results)
    else:
        st.divider()
        _render_formulario(editing_id)


main()
