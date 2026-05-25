
from datetime import datetime
from pathlib import Path
import pandas as pd
import pdf_report
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from charts import (
    fig_distribucion_horas,
    fig_metros_equipo,
    fig_ranking_operadores,
    fig_rendimiento_equipo,
    fig_utilizacion_equipo,
)
from catalogs import CONDICIONES_TERRENO, FASES_BASE, MALLAS_BASE, TIPOS_PERFORACION, TURNOS
from data import anexar_registro, crear_registro, leer_reportes, normalizar_tipo_detencion
from metrics import (
    calcular_disponibilidad,
    calcular_rendimiento_consolidado,
    calcular_utilizacion,
    registros_productivos,
    resumen_general_aceros,
    resumen_general_equipos,
    resumen_general_operadores,
    totales_productivos,
)
from utils import (
    CODIGOS_OPERADOR,
    EQUIPOS,
    EXCEL_PATH,
    HORAS_TURNO,
    OPERADORES,
    TIPOS_DETENCION,
    buscar_columna,
    limpiar_entero,
    normalizar_nombre_columna,
    opciones_desde_historial,
    ruta_imagen_equipo,
    serie_numerica,
    unir_valores,
)
from validation import existe_reporte_duplicado, validar_operador_obligatorio, validar_total_horas_turno

REPORTES_PDF_DIR = Path(EXCEL_PATH).parent / "reportes_pdf"

DETENCION_HORAS_COLUMNAS = {
    "Falla Operacional": "Falla Operacional",
    "Avería mecánica": "Horas detención mecánica",
    "Cambio de aceros": "Cambio de aceros",
    "Geología": "Geología",
    "Seguridad": "Seguridad",
    "Colación": "Colación",
    "Agua": "Relleno de agua",
    "Combustible": "Combustible",
    "Traslado": "Traslado",
    "Cambio Turno": "Cambio turno",
    "Standby por falta de tajo/Patio": "Standby por falta de tajo/Patio",
    "Sin marcación": "Sin marcación",
    "Mantención Programada": "Mantención Programada",
    "Tronadura": "Tronadura",
    "Falta operador": "Falta operador",
    "Otros": "Otros",
}

COLUMNAS_HORAS_DETENCION = list(dict.fromkeys(DETENCION_HORAS_COLUMNAS.values()))

st.set_page_config(
    page_title="Reporte de Perforación",
    page_icon="⛏️",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
    [data-testid="stMetricValue"] {font-size: 1.65rem;}
    div[data-testid="stDataFrame"] {border: 1px solid #e5e7eb; border-radius: 6px;}
    </style>
    """,
    unsafe_allow_html=True,
)


def aplicar_filtros(df):
    if df.empty:
        return df

    with st.sidebar:
        st.header("Filtros")

        if "Fecha turno" in df.columns and df["Fecha turno"].notna().any():
            fechas = pd.to_datetime(df["Fecha turno"], errors="coerce")
            min_fecha = fechas.min().date()
            max_fecha = fechas.max().date()
            rango = st.date_input(
                "Rango de fechas",
                value=(min_fecha, max_fecha),
                min_value=min_fecha,
                max_value=max_fecha,
            )
        else:
            rango = None

        equipos = sorted(df.get("Equipo", pd.Series(dtype=str)).dropna().astype(str).unique())
        operadores = sorted(df.get("Operador", pd.Series(dtype=str)).dropna().astype(str).unique())
        turnos = sorted(df.get("Turno", pd.Series(dtype=str)).dropna().astype(str).unique())
        tipos_detencion = opciones_desde_historial(df, "Tipo detención", TIPOS_DETENCION)

        filtro_equipos = st.multiselect("Equipo", equipos, default=equipos)
        filtro_operadores = st.multiselect("Operador", operadores, default=operadores)
        filtro_turnos = st.multiselect("Turno", turnos, default=turnos)
        filtro_tipos_detencion = st.multiselect(
            "Tipo detención",
            tipos_detencion,
            default=tipos_detencion,
        )

    filtrado = df.copy()

    if rango and len(rango) == 2 and "Fecha turno" in filtrado.columns:
        fechas = pd.to_datetime(filtrado["Fecha turno"], errors="coerce").dt.date
        filtrado = filtrado[(fechas >= rango[0]) & (fechas <= rango[1])]

    if filtro_equipos and "Equipo" in filtrado.columns:
        filtrado = filtrado[filtrado["Equipo"].astype(str).isin(filtro_equipos)]

    if filtro_operadores and "Operador" in filtrado.columns:
        filtrado = filtrado[filtrado["Operador"].astype(str).isin(filtro_operadores)]

    if filtro_turnos and "Turno" in filtrado.columns:
        filtrado = filtrado[filtrado["Turno"].astype(str).isin(filtro_turnos)]

    if (
        filtro_tipos_detencion
        and "Tipo detención" in filtrado.columns
        and set(filtro_tipos_detencion) != set(tipos_detencion)
    ):
        seleccionados = set(filtro_tipos_detencion)
        filtrado = filtrado[
            filtrado["Tipo detención"].fillna("").astype(str).apply(
                lambda valor: bool(
                    seleccionados.intersection(
                        item.strip() for item in valor.split(",") if item.strip()
                    )
                )
            )
        ]

    return filtrado


def mostrar_figura(fig, mensaje, key):
    if fig is None:
        st.info(mensaje)
    else:
        st.plotly_chart(fig, use_container_width=True, key=key)


def limpiar_formulario():
    st.session_state["form_version"] = st.session_state.get("form_version", 0) + 1


def texto_lista(valores):
    return unir_valores(str(valor).strip() for valor in valores if str(valor).strip())


def texto_lista_enteros(valores):
    return unir_valores(limpiar_entero(valor) for valor in valores if str(valor).strip())


def dividir_valores_libres(valor):
    texto = str(valor).replace("/", ",")
    return [item.strip() for item in texto.split(",") if item.strip()]


def limpiar_valores_etiquetas(valores, enteros=False):
    limpios = []
    for valor in valores:
        for item in dividir_valores_libres(valor):
            limpio = limpiar_entero(item) if enteros else item
            if limpio and limpio not in limpios:
                limpios.append(limpio)

    return limpios


def equipos_esperados():
    return [(modelo, numero) for modelo, numeros in EQUIPOS.items() for numero in numeros]


def mostrar_alerta_reportes_faltantes(df):
    columnas = {"Fecha turno", "Turno", "Modelo equipo", "Número equipo"}
    if df.empty or not columnas.issubset(df.columns):
        return

    fechas = pd.to_datetime(df["Fecha turno"], errors="coerce").dt.date.dropna().unique()
    turnos = df["Turno"].dropna().astype(str).str.strip()
    turnos = sorted(turno for turno in turnos.unique() if turno)

    if len(fechas) != 1 or len(turnos) != 1:
        st.info("Selecciona una sola fecha y un solo turno para validar reportes faltantes por equipo.")
        return

    fecha = fechas[0]
    turno = turnos[0]
    registrados = set(
        zip(
            df["Modelo equipo"].astype(str).str.strip(),
            df["Número equipo"].astype(str).apply(limpiar_entero),
        )
    )
    faltantes = [
        f"{modelo} {numero}"
        for modelo, numero in equipos_esperados()
        if (modelo, limpiar_entero(numero)) not in registrados
    ]
    fecha_texto = pd.to_datetime(fecha).strftime("%d-%m-%Y")

    if faltantes:
        st.warning(
            f"Faltan reportes por registrar para la fecha {fecha_texto} turno {turno}: "
            + ", ".join(faltantes)
        )
    else:
        st.success(f"Reportes completos: los 6 equipos están registrados para esta fecha y turno.")


def columnas_horas_turno():
    return ["Horas efectivas perforando", *COLUMNAS_HORAS_DETENCION]


def etiqueta_hora(columna):
    etiquetas = {
        "Horas detención mecánica": "Avería mecánica",
        "Relleno de agua": "Agua",
        "Cambio turno": "Cambio Turno",
    }
    return etiquetas.get(columna, columna)


def seccion_reporte_pdf(df):
    st.subheader("Reporte PDF por fecha y turno")

    if "Fecha turno" not in df.columns or "Turno" not in df.columns:
        st.info("No hay columnas suficientes para generar PDF por fecha y turno.")
        return

    fechas = pd.to_datetime(df["Fecha turno"], errors="coerce").dt.date.dropna()
    if fechas.empty:
        st.info("No hay fechas válidas para generar PDF.")
        return

    fechas_disponibles = sorted(fechas.unique(), reverse=True)
    col_fecha, col_turno, col_boton = st.columns([1, 1, 1])
    with col_fecha:
        fecha_pdf = st.selectbox("Fecha turno PDF", fechas_disponibles, format_func=lambda fecha: fecha.strftime("%d-%m-%Y"))
    turnos_pdf = sorted(df["Turno"].dropna().astype(str).str.strip().unique())
    with col_turno:
        turno_pdf = st.selectbox("Turno PDF", turnos_pdf)

    fechas_df = pd.to_datetime(df["Fecha turno"], errors="coerce").dt.date
    df_pdf = df[(fechas_df == fecha_pdf) & (df["Turno"].astype(str).str.strip() == turno_pdf)].copy()
    with col_boton:
        st.write("")
        st.write("")
        generar = st.button("Generar reporte PDF", type="primary")

    if generar:
        if df_pdf.empty:
            st.warning("No hay registros para la fecha y turno seleccionados.")
            return

        try:
            ruta_pdf = pdf_report.generar_pdf(df_pdf, fecha_pdf, turno_pdf, df)
        except Exception as exc:
            st.error(f"No se pudo generar el PDF: {exc}")
            return

        st.success(f"PDF generado correctamente: {ruta_pdf.name}")
        with open(ruta_pdf, "rb") as archivo_pdf:
            st.download_button(
                "Descargar reporte PDF",
                data=archivo_pdf,
                file_name=ruta_pdf.name,
                mime="application/pdf",
            )


def formulario_registro(df_historial):
    st.header("Registro operacional")
    form_version = st.session_state.get("form_version", 0)

    def k(nombre):
        return f"{nombre}_{form_version}"

    col_equipo, col_operador, col_fecha = st.columns([1.2, 1.2, 1])

    with col_equipo:
        modelo_equipo = st.selectbox("Modelo equipo", list(EQUIPOS.keys()), key=k("modelo_equipo"))
        numero_equipo = st.selectbox("Número equipo", EQUIPOS[modelo_equipo], key=k(f"numero_{modelo_equipo}"))
        imagen = ruta_imagen_equipo(modelo_equipo, numero_equipo)
        if imagen:
            st.image(str(imagen), caption=f"{modelo_equipo} {numero_equipo}", use_container_width=True)

    with col_operador:
        operador = st.selectbox(
            "Operador",
            OPERADORES,
            index=None,
            placeholder="Selecciona operador",
            key=k("operador"),
        )
        codigo_operador = CODIGOS_OPERADOR.get(operador, "")
        st.text_input(
            "Código de operador",
            value=codigo_operador,
            disabled=True,
            key=f"{k('codigo_operador')}_{operador or 'sin_operador'}",
        )
        turno = st.selectbox("Turno", TURNOS, key=k("turno"))

    with col_fecha:
        fecha_turno = st.date_input("Fecha turno", key=k("fecha_turno"))
        area_operacional = st.text_input("Área operacional", value="Proyecto DES", key=k("area_operacional"))

    st.subheader("Ubicación y condiciones")
    col_ubicacion_1, col_ubicacion_2, col_ubicacion_3 = st.columns(3)
    with col_ubicacion_1:
        banco = st.multiselect(
            "Banco",
            opciones_desde_historial(df_historial, "Banco"),
            accept_new_options=True,
            placeholder="Escribe y presiona Enter",
            key=k("banco"),
        )
        malla = st.multiselect(
            "Malla",
            opciones_desde_historial(
                df_historial,
                "Malla",
                MALLAS_BASE,
            ),
            accept_new_options=True,
            placeholder="Escribe y presiona Enter",
            key=k("malla"),
        )
    with col_ubicacion_2:
        fase = st.multiselect(
            "Fase",
            opciones_desde_historial(
                df_historial,
                "Fase",
                FASES_BASE,
            ),
            accept_new_options=True,
            placeholder="Escribe y presiona Enter",
            key=k("fase"),
        )
        opciones_tipo_perforacion = [
            opcion
            for opcion in opciones_desde_historial(
                df_historial,
                "Tipo de perforación",
                TIPOS_PERFORACION,
            )
            if str(opcion).strip() != "Buffer"
        ]
        tipo_perforacion = st.multiselect(
            "Tipo de perforación",
            opciones_tipo_perforacion,
            key=k("tipo_perforacion"),
        )
        numero_precorte = ""
        if "Precorte" in tipo_perforacion:
            numero_precorte = st.number_input(
                "Número de precorte",
                min_value=1,
                step=1,
                key=k("numero_precorte"),
            )
    with col_ubicacion_3:
        condicion_terreno = st.multiselect(
            "Condición del terreno",
            opciones_desde_historial(
                df_historial,
                "Condición del terreno",
                CONDICIONES_TERRENO,
            ),
            accept_new_options=True,
            placeholder="Escribe y presiona Enter",
            key=k("condicion_terreno"),
        )
        numero_bit = st.text_input("Número serie Tricono/Bit", key=k("numero_bit"))

    st.subheader("Producción y consumos")
    col_prod_1, col_prod_2, col_prod_3 = st.columns(3)
    with col_prod_1:
        metros = st.number_input("Metros perforados", min_value=0.0, step=1.0, key=k("metros"))
        pozos = st.number_input("Pozos perforados turno", min_value=0, step=1, key=k("pozos"))
    with col_prod_2:
        petroleo = st.number_input("Petróleo litros", min_value=0.0, step=1.0, key=k("petroleo"))
    with col_prod_3:
        horometro_inicial = st.number_input("Horómetro inicial", min_value=0.0, step=0.1, format="%.1f", key=k("horometro_inicial"))
        horometro_final = st.number_input("Horómetro final", min_value=0.0, step=0.1, format="%.1f", key=k("horometro_final"))
        diferencia_horometro = round(horometro_final - horometro_inicial, 2)
        st.metric("Horas de motor", f"{diferencia_horometro:.2f} h")

    tipo_detencion = st.multiselect(
        "Tipo detención",
        opciones_desde_historial(df_historial, "Tipo detención", TIPOS_DETENCION),
        key=k("tipo_detencion"),
    )
    tipos_normalizados = []
    for tipo in tipo_detencion:
        for item in normalizar_tipo_detencion(tipo).split(", "):
            if item and item not in tipos_normalizados:
                tipos_normalizados.append(item)
    tipo_detencion = tipos_normalizados
    causa_detencion = st.text_input("Causa detención", key=k("causa_detencion"))
    observaciones = st.text_area("Observaciones", key=k("observaciones"))

    st.subheader("Horas del turno")
    horas_columnas = {columna: 0.0 for columna in COLUMNAS_HORAS_DETENCION}
    horas_efectivas = st.number_input("Horas efectivas perforando", min_value=0.0, max_value=12.0, step=0.5, key=k("horas_efectivas"))

    detenciones_visibles = [tipo for tipo in tipo_detencion if tipo in DETENCION_HORAS_COLUMNAS]
    if detenciones_visibles:
        columnas_detencion = st.columns(3)
        for indice, tipo in enumerate(detenciones_visibles):
            columna_hora = DETENCION_HORAS_COLUMNAS[tipo]
            with columnas_detencion[indice % len(columnas_detencion)]:
                horas_columnas[columna_hora] = st.number_input(
                    tipo,
                    min_value=0.0,
                    max_value=12.0,
                    step=0.5,
                    key=k(f"horas_{normalizar_nombre_columna(tipo).replace(' ', '_').replace('/', '_')}"),
                )

    horas_averia = horas_columnas.get("Horas detención mecánica", 0.0)
    horas_no_efectivas = round(sum(horas_columnas.values()) - horas_averia, 2)
    total_horas = round(horas_efectivas + sum(horas_columnas.values()), 2)
    diferencia_turno = round(HORAS_TURNO - total_horas, 2)

    st.info(
        f"Total turno: {total_horas:.2f} / {HORAS_TURNO} h | "
        f"Efectivas {horas_efectivas:.2f} h | "
        f"Avería {horas_averia:.2f} h | "
        f"No efectivas {horas_no_efectivas:.2f} h"
    )
    if diferencia_turno > 0:
        st.warning(f"Faltan {diferencia_turno:.2f} h para completar el turno.")
    elif diferencia_turno < 0:
        st.error(f"El turno excede por {abs(diferencia_turno):.2f} h.")

    rendimiento_turno = calcular_rendimiento_consolidado(pd.DataFrame([{
        "Metros perforados": metros,
        "Horas efectivas perforando": horas_efectivas,
    }]))
    utilizacion = calcular_utilizacion(horas_efectivas)
    disponibilidad = calcular_disponibilidad(horas_averia)

    st.subheader("KPI del turno")
    k1, k2, k3 = st.columns(3)
    k1.metric("Rendimiento m/h", f"{rendimiento_turno:.2f}")
    k2.metric("Utilización", f"{utilizacion:.2f}%")
    k3.metric("Disponibilidad", f"{disponibilidad:.2f}%")

    if st.button("Guardar reporte", type="primary", key=k("guardar_reporte")):
        if not validar_total_horas_turno(total_horas):
            if diferencia_turno > 0:
                st.error(f"No se puede guardar. Faltan {diferencia_turno:.2f} h para completar {HORAS_TURNO:.2f} h.")
            else:
                st.error(f"No se puede guardar. El turno excede por {abs(diferencia_turno):.2f} h.")
            return

        if not validar_operador_obligatorio(operador):
            st.error("Debe ingresar el nombre del operador.")
            return

        if existe_reporte_duplicado(df_historial, fecha_turno, turno, modelo_equipo, numero_equipo, operador):
            st.error("Ya existe un reporte registrado para este equipo, operador, turno y fecha.")
            return

        registro = crear_registro({
            "Modelo equipo": modelo_equipo,
            "Número equipo": numero_equipo,
            "Operador": operador,
            "Turno": turno,
            "Código operador": codigo_operador,
            "Fecha turno": fecha_turno,
            "Área operacional": area_operacional,
            "Petróleo litros": petroleo,
            "Horómetro inicial": horometro_inicial,
            "Horómetro final": horometro_final,
            "Diferencia horómetro": diferencia_horometro,
            "Horas de motor": diferencia_horometro,
            "Banco": texto_lista_enteros(limpiar_valores_etiquetas(banco, enteros=True)),
            "Malla": texto_lista(limpiar_valores_etiquetas(malla)),
            "Fase": texto_lista_enteros(limpiar_valores_etiquetas(fase, enteros=True)),
            "Tipo de perforación": unir_valores(tipo_perforacion),
            "Número precorte": numero_precorte if "Precorte" in tipo_perforacion else "",
            "Número serie Tricono/Bit": numero_bit,
            "Condición del terreno": texto_lista(limpiar_valores_etiquetas(condicion_terreno)),
            "Tipo detención": unir_valores(tipo_detencion),
            "Causa detención": causa_detencion,
            "Horas detención mecánica": horas_averia,
            "Horas detención No efectivas": horas_no_efectivas,
            "Horas efectivas perforando": horas_efectivas,
            "Combustible": horas_columnas.get("Combustible", 0.0),
            "Relleno de agua": horas_columnas.get("Relleno de agua", 0.0),
            "Colación": horas_columnas.get("Colación", 0.0),
            "Traslado": horas_columnas.get("Traslado", 0.0),
            "Standby por falta de tajo/Patio": horas_columnas.get("Standby por falta de tajo/Patio", 0.0),
            "Falla Operacional": horas_columnas.get("Falla Operacional", 0.0),
            "Cambio de aceros": horas_columnas.get("Cambio de aceros", 0.0),
            "Geología": horas_columnas.get("Geología", 0.0),
            "Seguridad": horas_columnas.get("Seguridad", 0.0),
            "Sin marcación": horas_columnas.get("Sin marcación", 0.0),
            "Mantención Programada": horas_columnas.get("Mantención Programada", 0.0),
            "Tronadura": horas_columnas.get("Tronadura", 0.0),
            "Avería": horas_averia,
            "Cambio turno": horas_columnas.get("Cambio turno", 0.0),
            "Falta operador": horas_columnas.get("Falta operador", 0.0),
            "Otros": horas_columnas.get("Otros", 0.0),
            "Total horas ingresadas": total_horas,
            "Metros perforados": metros,
            "Pozos perforados turno": pozos,
            "Rendimiento m/h": round(rendimiento_turno, 2),
            "Disponibilidad %": round(disponibilidad, 2),
            "Utilización %": round(utilizacion, 2),
            "Observaciones": observaciones,
        })

        try:
            anexar_registro(registro)
        except PermissionError:
            st.error("No se pudo guardar. Cierra el archivo Excel y vuelve a intentar.")
            return

        st.session_state["reporte_guardado"] = True
        limpiar_formulario()
        st.rerun()


def dashboard(df):
    st.header("Dashboard operacional")

    if df.empty:
        st.info("Aún no existe historial. Guarda el primer reporte para ver tablas y gráficos.")
        return

    seccion_reporte_pdf(df)

    df_filtrado = aplicar_filtros(df)
    if df_filtrado.empty:
        st.warning("No hay registros para los filtros seleccionados.")
        return

    df_analisis = df_filtrado[
        ~(
            df_filtrado["Modelo equipo"].astype(str).str.strip().str.upper().eq("PV271")
            & df_filtrado["Número equipo"].astype(str).apply(limpiar_entero).eq("9291")
        )
    ].copy()
    df_productivo = registros_productivos(df_analisis)
    rendimiento = calcular_rendimiento_consolidado(df_analisis)

    mostrar_alerta_reportes_faltantes(df_analisis)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Metros productivos", f"{df_productivo['Metros perforados'].sum():,.2f}")
    m2.metric("Horas efectivas", f"{df_productivo['Horas efectivas perforando'].sum():,.2f}")
    m3.metric("Rendimiento real", f"{rendimiento:.2f} m/h")
    m4.metric("Registros", f"{len(df_filtrado):,.0f}")

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
        st.dataframe(tabla_operadores, use_container_width=True, hide_index=True)

    with tabs[2]:
        st.subheader("Equipos")
        col_a, col_b = st.columns(2)
        with col_a:
            mostrar_figura(
                fig_rendimiento_equipo(df_productivo),
                "No hay rendimiento productivo por equipo.",
                key="grafico_equipos_rendimiento",
            )
        with col_b:
            mostrar_figura(
                fig_metros_equipo(df_productivo),
                "No hay metros productivos por equipo.",
                key="grafico_equipos_metros",
            )
        mostrar_figura(
            fig_utilizacion_equipo(df_analisis),
            "No hay datos de utilización por equipo.",
            key="grafico_equipos_utilizacion",
        )

    with tabs[3]:
        st.subheader("Distribución de horas")
        mostrar_figura(
            fig_distribucion_horas(df_analisis),
            "No hay horas válidas para graficar.",
            key="grafico_horas_distribucion",
        )
        horas = {
            etiqueta_hora(columna): pd.to_numeric(df_analisis[columna], errors="coerce").fillna(0).sum()
            for columna in columnas_horas_turno()
            if columna in df_analisis.columns
        }
        st.dataframe(
            pd.DataFrame({"Categoría": horas.keys(), "Horas": [round(valor, 2) for valor in horas.values()]}),
            use_container_width=True,
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
            historial["Banco"] = historial["Banco"].apply(lambda valor: unir_valores(limpiar_entero(item) for item in str(valor).split(",")))
        historial = historial.sort_values("Fecha turno", na_position="last") if "Fecha turno" in visibles else historial
        st.dataframe(
            historial,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Operador": st.column_config.TextColumn("Operador", pinned=True),
                "Modelo equipo": st.column_config.TextColumn("Modelo equipo", pinned=True),
                "Número equipo": st.column_config.TextColumn("Número equipo", pinned=True),
            },
        )

    st.subheader("Resumen general por operador")
    st.dataframe(
        resumen_general_operadores(df_analisis),
        use_container_width=True,
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
        resumen_general_equipos(df_analisis),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Modelo equipo": st.column_config.TextColumn("Modelo equipo", pinned=True),
            "Número equipo": st.column_config.TextColumn("Número equipo", pinned=True),
            "Disponibilidad promedio": st.column_config.NumberColumn(format="%.2f%%"),
            "Utilización promedio": st.column_config.NumberColumn(format="%.2f%%"),
            "Rendimiento consolidado m/h": st.column_config.NumberColumn(format="%.2f"),
            "Metros totales perforados": st.column_config.NumberColumn(format="%.2f"),
            "Horas efectivas perforando": st.column_config.NumberColumn(format="%.2f"),
            "Horas avería equipo": st.column_config.NumberColumn(format="%.2f"),
            "Horas no efectivas": st.column_config.NumberColumn(format="%.2f"),
        },
    )

    st.subheader("Resumen general de aceros de perforación")
    st.dataframe(
        resumen_general_aceros(df_analisis),
        use_container_width=True,
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


st.title("Sistema de Reporte de Perforación")
st.caption(f"Aplicación oficial: {EXCEL_PATH.parent}")

if st.session_state.pop("reporte_guardado", False):
    st.success("Reporte guardado correctamente en Excel.")

df_reportes = leer_reportes()

with st.expander("Nuevo reporte operacional", expanded=True):
    formulario_registro(df_reportes)

dashboard(df_reportes)
