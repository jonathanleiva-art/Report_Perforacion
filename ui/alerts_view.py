from unicodedata import normalize

import pandas as pd
import streamlit as st

from alerts import evaluar_alertas_operacionales
from ui.formatting import dataframe_visible, texto_visible
from utils import HORAS_TURNO


def mostrar_alertas_operacionales(df, consultar_alertas_fn=None, filtros_sql=None):
    st.subheader("Alertas operacionales")
    if consultar_alertas_fn is not None and filtros_sql is not None:
        resultado = consultar_alertas_fn(**filtros_sql, horas_turno=HORAS_TURNO)
        detalle = resultado.get("detalle", pd.DataFrame())
    else:
        if df is None or df.empty:
            st.info("No hay registros para evaluar alertas operacionales.")
            return
        resultado = evaluar_alertas_operacionales(df, horas_turno=HORAS_TURNO)
        detalle = resultado.get("detalle", pd.DataFrame())

    for tipo, mensaje in resultado["mensajes"]:
        if tipo == "error":
            st.error(texto_visible(mensaje))
        elif tipo == "success":
            st.success(texto_visible(mensaje))
        else:
            st.warning(texto_visible(mensaje))

    if resultado["sin_alertas"]:
        st.success("Sin alertas operacionales para los filtros actuales.")
        return

    if not detalle.empty:
        st.markdown("**Detalle de alertas**")
        detalle_filtrado = filtrar_detalle_alertas(detalle)
        mostrar_resumen_alertas(detalle_filtrado)
        total_registros = len(detalle_filtrado)
        if total_registros > 0:
            filas_por_pagina = st.number_input(
                "Filas por página",
                min_value=1,
                max_value=1000,
                value=min(250, total_registros),
                step=25,
                key="alertas_vista_filas_pagina",
            )
            total_paginas = max(1, (total_registros + int(filas_por_pagina) - 1) // int(filas_por_pagina))
            pagina = st.number_input(
                "Página",
                min_value=1,
                max_value=total_paginas,
                value=1,
                step=1,
                key="alertas_vista_pagina",
            )
            inicio = (int(pagina) - 1) * int(filas_por_pagina)
            fin = min(inicio + int(filas_por_pagina), total_registros)
            st.caption(f"Mostrando {inicio + 1}-{fin} de {total_registros} registros.")
            st.dataframe(dataframe_visible(detalle_filtrado.iloc[inicio:fin]), width="stretch", hide_index=True)
        else:
            st.dataframe(dataframe_visible(detalle_filtrado), width="stretch", hide_index=True)


def filtrar_detalle_alertas(detalle):
    filtrado = detalle.copy()
    columnas_filtro = ["Tipo de alerta", "Equipo", "Número de equipo", "Operador"]
    columnas_disponibles = [columna for columna in columnas_filtro if columna in filtrado.columns]
    if not columnas_disponibles:
        return filtrado

    columnas = st.columns(len(columnas_disponibles))
    for contenedor, columna in zip(columnas, columnas_disponibles):
        opciones = opciones_filtro_alertas(filtrado[columna])
        seleccion = contenedor.selectbox(
            texto_visible(columna),
            ["Todos", *opciones],
            format_func=texto_visible,
            key=f"filtro_alertas_{normalizar_nombre_columna(columna)}",
        )
        if seleccion != "Todos":
            filtrado = filtrado[filtrado[columna].astype(str).eq(seleccion)]

    return filtrado.reset_index(drop=True)


def opciones_filtro_alertas(serie):
    valores = serie.dropna().astype(str)
    if serie.name == "Tipo de alerta":
        partes = [
            parte.strip()
            for valor in valores
            for parte in valor.split(",")
            if parte.strip()
        ]
        return sorted(dict.fromkeys(partes))

    return sorted(valor for valor in valores.unique() if valor.strip())


def mostrar_resumen_alertas(detalle):
    if detalle.empty or "Tipo de alerta" not in detalle.columns:
        st.info("No hay alertas visibles con los filtros actuales.")
        return

    conteos = {}
    for valor in detalle["Tipo de alerta"].dropna().astype(str):
        for alerta in [parte.strip() for parte in valor.split(",") if parte.strip()]:
            conteos[alerta] = conteos.get(alerta, 0) + 1

    if not conteos:
        st.info("No hay alertas visibles con los filtros actuales.")
        return

    resumen = pd.DataFrame(
        sorted(conteos.items(), key=lambda item: item[1], reverse=True),
        columns=["Tipo de alerta", "Registros"],
    )
    st.markdown("**Resumen de alertas**")
    st.dataframe(dataframe_visible(resumen), width="stretch", hide_index=True)


def normalizar_nombre_columna(nombre):
    texto = normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode("ascii")
    return texto.lower().strip()
