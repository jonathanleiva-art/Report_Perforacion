from xml.sax.saxutils import escape

import pandas as pd
import streamlit as st

import db
from charts import (
    fig_distribucion_horas,
    fig_kpi_equipo,
    fig_ranking_operadores,
    resumen_kpi_equipos,
)
from metrics import calcular_rendimiento_consolidado, registros_productivos
from services import kpi_service
from services.malla_service import resumen_avance_malla
from utils import OPERADORES, limpiar_entero, ruta_imagen_equipo

REEMPLAZOS_TEXTO_VISIBLE = {
    "Número": "Número",
    "Código": "Código",
    "Tipo detención": "Tipo detención",
    "Causa detención": "Causa detención",
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


def serie_numerica(df, *columnas):
    return kpi_service.serie_numerica(df, *columnas)


def totales_productivos(df):
    return kpi_service.totales_productivos(df)


def mostrar_figura(fig, mensaje, key):
    if fig is None:
        st.info(texto_visible(mensaje))
    else:
        st.plotly_chart(fig, width="stretch", key=key)


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
    columnas = [
        "Operador",
        "Disponibilidad promedio",
        "Utilización promedio",
        "Rendimiento consolidado m/h",
        "Metros totales perforados",
    ]
    filtros_sql = st.session_state.get("dashboard_sql_filters")
    if filtros_sql:
        resumen = db.consultar_resumen_operadores_filtrado(**filtros_sql)
        if not resumen.empty:
            resumen = resumen.reindex(columns=columnas, fill_value=0)
            return resumen.sort_values("Metros totales perforados", ascending=False)

    operadores = sorted(set(OPERADORES) | set(df.get("Operador", pd.Series(dtype=str)).dropna().astype(str)))
    filas = []

    for operador in operadores:
        df_operador = df[df["Operador"].astype(str) == operador].copy() if "Operador" in df.columns else pd.DataFrame()
        disponibilidad = serie_numerica(df_operador, "Disponibilidad %")
        utilizacion = serie_numerica(df_operador, "Utilización %", "Utilizacion %")
        total_metros, _, rendimiento = totales_productivos(df_operador)

        filas.append({
            "Operador": operador,
            "Disponibilidad promedio": round(disponibilidad.mean(), 2) if not disponibilidad.empty else 0.0,
            "Utilización promedio": round(utilizacion.mean(), 2) if not utilizacion.empty else 0.0,
            "Rendimiento consolidado m/h": round(rendimiento, 2),
            "Metros totales perforados": round(total_metros, 2),
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
    if filtros_sql:
        resumen = db.consultar_resumen_operacional_equipos_filtrado(**filtros_sql)
        if not resumen.empty:
            resumen = resumen.rename(columns={
                "Disponibilidad %": "Disponibilidad promedio",
                "Utilización %": "Utilización promedio",
                "Metros perforados": "Metros totales perforados",
            })
            return resumen.reindex(columns=columnas).sort_values("Metros totales perforados", ascending=False)

    if df.empty or not {"Modelo equipo", "Número equipo"}.issubset(df.columns):
        return pd.DataFrame(columns=columnas)

    resumen = resumen_operacional_equipos_fn(df).rename(columns={
        "Disponibilidad %": "Disponibilidad promedio",
        "Utilización %": "Utilización promedio",
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
    if filtros_sql:
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
    if filtros_sql:
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
                        <div style="margin-top:8px;color:#334155;font-size:0.86rem;">Operador: <b>{escape(str(equipo["Operador"]) or "Sin operador")}</b></div>
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
                    utilizacion = max(min(float(equipo["Utilización %"]), 100), 0)
                    st.caption(f"Disponibilidad {disponibilidad:.2f}%")
                    st.progress(disponibilidad / 100)
                    st.caption(f"Utilización {utilizacion:.2f}%")
                    st.progress(utilizacion / 100)


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
    st.header("Dashboard operacional")

    if df.empty:
        st.info("Aún no existe historial. Guarda el primer reporte para ver tablas y gráficos.")
        return

    df_filtrado = aplicar_filtros_fn(df)
    if df_filtrado.empty:
        st.warning("No hay registros para los filtros seleccionados.")
        return

    seccion_reporte_pdf_fn(df_filtrado)

    df_analisis = df_filtrado[
        ~(
            df_filtrado["Modelo equipo"].astype(str).str.strip().str.upper().eq("PV271")
            & df_filtrado["Número equipo"].astype(str).apply(limpiar_entero_fn).eq("9291")
        )
    ].copy()
    df_productivo = registros_productivos(df_analisis)
    rendimiento = calcular_rendimiento_consolidado(df_analisis)

    mostrar_alerta_reportes_faltantes_fn(df_analisis)
    mostrar_alertas_operacionales_fn(
        df_analisis,
        consultar_alertas_fn=db.consultar_alertas_operacionales_filtradas,
        filtros_sql=st.session_state.get("dashboard_sql_filters"),
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Metros productivos", f"{df_productivo['Metros perforados'].sum():,.2f}")
    m2.metric("Horas efectivas", f"{df_productivo['Horas efectivas perforando'].sum():,.2f}")
    m3.metric("Rendimiento real", f"{rendimiento:.2f} m/h")
    m4.metric("Registros", f"{len(df_filtrado):,.0f}")

    st.subheader("Avance de Malla")
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
        tabla_operadores = calcular_rendimiento_consolidado(df_productivo, ["Operador"]).sort_values(
            "Rendimiento m/h",
            ascending=False,
        )
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
                fig_kpi_equipo(df_analisis, "Utilización %", "Utilización por equipo", "%", "#0F766E"),
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
            "Turno",
            "Banco",
            "Malla",
            "Fase",
            "Tipo detención",
            "Causa detención",
            "Horas efectivas perforando",
            "Horas detención mecánica",
            "Horas detención No efectivas",
            "Metros perforados",
            "Rendimiento m/h",
            "Disponibilidad %",
            "Utilización %",
            "Observaciones",
        ]
        visibles = [col for col in columnas if col in df_filtrado.columns]
        historial = df_filtrado[visibles].copy()
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

    st.subheader("Resumen general por operador")
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

    st.subheader("Resumen general por equipo")
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

    st.subheader("Resumen general de aceros de perforación")
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
