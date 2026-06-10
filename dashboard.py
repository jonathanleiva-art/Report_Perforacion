from xml.sax.saxutils import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import db
from charts import (
    fig_alertas_operacionales_ejecutivo,
    fig_distribucion_horas,
    fig_evolucion_diaria_metros_ejecutivo,
    fig_impacto_categoria_detencion,
    fig_metros_equipo,
    fig_pareto_detenciones,
    fig_pareto_impacto_horas_perdidas,
    fig_kpi_equipo,
    fig_ranking_operadores,
    fig_ranking_operadores_metros,
    fig_rendimiento_equipo,
    fig_utilizacion_disponibilidad_equipo,
    resumen_kpi_equipos,
    causas_detencion_sin_categoria,
    tabla_impacto_categoria_detencion,
    tabla_pareto_impacto_horas_perdidas,
)
from metrics import calcular_kpis_consolidados_dataframe, calcular_rendimiento_consolidado, registros_productivos
from services import catalog_service
from services import executive_service
from services import kpi_service
from services.malla_service import resumen_avance_malla
from ui.components import (
    control_center_header,
    fleet_status_card,
    kpi_hero_card,
    operational_alert_card,
    recommendation_panel,
    section_header,
    status_panel,
)
from utils import OPERADORES, limpiar_entero, ruta_imagen_equipo

REEMPLAZOS_TEXTO_VISIBLE = {
    "Número": "Número",
    "Código": "Código",
    "Tipo detención": "Tipo detención",
    "Horas detención": "Horas detención",
    "Utilización": "Utilización",
    "utilización": "utilización",
    "avería": "avería",
    "perforación": "perforación",
    "Mantención": "Mantención",
    "mantención": "mantención",
}


def texto_visible(valor):
    texto = str(valor)
    for _ in range(2):
        corregido = texto
        for encoding in ("latin1", "cp1252"):
            try:
                corregido = texto.encode(encoding).decode("utf-8")
                break
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
        if corregido == texto:
            break
        texto = corregido
    for origen, destino in REEMPLAZOS_TEXTO_VISIBLE.items():
        texto = texto.replace(origen, destino)
    texto = texto.replace("", "")
    return texto


def dataframe_visible(df):
    resultado = df.rename(columns=texto_visible).copy()
    for columna in resultado.columns:
        if not (pd.api.types.is_object_dtype(resultado[columna]) or pd.api.types.is_string_dtype(resultado[columna])):
            continue
        resultado[columna] = resultado[columna].map(lambda valor: texto_visible(valor) if pd.notna(valor) else valor)
    vistos = {}
    columnas = []
    for columna in resultado.columns:
        nombre = str(columna)
        vistos[nombre] = vistos.get(nombre, 0) + 1
        if vistos[nombre] > 1:
            nombre = f"{nombre} ({vistos[nombre]})"
        columnas.append(nombre)
    resultado.columns = columnas
    return resultado


def normalizar_nombre_columna(nombre):
    return kpi_service.normalizar_nombre_columna(nombre)


def buscar_columna(df, *candidatos):
    return kpi_service.buscar_columna(df, *candidatos)


def columna_operador_visual(df):
    if "operador_nombre" in df.columns:
        valores = df["operador_nombre"].fillna("").astype(str).str.strip()
        if valores.ne("").any():
            return "operador_nombre"
    return "Operador"


def serie_numerica(df, *columnas):
    return kpi_service.serie_numerica(df, *columnas)


def totales_productivos(df):
    return kpi_service.totales_productivos(df)


def usando_fuente_excel():
    return st.session_state.get("dashboard_data_source") in {"ciclos", "excel_operacional"}


def mostrar_figura(fig, mensaje, key):
    if fig is None:
        st.info(texto_visible(mensaje))
    else:
        st.plotly_chart(fig, width="stretch", key=key)


def _estado_visual_desde_semaforo(estado):
    return {
        "verde": "ok",
        "amarillo": "warning",
        "rojo": "alert",
    }.get(str(estado or "").lower(), "neutral")


def _estado_visual_flota(estado):
    texto = str(estado or "").lower()
    if "aver" in texto or "cr" in texto or "fuera" in texto:
        return "alert"
    if "mant" in texto or "parcial" in texto or "standby" in texto:
        return "warning"
    if "operativo" in texto:
        return "ok"
    return "neutral"


def _sumar_serie(df, *columnas):
    if df is None or df.empty:
        return 0.0
    return float(serie_numerica(df, *columnas).sum())


def _numero_seguro(valor):
    return float(pd.to_numeric(pd.Series([valor]), errors="coerce").fillna(0).iloc[0])


def _formatear_meta_control(filtros_sql):
    filtros = filtros_sql or {}
    fecha_inicio = _formatear_filtro_activo(filtros.get("fecha_inicio") or filtros.get("fecha_desde"))
    fecha_fin = _formatear_filtro_activo(filtros.get("fecha_fin") or filtros.get("fecha_hasta"))
    turno = _formatear_filtro_activo(filtros.get("turno"))
    return f"{fecha_inicio} - {fecha_fin} | Turno: {turno}"


def _resumen_ejecutivo_texto(kpis, salud, cantidad_alertas):
    semaforo = salud.get("semaforo", {})
    return (
        f"{semaforo.get('titulo', 'Estado operacional')}: "
        f"{kpis['metros_perforados_totales']:,.0f} m perforados, "
        f"{kpis['rendimiento_promedio']:,.2f} m/h, "
        f"{kpis['disponibilidad_promedio']:,.2f}% de disponibilidad y "
        f"{cantidad_alertas} alerta(s) operacional(es) en el periodo filtrado."
    )


def _recomendacion_operacional(kpis, salud, detalle_alertas):
    if detalle_alertas is not None and not detalle_alertas.empty:
        columna = "Recomendación operacional"
        if columna in detalle_alertas.columns:
            recomendaciones = [
                texto_visible(valor)
                for valor in detalle_alertas[columna].dropna().astype(str)
                if str(valor).strip()
            ]
            if recomendaciones:
                return recomendaciones[0]
        return "Priorizar revisión de alertas críticas y validar continuidad operacional de los equipos afectados."

    semaforo = salud.get("semaforo", {})
    if semaforo.get("estado") == "rojo":
        return "Activar revisión operacional inmediata sobre disponibilidad, utilización y detenciones del periodo."
    if float(kpis.get("utilizacion_promedio", 0) or 0) < 70:
        return "Revisar causas de baja utilización y reducir tiempos no efectivos antes del siguiente corte operacional."
    if float(kpis.get("disponibilidad_promedio", 0) or 0) < 85:
        return "Coordinar mantenimiento y confiabilidad para recuperar disponibilidad de flota."
    return "Mantener seguimiento de rendimiento, disponibilidad y detenciones para sostener la continuidad operacional."


def _calcular_kpis_periodo_anterior(df_full, filtros_sql):
    if df_full is None or df_full.empty:
        return None
    filtros = filtros_sql or {}
    fecha_inicio_str = filtros.get("fecha_inicio") or filtros.get("fecha_desde")
    fecha_fin_str = filtros.get("fecha_fin") or filtros.get("fecha_hasta")
    if not fecha_inicio_str or not fecha_fin_str:
        return None
    fecha_col = buscar_columna(df_full, "Fecha turno", "fecha_turno")
    if not fecha_col:
        return None
    fi = pd.to_datetime(fecha_inicio_str).normalize()
    ff = pd.to_datetime(fecha_fin_str).normalize()
    duracion = max((ff - fi).days + 1, 1)
    fi_ant = fi - pd.Timedelta(days=duracion)
    ff_ant = fi - pd.Timedelta(days=1)
    fechas = pd.to_datetime(df_full[fecha_col], errors="coerce").dt.normalize()
    df_ant = df_full.loc[(fechas >= fi_ant) & (fechas <= ff_ant)].copy()
    if df_ant.empty:
        return None
    try:
        panel = executive_service.construir_panel_ejecutivo(df_ant)
        kpis_ant = dict(panel.get("kpis", {}))
        kpis_ant["_registros"] = float(len(df_ant))
        kpis_ant["_pozos"] = float(serie_numerica(df_ant, "Pozos perforados", "Pozos perforados turno", "Cantidad pozos perforados").sum())
        kpis_ant["_mantencion"] = float(serie_numerica(df_ant, "Mantención Programada", "Mantencion Programada", "Horas MP", "horas_mp").sum())
        return kpis_ant
    except Exception:
        return None


def _render_kpis_centro_control(kpis, df_analisis, kpis_anterior=None):
    pozos = _sumar_serie(df_analisis, "Pozos perforados", "Pozos perforados turno", "Cantidad pozos perforados")
    mantencion = _sumar_serie(df_analisis, "Mantención Programada", "Mantencion Programada", "Horas MP", "horas_mp")
    registros = float(len(df_analisis))

    metros = float(kpis.get("metros_perforados_totales") or 0)
    disp = float(kpis.get("disponibilidad_promedio") or 0)
    util = float(kpis.get("utilizacion_promedio") or 0)
    rend = float(kpis.get("rendimiento_promedio") or 0)
    hef = float(kpis.get("horas_efectivas") or 0)
    hne = float(kpis.get("horas_no_efectivas") or 0)
    hav = float(kpis.get("horas_averia") or 0)

    def _ant(clave):
        if kpis_anterior is None:
            return 0.0
        return float(kpis_anterior.get(clave) or 0)

    def _delta(actual, ant_val, fmt="+.1f", sufijo=""):
        if kpis_anterior is None:
            return None
        return f"{actual - ant_val:{fmt}}{sufijo} vs período anterior"

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Disponibilidad promedio", f"{disp:.1f}%",
                  delta=_delta(disp, _ant("disponibilidad_promedio"), sufijo=" pp"))
    with col2:
        st.metric("Utilización promedio", f"{util:.1f}%",
                  delta=_delta(util, _ant("utilizacion_promedio"), sufijo=" pp"))
    with col3:
        st.metric("Rendimiento m/h", f"{rend:.2f} m/h",
                  delta=_delta(rend, _ant("rendimiento_promedio"), fmt="+.2f", sufijo=" m/h"))

    col4, col5, col6 = st.columns(3)
    with col4:
        st.metric("Metros perforados", f"{metros:,.0f} m",
                  delta=_delta(metros, _ant("metros_perforados_totales"), fmt="+,.0f", sufijo=" m"))
    with col5:
        st.metric("Registros del período", f"{registros:,.0f}",
                  delta=_delta(registros, _ant("_registros"), fmt="+,.0f"))
    with col6:
        st.metric("Pozos ejecutados", f"{pozos:,.0f}",
                  delta=_delta(pozos, _ant("_pozos"), fmt="+,.0f", sufijo=" pozos"))

    col7, col8, col9 = st.columns(3)
    with col7:
        st.metric("Horas efectivas", f"{hef:,.1f} h",
                  delta=_delta(hef, _ant("horas_efectivas"), sufijo=" h"))
    with col8:
        st.metric("Horas no efectivas", f"{hne:,.1f} h",
                  delta=_delta(hne, _ant("horas_no_efectivas"), sufijo=" h"),
                  delta_color="inverse")
    with col9:
        st.metric("Averías", f"{hav:,.1f} h",
                  delta=_delta(hav, _ant("horas_averia"), sufijo=" h"),
                  delta_color="inverse")

    col10, _, __ = st.columns(3)
    with col10:
        st.metric("Mantención programada", f"{mantencion:,.1f} h",
                  delta=_delta(mantencion, _ant("_mantencion"), sufijo=" h"),
                  delta_color="inverse")


def _render_estado_flota_control(resumen):
    if resumen is None or resumen.empty:
        st.info("No hay datos de flota para el periodo filtrado.")
        return

    for indice in range(0, len(resumen), 3):
        columnas = st.columns(3)
        for columna, (_, equipo) in zip(columnas, resumen.iloc[indice:indice + 3].iterrows()):
            modelo = texto_visible(equipo.get("Modelo equipo", "Equipo"))
            numero = limpiar_entero(equipo.get("Número equipo", ""))
            estado = texto_visible(equipo.get("Estado operacional", "Sin estado"))
            operador = texto_visible(equipo.get("operador_nombre") or equipo.get("Operador") or "Sin operador")
            with columna:
                fleet_status_card(
                    f"{modelo} {numero}".strip(),
                    estado,
                    detail=f"Operador: {operador}",
                    state=_estado_visual_flota(estado),
                    metrics=[
                        {"label": "Metros", "value": f"{_numero_seguro(equipo.get('Metros perforados', 0)):,.0f}"},
                        {"label": "Pozos", "value": f"{_numero_seguro(equipo.get('Pozos perforados', 0)):,.0f}"},
                        {"label": "Disp.", "value": f"{_numero_seguro(equipo.get('Disponibilidad %', 0)):,.1f}%"},
                        {"label": "Util.", "value": f"{_numero_seguro(equipo.get('Utilización', 0)):,.1f}%"},
                    ],
                )


def _render_alertas_criticas(detalle_alertas):
    if detalle_alertas is None or detalle_alertas.empty:
        operational_alert_card("Sin alertas críticas", "No se detectan alertas operacionales para el filtro actual.", state="ok")
        return

    muestra = detalle_alertas.head(3)
    columnas = st.columns(len(muestra))
    for columna, (_, alerta) in zip(columnas, muestra.iterrows()):
        tipo = texto_visible(alerta.get("Tipo de alerta", "Alerta operacional"))
        equipo = texto_visible(alerta.get("Equipo", alerta.get("Número de equipo", "")))
        recomendacion = texto_visible(alerta.get("Recomendación operacional", "Revisar condición operacional."))
        detalle = f"{equipo}: {recomendacion}" if equipo else recomendacion
        with columna:
            operational_alert_card(tipo, detalle, state="alert")


def _render_graficos_centro_control(df_analisis, df_productivo, detalle_alertas):
    section_header("Gráficos principales", "Producción, operadores, detenciones y tendencia del periodo.", kicker="Control")
    fila_1_a, fila_1_b = st.columns(2)
    with fila_1_a:
        mostrar_figura(
            fig_metros_equipo(df_analisis),
            "No hay metros productivos por equipo.",
            key="control_metros_equipo",
        )
    with fila_1_b:
        mostrar_figura(
            fig_ranking_operadores_metros(df_productivo),
            "No hay registros productivos para ranking por metros.",
            key="control_ranking_operadores_metros",
        )

    fila_2_a, fila_2_b = st.columns(2)
    with fila_2_a:
        mostrar_figura(
            fig_pareto_detenciones(df_analisis),
            "No hay detenciones suficientes para construir el Pareto.",
            key="control_pareto_detenciones",
        )
    with fila_2_b:
        mostrar_figura(
            fig_evolucion_diaria_metros_ejecutivo(df_analisis),
            "No hay fechas suficientes para mostrar evolución diaria.",
            key="control_evolucion_diaria",
        )

    mostrar_figura(
        fig_pareto_impacto_horas_perdidas(df_analisis),
        "No hay horas perdidas suficientes para construir el Pareto de impacto.",
        key="control_pareto_impacto_horas_perdidas",
    )
    st.caption("Este Pareto muestra el impacto real en horas perdidas, no solo la cantidad de eventos registrados.")
    tabla_impacto = tabla_pareto_impacto_horas_perdidas(df_analisis)
    if tabla_impacto is not None and not tabla_impacto.empty:
        tabla_impacto = tabla_impacto.copy()
        tabla_impacto["Eventos"] = tabla_impacto["Eventos"].astype(int)
        st.dataframe(
            tabla_impacto,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Causa": st.column_config.TextColumn("Causa"),
                "Eventos": st.column_config.NumberColumn("Eventos", format="%d"),
                "Horas perdidas": st.column_config.NumberColumn("Horas perdidas", format="%.1f"),
                "Promedio h/evento": st.column_config.NumberColumn("Promedio h/evento", format="%.1f"),
                "% impacto": st.column_config.NumberColumn("% impacto", format="%.1f"),
            },
        )

    tabla_categoria = tabla_impacto_categoria_detencion(df_analisis)
    if tabla_categoria is not None and not tabla_categoria.empty:
        categoria_top = tabla_categoria.iloc[0]
        st.metric(
            "Categoría con mayor impacto",
            f"{categoria_top['Categoría']} - {categoria_top['Horas perdidas']:.1f} h ({categoria_top['% impacto']:.1f}%)",
        )
        recomendacion_categoria = catalog_service.generar_recomendacion_operacional(
            categoria_top["Categoría"],
            categoria_top["Horas perdidas"],
            categoria_top["% impacto"],
        )
        recommendation_panel(
            "Recomendación Operacional Automática",
            recomendacion_categoria["mensaje"],
            state=recomendacion_categoria["estado"],
        )

        causas_sin_categoria = causas_detencion_sin_categoria(df_analisis)
        if causas_sin_categoria:
            causas_alerta = ", ".join(causas_sin_categoria[:8])
            sufijo = "..." if len(causas_sin_categoria) > 8 else ""
            st.warning(f"Existen causas de detención sin categoría operacional: {causas_alerta}{sufijo}")

        mostrar_figura(
            fig_impacto_categoria_detencion(df_analisis),
            "No hay horas perdidas suficientes para construir el impacto por categoría.",
            key="control_impacto_categoria_detencion",
        )

        tabla_categoria = tabla_categoria.copy()
        tabla_categoria["Eventos"] = tabla_categoria["Eventos"].astype(int)
        st.dataframe(
            tabla_categoria,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Categoría": st.column_config.TextColumn("Categoría"),
                "Eventos": st.column_config.NumberColumn("Eventos", format="%d"),
                "Horas perdidas": st.column_config.NumberColumn("Horas perdidas", format="%.1f"),
                "Promedio h/evento": st.column_config.NumberColumn("Promedio h/evento", format="%.1f"),
                "% impacto": st.column_config.NumberColumn("% impacto", format="%.1f"),
            },
        )

    with st.expander("Ver gráficos complementarios", expanded=False):
        col_a, col_b = st.columns(2)
        with col_a:
            mostrar_figura(
                fig_utilizacion_disponibilidad_equipo(df_analisis),
                "No hay datos de utilización y disponibilidad por equipo.",
                key="control_utilizacion_disponibilidad",
            )
        with col_b:
            mostrar_figura(
                fig_alertas_operacionales_ejecutivo(detalle_alertas),
                "No hay alertas operacionales para los filtros actuales.",
                key="control_alertas_operacionales",
            )


def fig_evolucion_diaria_metros(df):
    if df.empty or "Fecha turno" not in df.columns or "Metros perforados" not in df.columns:
        return None

    base = df.copy()
    base["Fecha turno"] = pd.to_datetime(base["Fecha turno"], errors="coerce")
    base = base.dropna(subset=["Fecha turno"])
    if base.empty:
        return None

    data = base.groupby(base["Fecha turno"].dt.date, as_index=False)["Metros perforados"].sum()
    if data.empty:
        return None

    data = data.rename(columns={"Fecha turno": "Fecha"})
    fig = px.line(
        data,
        x="Fecha",
        y="Metros perforados",
        markers=True,
        title="Evolución diaria de metros perforados",
        color_discrete_sequence=["#2563EB"],
    )
    fig.update_traces(line=dict(width=3), marker=dict(size=9))
    fig.update_layout(xaxis_title="Fecha", yaxis_title="Metros perforados")
    return fig


def fig_detenciones_principales(df):
    if df.empty:
        return None

    columnas = [col for col in ["Tipo detención"] if col in df.columns]
    if not columnas:
        return None

    valores = []
    for columna in columnas:
        for valor in df[columna].dropna().astype(str):
            for parte in valor.split(","):
                texto = catalog_service.normalizar_causa_detencion(parte)
                if texto:
                    valores.append(texto)
    if not valores:
        return None

    conteo = pd.Series(valores).value_counts().reset_index()
    conteo.columns = ["Detención", "Cantidad"]
    conteo = conteo.head(10).sort_values("Cantidad", ascending=True)

    fig = px.bar(
        conteo,
        x="Cantidad",
        y="Detención",
        orientation="h",
        title="Detenciones principales",
        text="Cantidad",
        color_discrete_sequence=["#0F766E"],
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(xaxis_title="Cantidad", yaxis_title="")
    return fig


def fig_alertas_operacionales(df, filtros_sql):
    try:
        resultado = db.consultar_alertas_operacionales_filtradas(**(filtros_sql or {}), horas_turno=12)
    except Exception:
        return None

    detalle = resultado.get("detalle", pd.DataFrame())
    if detalle.empty or "Tipo de alerta" not in detalle.columns:
        return None

    valores = []
    for valor in detalle["Tipo de alerta"].dropna().astype(str):
        for parte in valor.split(","):
            texto = parte.strip()
            if texto:
                valores.append(texto)
    if not valores:
        return None

    conteo = pd.Series(valores).value_counts().reset_index()
    conteo.columns = ["Alerta", "Cantidad"]
    conteo = conteo.head(10).sort_values("Cantidad", ascending=True)

    fig = px.bar(
        conteo,
        x="Cantidad",
        y="Alerta",
        orientation="h",
        title="Alertas operacionales",
        text="Cantidad",
        color_discrete_sequence=["#DC2626"],
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(xaxis_title="Cantidad", yaxis_title="")
    return fig


def mostrar_panel_graficos_resumen(df_analisis, filtros_sql, resumen_flota=None, df_full=None):
    panel = executive_service.construir_panel_ejecutivo(df_analisis)
    kpis = panel["kpis"]
    salud = panel["salud"]
    alertas = panel["alertas"]
    detalle_alertas = alertas.get("detalle", pd.DataFrame())
    df_productivo = df_analisis.copy() if usando_fuente_excel() else registros_productivos(df_analisis)

    control_center_header(
        "Centro de Control de Perforación",
        "Proyecto DES - Encuentro OXE",
        meta=_formatear_meta_control(filtros_sql),
    )
    estado = salud.get("semaforo", {})
    estado_visual = _estado_visual_desde_semaforo(estado.get("estado"))
    status_panel(
        estado.get("titulo", "Estado operacional"),
        estado.get("mensaje", ""),
        state=estado_visual,
        meta=f"{estado.get('estado', '').upper()} | Índice {salud['indice']:,.2f}",
    )

    recommendation_panel(
        "Resumen ejecutivo del periodo",
        _resumen_ejecutivo_texto(kpis, salud, len(detalle_alertas)),
        state=estado_visual,
    )

    section_header("KPI principales", "Lectura ejecutiva de producción, disponibilidad y tiempos.", kicker="KPIs")
    kpis_anterior = _calcular_kpis_periodo_anterior(df_full, filtros_sql)
    _render_kpis_centro_control(kpis, df_analisis, kpis_anterior=kpis_anterior)

    section_header("Estado de flota", "Condición operacional por equipo en el periodo filtrado.", kicker="Flota")
    _render_estado_flota_control(resumen_flota)

    section_header("Alertas críticas", "Eventos operacionales que requieren revisión prioritaria.", kicker="Riesgo")
    _render_alertas_criticas(detalle_alertas)

    recommendation_panel(
        "Recomendación operacional automática",
        _recomendacion_operacional(kpis, salud, detalle_alertas),
        state=estado_visual,
    )

    _render_graficos_centro_control(df_analisis, df_productivo, detalle_alertas)


def mostrar_diagnostico_filtros():
    diagnostico = st.session_state.get("dashboard_filter_diagnostics") or {}
    if not diagnostico:
        return

    def _formatear_fecha(valor):
        if not valor:
            return "Sin filtro"
        if hasattr(valor, "strftime"):
            return valor.strftime("%d/%m/%Y")
        return str(valor)

    st.subheader("Diagnóstico de filtros")
    with st.expander("Ver detalle de carga", expanded=False):
        fila_1 = st.columns(4)
        fila_1[0].metric("Base SQLite", f"{int(diagnostico.get('total_base', 0)):,.0f}")
        fila_1[1].metric("Por fecha", f"{int(diagnostico.get('por_fecha', 0)):,.0f}")
        fila_1[2].metric("Por equipo", f"{int(diagnostico.get('por_equipo', 0)):,.0f}")
        fila_1[3].metric("Por operador", f"{int(diagnostico.get('por_operador', 0)):,.0f}")

        st.metric("Resultado final", f"{int(diagnostico.get('resultado_final', 0)):,.0f}")
        st.caption(
            "Fecha aplicada: "
            f"{_formatear_fecha(diagnostico.get('fecha_inicio'))} - {_formatear_fecha(diagnostico.get('fecha_fin'))}"
        )

        equipos = diagnostico.get("equipos") or []
        operadores = diagnostico.get("operadores") or []
        turnos = diagnostico.get("turnos") or []
        st.caption(
            f"Equipos: {len(equipos)} | Operadores: {len(operadores)} | Turnos: {len(turnos)}"
        )

        if int(diagnostico.get("resultado_final", 0)) == 0 and int(diagnostico.get("total_base", 0)) > 0:
            st.warning(
                "La combinación actual de filtros no devuelve registros. "
                "Restablece filtros o reduce el alcance para volver a visualizar gráficos."
            )


def _formatear_fecha_dashboard(valor):
    if not valor:
        return "Sin fecha"
    if hasattr(valor, "strftime"):
        return valor.strftime("%d/%m/%Y")
    fecha = pd.to_datetime(valor, errors="coerce")
    if pd.notna(fecha):
        return fecha.strftime("%d/%m/%Y")
    return str(valor)


def _valores_seleccionados_texto(valores):
    valores = [str(valor).strip() for valor in (valores or []) if str(valor).strip()]
    if not valores:
        return "Todos"
    if len(valores) <= 3:
        return ", ".join(valores)
    return ", ".join(valores[:3]) + f" (+{len(valores) - 3})"


def mostrar_resumen_fuente_activa(df, df_filtrado=None):
    diagnostico = st.session_state.get("dashboard_filter_diagnostics") or {}
    if df is None:
        return
    total_base = int(diagnostico.get("total_base", len(df)))
    resultado = int(diagnostico.get("resultado_final", len(df_filtrado) if df_filtrado is not None else len(df)))
    columna_fecha = "fecha_turno" if "fecha_turno" in df.columns else "Fecha turno"
    fechas = pd.to_datetime(df.get(columna_fecha, pd.Series(dtype=object)), errors="coerce").dt.date.dropna()
    fecha_min = diagnostico.get("fecha_min_fuente") or (fechas.min() if not fechas.empty else None)
    fecha_max = diagnostico.get("fecha_max_fuente") or (fechas.max() if not fechas.empty else None)
    operadores = diagnostico.get("operadores") or []
    equipos = diagnostico.get("equipos") or []

    st.subheader("Resumen de fuente activa")
    col_1, col_2, col_3 = st.columns(3)
    col_1.metric("Registros disponibles antes de filtros", f"{total_base:,.0f}")
    col_2.metric("Registros despues de filtros", f"{resultado:,.0f}")
    col_3.metric("Fecha minima/maxima", f"{_formatear_fecha_dashboard(fecha_min)} - {_formatear_fecha_dashboard(fecha_max)}")
    st.caption(
        "Operadores seleccionados: "
        f"{_valores_seleccionados_texto(operadores)} | Equipos seleccionados: {_valores_seleccionados_texto(equipos)}"
    )


def mostrar_mensaje_sin_registros_filtrados():
    diagnostico = st.session_state.get("dashboard_filter_diagnostics") or {}
    fecha_inicio = _formatear_fecha_dashboard(diagnostico.get("fecha_inicio"))
    fecha_fin = _formatear_fecha_dashboard(diagnostico.get("fecha_fin"))
    fuente_inicio = _formatear_fecha_dashboard(diagnostico.get("fecha_min_fuente"))
    fuente_fin = _formatear_fecha_dashboard(diagnostico.get("fecha_max_fuente"))
    st.warning("No hay registros para los filtros seleccionados.")
    st.info(
        "Rango seleccionado: "
        f"{fecha_inicio} - {fecha_fin}. Rango real de la fuente: {fuente_inicio} - {fuente_fin}. "
        f"Operadores seleccionados: {_valores_seleccionados_texto(diagnostico.get('operadores'))}. "
        "Restablece filtros o amplia el rango de fechas para volver a visualizar graficos."
    )


def tipo_acero(modelo):
    return "Tricono" if str(modelo).strip() == "Sandvik D75KS" else "Bit"


def orden_modelo_acero(modelo):
    orden = {
        "Sandvik D75KS": 1,
        "FlexiROC D65": 2,
        "SmartROC D65": 3,
    }
    return orden.get(str(modelo).strip(), 99)


def numeros_bit_tricono(df):
    columna = buscar_columna(df, "Número serie Tricono/Bit")
    if not columna:
        return ""

    valores = []
    for valor in df[columna].dropna().astype(str):
        texto = valor.strip()
        if texto and texto.lower() not in ("nan", "none", "nat") and texto not in valores:
            valores.append(texto)

    return ", ".join(valores)


def mostrar_imagenes_kpi_equipos(df, *, equipos_esperados_fn, resumen_kpi_equipos_fn=resumen_kpi_equipos, ruta_imagen_equipo_fn=ruta_imagen_equipo, limpiar_entero_fn=limpiar_entero):
    equipos_base = resumen_kpi_equipos_fn(df)
    if equipos_base.empty:
        equipos_base = pd.DataFrame(
            [
                {"Modelo equipo": modelo, "Número equipo": numero, "Equipo": f"{modelo} {numero}"}
                for modelo, numero in equipos_esperados_fn()
            ]
        )

    columnas = st.columns(3)
    for indice, fila in equipos_base.iterrows():
        modelo = str(fila.get("Modelo equipo", ""))
        numero = limpiar_entero_fn(fila.get("Número equipo", ""))
        imagen = ruta_imagen_equipo_fn(modelo, numero)
        with columnas[indice % len(columnas)]:
            if imagen:
                st.image(str(imagen), caption=f"{modelo} {numero}", width="stretch")
            else:
                st.caption(f"{modelo} {numero}")


def resumen_general_operadores(df):
    operador_col = columna_operador_visual(df)
    columnas = [
        "Operador",
        "Disponibilidad promedio",
        "Utilización promedio",
        "Rendimiento consolidado m/h",
        "Metros totales perforados",
    ]
    filtros_sql = st.session_state.get("dashboard_sql_filters")
    usando_excel = usando_fuente_excel()
    if filtros_sql and not usando_excel:
        resumen = db.consultar_resumen_operadores_filtrado(**filtros_sql)
        if not resumen.empty:
            resumen = resumen.reindex(columns=columnas, fill_value=0)
            return resumen.sort_values("Metros totales perforados", ascending=False)

    operadores_base = set(df.get(operador_col, pd.Series(dtype=str)).dropna().astype(str))
    operadores = sorted(operadores_base if usando_excel else set(OPERADORES) | operadores_base)
    filas = []

    for operador in operadores:
        df_operador = df[df[operador_col].astype(str) == operador].copy() if operador_col in df.columns else pd.DataFrame()
        kpis = calcular_kpis_consolidados_dataframe(df_operador)

        filas.append({
            "Operador": operador,
            "Disponibilidad promedio": round(kpis["disponibilidad"], 2),
            "Utilización promedio": round(kpis["utilizacion"], 2),
            "Rendimiento consolidado m/h": round(kpis["rendimiento"], 2),
            "Metros totales perforados": round(kpis["metros"], 2),
        })

    return pd.DataFrame(filas, columns=columnas).sort_values("Metros totales perforados", ascending=False)


def resumen_general_equipos(df, *, resumen_operacional_equipos_fn):
    columnas = [
        "Modelo equipo",
        "Número equipo",
        "Disponibilidad promedio",
        "Utilización promedio",
        "Rendimiento consolidado m/h",
        "Metros totales perforados",
        "Pozos perforados",
        "Horas efectivas perforando",
        "Horas avería equipo",
        "Horas no efectivas",
    ]
    filtros_sql = st.session_state.get("dashboard_sql_filters")
    if filtros_sql and not usando_fuente_excel():
        resumen = db.consultar_resumen_operacional_equipos_filtrado(**filtros_sql)
        if not resumen.empty:
            resumen = resumen.rename(columns={
                "Disponibilidad %": "Disponibilidad promedio",
                "Utilización": "Utilización promedio",
                "Metros perforados": "Metros totales perforados",
            })
            return resumen.reindex(columns=columnas).sort_values("Metros totales perforados", ascending=False)

    if df.empty or not {"Modelo equipo", "Número equipo"}.issubset(df.columns):
        return pd.DataFrame(columns=columnas)

    resumen = resumen_operacional_equipos_fn(df).rename(columns={
        "Disponibilidad %": "Disponibilidad promedio",
        "Utilización": "Utilización promedio",
        "Metros perforados": "Metros totales perforados",
    })
    return resumen[columnas].sort_values("Metros totales perforados", ascending=False)


def resumen_general_aceros(df):
    columnas = [
        "Modelo equipo",
        "Número equipo",
        "Tipo acero",
        "Número Bit / Tricono",
        "Metros totales perforados",
        "Rendimiento consolidado m/h",
    ]
    filtros_sql = st.session_state.get("dashboard_sql_filters")
    if filtros_sql and not usando_fuente_excel():
        resumen = db.consultar_resumen_aceros_filtrado(**filtros_sql)
        if not resumen.empty:
            return resumen

    if df.empty or not {"Modelo equipo", "Número equipo"}.issubset(df.columns):
        return pd.DataFrame(columns=columnas)

    filas = []
    for (modelo, numero), df_equipo in df.groupby(["Modelo equipo", "Número equipo"], dropna=False):
        total_metros, _, rendimiento = totales_productivos(df_equipo)
        filas.append({
            "Modelo equipo": modelo,
            "Número equipo": numero,
            "Tipo acero": tipo_acero(modelo),
            "Número Bit / Tricono": numeros_bit_tricono(df_equipo),
            "Metros totales perforados": round(total_metros, 2),
            "Rendimiento consolidado m/h": round(rendimiento, 2),
        })

    resumen = pd.DataFrame(filas, columns=columnas)
    resumen["_orden_modelo"] = resumen["Modelo equipo"].apply(orden_modelo_acero)
    resumen["_orden_numero"] = pd.to_numeric(resumen["Número equipo"], errors="coerce").fillna(999999)
    return resumen.sort_values(["_orden_modelo", "_orden_numero"]).drop(columns=["_orden_modelo", "_orden_numero"])


def mostrar_tarjetas_kpi_equipos(
    df,
    *,
    resumen_operacional_equipos_fn,
    color_estado_operacional_fn,
    color_texto_estado_operacional_fn,
    ruta_imagen_equipo_fn=ruta_imagen_equipo,
    limpiar_entero_fn=limpiar_entero,
):
    filtros_sql = st.session_state.get("dashboard_sql_filters")
    if filtros_sql and not usando_fuente_excel():
        resumen = db.consultar_resumen_operacional_equipos_filtrado(**filtros_sql)
    else:
        resumen = resumen_operacional_equipos_fn(df)
    if resumen.empty:
        st.info("No hay datos de equipos para construir KPI operacionales.")
        return

    estados = resumen["Estado operacional"].value_counts()
    marcaciones = resumen["Marcación"].value_counts() if "Marcación" in resumen.columns else {}
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Operativos", int(estados.get("Operativo", 0)))
    c2.metric("Parciales", int(estados.get("Operativo parcial", 0)))
    c3.metric("Avería", int(estados.get("Avería", 0)))
    c4.metric("Mantención", int(estados.get("Mantención Programada", 0)))
    c5.metric("Standby sin tajo/patio", int(marcaciones.get("Standby por falta de tajo/Patio", 0)))

    for indice in range(0, len(resumen), 3):
        columnas = st.columns(3)
        for columna, (_, equipo) in zip(columnas, resumen.iloc[indice:indice + 3].iterrows()):
            modelo = str(equipo["Modelo equipo"])
            numero = limpiar_entero_fn(equipo["Número equipo"])
            estado = str(equipo["Estado operacional"])
            color_fondo = color_estado_operacional_fn(estado)
            color_texto = color_texto_estado_operacional_fn(estado)
            imagen = ruta_imagen_equipo_fn(modelo, numero)
            with columna:
                with st.container(border=True):
                    if imagen:
                        st.image(str(imagen), width="stretch")
                    st.markdown(
                        f"""
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">
                            <div>
                                <div style="font-weight:700;font-size:1.02rem;color:#0F172A;">{escape(modelo)}</div>
                                <div style="font-size:0.88rem;color:#475569;">Equipo {escape(numero)}</div>
                            </div>
                            <div style="background:{color_fondo};color:{color_texto};border:1px solid {color_texto}33;border-radius:999px;padding:3px 9px;font-size:0.74rem;font-weight:700;white-space:nowrap;">
                                {escape(estado)}
                            </div>
                        </div>
                        <div style="margin-top:8px;color:#334155;font-size:0.86rem;">Operador: <b>{escape(str(equipo.get("operador_nombre") or equipo["Operador"]) or "Sin operador")}</b></div>
                        """,
                        unsafe_allow_html=True,
                    )
                    k1, k2 = st.columns(2)
                    k1.metric("Metros", f"{equipo['Metros perforados']:,.2f}")
                    k2.metric("Pozos", f"{equipo['Pozos perforados']:,.0f}")
                    k3, k4 = st.columns(2)
                    k3.metric("Rendimiento", f"{equipo['Rendimiento consolidado m/h']:,.2f} m/h")
                    k4.metric("H. efectivas", f"{equipo['Horas efectivas perforando']:,.2f} h")
                    disponibilidad = max(min(float(equipo["Disponibilidad %"]), 100), 0)
                    utilizacion = max(min(float(equipo["Utilización"]), 100), 0)
                    st.caption(f"Disponibilidad {disponibilidad:.2f}%")
                    st.progress(disponibilidad / 100)
                    st.caption(f"Utilización {utilizacion:.2f}%")
                    st.progress(utilizacion / 100)


def _formatear_filtro_activo(valor):
    if valor is None:
        return "Sin filtro"
    if isinstance(valor, (list, tuple, set)):
        valores = [str(item) for item in valor if str(item).strip()]
        return ", ".join(valores) if valores else "Todos"
    if hasattr(valor, "strftime"):
        return valor.strftime("%Y-%m-%d")
    texto = str(valor).strip()
    return texto if texto else "Sin filtro"


def _obtener_df_base_periodo_dashboard(df_completo, filtros):
    if usando_fuente_excel():
        base = df_completo.copy() if df_completo is not None else pd.DataFrame()
        if base.empty or "Fecha turno" not in base.columns:
            return base
        fecha_inicio = (filtros or {}).get("fecha_inicio") or (filtros or {}).get("fecha_desde")
        fecha_fin = (filtros or {}).get("fecha_fin") or (filtros or {}).get("fecha_hasta")
        fechas = pd.to_datetime(base["Fecha turno"], errors="coerce")
        if fecha_inicio is not None:
            base = base[fechas >= pd.to_datetime(fecha_inicio, errors="coerce")]
            fechas = pd.to_datetime(base["Fecha turno"], errors="coerce")
        if fecha_fin is not None:
            base = base[fechas <= pd.to_datetime(fecha_fin, errors="coerce")]
        return base.copy()

    filtros = filtros or {}
    fecha_inicio = filtros.get("fecha_inicio") or filtros.get("fecha_desde")
    fecha_fin = filtros.get("fecha_fin") or filtros.get("fecha_hasta")
    try:
        if db.DB_PATH.exists():
            return db.consultar_registros_edicion(
                fecha_desde=fecha_inicio,
                fecha_hasta=fecha_fin,
                limit=None,
            )
    except Exception:
        pass

    base = df_completo.copy() if df_completo is not None else pd.DataFrame()
    if base.empty or "Fecha turno" not in base.columns:
        return base

    fechas = pd.to_datetime(base["Fecha turno"], errors="coerce")
    if fecha_inicio is not None:
        base = base[fechas >= pd.to_datetime(fecha_inicio, errors="coerce")]
        fechas = pd.to_datetime(base["Fecha turno"], errors="coerce")
    if fecha_fin is not None:
        base = base[fechas <= pd.to_datetime(fecha_fin, errors="coerce")]
    return base.copy()


def mostrar_trazabilidad_kpi_productivo(df_analisis, df_base_periodo=None):
    trazabilidad = kpi_service.trazabilidad_kpis_productivos(df_analisis)
    filtros = st.session_state.get("dashboard_sql_filters", {}) or {}
    comparativo = kpi_service.comparar_base_vs_analisis_kpis(
        df_base_periodo if df_base_periodo is not None else df_analisis,
        df_analisis,
        filtros=filtros,
    )

    with st.expander("Trazabilidad KPI productivo", expanded=False):
        st.caption("Diagnóstico aplicado sobre el mismo conjunto filtrado usado por los KPI visibles del dashboard.")

        fila_1 = st.columns(3)
        fila_1[0].metric("Metros totales", f"{trazabilidad['metros_totales']:,.2f}")
        fila_1[1].metric("Metros productivos", f"{trazabilidad['metros_productivos']:,.2f}")
        fila_1[2].metric("Metros excluidos", f"{trazabilidad['metros_excluidos']:,.2f}")

        fila_2 = st.columns(3)
        fila_2[0].metric("Horas totales", f"{trazabilidad['horas_efectivas_totales']:,.2f}")
        fila_2[1].metric("Horas productivas", f"{trazabilidad['horas_efectivas_productivas']:,.2f}")
        fila_2[2].metric("Horas excluidas", f"{trazabilidad['horas_excluidas']:,.2f}")

        fila_3 = st.columns(3)
        fila_3[0].metric("Registros totales", f"{trazabilidad['registros_totales']:,.0f}")
        fila_3[1].metric("Registros productivos", f"{trazabilidad['registros_productivos']:,.0f}")
        fila_3[2].metric("Registros excluidos", f"{trazabilidad['registros_excluidos']:,.0f}")

        st.caption("Filtros activos")
        filtros_activos = pd.DataFrame(
            [
                {"Filtro": clave, "Valor": _formatear_filtro_activo(valor)}
                for clave, valor in filtros.items()
            ]
        )
        if filtros_activos.empty:
            st.info("No hay filtros activos registrados en la sesión.")
        else:
            st.dataframe(dataframe_visible(filtros_activos), width="stretch", hide_index=True)

        st.caption("Comparativo base completa del periodo vs df_analisis")
        fila_4 = st.columns(3)
        fila_4[0].metric("Registros base periodo", f"{comparativo['registros_base']:,.0f}")
        fila_4[1].metric("Registros df_analisis", f"{comparativo['registros_analisis']:,.0f}")
        fila_4[2].metric("Registros ausentes", f"{comparativo['registros_ausentes']:,.0f}")

        fila_5 = st.columns(2)
        fila_5[0].metric("Metros ausentes", f"{comparativo['metros_ausentes']:,.2f}")
        fila_5[1].metric("Horas ausentes", f"{comparativo['horas_ausentes']:,.2f}")

        detalle_ausentes = comparativo["detalle_registros_ausentes"]
        if detalle_ausentes.empty:
            st.info("No hay registros presentes en la base del periodo que falten en df_analisis.")
        else:
            st.dataframe(dataframe_visible(detalle_ausentes), width="stretch", hide_index=True)

        detalle = trazabilidad["detalle_registros_excluidos"]
        st.caption("Registros excluidos por regla productiva")
        if detalle.empty:
            st.info("No existen registros excluidos para el conjunto filtrado actual.")
        else:
            st.dataframe(dataframe_visible(detalle), width="stretch", hide_index=True)

        sospechosos = kpi_service.detectar_registros_kpi_sospechosos(
            df_base_periodo if df_base_periodo is not None else df_analisis
        )
        st.caption("Registros sospechosos para auditoría KPI")
        if sospechosos.empty:
            st.info("No se detectan registros sospechosos con la regla operacional actual.")
        else:
            st.warning("Se detectaron registros para revisión. No se modifican datos históricos.")
            st.dataframe(dataframe_visible(sospechosos), width="stretch", hide_index=True)


def _render_graficos_tendencia(df, limpiar_entero_fn):
    fecha_col = buscar_columna(df, "Fecha turno", "fecha_turno")
    numero_col = buscar_columna(df, "Número equipo", "numero_equipo")
    disp_col = buscar_columna(df, "Disponibilidad %")
    util_col = buscar_columna(df, "Utilización", "Utilización %")
    metros_col = buscar_columna(df, "Metros perforados")
    rend_col = buscar_columna(df, "Rendimiento m/h")

    if not fecha_col or not numero_col:
        st.info("No hay datos suficientes para graficar tendencias.")
        return

    cols_usar = [c for c in [fecha_col, numero_col, disp_col, util_col, metros_col, rend_col] if c]
    df_plot = df[cols_usar].copy()
    df_plot[fecha_col] = pd.to_datetime(df_plot[fecha_col], errors="coerce")
    df_plot = df_plot.dropna(subset=[fecha_col])
    if df_plot.empty:
        st.info("No hay registros con fecha válida para graficar.")
        return

    df_plot[numero_col] = df_plot[numero_col].astype(str).apply(limpiar_entero_fn)

    agg_dict = {}
    for col in [disp_col, util_col, rend_col]:
        if col:
            df_plot[col] = pd.to_numeric(df_plot[col], errors="coerce")
            agg_dict[col] = "mean"
    if metros_col:
        df_plot[metros_col] = pd.to_numeric(df_plot[metros_col], errors="coerce")
        agg_dict[metros_col] = "sum"

    df_grouped = df_plot.groupby([fecha_col, numero_col]).agg(agg_dict).reset_index()
    equipos = sorted(df_grouped[numero_col].unique())
    palette = px.colors.qualitative.Plotly

    _GRID = "rgba(255,255,255,0.08)"
    _TICK = dict(color="rgba(255,255,255,0.6)")
    _TITLE_FONT = dict(color="white", size=13)
    _LEGEND = dict(
        orientation="v",
        yanchor="top", y=1,
        xanchor="left", x=1.02,
        bgcolor="rgba(0,0,0,0.6)",
        bordercolor="rgba(255,255,255,0.15)",
        borderwidth=1,
        font=dict(size=11, color="white"),
        groupclick="toggleitem",
    )
    _LAYOUT = dict(
        height=300,
        margin=dict(l=0, r=160, t=40, b=0),
        plot_bgcolor="rgba(255,255,255,0.05)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=_LEGEND,
    )
    _XAXIS = dict(gridcolor=_GRID, tickfont=_TICK)
    _YAXIS = dict(gridcolor=_GRID, tickfont=_TICK)
    _LABEL_COLOR = dict(color="rgba(255,255,255,0.5)")

    col1, col2 = st.columns([1, 1])

    # ── Gráfico 1: Disponibilidad y Utilización ────────────────────────
    with col1:
        fig1 = go.Figure()
        for idx, equipo in enumerate(equipos):
            df_eq = df_grouped[df_grouped[numero_col] == equipo].sort_values(fecha_col)
            color = palette[idx % len(palette)]
            if disp_col:
                fig1.add_trace(go.Scatter(
                    x=df_eq[fecha_col], y=df_eq[disp_col],
                    name=f"Disp. {equipo}",
                    mode="lines+markers",
                    line=dict(width=2.5, color=color),
                    marker=dict(size=5),
                    legendgroup=str(equipo),
                    legendgrouptitle_text=f"Equipo {equipo}",
                ))
            if util_col:
                fig1.add_trace(go.Scatter(
                    x=df_eq[fecha_col], y=df_eq[util_col],
                    name=f"Util. {equipo}",
                    mode="lines",
                    line=dict(width=1.5, color=color, dash="dot"),
                    legendgroup=str(equipo),
                ))
        fig1.add_hline(
            y=85, line_dash="dash", line_color="orange",
            annotation_text="Meta disp. 85%", annotation_position="bottom right",
        )
        fig1.update_layout(
            title=dict(text="Disponibilidad y Utilización por equipo", font=_TITLE_FONT),
            xaxis=_XAXIS,
            yaxis=dict(**_YAXIS, title=dict(text="%", font=_LABEL_COLOR)),
            **_LAYOUT,
        )
        st.plotly_chart(fig1, use_container_width=True)

    # ── Gráfico 2: Metros perforados ───────────────────────────────────
    with col2:
        fig2 = go.Figure()
        if metros_col:
            for idx, equipo in enumerate(equipos):
                df_eq = df_grouped[df_grouped[numero_col] == equipo].sort_values(fecha_col)
                fig2.add_trace(go.Bar(
                    x=df_eq[fecha_col], y=df_eq[metros_col],
                    name=equipo,
                    marker_color=palette[idx % len(palette)],
                    legendgroup=str(equipo),
                ))
        fig2.update_layout(
            barmode="stack",
            title=dict(text="Metros perforados por equipo", font=_TITLE_FONT),
            xaxis=_XAXIS,
            yaxis=dict(**_YAXIS, title=dict(text="m", font=_LABEL_COLOR)),
            **_LAYOUT,
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── Gráfico 3: Rendimiento m/h ─────────────────────────────────────
    if rend_col:
        col3, _ = st.columns([1, 1])
        with col3:
            fig3 = go.Figure()
            for idx, equipo in enumerate(equipos):
                df_eq = df_grouped[df_grouped[numero_col] == equipo].sort_values(fecha_col)
                fig3.add_trace(go.Scatter(
                    x=df_eq[fecha_col], y=df_eq[rend_col],
                    name=equipo,
                    mode="lines+markers",
                    line=dict(width=2.5, color=palette[idx % len(palette)]),
                    marker=dict(size=5),
                    legendgroup=str(equipo),
                ))
            fig3.add_hline(
                y=30, line_dash="dash", line_color="green",
                annotation_text="Meta 30 m/h", annotation_position="bottom right",
            )
            fig3.update_layout(
                title=dict(text="Rendimiento m/h por equipo", font=_TITLE_FONT),
                xaxis=_XAXIS,
                yaxis=dict(**_YAXIS, title=dict(text="m/h", font=_LABEL_COLOR)),
                **{**_LAYOUT, "height": 280},
            )
            st.plotly_chart(fig3, use_container_width=True)


def _render_ranking_horas_motor(df, limpiar_entero_fn):
    section_header(
        "Ranking horas de motor por operador",
        "Acumulado del período · Base de pago por horas de horómetro",
        kicker="Ranking",
    )

    col_hrs = buscar_columna(df,
        "Diferencia horómetro", "Diferencia horometro",
        "Diferencia Horómetro", "dif_horometro",
    )
    col_hi = buscar_columna(df, "Horómetro inicial", "Horometro inicial", "horometro_inicial")
    col_hf = buscar_columna(df, "Horómetro final",   "Horometro final",   "horometro_final")
    col_op = buscar_columna(df, "Operador", "operador")
    col_eq = buscar_columna(df, "Número equipo", "Numero equipo", "numero_equipo")
    col_fe = buscar_columna(df, "Fecha turno", "Fecha", "fecha_turno")

    if not col_op:
        st.info("Sin columna Operador.")
        return

    df_w = df.copy()

    if not col_hrs and col_hi and col_hf:
        df_w["_hrs_motor"] = (
            pd.to_numeric(df_w[col_hf], errors="coerce") -
            pd.to_numeric(df_w[col_hi], errors="coerce")
        ).clip(lower=0)
        col_hrs = "_hrs_motor"
    elif not col_hrs:
        st.info("No se encontró columna de horómetro en los datos.")
        return

    df_w[col_hrs] = pd.to_numeric(df_w[col_hrs], errors="coerce").fillna(0)
    df_w = df_w[df_w[col_hrs] > 0]

    if df_w.empty:
        st.info("No hay registros de horómetro en el período seleccionado.")
        return

    agg = {col_hrs: ["sum", "count", "mean"]}
    if col_eq:
        agg[col_eq] = lambda x: ", ".join(sorted(set(str(limpiar_entero_fn(v)) for v in x.dropna())))
    if col_fe:
        agg[col_fe] = "max"

    rank = df_w.groupby(col_op).agg(agg).reset_index()
    rank.columns = ["operador", "horas_motor", "turnos", "promedio_turno"] + (
        (["equipos"] if col_eq else []) + (["ultima_fecha"] if col_fe else [])
    )
    rank = rank.sort_values("horas_motor", ascending=False).reset_index(drop=True)
    rank["horas_motor"]    = rank["horas_motor"].round(1)
    rank["promedio_turno"] = rank["promedio_turno"].round(2)

    total  = rank["horas_motor"].sum()
    maximo = rank["horas_motor"].max()
    prom   = rank["horas_motor"].mean()

    col_t, col_g = st.columns([1, 1])

    with col_t:
        st.markdown("##### Posiciones")
        for i, row in rank.iterrows():
            pos = i + 1
            pct_barra = row["horas_motor"] / maximo if maximo > 0 else 0
            pct_total = row["horas_motor"] / total * 100 if total > 0 else 0
            emoji = "🥇" if pos == 1 else "🥈" if pos == 2 else "🥉" if pos == 3 else ("⬇" if pos == len(rank) else f"#{pos}")
            color = "#F97316" if pos == 1 else "#94A3B8" if pos == 2 else "#B45309" if pos == 3 else ("#EF4444" if pos == len(rank) else "#3B82F6")
            equipos_txt = row.get("equipos", "") if "equipos" in row.index else ""

            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.04);border:0.5px solid rgba(255,255,255,0.10);
                        border-radius:10px;padding:10px 14px;margin-bottom:7px;">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <div style="display:flex;align-items:center;gap:10px;">
                  <span style="font-size:18px;">{emoji}</span>
                  <div>
                    <p style="margin:0;font-size:14px;font-weight:500;color:white;">{row['operador']}</p>
                    <p style="margin:0;font-size:11px;color:rgba(255,255,255,0.55);">
                      {int(row['turnos'])} turnos{(' · Eq: ' + str(equipos_txt)) if equipos_txt else ''}
                    </p>
                  </div>
                </div>
                <div style="text-align:right;">
                  <p style="margin:0;font-size:18px;font-weight:600;color:{color};">{row['horas_motor']:.1f} h</p>
                  <p style="margin:0;font-size:11px;color:rgba(255,255,255,0.55);">
                    {pct_total:.1f}% del total · {row['promedio_turno']:.1f} h/turno
                  </p>
                </div>
              </div>
              <div style="background:rgba(255,255,255,0.08);border-radius:4px;height:5px;">
                <div style="background:{color};width:{pct_barra*100:.1f}%;height:5px;border-radius:4px;"></div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(f"""
        <div style="background:rgba(249,115,22,0.10);border:1px solid rgba(249,115,22,0.25);
                    border-radius:10px;padding:10px 14px;margin-top:4px;
                    display:flex;justify-content:space-between;">
          <span style="color:rgba(255,255,255,0.70);font-size:13px;font-weight:500;">
            Total · {len(rank)} operadores
          </span>
          <span style="color:#F97316;font-size:16px;font-weight:600;">{total:.1f} h</span>
        </div>
        """, unsafe_allow_html=True)

    with col_g:
        st.markdown("##### Distribución")
        colores = [
            "#F97316" if i == 0 else "#EF4444" if i == len(rank) - 1 else "#3B82F6"
            for i in range(len(rank))
        ]
        fig = go.Figure(go.Bar(
            x=rank["horas_motor"],
            y=rank["operador"],
            orientation="h",
            marker=dict(color=colores, line=dict(width=0)),
            text=[f"{h:.1f} h" for h in rank["horas_motor"]],
            textposition="outside",
            textfont=dict(color="rgba(255,255,255,0.80)", size=11),
            hovertemplate="<b>%{y}</b><br>%{x:.1f} h horómetro<extra></extra>",
        ))
        fig.add_vline(
            x=prom, line_dash="dash", line_color="rgba(255,255,255,0.30)",
            annotation_text=f"Prom. {prom:.1f}h",
            annotation_font_color="rgba(255,255,255,0.50)",
            annotation_font_size=10,
        )
        fig.update_layout(
            height=max(300, len(rank) * 46),
            margin=dict(l=0, r=55, t=10, b=10),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(
                gridcolor="rgba(255,255,255,0.07)",
                tickfont=dict(color="rgba(255,255,255,0.55)", size=10),
                title=dict(text="Horas horómetro", font=dict(color="rgba(255,255,255,0.45)", size=11)),
            ),
            yaxis=dict(tickfont=dict(color="rgba(255,255,255,0.80)", size=11), autorange="reversed"),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

        c1, c2, c3 = st.columns(3)
        c1.metric("Mayor", f"{rank['horas_motor'].iloc[0]:.1f} h", rank["operador"].iloc[0].split()[0])
        c2.metric("Promedio", f"{prom:.1f} h")
        c3.metric(
            "Menor", f"{rank['horas_motor'].iloc[-1]:.1f} h",
            f"-{rank['horas_motor'].iloc[0] - rank['horas_motor'].iloc[-1]:.1f} h",
            delta_color="inverse",
        )


def _render_panel_estado_flota(
    df,
    resumen_operacional_equipos_fn,
    color_estado_operacional_fn,
    color_texto_estado_operacional_fn,
    limpiar_entero_fn,
):
    if df.empty:
        return
    fecha_col = buscar_columna(df, "Fecha turno", "fecha_turno")
    numero_col = buscar_columna(df, "Número equipo", "numero_equipo")
    if not fecha_col or not numero_col:
        return
    sort_cols = [fecha_col]
    hora_col = buscar_columna(df, "Hora registro", "hora_registro")
    if hora_col:
        sort_cols.append(hora_col)
    df_sorted = df.copy()
    df_sorted[fecha_col] = pd.to_datetime(df_sorted[fecha_col], errors="coerce")
    df_sorted = df_sorted.sort_values(sort_cols, ascending=False, na_position="last")
    df_ultimo = df_sorted.drop_duplicates(subset=[numero_col])
    resumen = resumen_operacional_equipos_fn(df_ultimo)
    if resumen.empty:
        return
    n_cols = min(len(resumen), 4)
    cols = st.columns(n_cols)
    for i, (_, fila) in enumerate(resumen.iterrows()):
        estado = str(fila.get("Estado operacional") or "Sin marcación")
        modelo = str(fila.get("Modelo equipo") or "")
        numero = str(fila.get("Número equipo") or "")
        operador = str(fila.get("Operador") or "—") or "—"
        metros = float(fila.get("Metros perforados") or 0)
        disponibilidad = float(fila.get("Disponibilidad %") or 0)
        utilizacion = float(fila.get("Utilización") or 0)
        color_fondo = color_estado_operacional_fn(estado)
        color_texto = color_texto_estado_operacional_fn(estado)
        with cols[i % n_cols]:
            st.markdown(
                f"""<div style="background:{color_fondo}; border-radius:12px; padding:14px 16px; margin-bottom:8px;">
  <div style="font-size:11px; font-weight:500; color:{color_texto}; text-transform:uppercase; letter-spacing:0.05em;">{escape(modelo)} {escape(numero)}</div>
  <div style="font-size:18px; font-weight:500; color:{color_texto}; margin:4px 0;">{escape(estado)}</div>
  <div style="font-size:12px; color:{color_texto}; opacity:0.8;">Operador: {escape(operador)}</div>
  <div style="font-size:12px; color:{color_texto}; opacity:0.8;">{metros:.1f} m · {disponibilidad:.0f}% disp · {utilizacion:.0f}% util</div>
</div>""",
                unsafe_allow_html=True,
            )


def dashboard(
    df,
    *,
    aplicar_filtros_fn,
    mostrar_alerta_reportes_faltantes_fn,
    mostrar_alertas_operacionales_fn,
    seccion_reporte_pdf_fn,
    resumen_operacional_equipos_fn,
    equipos_esperados_fn,
    ruta_imagen_equipo_fn,
    limpiar_entero_fn,
    color_estado_operacional_fn,
    color_texto_estado_operacional_fn,
    columnas_horas_turno_fn,
    etiqueta_hora_fn,
):
    section_header(
        "Dashboard operacional",
        "Lectura consolidada de productividad, cumplimiento, alertas, equipos y operadores.",
        kicker="Operacion",
    )

    if df.empty:
        st.info("Aún no existe historial. Guarda el primer reporte para ver tablas y gráficos.")
        return

    section_header("Estado actual de flota", "Estado operacional del último turno registrado por equipo.", kicker="Flota")
    _render_panel_estado_flota(
        df,
        resumen_operacional_equipos_fn,
        color_estado_operacional_fn,
        color_texto_estado_operacional_fn,
        limpiar_entero_fn,
    )

    with st.expander("Tendencia operacional", expanded=True):
        _render_graficos_tendencia(df, limpiar_entero_fn)

    with st.expander("Ranking horas de motor", expanded=True):
        _render_ranking_horas_motor(df, limpiar_entero_fn=limpiar_entero_fn)

    df_filtrado = aplicar_filtros_fn(df)
    if df_filtrado.empty:
        mostrar_resumen_fuente_activa(df, df_filtrado)
        mostrar_mensaje_sin_registros_filtrados()
        mostrar_diagnostico_filtros()
        return

    mostrar_resumen_fuente_activa(df, df_filtrado)
    seccion_reporte_pdf_fn(df_filtrado)

    df_analisis = df_filtrado[
        ~(
            df_filtrado["Modelo equipo"].astype(str).str.strip().str.upper().eq("PV271")
            & df_filtrado["Número equipo"].astype(str).apply(limpiar_entero_fn).eq("9291")
        )
    ].copy()
    df_productivo = df_analisis.copy() if usando_fuente_excel() else registros_productivos(df_analisis)

    mostrar_alerta_reportes_faltantes_fn(df_analisis)
    mostrar_alertas_operacionales_fn(
        df_analisis,
        consultar_alertas_fn=db.consultar_alertas_operacionales_filtradas,
        filtros_sql=st.session_state.get("dashboard_sql_filters"),
    )

    filtros_dashboard = st.session_state.get("dashboard_sql_filters", {}) or {}
    df_base_periodo = _obtener_df_base_periodo_dashboard(df, filtros_dashboard)
    if filtros_dashboard and not usando_fuente_excel():
        resumen_flota_control = db.consultar_resumen_operacional_equipos_filtrado(**filtros_dashboard)
    else:
        resumen_flota_control = resumen_operacional_equipos_fn(df_analisis)

    mostrar_panel_graficos_resumen(df_analisis, filtros_dashboard, resumen_flota=resumen_flota_control, df_full=df)

    with st.expander("Trazabilidad y diagnóstico de filtros", expanded=False):
        mostrar_trazabilidad_kpi_productivo(df_analisis, df_base_periodo=df_base_periodo)
        mostrar_diagnostico_filtros()

    section_header("Avance de malla", "Seguimiento operacional de pozos y metros por malla activa.", kicker="Malla")
    resumen_mallas = resumen_avance_malla()
    if resumen_mallas.empty:
        st.info("Aún no existen mallas registradas para mostrar avance.")
    else:
        orden = ["fecha", "turno", "banco", "fase", "malla"]
        existentes = [col for col in orden if col in resumen_mallas.columns]
        if existentes:
            resumen_mallas = resumen_mallas.sort_values(
                existentes,
                ascending=[False] * len(existentes),
                na_position="last",
            )
        malla_activa = resumen_mallas.iloc[0]
        st.caption(
            f"Malla activa: {malla_activa.get('banco', '')} | {malla_activa.get('fase', '')} | {malla_activa.get('malla', '')} "
            f"| Fecha: {malla_activa.get('fecha', '')} | Turno: {malla_activa.get('turno', '')}"
        )
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Pozos totales", int(malla_activa.get("pozos_totales", 0) or 0))
        col_m2.metric("Pozos perforados", int(malla_activa.get("pozos_perforados", 0) or 0))
        col_m3.metric("Pozos pendientes", int(malla_activa.get("pozos_pendientes", 0) or 0))
        col_m4, col_m5, col_m6 = st.columns(3)
        col_m4.metric("Metros planificados", f"{float(malla_activa.get('metros_planificados', 0) or 0):,.2f}")
        col_m5.metric("Metros perforados", f"{float(malla_activa.get('metros_perforados', 0) or 0):,.2f}")
        col_m6.metric("Avance", f"{float(malla_activa.get('porcentaje_avance', 0) or 0):,.2f}%")

    section_header("Analisis detallado", "Graficos, tablas y trazabilidad por dimension operacional.", kicker="Detalle")
    tabs = st.tabs(["Resumen", "Operadores", "Equipos", "Distribución de horas", "Historial"])

    with tabs[0]:
        st.subheader("Resumen")
        col_a, col_b = st.columns(2)
        with col_a:
            mostrar_figura(
                fig_ranking_operadores(df_productivo),
                "No hay registros productivos para ranking.",
                key="grafico_resumen_ranking_operadores",
            )
        with col_b:
            mostrar_figura(
                fig_distribucion_horas(df_analisis),
                "No hay horas válidas para graficar.",
                key="grafico_resumen_distribucion_horas",
            )

    with tabs[1]:
        st.subheader("Operadores")
        mostrar_figura(
            fig_ranking_operadores(df_productivo),
            "No hay registros productivos para operadores.",
            key="grafico_operadores_ranking",
        )
        operador_col = columna_operador_visual(df_productivo)
        tabla_operadores = calcular_rendimiento_consolidado(df_productivo, [operador_col]).sort_values(
            "Rendimiento m/h",
            ascending=False,
        )
        if operador_col != "Operador":
            tabla_operadores = tabla_operadores.rename(columns={operador_col: "Operador"})
        st.dataframe(dataframe_visible(tabla_operadores), width="stretch", hide_index=True)

    with tabs[2]:
        st.subheader("Equipos")
        st.subheader("KPI operacionales por equipo")
        mostrar_tarjetas_kpi_equipos(
            df_analisis,
            resumen_operacional_equipos_fn=resumen_operacional_equipos_fn,
            color_estado_operacional_fn=color_estado_operacional_fn,
            color_texto_estado_operacional_fn=color_texto_estado_operacional_fn,
            ruta_imagen_equipo_fn=ruta_imagen_equipo_fn,
            limpiar_entero_fn=limpiar_entero_fn,
        )

        graficos_kpi = [
            (
                fig_kpi_equipo(df_analisis, "Metros perforados", "Metros perforados por equipo", color="#2563EB"),
                "No hay metros productivos por equipo.",
                "grafico_kpi_equipos_metros",
            ),
            (
                fig_kpi_equipo(df_analisis, "Pozos perforados", "Pozos perforados por equipo", color="#7C3AED"),
                "No hay pozos perforados por equipo.",
                "grafico_kpi_equipos_pozos",
            ),
            (
                fig_kpi_equipo(df_analisis, "Disponibilidad %", "Disponibilidad por equipo", "%", "#15803D"),
                "No hay datos de disponibilidad por equipo.",
                "grafico_kpi_equipos_disponibilidad",
            ),
            (
                fig_kpi_equipo(df_analisis, "Utilización", "Utilización por equipo", "%", "#0F766E"),
                "No hay datos de utilización por equipo.",
                "grafico_kpi_equipos_utilizacion",
            ),
            (
                fig_kpi_equipo(df_analisis, "Rendimiento consolidado m/h", "Rendimiento consolidado por equipo", " m/h", "#0F766E"),
                "No hay rendimiento productivo por equipo.",
                "grafico_kpi_equipos_rendimiento",
            ),
            (
                fig_kpi_equipo(df_analisis, "Horas efectivas perforando", "Horas efectivas perforando por equipo", " h", "#2563EB"),
                "No hay horas efectivas por equipo.",
                "grafico_kpi_equipos_horas_efectivas",
            ),
            (
                fig_kpi_equipo(df_analisis, "Horas avería equipo", "Horas avería equipo por equipo", " h", "#B91C1C"),
                "No hay horas de avería por equipo.",
                "grafico_kpi_equipos_horas_averia",
            ),
        ]
        for indice in range(0, len(graficos_kpi), 2):
            col_a, col_b = st.columns(2)
            for columna, item in zip((col_a, col_b), graficos_kpi[indice:indice + 2]):
                figura, mensaje, key = item
                with columna:
                    mostrar_figura(figura, mensaje, key=key)

    with tabs[3]:
        st.subheader("Distribución de horas")
        mostrar_figura(
            fig_distribucion_horas(df_analisis),
            "No hay horas válidas para graficar.",
            key="grafico_horas_distribucion",
        )
        horas = {
            etiqueta_hora_fn(columna): pd.to_numeric(df_analisis[columna], errors="coerce").fillna(0).sum()
            for columna in columnas_horas_turno_fn()
            if columna in df_analisis.columns
        }
        st.dataframe(
            pd.DataFrame({"Categoría": horas.keys(), "Horas": [round(valor, 2) for valor in horas.values()]}),
            width="stretch",
            hide_index=True,
        )

    with tabs[4]:
        st.subheader("Historial")
        columnas = [
            "Fecha turno",
            "Modelo equipo",
            "Número equipo",
            "Operador",
            "operador_codigo",
            "Turno",
            "Banco",
            "Malla",
            "Fase",
            "Tipo detención",
            "Estatus del Equipo",
            "Horas efectivas perforando",
            "Horas detención mecánica",
            "Horas detención No efectivas",
            "Metros perforados",
            "Rendimiento m/h",
            "Disponibilidad %",
            "Utilización",
            "Observaciones",
        ]
        visibles = [col for col in columnas if col in df_filtrado.columns]
        historial = df_filtrado[visibles].copy()
        if "operador_nombre" in df_filtrado.columns and "Operador" in historial.columns:
            nombres = df_filtrado.loc[historial.index, "operador_nombre"].fillna("").astype(str).str.strip()
            historial.loc[nombres.ne(""), "Operador"] = nombres[nombres.ne("")]
        if "Banco" in historial.columns:
            historial["Banco"] = historial["Banco"].apply(lambda valor: ", ".join(str(item).strip() for item in str(valor).split(",") if str(item).strip()))
        historial = historial.sort_values("Fecha turno", na_position="last") if "Fecha turno" in visibles else historial
        if not historial.empty:
            total_registros = len(historial)
            filas_por_pagina = st.number_input(
                "Filas por página",
                min_value=1,
                max_value=1000,
                value=min(250, total_registros),
                step=25,
                key="dashboard_historial_filas_pagina",
            )
            total_paginas = max(1, (total_registros + int(filas_por_pagina) - 1) // int(filas_por_pagina))
            pagina = st.number_input(
                "Página",
                min_value=1,
                max_value=total_paginas,
                value=1,
                step=1,
                key="dashboard_historial_pagina",
            )
            inicio = (int(pagina) - 1) * int(filas_por_pagina)
            fin = min(inicio + int(filas_por_pagina), total_registros)
            st.caption(f"Mostrando {inicio + 1}-{fin} de {total_registros} registros.")
            historial = historial.iloc[inicio:fin]
        st.dataframe(
            dataframe_visible(historial),
            width="stretch",
            hide_index=True,
            column_config={
                "Operador": st.column_config.TextColumn("Operador", pinned=True),
                "Modelo equipo": st.column_config.TextColumn("Modelo equipo", pinned=True),
                "Número equipo": st.column_config.TextColumn("Número equipo", pinned=True),
            },
        )

    with st.expander("Tablas de detalle operacional", expanded=False):
        section_header("Resumen general por operador", "Productividad, disponibilidad y rendimiento consolidado por persona.", kicker="Tablas")
        st.dataframe(
            dataframe_visible(resumen_general_operadores(df_analisis)),
            width="stretch",
            hide_index=True,
            column_config={
                "Operador": st.column_config.TextColumn("Operador", pinned=True),
                "Disponibilidad promedio": st.column_config.NumberColumn(format="%.2f%%"),
                "Utilización promedio": st.column_config.NumberColumn(format="%.2f%%"),
                "Rendimiento consolidado m/h": st.column_config.NumberColumn(format="%.2f"),
                "Metros totales perforados": st.column_config.NumberColumn(format="%.2f"),
            },
        )

        section_header("Resumen general por equipo", "Estado y productividad consolidada de la flota.", kicker="Tablas")
        st.dataframe(
            dataframe_visible(resumen_general_equipos(df_analisis, resumen_operacional_equipos_fn=resumen_operacional_equipos_fn)),
            width="stretch",
            hide_index=True,
            column_config={
                "Modelo equipo": st.column_config.TextColumn("Modelo equipo", pinned=True),
                "Número equipo": st.column_config.TextColumn("Número equipo", pinned=True),
                "Disponibilidad promedio": st.column_config.NumberColumn(format="%.2f%%"),
                "Utilización promedio": st.column_config.NumberColumn(format="%.2f%%"),
                "Rendimiento consolidado m/h": st.column_config.NumberColumn(format="%.2f"),
                "Metros totales perforados": st.column_config.NumberColumn(format="%.2f"),
                "Pozos perforados": st.column_config.NumberColumn(format="%.0f"),
                "Horas efectivas perforando": st.column_config.NumberColumn(format="%.2f"),
                "Horas avería equipo": st.column_config.NumberColumn(format="%.2f"),
                "Horas no efectivas": st.column_config.NumberColumn(format="%.2f"),
            },
        )

        section_header("Resumen general de aceros de perforacion", "Metros y rendimiento por configuracion de aceros.", kicker="Tablas")
        st.dataframe(
            dataframe_visible(resumen_general_aceros(df_analisis)),
            width="stretch",
            hide_index=True,
            column_config={
                "Modelo equipo": st.column_config.TextColumn("Modelo equipo", pinned=True),
                "Número equipo": st.column_config.TextColumn("Número equipo", pinned=True),
                "Tipo acero": st.column_config.TextColumn("Tipo acero"),
                "Número Bit / Tricono": st.column_config.TextColumn("Número Bit / Tricono"),
                "Metros totales perforados": st.column_config.NumberColumn(format="%.2f"),
                "Rendimiento consolidado m/h": st.column_config.NumberColumn(format="%.2f"),
            },
        )
