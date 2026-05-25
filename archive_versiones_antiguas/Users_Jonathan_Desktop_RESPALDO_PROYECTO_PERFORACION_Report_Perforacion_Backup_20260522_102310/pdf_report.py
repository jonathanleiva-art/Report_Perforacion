"""PDF report generation helpers for the drilling report project.

This module is prepared as an external copy of the PDF-related logic. It is not
connected from app_perforacion.py yet, so current application behavior remains
unchanged.
"""

from datetime import datetime
from pathlib import Path
from unicodedata import normalize

import pandas as pd
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from metrics import calcular_rendimiento_consolidado, registros_productivos
from schema import COLUMNAS_HORAS_DETENCION
from utils import EQUIPOS, EXCEL_PATH, HORAS_TURNO, limpiar_entero

REPORTES_PDF_DIR = Path(EXCEL_PATH).parent / "reportes_pdf"


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


def totales_productivos(df):
    metros = serie_numerica(df, "Metros perforados")
    horas = serie_numerica(df, "Horas efectivas perforando")
    productivos = (metros > 0) & (horas > 0)
    total_metros = metros[productivos].sum()
    total_horas = horas[productivos].sum()
    rendimiento = total_metros / total_horas if total_horas > 0 else 0

    return total_metros, total_horas, rendimiento


def tabla_pdf(datos, anchos=None):
    tabla = Table(datos, colWidths=anchos, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    return tabla


def texto_pdf(valor):
    if pd.isna(valor):
        return ""
    if isinstance(valor, float):
        return f"{valor:.2f}"
    return str(valor)


def columnas_horas_turno():
    return ["Horas efectivas perforando", *COLUMNAS_HORAS_DETENCION]


def etiqueta_hora(columna):
    etiquetas = {
        "Horas detención mecánica": "Avería mecánica",
        "Relleno de agua": "Agua",
        "Cambio turno": "Cambio Turno",
    }
    return etiquetas.get(columna, columna)


def numero_pdf(valor):
    return pd.to_numeric(pd.Series([valor]), errors="coerce").fillna(0).iloc[0]


def formato_numero(valor, decimales=2, sufijo=""):
    numero = numero_pdf(valor)
    return f"{numero:,.{decimales}f}{sufijo}"


def color_estado(valor, bueno=80, medio=60):
    valor = numero_pdf(valor)
    if valor >= bueno:
        return colors.HexColor("#15803D")
    if valor >= medio:
        return colors.HexColor("#B45309")
    return colors.HexColor("#B91C1C")


def crear_estilos_pdf():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="PortadaTitulo",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=28,
        leading=32,
        textColor=colors.white,
        alignment=TA_CENTER,
        spaceAfter=16,
    ))
    styles.add(ParagraphStyle(
        name="PortadaSubtitulo",
        parent=styles["Normal"],
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#DCE7F3"),
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name="Seccion",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=colors.HexColor("#17324D"),
        spaceBefore=8,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="Texto",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1F2937"),
    ))
    styles.add(ParagraphStyle(
        name="Nota",
        parent=styles["Normal"],
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#4B5563"),
    ))
    return styles


def logo_pdf():
    candidatos = ["logo.png", "logo.jpg", "logo.jpeg", "LOGO.png", "LOGO.jpg", "LOGO.jpeg"]
    for nombre in candidatos:
        ruta = Path(EXCEL_PATH).parent / nombre
        if ruta.exists():
            return ruta
    return None


def tabla_datos_pdf(datos, anchos=None, font_size=7.5):
    tabla = Table(datos, colWidths=anchos, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17324D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEADING", (0, 0), (-1, -1), font_size + 2),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tabla


def tarjetas_kpi_pdf(kpis):
    filas = []
    celdas = []
    for titulo, valor, detalle, color in kpis:
        celdas.append(Table(
            [[titulo], [valor], [detalle]],
            colWidths=[5.0 * cm],
            rowHeights=[0.55 * cm, 0.9 * cm, 0.55 * cm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.8, color),
                ("LINEBEFORE", (0, 0), (0, -1), 5, color),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#475569")),
                ("TEXTCOLOR", (0, 1), (-1, 1), color),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 7.5),
                ("FONTSIZE", (0, 1), (-1, 1), 15),
                ("FONTSIZE", (0, 2), (-1, 2), 7),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]),
        ))
    for i in range(0, len(celdas), 5):
        filas.append(celdas[i:i + 5])
    return Table(filas, hAlign="CENTER", style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))


def grafico_barras_pdf(datos, titulo, width=23.5 * cm, height=6.2 * cm, color="#2563EB"):
    datos = [(str(nombre), float(valor)) for nombre, valor in datos if float(valor) > 0]
    dibujo = Drawing(width, height)
    dibujo.add(String(0, height - 12, titulo, fontName="Helvetica-Bold", fontSize=10, fillColor=colors.HexColor("#17324D")))
    if not datos:
        dibujo.add(String(0, height / 2, "Sin datos disponibles", fontSize=8, fillColor=colors.HexColor("#64748B")))
        return dibujo

    max_valor = max(valor for _, valor in datos) or 1
    top = height - 28
    bar_h = min(15, (height - 35) / max(len(datos), 1) - 3)
    label_w = 5.6 * cm
    chart_w = width - label_w - 2.2 * cm
    for idx, (nombre, valor) in enumerate(datos[:10]):
        y = top - idx * (bar_h + 4)
        ancho = chart_w * valor / max_valor
        dibujo.add(String(0, y + 3, nombre[:36], fontSize=7, fillColor=colors.HexColor("#334155")))
        dibujo.add(Rect(label_w, y, chart_w, bar_h, fillColor=colors.HexColor("#E2E8F0"), strokeColor=None))
        dibujo.add(Rect(label_w, y, ancho, bar_h, fillColor=colors.HexColor(color), strokeColor=None))
        dibujo.add(String(label_w + chart_w + 4, y + 3, formato_numero(valor, 1), fontSize=7, fillColor=colors.HexColor("#334155")))
    return dibujo


def grafico_tendencia_pdf(datos, titulo, width=23.5 * cm, height=6.0 * cm):
    datos = [(str(fecha), float(valor)) for fecha, valor in datos if float(valor) > 0]
    dibujo = Drawing(width, height)
    dibujo.add(String(0, height - 12, titulo, fontName="Helvetica-Bold", fontSize=10, fillColor=colors.HexColor("#17324D")))
    if len(datos) < 2:
        dibujo.add(String(0, height / 2, "Sin datos históricos suficientes", fontSize=8, fillColor=colors.HexColor("#64748B")))
        return dibujo

    left = 1.0 * cm
    bottom = 0.8 * cm
    chart_w = width - 1.8 * cm
    chart_h = height - 2.0 * cm
    valores = [valor for _, valor in datos]
    min_v = min(valores)
    max_v = max(valores)
    rango = max(max_v - min_v, 1)
    dibujo.add(Line(left, bottom, left + chart_w, bottom, strokeColor=colors.HexColor("#94A3B8"), strokeWidth=0.7))
    dibujo.add(Line(left, bottom, left, bottom + chart_h, strokeColor=colors.HexColor("#94A3B8"), strokeWidth=0.7))

    puntos = []
    for idx, (_, valor) in enumerate(datos):
        x = left + chart_w * idx / (len(datos) - 1)
        y = bottom + chart_h * (valor - min_v) / rango
        puntos.append((x, y, valor))
    for (x1, y1, _), (x2, y2, _) in zip(puntos, puntos[1:]):
        dibujo.add(Line(x1, y1, x2, y2, strokeColor=colors.HexColor("#0F766E"), strokeWidth=1.5))
    for x, y, valor in puntos:
        dibujo.add(Rect(x - 2, y - 2, 4, 4, fillColor=colors.HexColor("#0F766E"), strokeColor=None))
    dibujo.add(String(left, 4, datos[0][0], fontSize=6.5, fillColor=colors.HexColor("#475569")))
    dibujo.add(String(left + chart_w - 45, 4, datos[-1][0], fontSize=6.5, fillColor=colors.HexColor("#475569")))
    dibujo.add(String(left + chart_w - 60, bottom + chart_h + 5, f"Max {formato_numero(max_v, 1)}", fontSize=6.5, fillColor=colors.HexColor("#475569")))
    return dibujo


def datos_detenciones(df):
    filas = []
    for columna in COLUMNAS_HORAS_DETENCION:
        if columna in df.columns:
            horas = pd.to_numeric(df[columna], errors="coerce").fillna(0).sum()
            if horas > 0:
                filas.append((etiqueta_hora(columna), round(horas, 2)))
    return sorted(filas, key=lambda item: item[1], reverse=True)


def tendencia_rendimiento(df):
    if df.empty or "Fecha turno" not in df.columns:
        return []
    base = df.copy()
    base["Fecha turno"] = pd.to_datetime(base["Fecha turno"], errors="coerce").dt.date
    filas = []
    for fecha, grupo in base.dropna(subset=["Fecha turno"]).groupby("Fecha turno"):
        _, _, rendimiento = totales_productivos(grupo)
        if rendimiento > 0:
            filas.append((pd.to_datetime(fecha).strftime("%d-%m"), round(rendimiento, 2)))
    return filas[-12:]


def resumen_ejecutivo_pdf(df_reporte, proyecto, fecha_pdf, turno, metricas):
    total_metros = metricas["metros"]
    rendimiento = metricas["rendimiento"]
    utilizacion = metricas["utilizacion"]
    disponibilidad = metricas["disponibilidad"]
    equipos = metricas["equipos"]
    no_efectivas = metricas["horas_no_efectivas"]
    return (
        f"Durante el turno {turno} del {fecha_pdf.strftime('%d-%m-%Y')} en {proyecto}, "
        f"se registraron {equipos} equipos con {formato_numero(total_metros, 2)} metros perforados "
        f"y un rendimiento consolidado de {formato_numero(rendimiento, 2)} m/h. "
        f"La utilización promedio fue {formato_numero(utilizacion, 2, '%')} y la disponibilidad promedio "
        f"alcanzó {formato_numero(disponibilidad, 2, '%')}. "
        f"El tiempo no efectivo consolidado fue {formato_numero(no_efectivas, 2)} h, "
        "por lo que las principales detenciones deben revisarse en el Pareto operacional del reporte."
    )


def alertas_pdf(df_reporte, metricas):
    alertas = []
    if metricas["utilizacion"] < 60:
        alertas.append(["Alta", "Baja utilización", f"Utilización promedio {formato_numero(metricas['utilizacion'], 2, '%')}"])
    elif metricas["utilizacion"] < 75:
        alertas.append(["Media", "Utilización bajo objetivo", f"Utilización promedio {formato_numero(metricas['utilizacion'], 2, '%')}"])

    sin_marcacion = 0
    if "Sin marcación" in df_reporte.columns:
        sin_marcacion += pd.to_numeric(df_reporte["Sin marcación"], errors="coerce").fillna(0).sum()
    if "Tipo detención" in df_reporte.columns:
        sin_marcacion += df_reporte["Tipo detención"].astype(str).str.contains("Sin marcación", case=False, na=False).sum()
    if sin_marcacion > 0:
        alertas.append(["Media", "Registros sin marcación", f"Se detectaron {formato_numero(sin_marcacion, 1)} eventos/horas asociados"])

    if metricas["horas_averia"] > 0:
        alertas.append(["Alta", "Averías registradas", f"{formato_numero(metricas['horas_averia'], 2)} h de avería mecánica"])

    if metricas["horas_no_efectivas"] >= max(metricas["horas_efectivas"] * 0.35, 2):
        alertas.append(["Media", "Alto tiempo no efectivo", f"{formato_numero(metricas['horas_no_efectivas'], 2)} h no efectivas"])

    if not alertas:
        alertas.append(["OK", "Sin alertas críticas", "Indicadores dentro de rangos operacionales esperados"])
    return alertas


def semaforo_operacional(df_reporte):
    filas = [["Equipo", "Estado", "Base de clasificación"]]
    if df_reporte.empty or not {"Modelo equipo", "Número equipo"}.issubset(df_reporte.columns):
        return filas

    for (modelo, numero), grupo in df_reporte.groupby(["Modelo equipo", "Número equipo"], dropna=False):
        equipo = f"{modelo} {numero}".strip()
        averia = serie_numerica(grupo, "Horas detención mecánica", "Avería").sum()
        efectivas = serie_numerica(grupo, "Horas efectivas perforando").sum()
        sin_marcacion = serie_numerica(grupo, "Sin marcación").sum()
        tipo_sin_marcacion = grupo.get("Tipo detención", pd.Series(dtype=str)).astype(str).str.contains("Sin marcación", case=False, na=False).any()
        if sin_marcacion > 0 or tipo_sin_marcacion:
            filas.append([equipo, "Sin marcación", "Registro requiere revisión"])
        elif averia >= HORAS_TURNO * 0.5:
            filas.append([equipo, "Avería", f"{formato_numero(averia, 2)} h de avería"])
        elif efectivas > 0 and averia == 0:
            filas.append([equipo, "Operativo", f"{formato_numero(efectivas, 2)} h efectivas"])
        else:
            filas.append([equipo, "Parcial", f"{formato_numero(efectivas, 2)} h efectivas / {formato_numero(averia, 2)} h avería"])
    return filas


def equipos_esperados_pdf():
    return [(modelo, numero) for modelo, numeros in EQUIPOS.items() for numero in numeros]


def filas_equipos_pdf(df_reporte):
    columnas = [
        "Modelo",
        "N°",
        "Operador",
        "Estado",
        "Metros",
        "Rend. m/h",
        "H. efect.",
        "H. no efect.",
        "H. avería",
        "Disp. %",
        "Util. %",
        "Marcación",
    ]
    filas = [columnas]
    metricas = {
        "registrados": 0,
        "con_marcacion": 0,
        "sin_marcacion": 0,
    }
    if df_reporte.empty:
        for modelo, numero in equipos_esperados_pdf():
            filas.append([modelo, numero, "", "Sin marcación", "0.00", "0.00", "0.00", "0.00", "0.00", "0.00", "0.00", "Sin marcación"])
            metricas["sin_marcacion"] += 1
        return filas, metricas

    base = df_reporte.copy()
    if "Número equipo" in base.columns:
        base["Número equipo"] = base["Número equipo"].astype(str).apply(limpiar_entero)
    equipos_registrados = set()

    for modelo, numero in equipos_esperados_pdf():
        if {"Modelo equipo", "Número equipo"}.issubset(base.columns):
            grupo = base[
                base["Modelo equipo"].astype(str).str.strip().eq(str(modelo).strip())
                & base["Número equipo"].astype(str).apply(limpiar_entero).eq(limpiar_entero(numero))
            ].copy()
        else:
            grupo = pd.DataFrame()

        if grupo.empty:
            filas.append([modelo, numero, "", "Sin marcación", "0.00", "0.00", "0.00", "0.00", "0.00", "0.00", "0.00", "Sin marcación"])
            metricas["sin_marcacion"] += 1
            continue

        equipos_registrados.add((modelo, numero))
        operador = ", ".join(dict.fromkeys(grupo.get("Operador", pd.Series(dtype=str)).dropna().astype(str)))
        metros = serie_numerica(grupo, "Metros perforados").sum()
        horas_efectivas = serie_numerica(grupo, "Horas efectivas perforando").sum()
        horas_no_efectivas = serie_numerica(grupo, "Horas detención No efectivas").sum()
        horas_averia = serie_numerica(grupo, "Horas detención mecánica", "Avería").sum()
        rendimiento = metros / horas_efectivas if horas_efectivas > 0 else 0
        disponibilidad = serie_numerica(grupo, "Disponibilidad %").mean()
        utilizacion = serie_numerica(grupo, "Utilización %", "Utilizacion %").mean()
        tipo_detencion = grupo.get("Tipo detención", pd.Series(dtype=str)).astype(str)
        sin_marcacion_valor = serie_numerica(grupo, "Sin marcación").sum()
        sin_marcacion_tipo = tipo_detencion.str.contains("Sin marcación", case=False, na=False).any()
        tiene_marcacion = (metros > 0) or (horas_efectivas > 0) or (horas_no_efectivas > 0) or (horas_averia > 0)

        if sin_marcacion_valor > 0 or sin_marcacion_tipo or not tiene_marcacion:
            estado = "Operativo sin marcación" if not tiene_marcacion else "Sin marcación"
            marcacion = "Sin marcación"
            metricas["sin_marcacion"] += 1
        elif horas_averia >= HORAS_TURNO * 0.5:
            estado = "Avería"
            marcacion = "Con marcación"
            metricas["con_marcacion"] += 1
        elif horas_efectivas > 0:
            estado = "Operativo"
            marcacion = "Con marcación"
            metricas["con_marcacion"] += 1
        else:
            estado = "Parcial"
            marcacion = "Con marcación"
            metricas["con_marcacion"] += 1

        filas.append([
            modelo,
            numero,
            operador,
            estado,
            formato_numero(metros, 2),
            formato_numero(rendimiento, 2),
            formato_numero(horas_efectivas, 2),
            formato_numero(horas_no_efectivas, 2),
            formato_numero(horas_averia, 2),
            formato_numero(disponibilidad, 2),
            formato_numero(utilizacion, 2),
            marcacion,
        ])

    metricas["registrados"] = len(equipos_registrados)
    return filas, metricas


def analisis_turno_pdf(fecha_pdf, turno, metricas, principal_detencion):
    causa = principal_detencion[0] if principal_detencion else "sin detenciones relevantes"
    horas_causa = principal_detencion[1] if principal_detencion else 0
    impacto = "El turno presenta continuidad operacional aceptable."
    if metricas["horas_averia"] > 0:
        impacto = "La avería mecánica impactó la disponibilidad operacional."
    elif metricas["horas_no_efectivas"] > metricas["horas_efectivas"] * 0.35:
        impacto = "El tiempo no efectivo representa una restricción relevante para la utilización."
    elif metricas.get("operativos_sin_marcacion", 0) > 0:
        impacto = "Existen equipos operativos sin marcación que requieren regularización del registro."

    return (
        f"Turno {turno} del {fecha_pdf.strftime('%d-%m-%Y')}: producción total "
        f"{formato_numero(metricas['metros'], 2)} m, rendimiento consolidado "
        f"{formato_numero(metricas['rendimiento'], 2)} m/h. La principal causa de detención fue "
        f"{causa} ({formato_numero(horas_causa, 2)} h). Se registran {metricas['con_marcacion']} equipos "
        f"con marcación y {metricas.get('operativos_sin_marcacion', 0)} equipos operativos sin marcación. "
        f"{impacto}"
    )


def generar_pdf(df_reporte, fecha_turno, turno, df_historico=None):
    REPORTES_PDF_DIR.mkdir(exist_ok=True)
    fecha_pdf = pd.to_datetime(fecha_turno).date()
    fecha_archivo = fecha_pdf.strftime("%Y-%m-%d")
    turno_archivo = str(turno).replace(" ", "_")
    ruta_pdf = REPORTES_PDF_DIR / f"reporte_perforacion_{fecha_archivo}_{turno_archivo}.pdf"

    doc = SimpleDocTemplate(
        str(ruta_pdf),
        pagesize=landscape(A4),
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
    )
    styles = crear_estilos_pdf()
    df_historico = df_historico if df_historico is not None else df_reporte
    proyecto = "Proyecto DES"
    if "Área operacional" in df_reporte.columns:
        valores_proyecto = [valor for valor in df_reporte["Área operacional"].dropna().astype(str).unique() if valor.strip()]
        if valores_proyecto:
            proyecto = valores_proyecto[0]

    total_metros, total_horas, rendimiento = totales_productivos(df_reporte)
    filas_equipos, metricas_equipos = filas_equipos_pdf(df_reporte)
    equipos = len(equipos_esperados_pdf())
    disponibilidad = serie_numerica(df_reporte, "Disponibilidad %").mean()
    utilizacion = serie_numerica(df_reporte, "Utilización %", "Utilizacion %").mean()
    horas_averia = serie_numerica(df_reporte, "Horas detención mecánica", "Avería").sum()
    horas_no_efectivas = serie_numerica(df_reporte, "Horas detención No efectivas").sum()
    petroleo = serie_numerica(df_reporte, "Petróleo litros").sum()
    pozos = serie_numerica(df_reporte, "Pozos perforados turno", "Cantidad pozos perforados").sum()
    equipos_operativos = metricas_equipos["con_marcacion"]
    metricas = {
        "metros": total_metros,
        "horas_efectivas": total_horas,
        "rendimiento": rendimiento,
        "equipos": equipos,
        "disponibilidad": disponibilidad if pd.notna(disponibilidad) else 0,
        "utilizacion": utilizacion if pd.notna(utilizacion) else 0,
        "horas_averia": horas_averia,
        "horas_no_efectivas": horas_no_efectivas,
        "petroleo": petroleo,
        "pozos": pozos,
        "equipos_operativos": equipos_operativos,
        "registrados": metricas_equipos["registrados"],
        "con_marcacion": metricas_equipos["con_marcacion"],
        "operativos_sin_marcacion": metricas_equipos["sin_marcacion"],
    }

    def pie_pagina(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(1.2 * cm, 0.55 * cm, f"Sistema de Reporte de Perforación | {proyecto}")
        canvas.drawRightString(landscape(A4)[0] - 1.2 * cm, 0.55 * cm, f"Página {canvas.getPageNumber()}")
        canvas.restoreState()

    story = []

    logo = logo_pdf()
    titulo = [
        Paragraph("REPORTE DE PERFORACIÓN", styles["PortadaTitulo"]),
        Paragraph("Análisis operacional y KPI del turno", styles["PortadaSubtitulo"]),
    ]
    encabezado_contenido = [[Image(str(logo), width=2.4 * cm, height=1.2 * cm), titulo] if logo else ["", titulo]]
    encabezado = Table(encabezado_contenido, colWidths=[3.0 * cm, landscape(A4)[0] - 5.4 * cm])
    encabezado.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0F2438")),
        ("LINEBELOW", (0, 0), (-1, -1), 4, colors.HexColor("#F59E0B")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(encabezado)
    story.append(Spacer(1, 0.25 * cm))
    portada_datos = [
        ["Fecha", fecha_pdf.strftime("%d-%m-%Y"), "Turno", str(turno)],
        ["Proyecto", proyecto, "Equipos registrados", equipos],
        ["Rendimiento consolidado", f"{formato_numero(rendimiento, 2)} m/h", "Generado", datetime.now().strftime("%d-%m-%Y %H:%M")],
    ]
    tabla_portada = Table(portada_datos, colWidths=[4.2 * cm, 7.0 * cm, 4.2 * cm, 7.0 * cm], hAlign="CENTER")
    tabla_portada.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0F172A")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(tabla_portada)
    story.append(Spacer(1, 0.18 * cm))

    kpis = [
        ("METROS PERFORADOS", formato_numero(total_metros, 2), "Producción total", colors.HexColor("#2563EB")),
        ("RENDIMIENTO", f"{formato_numero(rendimiento, 2)} m/h", "Consolidado", colors.HexColor("#0F766E")),
        ("DISPONIBILIDAD", formato_numero(metricas["disponibilidad"], 2, "%"), "Promedio turno", color_estado(metricas["disponibilidad"])),
        ("UTILIZACIÓN", formato_numero(metricas["utilizacion"], 2, "%"), "Promedio turno", color_estado(metricas["utilizacion"])),
        ("EQUIPOS REGISTRADOS", f"{metricas['registrados']}/{equipos}", "Reportados en turno", colors.HexColor("#7C3AED")),
        ("CON MARCACIÓN", str(metricas["con_marcacion"]), "Equipos con datos", colors.HexColor("#15803D")),
        ("SIN MARCACIÓN", str(metricas["operativos_sin_marcacion"]), "Requieren revisión", colors.HexColor("#64748B")),
        ("H. NO EFECTIVAS", formato_numero(horas_no_efectivas, 2), "Distribución turno", colors.HexColor("#B45309")),
        ("H. AVERÍA", formato_numero(horas_averia, 2), "Mecánica", colors.HexColor("#B91C1C")),
    ]
    story.append(tarjetas_kpi_pdf(kpis))
    story.append(Spacer(1, 0.18 * cm))

    detenciones = datos_detenciones(df_reporte)
    principal_detencion = detenciones[0] if detenciones else None
    story.append(Paragraph("Análisis breve del turno", styles["Seccion"]))
    story.append(Paragraph(analisis_turno_pdf(fecha_pdf, turno, metricas, principal_detencion), styles["Texto"]))
    story.append(Spacer(1, 0.18 * cm))

    horas = [["Categoría", "Horas"]]
    for columna in columnas_horas_turno():
        if columna in df_reporte.columns:
            horas.append([etiqueta_hora(columna), round(pd.to_numeric(df_reporte[columna], errors="coerce").fillna(0).sum(), 2)])
    produccion = [
        ["Indicador", "Valor"],
        ["Metros perforados", formato_numero(total_metros, 2)],
        ["Pozos perforados", formato_numero(pozos, 0)],
        ["Petróleo litros", formato_numero(petroleo, 2)],
        ["Horas efectivas", formato_numero(total_horas, 2)],
    ]
    kpi_tabla = [
        ["KPI", "Valor"],
        ["Rendimiento m/h", formato_numero(rendimiento, 2)],
        ["Disponibilidad promedio", formato_numero(metricas["disponibilidad"], 2, "%")],
        ["Utilización promedio", formato_numero(metricas["utilizacion"], 2, "%")],
        ["Horas avería", formato_numero(horas_averia, 2)],
        ["Horas no efectivas", formato_numero(horas_no_efectivas, 2)],
    ]
    story.append(Paragraph("Resumen operacional", styles["Seccion"]))
    story.append(Table(
        [[
            tabla_datos_pdf(produccion, [5 * cm, 3.2 * cm], 8),
            tabla_datos_pdf(horas, [5.5 * cm, 2.8 * cm], 8),
            tabla_datos_pdf(kpi_tabla, [5.2 * cm, 3.2 * cm], 8),
        ]],
        style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]),
    ))
    story.append(Spacer(1, 0.18 * cm))

    story.append(Paragraph("Detalle compacto por equipo", styles["Seccion"]))
    tabla_equipos = tabla_datos_pdf(
        filas_equipos,
        [2.7 * cm, 1.2 * cm, 3.1 * cm, 3.3 * cm, 1.8 * cm, 1.8 * cm, 1.7 * cm, 1.8 * cm, 1.7 * cm, 1.7 * cm, 1.7 * cm, 2.3 * cm],
        font_size=5.8,
    )
    for fila_idx, fila in enumerate(filas_equipos[1:], start=1):
        estado = fila[3]
        color = {
            "Operativo": colors.HexColor("#DCFCE7"),
            "Parcial": colors.HexColor("#FEF3C7"),
            "Avería": colors.HexColor("#FEE2E2"),
            "Sin marcación": colors.HexColor("#E5E7EB"),
            "Operativo sin marcación": colors.HexColor("#E0F2FE"),
        }.get(estado, colors.white)
        tabla_equipos.setStyle(TableStyle([("BACKGROUND", (3, fila_idx), (3, fila_idx), color)]))
    story.append(tabla_equipos)
    story.append(PageBreak())

    story.append(Paragraph("Gráficos operacionales resumidos", styles["Seccion"]))
    story.append(grafico_barras_pdf(detenciones, "Pareto de detenciones por horas", height=4.7 * cm, color="#B45309"))
    story.append(Spacer(1, 0.16 * cm))

    ranking_operadores = calcular_rendimiento_consolidado(registros_productivos(df_reporte), ["Operador"]).sort_values("Rendimiento m/h", ascending=False)
    datos_operadores = list(zip(ranking_operadores.get("Operador", []), ranking_operadores.get("Rendimiento m/h", [])))
    story.append(grafico_barras_pdf(datos_operadores, "Ranking operadores por rendimiento m/h", height=4.7 * cm, color="#2563EB"))
    story.append(Spacer(1, 0.16 * cm))

    ranking_equipos = calcular_rendimiento_consolidado(registros_productivos(df_reporte), ["Modelo equipo", "Número equipo"])
    if not ranking_equipos.empty:
        ranking_equipos["Equipo"] = ranking_equipos["Modelo equipo"].astype(str) + " " + ranking_equipos["Número equipo"].astype(str)
        ranking_equipos = ranking_equipos.sort_values("Rendimiento m/h", ascending=False)
    datos_equipos = list(zip(ranking_equipos.get("Equipo", []), ranking_equipos.get("Rendimiento m/h", []))) if not ranking_equipos.empty else []
    story.append(grafico_barras_pdf(datos_equipos, "Ranking equipos por rendimiento m/h", height=4.7 * cm, color="#0F766E"))

    doc.build(story, onFirstPage=pie_pagina, onLaterPages=pie_pagina)
    return ruta_pdf
