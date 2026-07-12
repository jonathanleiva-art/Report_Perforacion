import pandas as pd
import streamlit as st
import re

import db
from operators import etiqueta_operador
from services import ciclos_service, operational_excel_service
from ui.formatting import texto_visible
from utils import TIPOS_DETENCION, opciones_desde_historial

FASES_CONSULTA = ["Todas", "Fase 1", "Fase 2"]


def _opciones_desde_sql(columna):
    try:
        valores = db.obtener_valores_distintos_columna(columna)
    except Exception:
        valores = []
    return valores


def _seleccion_o_todo(seleccion, opciones):
    if not seleccion:
        return list(opciones)
    validas = [valor for valor in seleccion if valor in opciones]
    return validas or list(opciones)


def _solo_si_parcial(seleccion, opciones):
    seleccion_normalizada = {str(valor).strip() for valor in seleccion if str(valor).strip()}
    opciones_normalizadas = {str(valor).strip() for valor in opciones if str(valor).strip()}
    if not seleccion_normalizada or seleccion_normalizada == opciones_normalizadas:
        return []
    return list(seleccion)


def _etiqueta_operador(valor):
    return texto_visible(etiqueta_operador(valor))


def _normalizar_rango_fechas(rango, rango_defecto):
    if isinstance(rango, (tuple, list)):
        valores = [valor for valor in rango if valor is not None]
        if len(valores) >= 2:
            return valores[0], valores[-1]
        if len(valores) == 1:
            return valores[0], valores[0]
    if rango is None:
        if isinstance(rango_defecto, (tuple, list)) and len(rango_defecto) == 2:
            return rango_defecto[0], rango_defecto[1]
        return None, None
    return rango, rango


def _serie_opciones(df, columna):
    if columna not in df.columns:
        return []
    valores = df[columna].dropna().astype(str).str.strip()
    return sorted(valores[valores.ne("")].unique())


_COLUMNAS_CSV_SPLIT = {"Banco", "Malla", "Fase"}


def _serie_opciones_split(df, columna):
    """Como _serie_opciones pero divide valores separados por coma en tokens individuales."""
    if columna not in df.columns:
        return []
    resultado: set = set()
    for val in df[columna].dropna():
        for parte in str(val).split(","):
            p = parte.strip()
            if p and p.lower() not in ("nan", "none", "nat"):
                resultado.add(p)
    return sorted(resultado)


def _valor_contiene_fase(valor, consulta_fase):
    if consulta_fase == "Todas":
        return True
    objetivo = "1" if consulta_fase == "Fase 1" else "2"
    texto = str(valor or "").strip().lower()
    if not texto or texto in {"nan", "none", "nat"}:
        return False
    numeros = re.findall(r"\d+", texto)
    if objetivo in numeros:
        return True
    compactado = re.sub(r"\s+", "", texto)
    return compactado in {f"f{objetivo}", f"fase{objetivo}"}


def _filtrar_consulta_fase_dataframe(df, consulta_fase):
    if consulta_fase == "Todas" or df.empty:
        return df
    columna = "Fase" if "Fase" in df.columns else "fase" if "fase" in df.columns else None
    if columna is None:
        return df
    return df[df[columna].apply(lambda valor: _valor_contiene_fase(valor, consulta_fase))].copy()


def _valores_fase_para_sql(fases, consulta_fase):
    if consulta_fase == "Todas":
        return []
    return [fase for fase in fases if _valor_contiene_fase(fase, consulta_fase)]


def _columna_operador_filtro(df):
    if "operador" in df.columns:
        return "operador"
    if "operador_display" in df.columns:
        return "operador_display"
    if "operador_nombre" in df.columns and df["operador_nombre"].fillna("").astype(str).str.strip().ne("").any():
        return "operador_nombre"
    return "Operador"


def _aplicar_filtros_dataframe(df, filtros_sql, tipos_detencion):
    filtrado = df.copy()
    if filtrado.empty:
        return filtrado

    fecha_inicio = filtros_sql.get("fecha_inicio")
    fecha_fin = filtros_sql.get("fecha_fin")
    columna_fecha = "fecha_turno" if "fecha_turno" in filtrado.columns else "Fecha turno"
    if columna_fecha in filtrado.columns and (fecha_inicio is not None or fecha_fin is not None):
        fechas = pd.to_datetime(filtrado[columna_fecha], errors="coerce")
        if fecha_inicio is not None:
            filtrado = filtrado[fechas >= pd.to_datetime(fecha_inicio, errors="coerce")]
            fechas = pd.to_datetime(filtrado[columna_fecha], errors="coerce")
        if fecha_fin is not None:
            filtrado = filtrado[fechas <= pd.to_datetime(fecha_fin, errors="coerce")]

    for columna, clave in [
        ("equipo", "equipos"),
        ("Equipo", "equipos"),
        (_columna_operador_filtro(filtrado), "operadores"),
        ("turno", "turnos"),
        ("Turno", "turnos"),
        ("Banco", "banco"),
        ("Malla", "malla"),
        ("Fase", "fase"),
        ("Tipo de perforaciÃƒÂ³n", "tipo_perforacion"),
        ("Tipo de perforaciÃ³n", "tipo_perforacion"),
    ]:
        valores = filtros_sql.get(clave)
        if columna not in filtrado.columns or not valores:
            continue
        seleccionados = {str(valor).strip() for valor in valores if str(valor).strip()}
        if not seleccionados:
            continue
        if columna in _COLUMNAS_CSV_SPLIT:
            def _contiene_token(val, sel=seleccionados):
                partes = {p.strip() for p in str(val or "").split(",") if p.strip()}
                return bool(partes & sel)
            filtrado = filtrado[filtrado[columna].fillna("").apply(_contiene_token)]
        else:
            filtrado = filtrado[filtrado[columna].fillna("").astype(str).str.strip().isin(seleccionados)]

    if filtro_tipos := filtros_sql.get("tipos_detencion"):
        for columna_detencion in ("Tipo detenciÃƒÂ³n", "Tipo detenciÃ³n"):
            if columna_detencion not in filtrado.columns or set(filtro_tipos) == set(tipos_detencion):
                continue
            seleccionados = set(filtro_tipos)
            filtrado = filtrado[
                filtrado[columna_detencion].fillna("").astype(str).apply(
                    lambda valor: bool(
                        seleccionados.intersection(
                            item.strip() for item in valor.split(",") if item.strip()
                        )
                    )
                )
            ]
            break
    return filtrado


def _contar_seguro(**filtros):
    try:
        return db.contar_historial_filtrado(**filtros)
    except Exception:
        return 0


def _rango_real_dataframe(df):
    columna = "fecha_turno" if "fecha_turno" in df.columns else "Fecha turno"
    if columna not in df.columns:
        return None, None
    fechas = pd.to_datetime(df[columna], errors="coerce").dt.date.dropna()
    if fechas.empty:
        return None, None
    return fechas.min(), fechas.max()


def _restablecer_filtros_dashboard(claves):
    for clave in claves:
        st.session_state.pop(clave, None)
    st.session_state.pop("dashboard_sql_filters", None)
    st.rerun()


def aplicar_filtros(df):
    if df.empty and not db.DB_PATH.exists():
        return df

    tipo_fuente = st.session_state.get("dashboard_data_source")
    usar_ciclos_fuente = tipo_fuente == "ciclos"
    usar_operacional_fuente = tipo_fuente == "excel_operacional"
    id_fuente = st.session_state.get("dashboard_data_source_id")
    opciones_ciclos_fuente = ciclos_service.obtener_opciones_filtros_ciclos() if usar_ciclos_fuente else {}
    opciones_operacional_fuente = operational_excel_service.obtener_opciones_filtros_operacional(id_fuente=id_fuente) if usar_operacional_fuente else {}
    if usar_ciclos_fuente or usar_operacional_fuente:
        opciones_fechas = opciones_ciclos_fuente.get("fechas", []) if usar_ciclos_fuente else opciones_operacional_fuente.get("fechas", [])
        fechas_fuente = pd.to_datetime(pd.Series(opciones_fechas), errors="coerce").dt.date.dropna()
        if fechas_fuente.empty and "Fecha turno" in df.columns:
            fechas_fuente = pd.to_datetime(df["Fecha turno"], errors="coerce").dt.date.dropna()
        rango_defecto = (fechas_fuente.min(), fechas_fuente.max()) if not fechas_fuente.empty else (None, None)
    else:
        rango_defecto = db.obtener_rango_fechas()

    # Override date range default with month selector if active
    mes_periodo = st.session_state.get("dashboard_mes_periodo")
    if mes_periodo is not None:
        rango_defecto = mes_periodo
    claves_widgets = [
        "dashboard_fecha",
        "dashboard_equipos",
        "dashboard_operadores",
        "dashboard_turnos",
        "dashboard_tipos_detencion",
        "dashboard_bancos",
        "dashboard_mallas",
        "filtro_fase_dashboard_visible",
        "dashboard_fases",
        "dashboard_tipos_perforacion",
    ]
    with st.sidebar:
        st.header("Filtros")
        if st.button("Restablecer filtros", width="stretch"):
            _restablecer_filtros_dashboard(claves_widgets)

        if all(valor is not None for valor in rango_defecto):
            rango = st.date_input(
                "Rango de fechas",
                value=rango_defecto,
                min_value=rango_defecto[0],
                max_value=rango_defecto[1],
                format="DD/MM/YYYY",
                key="dashboard_fecha",
            )
        else:
            rango = st.date_input("Rango de fechas", value=None, format="DD/MM/YYYY", key="dashboard_fecha")

        usar_ciclos = st.session_state.get("dashboard_data_source") == "ciclos"
        usar_operacional = st.session_state.get("dashboard_data_source") == "excel_operacional"
        opciones_ciclos = opciones_ciclos_fuente if usar_ciclos else {}
        opciones_operacional = opciones_operacional_fuente if usar_operacional else {}
        usar_excel = usar_ciclos or usar_operacional
        fecha_inicio_filtro, fecha_fin_filtro = _normalizar_rango_fechas(rango, rango_defecto)
        df_opciones = df
        if usar_excel:
            df_opciones = _aplicar_filtros_dataframe(
                df,
                {"fecha_inicio": fecha_inicio_filtro, "fecha_fin": fecha_fin_filtro},
                [],
            )
        operador_col = _columna_operador_filtro(df_opciones)
        equipos = ((_serie_opciones(df_opciones, "equipo") or _serie_opciones(df_opciones, "Equipo") or opciones_ciclos.get("equipos") or opciones_operacional.get("equipos")) if usar_excel else (_opciones_desde_sql("Equipo") or _serie_opciones(df, "Equipo")))
        operadores = ((_serie_opciones(df_opciones, operador_col) or opciones_ciclos.get("operadores") or opciones_operacional.get("operadores")) if usar_excel else (_opciones_desde_sql("Operador") or _serie_opciones(df, "Operador")))
        turnos = ((_serie_opciones(df_opciones, "turno") or _serie_opciones(df_opciones, "Turno") or opciones_ciclos.get("turnos") or opciones_operacional.get("turnos")) if usar_excel else (_opciones_desde_sql("Turno") or _serie_opciones(df, "Turno")))
        bancos = _serie_opciones_split(df_opciones, "Banco") if usar_excel else (_opciones_desde_sql("Banco") or _serie_opciones_split(df, "Banco"))
        mallas = _serie_opciones_split(df_opciones, "Malla") if usar_excel else (_opciones_desde_sql("Malla") or _serie_opciones_split(df, "Malla"))
        fases = _serie_opciones_split(df_opciones, "Fase") if usar_excel else (_opciones_desde_sql("Fase") or _serie_opciones_split(df, "Fase"))
        tipos_perforacion = _serie_opciones(df, "Tipo de perforación") if usar_excel else (_opciones_desde_sql("Tipo de perforaciÃ³n") or _serie_opciones(df, "Tipo de perforaciÃ³n"))
        tipos_detencion = [] if usar_excel else _opciones_desde_sql("Tipo detenciÃ³n")
        if not tipos_detencion:
            tipos_detencion = opciones_desde_historial(df, "Tipo detenciÃ³n", TIPOS_DETENCION)
        else:
            tipos_detencion = sorted(
                dict.fromkeys(
                    parte.strip()
                    for valor in tipos_detencion
                    for parte in str(valor).split(",")
                    if parte.strip()
                )
            )

        filtro_equipos = st.multiselect("Equipo", equipos, default=equipos, key="dashboard_equipos")
        operador_format_func = texto_visible if usar_excel else _etiqueta_operador
        filtro_operadores = st.multiselect("Operador", operadores, default=operadores, format_func=operador_format_func, key="dashboard_operadores")
        filtro_turnos = st.multiselect("Turno", turnos, default=turnos, format_func=texto_visible, key="dashboard_turnos")
        filtro_tipos_detencion = st.multiselect(
            "Tipo detenciÃ³n",
            tipos_detencion,
            default=tipos_detencion,
            format_func=texto_visible,
            key="dashboard_tipos_detencion",
        )
        filtro_bancos = st.multiselect("Banco", bancos, default=bancos, key="dashboard_bancos")
        filtro_mallas = st.multiselect("Malla", mallas, default=mallas, key="dashboard_mallas")
        consulta_fase = st.session_state.get("filtro_fase_dashboard_visible", "Todas")
        filtro_fases = fases
        filtro_tipos_perforacion = st.multiselect(
            "Tipo de perforaciÃ³n",
            tipos_perforacion,
            default=tipos_perforacion,
            key="dashboard_tipos_perforacion",
        )

    filtro_equipos = _seleccion_o_todo(filtro_equipos, equipos)
    filtro_operadores = _seleccion_o_todo(filtro_operadores, operadores)
    filtro_turnos = _seleccion_o_todo(filtro_turnos, turnos)
    filtro_tipos_detencion = _seleccion_o_todo(filtro_tipos_detencion, tipos_detencion)
    filtro_bancos = _seleccion_o_todo(filtro_bancos, bancos)
    filtro_mallas = _seleccion_o_todo(filtro_mallas, mallas)
    filtro_fases = _seleccion_o_todo(filtro_fases, fases)
    fases_sql = _valores_fase_para_sql(filtro_fases, consulta_fase)
    filtro_tipos_perforacion = _seleccion_o_todo(filtro_tipos_perforacion, tipos_perforacion)

    filtros_sql = {
        "fecha_inicio": None,
        "fecha_fin": None,
        "turnos": _solo_si_parcial(filtro_turnos, turnos),
        "equipos": _solo_si_parcial(filtro_equipos, equipos),
        "operadores": _solo_si_parcial(filtro_operadores, operadores),
        "tipos_detencion": _solo_si_parcial(filtro_tipos_detencion, tipos_detencion),
        "banco": _solo_si_parcial(filtro_bancos, bancos),
        "malla": _solo_si_parcial(filtro_mallas, mallas),
        "fase": fases_sql,
        "tipo_perforacion": _solo_si_parcial(filtro_tipos_perforacion, tipos_perforacion),
    }
    filtros_sql["fecha_inicio"], filtros_sql["fecha_fin"] = fecha_inicio_filtro, fecha_fin_filtro

    st.session_state["dashboard_sql_filters"] = filtros_sql
    st.session_state["dashboard_consulta_fase_activa"] = consulta_fase

    fecha_min_fuente, fecha_max_fuente = _rango_real_dataframe(df)
    diagnostico = {
        "total_base": len(df) if usar_operacional_fuente else _contar_seguro(),
        "por_fecha": _contar_seguro(
            fecha_inicio=filtros_sql.get("fecha_inicio"),
            fecha_fin=filtros_sql.get("fecha_fin"),
        ),
        "por_equipo": _contar_seguro(equipos=filtro_equipos),
        "por_operador": _contar_seguro(operadores=filtro_operadores),
        "resultado_final": 0,
        "fecha_inicio": filtros_sql.get("fecha_inicio"),
        "fecha_fin": filtros_sql.get("fecha_fin"),
        "fecha_min_fuente": fecha_min_fuente,
        "fecha_max_fuente": fecha_max_fuente,
        "equipos": filtro_equipos,
        "operadores": filtro_operadores,
        "turnos": filtro_turnos,
        "tipos_detencion": filtro_tipos_detencion,
        "banco": filtro_bancos,
        "malla": filtro_mallas,
        "fase": consulta_fase,
        "tipo_perforacion": filtro_tipos_perforacion,
    }

    if st.session_state.get("dashboard_data_source") in {"ciclos", "excel_operacional"}:
        filtrado = _aplicar_filtros_dataframe(df, filtros_sql, tipos_detencion)
    elif db.DB_PATH.exists():
        try:
            filtrado = db.consultar_historial_filtrado(**filtros_sql)
        except Exception:
            filtrado = df.copy()
    else:
        filtrado = df.copy()

    filtrado = _filtrar_consulta_fase_dataframe(filtrado, consulta_fase)

    if (
        not filtrado.empty
        and filtro_tipos_detencion
        and "Tipo detenciÃ³n" in filtrado.columns
        and set(filtro_tipos_detencion) != set(tipos_detencion)
    ):
        seleccionados = set(filtro_tipos_detencion)
        filtrado = filtrado[
            filtrado["Tipo detenciÃ³n"].fillna("").astype(str).apply(
                lambda valor: bool(
                    seleccionados.intersection(
                        item.strip() for item in valor.split(",") if item.strip()
                    )
                )
            )
        ]

    if st.session_state.get("dashboard_data_source") in {"ciclos", "excel_operacional"}:
        diagnostico["total_base"] = len(df)
        diagnostico["por_fecha"] = len(_aplicar_filtros_dataframe(df, {**filtros_sql, "equipos": [], "operadores": [], "turnos": [], "banco": [], "malla": [], "fase": [], "tipo_perforacion": [], "tipos_detencion": []}, tipos_detencion))
        diagnostico["por_equipo"] = len(_aplicar_filtros_dataframe(df, {"equipos": filtro_equipos}, tipos_detencion))
        diagnostico["por_operador"] = len(_aplicar_filtros_dataframe(df, {"operadores": filtro_operadores}, tipos_detencion))

    diagnostico["resultado_final"] = len(filtrado)
    st.session_state["dashboard_filter_diagnostics"] = diagnostico

    return filtrado
