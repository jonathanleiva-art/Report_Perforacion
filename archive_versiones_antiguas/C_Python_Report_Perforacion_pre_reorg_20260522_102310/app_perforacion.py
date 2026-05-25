from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
import streamlit as st
from unicodedata import normalize

from charts import (
    fig_distribucion_horas,
    fig_metros_equipo,
    fig_ranking_operadores,
    fig_rendimiento_equipo,
    fig_utilizacion_equipo,
)
from data import anexar_registro, crear_registro, leer_reportes
from metrics import (
    calcular_disponibilidad,
    calcular_rendimiento_consolidado,
    calcular_utilizacion,
    registros_productivos,
)
from utils import (
    CODIGOS_OPERADOR,
    EQUIPOS,
    EXCEL_PATH,
    HORAS_TURNO,
    OPERADORES,
    limpiar_entero,
    opciones_desde_historial,
    ruta_imagen_equipo,
    unir_valores,
)

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

        filtro_equipos = st.multiselect("Equipo", equipos, default=equipos)
        filtro_operadores = st.multiselect("Operador", operadores, default=operadores)
        filtro_turnos = st.multiselect("Turno", turnos, default=turnos)

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


def existe_reporte_duplicado(df, fecha_turno, turno, modelo_equipo, numero_equipo, operador):
    columnas = {"Fecha turno", "Turno", "Modelo equipo", "Número equipo", "Operador"}
    if df.empty or not columnas.issubset(df.columns):
        return False

    fechas = pd.to_datetime(df["Fecha turno"], errors="coerce").dt.date
    return bool(
        (
            fechas.eq(fecha_turno)
            & df["Turno"].astype(str).str.strip().eq(str(turno).strip())
            & df["Modelo equipo"].astype(str).str.strip().eq(str(modelo_equipo).strip())
            & df["Número equipo"].astype(str).apply(limpiar_entero).eq(limpiar_entero(numero_equipo))
            & df["Operador"].astype(str).str.strip().eq(str(operador).strip())
        ).any()
    )


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


def normalizar_nombre_columna(nombre):
    texto = normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode("ascii")
    return texto.lower().strip()


def buscar_columna(df, *candidatos):
    columnas_normalizadas = {normalizar_nombre_columna(col): col for col in df.columns}
    for candidato in candidatos:
        columna = columnas_normalizadas.get(normalizar_nombre_columna(candidato))
        if columna:
            return columna

    return None


def serie_numerica(df, *columnas):
    columna = buscar_columna(df, *columnas)
    if not columna:
        return pd.Series(dtype=float)

    return pd.to_numeric(df[columna], errors="coerce").fillna(0)


def valor_fila(fila, *columnas, default=""):
    for columna in columnas:
        if columna in fila.index:
            valor = fila[columna]
            if pd.notna(valor):
                texto = str(valor).strip()
                if texto and texto.lower() not in ("nan", "none", "nat"):
                    return texto

    return default


def numero_fila(fila, *columnas):
    valor = valor_fila(fila, *columnas, default=0)
    numero = pd.to_numeric(valor, errors="coerce")
    return 0.0 if pd.isna(numero) else float(numero)


def estatus_operacional(fila):
    horas_efectivas = numero_fila(fila, "Horas efectivas perforando")
    horas_averia = numero_fila(fila, "Horas detención mecánica", "Avería")
    horas_no_efectivas = numero_fila(fila, "Horas detención No efectivas")

    if horas_efectivas > 0 and (horas_averia > 0 or horas_no_efectivas > 0):
        return "Operativo parcial"
    if horas_efectivas > 0:
        return "Operativo con marcación"
    if horas_averia > 0:
        return "En avería"
    if horas_no_efectivas > 0:
        return "Operativo sin marcación"
    return "Sin registro operacional"


def texto_pdf(valor):
    return escape(str(valor)) if valor is not None else ""


def detalle_equipo_estatus(fila):
    modelo = valor_fila(fila, "Modelo equipo")
    numero = limpiar_entero(valor_fila(fila, "Número equipo"))
    estatus = estatus_operacional(fila)
    horas_averia = numero_fila(fila, "Horas detención mecánica", "Avería")
    tipo_detencion = valor_fila(fila, "Tipo detención")
    observacion = valor_fila(fila, "Observaciones", "Causa detención")
    detalle = f"{modelo} {numero}"

    if estatus == "En avería":
        detalle += f" | Motivo: {tipo_detencion or 'Sin detalle'} | Horas avería: {horas_averia:.2f}"
        if observacion:
            detalle += f" | Observación: {observacion}"
    elif estatus == "Operativo parcial" and horas_averia > 0:
        detalle += f" | Con avería: Sí | Horas avería: {horas_averia:.2f}"
        if tipo_detencion:
            detalle += f" | Tipo detención: {tipo_detencion}"

    return detalle


def dataframe_sin_pv271(df):
    if df.empty or not {"Modelo equipo", "Número equipo"}.issubset(df.columns):
        return df.copy()

    return df[
        ~(
            df["Modelo equipo"].astype(str).str.strip().str.upper().eq("PV271")
            & df["Número equipo"].astype(str).apply(limpiar_entero).eq("9291")
        )
    ].copy()


def etiqueta_equipo(df):
    return df["Modelo equipo"].astype(str) + " " + df["Número equipo"].astype(str).apply(limpiar_entero)


def guardar_grafico_pdf(fig, ruta):
    fig.savefig(ruta, dpi=180, bbox_inches="tight", facecolor="white")


def crear_graficos_pdf(df_turno, conteo_estatus, fecha_archivo, turno):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    carpeta = EXCEL_PATH.parent / "temp_charts"
    carpeta.mkdir(exist_ok=True)
    df = dataframe_sin_pv271(df_turno)
    rutas = []
    sufijo = f"{fecha_archivo}_{turno}".replace(" ", "_")
    colores = ["#1F77B4", "#2CA02C", "#FF7F0E", "#D62728", "#9467BD", "#17BECF"]

    def registrar(fig, nombre):
        ruta = carpeta / f"{nombre}_{sufijo}.png"
        guardar_grafico_pdf(fig, ruta)
        plt.close(fig)
        rutas.append(ruta)

    if not df.empty and {"Modelo equipo", "Número equipo", "Metros perforados", "Horas efectivas perforando"}.issubset(df.columns):
        rendimiento = df.copy()
        rendimiento["Metros perforados"] = pd.to_numeric(rendimiento["Metros perforados"], errors="coerce").fillna(0)
        rendimiento["Horas efectivas perforando"] = pd.to_numeric(rendimiento["Horas efectivas perforando"], errors="coerce").fillna(0)
        rendimiento = rendimiento.groupby(["Modelo equipo", "Número equipo"], as_index=False).agg({
            "Metros perforados": "sum",
            "Horas efectivas perforando": "sum",
        })
        rendimiento = rendimiento[rendimiento["Horas efectivas perforando"] > 0].copy()
        if not rendimiento.empty:
            rendimiento["Equipo"] = etiqueta_equipo(rendimiento)
            rendimiento["Rendimiento m/h"] = rendimiento["Metros perforados"] / rendimiento["Horas efectivas perforando"]
            rendimiento = rendimiento.sort_values("Rendimiento m/h", ascending=True)
            fig, ax = plt.subplots(figsize=(10, 5.4))
            bars = ax.barh(rendimiento["Equipo"], rendimiento["Rendimiento m/h"], color="#1F77B4")
            ax.set_title("Rendimiento por equipo", fontsize=14, fontweight="bold", pad=14)
            ax.set_xlabel("m/h")
            ax.bar_label(bars, fmt="%.2f", padding=4, fontsize=9)
            ax.grid(axis="x", alpha=0.25)
            ax.set_xlim(0, max(rendimiento["Rendimiento m/h"].max() * 1.18, 1))
            fig.tight_layout()
            registrar(fig, "rendimiento_equipo")

    if not df.empty and {"Modelo equipo", "Número equipo", "Metros perforados"}.issubset(df.columns):
        metros = df.copy()
        metros["Metros perforados"] = pd.to_numeric(metros["Metros perforados"], errors="coerce").fillna(0)
        metros = metros.groupby(["Modelo equipo", "Número equipo"], as_index=False)["Metros perforados"].sum()
        metros["Equipo"] = etiqueta_equipo(metros)
        metros = metros.sort_values("Metros perforados", ascending=False)
        fig, ax = plt.subplots(figsize=(10, 5.4))
        bars = ax.bar(metros["Equipo"], metros["Metros perforados"], color="#2CA02C")
        ax.set_title("Metros perforados por equipo", fontsize=14, fontweight="bold", pad=14)
        ax.set_ylabel("Metros")
        ax.tick_params(axis="x", rotation=25)
        ax.bar_label(bars, fmt="%.2f", padding=3, fontsize=9)
        ax.grid(axis="y", alpha=0.25)
        
        fig.tight_layout()
        registrar(fig, "metros_equipo")

    horas = {
        "Horas efectivas perforando": pd.to_numeric(df.get("Horas efectivas perforando", 0), errors="coerce").fillna(0).sum(),
        "Horas avería equipo": pd.to_numeric(df.get("Horas detención mecánica", df.get("Avería", 0)), errors="coerce").fillna(0).sum(),
        "Horas no efectivas": pd.to_numeric(df.get("Horas detención No efectivas", 0), errors="coerce").fillna(0).sum(),
    }
    horas = {k: v for k, v in horas.items() if v > 0}
    if horas:
        fig, ax = plt.subplots(figsize=(8.5, 5.4))
        wedges, _, autotexts = ax.pie(
            horas.values(),
            labels=horas.keys(),
            autopct=lambda pct: f"{pct:.1f}%",
            startangle=90,
            colors=["#2CA02C", "#D62728", "#FFBF00"],
            wedgeprops=dict(width=0.42, edgecolor="white"),
        )
        ax.set_title("Distribución de horas del turno", fontsize=14, fontweight="bold", pad=14)
        for text in autotexts:
            text.set_fontsize(9)
            text.set_color("#111111")
        ax.legend(wedges, [f"{k}: {v:.2f} h" for k, v in horas.items()], loc="lower center", bbox_to_anchor=(0.5, -0.18), ncol=1, fontsize=9)
        fig.tight_layout()
        registrar(fig, "distribucion_horas")

    estatus_validos = ["Operativo con marcación", "Operativo parcial", "Operativo sin marcación", "En avería"]
    estatus_data = {estatus: conteo_estatus.get(estatus, 0) for estatus in estatus_validos if conteo_estatus.get(estatus, 0) > 0}
    if estatus_data:
        fig, ax = plt.subplots(figsize=(9.5, 5.4))
        bars = ax.bar(estatus_data.keys(), estatus_data.values(), color=["#2CA02C", "#1F77B4", "#FF7F0E", "#D62728"])
        ax.set_title("Estatus operacional de equipos", fontsize=14, fontweight="bold", pad=14)
        ax.set_ylabel("Equipos")
        ax.tick_params(axis="x", rotation=18)
        ax.bar_label(bars, fmt="%.0f", padding=3, fontsize=10)
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        registrar(fig, "estatus_operacional")

    if not df.empty and {"Modelo equipo", "Número equipo"}.issubset(df.columns):
        disponibilidad_col = buscar_columna(df, "Disponibilidad %")
        utilizacion_col = buscar_columna(df, "Utilización %", "Utilizacion %")
        if disponibilidad_col and utilizacion_col:
            metricas = df.copy()
            metricas[disponibilidad_col] = pd.to_numeric(metricas[disponibilidad_col], errors="coerce").fillna(0)
            metricas[utilizacion_col] = pd.to_numeric(metricas[utilizacion_col], errors="coerce").fillna(0)
            metricas = metricas.groupby(["Modelo equipo", "Número equipo"], as_index=False).agg({
                disponibilidad_col: "mean",
                utilizacion_col: "mean",
            })
            metricas["Equipo"] = etiqueta_equipo(metricas)
            x = range(len(metricas))
            ancho = 0.38
            fig, ax = plt.subplots(figsize=(10.5, 5.4))
            bars_disp = ax.bar([i - ancho / 2 for i in x], metricas[disponibilidad_col], width=ancho, label="Disponibilidad %", color="#1F77B4")
            bars_util = ax.bar([i + ancho / 2 for i in x], metricas[utilizacion_col], width=ancho, label="Utilización %", color="#FF7F0E")
            ax.set_title("Disponibilidad y utilización promedio por equipo", fontsize=14, fontweight="bold", pad=14)
            ax.set_ylabel("%")
            ax.set_xticks(list(x))
            ax.set_xticklabels(metricas["Equipo"], rotation=25, ha="right")
            ax.set_ylim(0, 110)
            ax.bar_label(bars_disp, fmt="%.1f", padding=2, fontsize=8)
            ax.bar_label(bars_util, fmt="%.1f", padding=2, fontsize=8)
            ax.legend(loc="upper right")
            ax.grid(axis="y", alpha=0.25)
            fig.tight_layout()
            registrar(fig, "disponibilidad_utilizacion")

    return rutas


def filtrar_fecha_turno(df, fecha_turno, turno):
    if df.empty or not {"Fecha turno", "Turno"}.issubset(df.columns):
        return pd.DataFrame(columns=df.columns)

    fechas = pd.to_datetime(df["Fecha turno"], errors="coerce").dt.date
    return df[
        fechas.eq(fecha_turno)
        & df["Turno"].astype(str).str.strip().eq(str(turno).strip())
    ].copy()


def equipos_faltantes_turno(df_turno):
    registrados = set()
    if {"Modelo equipo", "Número equipo"}.issubset(df_turno.columns):
        registrados = set(
            zip(
                df_turno["Modelo equipo"].astype(str).str.strip(),
                df_turno["Número equipo"].astype(str).apply(limpiar_entero),
            )
        )

    return [
        f"{modelo} {numero}"
        for modelo, numero in equipos_esperados()
        if (modelo, limpiar_entero(numero)) not in registrados
    ]


def totales_productivos(df):
    metros = serie_numerica(df, "Metros perforados")
    horas = serie_numerica(df, "Horas efectivas perforando")
    productivos = (metros > 0) & (horas > 0)
    total_metros = metros[productivos].sum()
    total_horas = horas[productivos].sum()
    rendimiento = total_metros / total_horas if total_horas > 0 else 0

    return total_metros, total_horas, rendimiento


def resumen_general_operadores(df):
    columnas = [
        "Operador",
        "Disponibilidad promedio",
        "Utilización promedio",
        "Rendimiento consolidado m/h",
        "Metros totales perforados",
    ]
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

    return pd.DataFrame(filas, columns=columnas).sort_values(
        "Metros totales perforados",
        ascending=False,
    )


def resumen_general_equipos(df):
    columnas = [
        "Modelo equipo",
        "Número equipo",
        "Disponibilidad promedio",
        "Utilización promedio",
        "Rendimiento consolidado m/h",
        "Metros totales perforados",
        "Horas efectivas perforando",
        "Horas avería equipo",
        "Horas no efectivas",
    ]
    if df.empty or not {"Modelo equipo", "Número equipo"}.issubset(df.columns):
        return pd.DataFrame(columns=columnas)

    filas = []
    for (modelo, numero), df_equipo in df.groupby(["Modelo equipo", "Número equipo"], dropna=False):
        total_metros, total_horas, rendimiento = totales_productivos(df_equipo)
        disponibilidad = serie_numerica(df_equipo, "Disponibilidad %")
        utilizacion = serie_numerica(df_equipo, "Utilización %", "Utilizacion %")
        horas_averia = serie_numerica(df_equipo, "Horas detención mecánica", "Avería").sum()
        horas_no_efectivas = serie_numerica(df_equipo, "Horas detención No efectivas").sum()

        filas.append({
            "Modelo equipo": modelo,
            "Número equipo": numero,
            "Disponibilidad promedio": round(disponibilidad.mean(), 2) if not disponibilidad.empty else 0.0,
            "Utilización promedio": round(utilizacion.mean(), 2) if not utilizacion.empty else 0.0,
            "Rendimiento consolidado m/h": round(rendimiento, 2),
            "Metros totales perforados": round(total_metros, 2),
            "Horas efectivas perforando": round(total_horas, 2),
            "Horas avería equipo": round(horas_averia, 2),
            "Horas no efectivas": round(horas_no_efectivas, 2),
        })

    return pd.DataFrame(filas, columns=columnas).sort_values(
        "Metros totales perforados",
        ascending=False,
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


def generar_reporte_pdf_turno(df_turno, fecha_turno, turno):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise RuntimeError("Falta instalar reportlab. Ejecuta: pip install reportlab") from exc

    carpeta = EXCEL_PATH.parent / "reportes_pdf"
    carpeta.mkdir(exist_ok=True)
    fecha_archivo = pd.to_datetime(fecha_turno).strftime("%Y-%m-%d")
    ruta_pdf = carpeta / f"reporte_perforacion_{fecha_archivo}_{turno}.pdf"

    styles = getSampleStyleSheet()
    title = styles["Title"]
    heading = styles["Heading2"]
    normal = styles["BodyText"]
    small = styles["BodyText"]
    small.fontSize = 8
    small.leading = 10

    faltantes = equipos_faltantes_turno(df_turno)
    area = valor_fila(df_turno.iloc[0], "Área operacional") if not df_turno.empty else ""
    metros_totales = pd.to_numeric(df_turno.get("Metros perforados", 0), errors="coerce").fillna(0).sum()
    horas_efectivas = pd.to_numeric(df_turno.get("Horas efectivas perforando", 0), errors="coerce").fillna(0).sum()
    horas_averia = pd.to_numeric(df_turno.get("Horas detención mecánica", df_turno.get("Avería", 0)), errors="coerce").fillna(0).sum()
    horas_no_efectivas = pd.to_numeric(df_turno.get("Horas detención No efectivas", 0), errors="coerce").fillna(0).sum()
    rendimiento = calcular_rendimiento_consolidado(df_turno)
    disponibilidad = serie_numerica(df_turno, "Disponibilidad %").mean() if not df_turno.empty else 0
    utilizacion = serie_numerica(df_turno, "Utilización %", "Utilizacion %").mean() if not df_turno.empty else 0
    conteo_estatus = (
        df_turno.apply(estatus_operacional, axis=1).value_counts().to_dict()
        if not df_turno.empty
        else {}
    )
    rutas_graficos = crear_graficos_pdf(df_turno, conteo_estatus, fecha_archivo, turno)

    elementos = [
        Paragraph("Reporte operacional de perforación", title),
        Spacer(1, 0.25 * cm),
        Paragraph("Datos generales", heading),
    ]

    datos_generales = [
        ["Fecha turno", fecha_archivo, "Turno", turno],
        ["Área operacional", area, "Total equipos registrados", str(len(df_turno))],
        ["Validación equipos", "Todos registrados" if not faltantes else "Faltan: " + ", ".join(faltantes), "", ""],
    ]
    tabla_general = Table(datos_generales, colWidths=[4 * cm, 8 * cm, 4 * cm, 6 * cm])
    tabla_general.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8EEF7")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#E8EEF7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elementos.extend([tabla_general, Spacer(1, 0.35 * cm), Paragraph("Detalle por equipo", heading)])

    detalle_headers = [
        "Equipo",
        "Estatus operacional",
        "Operador",
        "Ubicación",
        "Perforación",
        "Producción",
        "Horas",
        "KPI",
        "Acero",
    ]
    detalle = [detalle_headers]
    if not df_turno.empty:
        orden = df_turno.copy()
        orden["_orden_modelo"] = orden["Modelo equipo"].apply(orden_modelo_acero)
        orden["_orden_numero"] = pd.to_numeric(orden["Número equipo"], errors="coerce").fillna(999999)
        orden = orden.sort_values(["_orden_modelo", "_orden_numero"])

        for _, fila in orden.iterrows():
            modelo = valor_fila(fila, "Modelo equipo")
            numero = limpiar_entero(valor_fila(fila, "Número equipo"))
            horas_motor = numero_fila(fila, "Horas de motor", "Diferencia horómetro")
            estatus = estatus_operacional(fila)
            detalle.append([
                Paragraph(f"{modelo}<br/>{numero}", small),
                Paragraph(estatus, small),
                Paragraph(
                    f"{valor_fila(fila, 'Operador')}<br/>Código: {valor_fila(fila, 'Código operador')}",
                    small,
                ),
                Paragraph(
                    f"Banco: {valor_fila(fila, 'Banco')}<br/>Malla: {valor_fila(fila, 'Malla')}<br/>Fase: {valor_fila(fila, 'Fase')}",
                    small,
                ),
                Paragraph(
                    f"Tipo: {valor_fila(fila, 'Tipo de perforación')}<br/>Terreno: {valor_fila(fila, 'Condición del terreno')}",
                    small,
                ),
                Paragraph(
                    f"Metros: {numero_fila(fila, 'Metros perforados'):.2f}<br/>Pozos: {valor_fila(fila, 'Pozos perforados turno', 'Cantidad pozos perforados')}"
                    f"<br/>Horómetro: {numero_fila(fila, 'Horómetro inicial'):.1f} - {numero_fila(fila, 'Horómetro final'):.1f}"
                    f"<br/>Motor: {horas_motor:.2f}",
                    small,
                ),
                Paragraph(
                    f"Efectivas: {numero_fila(fila, 'Horas efectivas perforando'):.2f}<br/>Avería: {numero_fila(fila, 'Horas detención mecánica', 'Avería'):.2f}"
                    f"<br/>No efectivas: {numero_fila(fila, 'Horas detención No efectivas'):.2f}",
                    small,
                ),
                Paragraph(
                    f"Rend.: {numero_fila(fila, 'Rendimiento m/h'):.2f}<br/>Disp.: {numero_fila(fila, 'Disponibilidad %'):.2f}%"
                    f"<br/>Util.: {numero_fila(fila, 'Utilización %', 'Utilizacion %'):.2f}%",
                    small,
                ),
                Paragraph(
                    f"{tipo_acero(modelo)}<br/>{valor_fila(fila, 'Número serie Tricono/Bit')}",
                    small,
                ),
            ])

    tabla_detalle = Table(detalle, repeatRows=1, colWidths=[2.4 * cm, 3.0 * cm, 3.0 * cm, 3.6 * cm, 3.5 * cm, 3.7 * cm, 3.1 * cm, 2.9 * cm, 2.4 * cm])
    tabla_detalle.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elementos.extend([tabla_detalle, Spacer(1, 0.35 * cm), Paragraph("Resumen del turno", heading)])

    resumen = [
        ["Metros totales perforados", f"{metros_totales:.2f}", "Horas efectivas totales", f"{horas_efectivas:.2f}"],
        ["Horas de avería totales", f"{horas_averia:.2f}", "Horas no efectivas totales", f"{horas_no_efectivas:.2f}"],
        ["Rendimiento consolidado", f"{rendimiento:.2f} m/h", "Disponibilidad promedio", f"{disponibilidad:.2f}%"],
        ["Utilización promedio", f"{utilizacion:.2f}%", "Equipos faltantes", "Ninguno" if not faltantes else ", ".join(faltantes)],
    ]
    tabla_resumen = Table(resumen, colWidths=[5 * cm, 5 * cm, 5 * cm, 10 * cm])
    tabla_resumen.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8EEF7")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#E8EEF7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elementos.extend([tabla_resumen, Spacer(1, 0.25 * cm), Paragraph("Resumen por estatus operacional", heading)])

    orden_estatus = [
        "Operativo con marcación",
        "Operativo parcial",
        "Operativo sin marcación",
        "En avería",
        "Sin registro operacional",
    ]
    equipos_por_estatus = {estatus: [] for estatus in orden_estatus}
    if not df_turno.empty:
        for _, fila in orden.iterrows():
            estatus = estatus_operacional(fila)
            equipos_por_estatus.setdefault(estatus, []).append(detalle_equipo_estatus(fila))

    resumen_estatus = [["Estatus operacional", "Detalle equipos"]]
    for estatus in orden_estatus:
        equipos = equipos_por_estatus.get(estatus, [])
        if not equipos:
            continue

        detalle = "<br/>".join(f"• {texto_pdf(equipo)}" for equipo in equipos)
        resumen_estatus.append([
            Paragraph(f"{texto_pdf(estatus)}<br/>{len(equipos)} equipos", small),
            Paragraph(detalle, small),
        ])

    if len(resumen_estatus) == 1:
        resumen_estatus.append(["Sin registros", "0 equipos"])

    tabla_estatus = Table(resumen_estatus, colWidths=[6 * cm, 19 * cm])
    tabla_estatus.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elementos.append(tabla_estatus)

    if rutas_graficos:
        elementos.extend([Spacer(1, 0.35 * cm), Paragraph("Gráficos operacionales", heading)])
        filas_graficos = []
        for indice in range(0, len(rutas_graficos), 2):
            fila = []
            for ruta in rutas_graficos[indice:indice + 2]:
                fila.append(Image(str(ruta), width=12.8 * cm, height=7.0 * cm))
            if len(fila) == 1:
                fila.append("")
            filas_graficos.append(fila)

        tabla_graficos = Table(filas_graficos, colWidths=[13.4 * cm, 13.4 * cm])
        tabla_graficos.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        elementos.append(tabla_graficos)

    doc = SimpleDocTemplate(
        str(ruta_pdf),
        pagesize=landscape(A4),
        leftMargin=0.8 * cm,
        rightMargin=0.8 * cm,
        topMargin=0.8 * cm,
        bottomMargin=0.8 * cm,
    )
    try:
        doc.build(elementos)
    finally:
        for ruta in rutas_graficos:
            try:
                Path(ruta).unlink(missing_ok=True)
            except OSError:
                pass
    return ruta_pdf


def selector_reporte_pdf(df):
    st.subheader("Reporte PDF por fecha y turno")
    if df.empty or not {"Fecha turno", "Turno"}.issubset(df.columns):
        st.info("No hay datos suficientes para generar PDF.")
        return

    fechas = pd.to_datetime(df["Fecha turno"], errors="coerce").dt.date.dropna()
    turnos = sorted(turno for turno in df["Turno"].dropna().astype(str).str.strip().unique() if turno)
    if fechas.empty or not turnos:
        st.info("No hay fechas o turnos disponibles para generar PDF.")
        return

    col_fecha, col_turno, col_boton = st.columns([1.2, 1, 1])
    with col_fecha:
        fecha_pdf = st.selectbox(
            "Fecha turno PDF",
            sorted(fechas.unique()),
            format_func=lambda fecha: pd.to_datetime(fecha).strftime("%d-%m-%Y"),
            key="pdf_fecha_turno",
        )
    with col_turno:
        turno_pdf = st.selectbox("Turno PDF", turnos, key="pdf_turno")

    df_turno = filtrar_fecha_turno(df, fecha_pdf, turno_pdf)
    with col_boton:
        st.write("")
        st.write("")
        generar = st.button("Generar reporte PDF", key="generar_reporte_pdf")

    if generar:
        if df_turno.empty:
            st.warning("No hay registros para la fecha y turno seleccionados.")
            return

        try:
            ruta_pdf = generar_reporte_pdf_turno(df_turno, fecha_pdf, turno_pdf)
        except RuntimeError as exc:
            st.error(str(exc))
            return

        st.success(f"Reporte PDF generado: {ruta_pdf}")
        st.download_button(
            "Descargar reporte PDF",
            data=Path(ruta_pdf).read_bytes(),
            file_name=Path(ruta_pdf).name,
            mime="application/pdf",
            key="descargar_reporte_pdf",
        )


def resumen_general_aceros(df):
    columnas = [
        "Modelo equipo",
        "Número equipo",
        "Tipo acero",
        "Número Bit / Tricono",
        "Metros totales perforados",
        "Rendimiento consolidado m/h",
    ]
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
    return resumen.sort_values(["_orden_modelo", "_orden_numero"]).drop(
        columns=["_orden_modelo", "_orden_numero"],
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
        turno = st.selectbox("Turno", ["Día", "Noche"], key=k("turno"))

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
                [str(numero) for numero in range(107, 126)],
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
                [str(numero) for numero in range(1, 9)],
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
                ["Producción", "Precorte", "Buffer 1", "Buffer 2", "Repaso", "Borde", "Auxiliares"],
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
                [
                    "Blando",
                    "Medio",
                    "Duro",
                    "Fracturado",
                    "Inestable",
                    "Relleno",
                    "Con presencia de agua",
                ],
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
        ["Falla Operacional", "Avería mecánica", "Cambio de Aceros", "Geología", "Seguridad", "Colación", "Agua", "Combustible", "Traslado", "Cambio Turno", "Otros"],
        key=k("tipo_detencion"),
    )
    causa_detencion = st.text_input("Causa detención", key=k("causa_detencion"))
    observaciones = st.text_area("Observaciones", key=k("observaciones"))

    st.subheader("Horas del turno")
    col_horas_1, col_horas_2, col_horas_3 = st.columns(3)
    with col_horas_1:
        horas_efectivas = st.number_input("Horas efectivas perforando", min_value=0.0, max_value=12.0, step=0.5, key=k("horas_efectivas"))
        horas_averia = st.number_input("Horas avería equipo", min_value=0.0, max_value=12.0, step=0.5, key=k("horas_averia"))
        horas_combustible = st.number_input("Combustible", min_value=0.0, max_value=12.0, step=0.5, key=k("horas_combustible"))
        horas_agua = st.number_input("Relleno de agua", min_value=0.0, max_value=12.0, step=0.5, key=k("horas_agua"))
    with col_horas_2:
        horas_colacion = st.number_input("Colación", min_value=0.0, max_value=12.0, step=0.5, key=k("horas_colacion"))
        horas_traslado = st.number_input("Traslado", min_value=0.0, max_value=12.0, step=0.5, key=k("horas_traslado"))
        horas_sin_marcacion = st.number_input("Standby por falta de tajo/Patio", min_value=0.0, max_value=12.0, step=0.5, key=k("horas_sin_marcacion"))
        horas_tronadura = st.number_input("Tronadura", min_value=0.0, max_value=12.0, step=0.5, key=k("horas_tronadura"))
    with col_horas_3:
        horas_mantencion = st.number_input("Mantención", min_value=0.0, max_value=12.0, step=0.5, key=k("horas_mantencion"))
        horas_cambio_turno = st.number_input("Cambio turno", min_value=0.0, max_value=12.0, step=0.5, key=k("horas_cambio_turno"))
        horas_falta_operador = st.number_input("Falta operador", min_value=0.0, max_value=12.0, step=0.5, key=k("horas_falta_operador"))
        horas_otros = st.number_input("Otros", min_value=0.0, max_value=12.0, step=0.5, key=k("horas_otros"))

    horas_no_efectivas = round(
        horas_combustible
        + horas_agua
        + horas_colacion
        + horas_traslado
        + horas_sin_marcacion
        + horas_tronadura
        + horas_mantencion
        + horas_cambio_turno
        + horas_falta_operador
        + horas_otros,
        2,
    )
    total_horas = round(horas_efectivas + horas_averia + horas_no_efectivas, 2)

    st.info(
        f"Total turno: {total_horas:.2f} / {HORAS_TURNO} h | "
        f"Efectivas {horas_efectivas:.2f} h | "
        f"Avería {horas_averia:.2f} h | "
        f"No efectivas {horas_no_efectivas:.2f} h"
    )

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
        if total_horas != HORAS_TURNO:
            st.error(f"No se puede guardar. El turno suma {total_horas:.2f} h y debe sumar {HORAS_TURNO:.2f} h.")
            return

        if not operador:
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
            "Combustible": horas_combustible,
            "Relleno de agua": horas_agua,
            "Colación": horas_colacion,
            "Traslado": horas_traslado,
            "Standby por falta de tajo/Patio": horas_sin_marcacion,
            "Tronadura": horas_tronadura,
            "Mantención": horas_mantencion,
            "Avería": horas_averia,
            "Cambio turno": horas_cambio_turno,
            "Falta operador": horas_falta_operador,
            "Otros": horas_otros,
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

    selector_reporte_pdf(df_analisis)

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
        columnas_horas = [
            "Horas efectivas perforando",
            "Horas detención mecánica",
            "Horas detención No efectivas",
            "Combustible",
            "Relleno de agua",
            "Colación",
            "Traslado",
            "Standby por falta de tajo/Patio",
            "Tronadura",
            "Mantención",
            "Cambio turno",
            "Falta operador",
            "Otros",
        ]
        horas = {
            columna: pd.to_numeric(df_analisis[columna], errors="coerce").fillna(0).sum()
            for columna in columnas_horas
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
