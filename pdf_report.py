from datetime import datetime
from pathlib import Path
import re
from unicodedata import normalize
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from audit import audit_log
from config import ASSETS_DIR, PROJECT_ROOT, REPORTS_PDF_DIR
from metrics import calcular_kpis_consolidados_dataframe, registros_productivos
from operators import agregar_columnas_operador_visual
from services import alert_service, kpi_service
from utils import (
    COLUMNAS_HORAS_DETENCION,
    DETENCION_HORAS_COLUMNAS,
    EXCEL_PATH,
    HORAS_TURNO,
    color_estado_operacional,
    color_texto_estado_operacional,
    limpiar_entero,
    ruta_imagen_equipo,
)

_CELL_WRAP = ParagraphStyle("cell_wrap_sm", fontSize=5.5, leading=7.5, alignment=1)
_OBS_WRAP = ParagraphStyle("obs_wrap", fontSize=7, leading=9)

REPORTES_PDF_DIR = REPORTS_PDF_DIR


def nombre_archivo_seguro(valor):
    texto = normalize("NFKD", str(valor)).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^A-Za-z0-9_.-]+", "_", texto).strip("_")
    return texto or "sin_turno"


def equipos_esperados():
    return kpi_service.equipos_esperados()


def normalizar_nombre_columna(nombre):
    return kpi_service.normalizar_nombre_columna(nombre)


def buscar_columna(df, *candidatos):
    return kpi_service.buscar_columna(df, *candidatos)


def serie_numerica(df, *columnas):
    return kpi_service.serie_numerica(df, *columnas)


def totales_productivos(df):
    return kpi_service.totales_productivos(df)


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
        "Relleno de agua": "Relleno de agua",
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
    styles.add(ParagraphStyle(
        name="SeccionNaranja",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=colors.HexColor("#E67E22"),
        spaceBefore=8,
        spaceAfter=6,
    ))
    return styles


def logo_pdf():
    candidatos = ["logo.png", "logo.jpg", "logo.jpeg", "LOGO.png", "LOGO.jpg", "LOGO.jpeg"]
    for nombre in candidatos:
        for carpeta in (PROJECT_ROOT, ASSETS_DIR):
            ruta = carpeta / nombre
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
        standby = serie_numerica(grupo, "Standby por falta de tajo/Patio").sum()
        tipo_standby = grupo.get("Tipo detención", pd.Series(dtype=str)).astype(str).str.contains("Standby por falta de tajo/Patio", case=False, na=False).any()
        if averia >= HORAS_TURNO * 0.5:
            filas.append([equipo, "Avería", f"{formato_numero(averia, 2)} h de avería"])
        elif efectivas > 0 and averia == 0:
            filas.append([equipo, "Operativo", f"{formato_numero(efectivas, 2)} h efectivas"])
        elif standby > 0 or tipo_standby:
            filas.append([equipo, "Operativo", "Standby por falta de tajo/Patio"])
        else:
            filas.append([equipo, "Parcial", f"{formato_numero(efectivas, 2)} h efectivas / {formato_numero(averia, 2)} h avería"])
    return filas


def equipos_esperados_pdf():
    return kpi_service.equipos_esperados()


def estado_operacional_equipo(metros, pozos, horas_efectivas, horas_no_efectivas, horas_averia, horas_mantencion):
    estado, marcacion = kpi_service.estado_operacional_equipo(
        metros,
        pozos,
        horas_efectivas,
        horas_no_efectivas,
        horas_averia,
        horas_mantencion,
    )
    reemplazos = {
        "Avería": "Avería",
        "Mantención Programada": "Mantención Programada",
        "Sin marcación": "Sin marcación",
        "Con marcación": "Con marcación",
    }
    return reemplazos.get(estado, estado), reemplazos.get(marcacion, marcacion)


def borde_estado_operacional(estado):
    return {
        # Valores oficiales
        "Equipo Operativo con marcación":              "#27AE60",
        "Equipo Operativo, sin marcación":             "#95A5A6",
        "Equipo Operativo, sin patio de perforación":  "#E67E22",
        "Equipo en Mantención Programada":             "#2980B9",
        "Equipo en Avería":                            "#C0392B",
        "Sin marcación":                               "#95A5A6",
        # Legacy
        "Con marcación":                               "#27AE60",
        "Con marcación (parcial)":                     "#E67E22",
        "Fuera de servicio por avería":                "#C0392B",
        "En mantención programada":                    "#2980B9",
        "Standby por falta de tajo/Patio":             "#E67E22",
        "Operativo":                                   "#27AE60",
        "Operativo parcial":                           "#E67E22",
        "Avería":                                      "#C0392B",
        "Mantención Programada":                       "#2980B9",
    }.get(estado, "#CBD5E1")


def ruta_imagen_equipo_pdf(modelo, numero):
    numero = limpiar_entero(numero)
    candidatos = {
        ("Sandvik D75KS", "9245"): ["SANDVIK D75 KS.jpeg"],
        ("Sandvik D75KS", "9277"): ["SANDVIK D75 KS.jpeg"],
        ("SmartROC D65", "9339"): ["SMART ROC D65.jpeg"],
        ("FlexiROC D65", "9259"): ["FLEXI ROC D65 9259.jpeg", "FLEXI ROC D5 9259"],
        ("FlexiROC D65", "9272"): ["FLEXI ROC D65 9272.jpeg"],
        ("FlexiROC D65", "9274"): ["FLEXI ROC D65 9274.jpeg"],
    }
    carpetas = [ASSETS_DIR, ASSETS_DIR / "equipos", PROJECT_ROOT]
    for nombre in candidatos.get((str(modelo), numero), []):
        for carpeta in carpetas:
            ruta = carpeta / nombre
            if ruta.exists():
                return ruta

    busqueda = f"{numero}"
    for carpeta in carpetas:
        if not carpeta.exists():
            continue
        for ruta in carpeta.iterdir():
            if ruta.is_file() and busqueda in ruta.name and str(modelo).split()[0].upper() in ruta.name.upper():
                return ruta
    return ruta_imagen_equipo(modelo, numero)


def resumen_operacional_equipos(df):
    return kpi_service.resumen_operacional_equipos(df)


def _sectores_por_equipo_pdf(df_reporte):
    columnas_sector = ["Sectores trabajados", "Tipo de perforación", "tipo_sector", "Tipo de sector", "Tipo sector"]
    columna_sector = next((col for col in columnas_sector if col in df_reporte.columns), None)
    if not columna_sector:
        return {}

    sectores_por_equipo = {}
    for _, registro in df_reporte.iterrows():
        clave = (
            str(registro.get("Modelo equipo", "") or "").strip(),
            limpiar_entero(registro.get("Número equipo", "")),
            str(registro.get("Operador", "") or "").strip(),
        )
        actuales = sectores_por_equipo.setdefault(clave, [])
        for item in str(registro.get(columna_sector, "") or "").split(","):
            sector = item.strip()
            if sector and sector.lower() not in ("nan", "none", "nat") and sector not in actuales:
                actuales.append(sector)
    return {clave: ", ".join(valores) for clave, valores in sectores_por_equipo.items()}


def filas_equipos_pdf(df_reporte):
    columnas = [
        "Modelo",
        "N°",
        "Operador",
        "Estatus",
        "Sector",
        "Metros",
        "Pozos",
        "Rend. m/h",
        "H. efect.",
        "H. no efect.",
        "H. avería",
        "Disp. %",
        "Util. %",
        "Estado del equipo",
    ]
    filas = [columnas]
    metricas = {
        "registrados": 0,
        "con_marcacion": 0,
        "standby_sin_tajo_patio": 0,
        "fuera_servicio": 0,
        "estados_raw": [],
    }

    resumen = resumen_operacional_equipos(df_reporte)
    estatus_por_equipo = {}
    sectores_por_equipo = _sectores_por_equipo_pdf(df_reporte)
    if "Estatus del Equipo" in df_reporte.columns:
        for _, registro in df_reporte.iterrows():
            estatus = str(registro.get("Estatus del Equipo", "") or "").strip()
            if not estatus:
                continue
            clave = (
                str(registro.get("Modelo equipo", "") or "").strip(),
                limpiar_entero(registro.get("Número equipo", "")),
                str(registro.get("Operador", "") or "").strip(),
            )
            estatus_por_equipo[clave] = estatus

    for _, equipo in resumen.iterrows():
        estado_eq = str(equipo.get("Estado del equipo", "Sin marcación"))
        if estado_eq in (
            "Equipo Operativo con marcación",
            "Con marcación", "Con marcación (parcial)",
        ):
            metricas["con_marcacion"] += 1
        elif estado_eq in ("Equipo en Avería", "Fuera de servicio por avería"):
            metricas["fuera_servicio"] += 1
        elif estado_eq in (
            "Equipo Operativo, sin patio de perforación",
            "Standby por falta de tajo/Patio",
        ):
            metricas["standby_sin_tajo_patio"] += 1

        clave_estatus = (
            str(equipo["Modelo equipo"]).strip(),
            limpiar_entero(equipo["Número equipo"]),
            str(equipo["Operador"]).strip(),
        )
        metricas["estados_raw"].append(estado_eq)
        filas.append([
            equipo["Modelo equipo"],
            equipo["Número equipo"],
            equipo["Operador"],
            estatus_por_equipo.get(clave_estatus, ""),
            sectores_por_equipo.get(clave_estatus, ""),
            formato_numero(equipo["Metros perforados"], 2),
            formato_numero(equipo["Pozos perforados"], 0),
            formato_numero(equipo["Rendimiento consolidado m/h"], 2),
            formato_numero(equipo["Horas efectivas perforando"], 2),
            formato_numero(equipo["Horas no efectivas"], 2),
            formato_numero(equipo["Horas avería equipo"], 2),
            formato_numero(equipo["Disponibilidad %"], 2),
            formato_numero(equipo["Utilización"], 2),
            Paragraph(escape(estado_eq), _CELL_WRAP),
        ])

    metricas["registrados"] = int((resumen["Estado del equipo"] != "Sin marcación").sum()) if not resumen.empty else 0
    return filas, metricas


def imagen_o_placeholder_pdf(ruta, width=5.2 * cm, height=3.4 * cm):
    if ruta and Path(ruta).exists():
        return Image(str(ruta), width=width, height=height)

    dibujo = Drawing(width, height)
    dibujo.add(Rect(0, 0, width, height, strokeColor=colors.HexColor("#CBD5E1"), fillColor=colors.HexColor("#F8FAFC")))
    dibujo.add(String(width / 2 - 1.8 * cm, height / 2, "Imagen no disponible", fontSize=8, fillColor=colors.HexColor("#64748B")))
    return dibujo


def tarjeta_equipo_pdf(equipo, styles):
    estado = str(equipo.get("Estado del equipo") or equipo.get("Estado operacional", "Sin marcación"))
    color_borde = colors.HexColor(borde_estado_operacional(estado))
    color_fondo = colors.HexColor(color_estado_operacional(estado))
    color_texto = colors.HexColor(color_texto_estado_operacional(estado))
    modelo = str(equipo["Modelo equipo"])
    numero = limpiar_entero(equipo["Número equipo"])
    imagen = imagen_o_placeholder_pdf(ruta_imagen_equipo_pdf(modelo, numero))

    titulo = Paragraph(f"<b>{escape(modelo)}</b><br/><font size='8'>Equipo {escape(numero)}</font>", styles["Texto"])
    estado_tag = Table(
        [[Paragraph(f"<b>{escape(estado)}</b>", styles["Texto"])]],
        colWidths=[4.3 * cm],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), color_fondo),
            ("TEXTCOLOR", (0, 0), (-1, -1), color_texto),
            ("BOX", (0, 0), (-1, -1), 0.4, color_borde),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]),
    )

    encabezado = Table(
        [[titulo, estado_tag]],
        colWidths=[6.1 * cm, 4.5 * cm],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]),
    )
    operador = str(equipo.get("operador_nombre") or equipo["Operador"]).strip() or "Sin operador"
    datos = [
        ["Operador", operador],
        ["Estado del equipo", str(equipo.get("Estado del equipo", estado))],
        ["Metros perforados", formato_numero(equipo["Metros perforados"], 2)],
        ["Pozos perforados", formato_numero(equipo["Pozos perforados"], 0)],
        ["Rendimiento m/h", formato_numero(equipo["Rendimiento consolidado m/h"], 2)],
        ["Disponibilidad", formato_numero(equipo["Disponibilidad %"], 2, "%")],
        ["Utilización", formato_numero(equipo["Utilización"], 2, "%")],
        ["Horas efectivas", formato_numero(equipo["Horas efectivas perforando"], 2)],
        ["Horas avería", formato_numero(equipo["Horas avería equipo"], 2)],
        ["Horas no efectivas", formato_numero(equipo["Horas no efectivas"], 2)],
    ]
    tabla_metricas = Table(
        [[Paragraph(f"<b>{escape(str(k))}</b>", styles["Texto"]), Paragraph(escape(str(v)), styles["Texto"])] for k, v in datos],
        colWidths=[4.2 * cm, 6.4 * cm],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F8FAFC")),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
            ("FONTSIZE", (0, 0), (-1, -1), 7.2),
            ("LEADING", (0, 0), (-1, -1), 8.5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]),
    )
    tarjeta = Table(
        [[imagen], [encabezado], [tabla_metricas]],
        colWidths=[11.1 * cm],
        style=TableStyle([
            ("BOX", (0, 0), (-1, -1), 1.0, color_borde),
            ("LINEBEFORE", (0, 0), (0, -1), 5, color_borde),
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]),
    )
    return tarjeta


def seccion_kpi_equipos_pdf(df_reporte, story, styles):
    resumen = resumen_operacional_equipos(df_reporte)
    if resumen.empty:
        return

    story.append(PageBreak())
    tarjetas = [tarjeta_equipo_pdf(equipo, styles) for _, equipo in resumen.iterrows()]
    for indice in range(0, len(tarjetas), 2):
        story.append(Paragraph("KPI operacional por equipo", styles["Seccion"]))
        story.append(Spacer(1, 0.12 * cm))
        par = tarjetas[indice:indice + 2]
        if len(par) == 1:
            par.append("")
        story.append(KeepTogether(Table(
            [par],
            colWidths=[12.2 * cm, 12.2 * cm],
            style=TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]),
        )))
        if indice + 2 < len(tarjetas):
            story.append(PageBreak())


def analisis_turno_pdf(fecha_pdf, turno, metricas, principal_detencion):
    causa = principal_detencion[0] if principal_detencion else "sin detenciones relevantes"
    horas_causa = principal_detencion[1] if principal_detencion else 0
    impacto = "El turno presenta continuidad operacional aceptable."
    if metricas["horas_averia"] > 0:
        impacto = "La avería mecánica impactó la disponibilidad operacional."
    elif metricas["horas_no_efectivas"] > metricas["horas_efectivas"] * 0.35:
        impacto = "El tiempo no efectivo representa una restricción relevante para la utilización."
    elif metricas.get("standby_sin_tajo_patio", 0) > 0:
        impacto = "Existen equipos operativos disponibles en standby por falta de tajo/patio."

    return (
        f"Turno {turno} del {fecha_pdf.strftime('%d-%m-%Y')}: producción total "
        f"{formato_numero(metricas['metros'], 2)} m, rendimiento consolidado "
        f"{formato_numero(metricas['rendimiento'], 2)} m/h. La principal causa de detención fue "
        f"{causa} ({formato_numero(horas_causa, 2)} h). Se registran {metricas['con_marcacion']} equipos "
        f"con marcación y {metricas.get('standby_sin_tajo_patio', 0)} equipos en standby por falta de tajo/patio. "
        f"{impacto}"
    )


def _resolver_periodo_pdf(fecha_turno):
    if isinstance(fecha_turno, (tuple, list)):
        valores = [pd.to_datetime(valor).date() for valor in fecha_turno if valor is not None]
        if len(valores) >= 2:
            return min(valores[0], valores[-1]), max(valores[0], valores[-1])
        if len(valores) == 1:
            return valores[0], valores[0]
    fecha = pd.to_datetime(fecha_turno).date()
    return fecha, fecha


def _fuente_datos_pdf(df_reporte, fuente_datos=None):
    if fuente_datos:
        return str(fuente_datos)
    if "Fuente de datos" in df_reporte.columns:
        valores = [
            str(valor).strip()
            for valor in df_reporte["Fuente de datos"].dropna().astype(str).unique()
            if str(valor).strip()
        ]
        if len(valores) == 1:
            return valores[0]
        if len(valores) > 1:
            return "Fuentes consolidadas"
    return "Fuente activa"


def _operador_col_pdf(df):
    for columna in ("operador_display", "operador_nombre"):
        if columna in df.columns:
            valores = df[columna].fillna("").astype(str).str.strip()
            if valores.ne("").any():
                return columna
    return "Operador"


def _equipo_col_pdf(df):
    if "Equipo" in df.columns:
        return "Equipo"
    if "Número equipo" in df.columns:
        return "Número equipo"
    return None


def _turno_visible_pdf(valor):
    texto = str(valor).strip()
    upper = normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").upper()
    if upper in {"1", "DIA"}:
        return "Día"
    if upper in {"2", "NOCHE"}:
        return "Noche"
    return texto


def _base_productiva_pdf(df_reporte):
    if "Fuente de datos" in df_reporte.columns:
        fuente = df_reporte["Fuente de datos"].astype(str)
        if fuente.str.contains("Ciclos|Registro de Perforación|Excel", case=False, na=False).any():
            return df_reporte.copy()
    return registros_productivos(df_reporte)


def _resumen_turno_pdf(df_reporte):
    columnas = ["Turno", "Metros", "Registros", "Horas efectivas", "Disponibilidad", "Utilización", "Rendimiento"]
    if df_reporte.empty or "Turno" not in df_reporte.columns:
        return [columnas]
    filas = [columnas]
    base = df_reporte.copy()
    base["_turno_pdf"] = base["Turno"].map(_turno_visible_pdf)
    for turno, grupo in base.groupby("_turno_pdf", dropna=False):
        metros = serie_numerica(grupo, "Metros perforados").sum()
        horas = serie_numerica(grupo, "Horas efectivas perforando").sum()
        kpis = calcular_kpis_consolidados_dataframe(grupo)
        rendimiento = metros / horas if horas > 0 else 0
        filas.append([
            turno,
            formato_numero(metros, 2),
            f"{len(grupo):,}",
            formato_numero(horas, 2),
            formato_numero(kpis["disponibilidad"], 2, "%"),
            formato_numero(kpis["utilizacion"], 2, "%"),
            formato_numero(rendimiento, 2),
        ])
    return filas


def _resumen_dia_pdf(df_reporte):
    columnas = ["Fecha", "Turno", "Metros", "Registros", "Equipos", "Operadores"]
    if df_reporte.empty or "Fecha turno" not in df_reporte.columns:
        return [columnas]
    filas = [columnas]
    base = df_reporte.copy()
    base["_fecha_pdf"] = pd.to_datetime(base["Fecha turno"], errors="coerce").dt.date
    base["_turno_pdf"] = base.get("Turno", pd.Series("", index=base.index)).map(_turno_visible_pdf)
    equipo_col = _equipo_col_pdf(base)
    operador_col = _operador_col_pdf(base)
    for (fecha, turno), grupo in base.dropna(subset=["_fecha_pdf"]).groupby(["_fecha_pdf", "_turno_pdf"], dropna=False):
        equipos = grupo[equipo_col].dropna().astype(str).str.strip().nunique() if equipo_col else 0
        operadores = grupo[operador_col].dropna().astype(str).str.strip().nunique() if operador_col in grupo.columns else 0
        filas.append([
            pd.to_datetime(fecha).strftime("%d-%m-%Y"),
            turno,
            formato_numero(serie_numerica(grupo, "Metros perforados").sum(), 2),
            f"{len(grupo):,}",
            f"{equipos:,}",
            f"{operadores:,}",
        ])
    return filas


def _ranking_equipos_pdf(df_reporte):
    columnas = ["Equipo", "Metros", "Registros", "Rendimiento", "Disponibilidad", "Utilización"]
    equipo_col = _equipo_col_pdf(df_reporte)
    if df_reporte.empty or not equipo_col:
        return [columnas]
    filas = [columnas]
    base = df_reporte.copy()
    for equipo, grupo in base.groupby(equipo_col, dropna=False):
        metros = serie_numerica(grupo, "Metros perforados").sum()
        horas = serie_numerica(grupo, "Horas efectivas perforando").sum()
        kpis = calcular_kpis_consolidados_dataframe(grupo)
        rendimiento = metros / horas if horas > 0 else 0
        filas.append([
            str(equipo),
            formato_numero(metros, 2),
            f"{len(grupo):,}",
            formato_numero(rendimiento, 2),
            formato_numero(kpis["disponibilidad"], 2, "%"),
            formato_numero(kpis["utilizacion"], 2, "%"),
        ])
    return [filas[0], *sorted(filas[1:], key=lambda fila: numero_pdf(str(fila[1]).replace(",", "")), reverse=True)[:15]]


def _ranking_operadores_pdf(df_reporte):
    columnas = ["Operador", "Metros", "Registros", "Rendimiento"]
    operador_col = _operador_col_pdf(df_reporte)
    if df_reporte.empty or operador_col not in df_reporte.columns:
        return [columnas]
    filas = [columnas]
    base = df_reporte.copy()
    for operador, grupo in base.groupby(operador_col, dropna=False):
        metros = serie_numerica(grupo, "Metros perforados").sum()
        horas = serie_numerica(grupo, "Horas efectivas perforando").sum()
        rendimiento = metros / horas if horas > 0 else 0
        filas.append([
            str(operador),
            formato_numero(metros, 2),
            f"{len(grupo):,}",
            formato_numero(rendimiento, 2),
        ])
    return [filas[0], *sorted(filas[1:], key=lambda fila: numero_pdf(str(fila[1]).replace(",", "")), reverse=True)[:15]]


def _split_csv(valor) -> list:
    texto = str(valor or "").strip()
    if not texto or texto.lower() in ("nan", "none", "nat"):
        return [""]
    partes = [v.strip() for v in texto.split(",") if v.strip()]
    return partes or [""]


def _seccion_ubicacion_pdf(df_reporte, story, styles):
    campos_loc = ["Banco", "Fase", "Malla"]
    campos_presentes = [c for c in campos_loc if c in df_reporte.columns]
    if not campos_presentes:
        return

    def _es_vacio(val):
        return str(val or "").strip().lower() in ("", "nan", "none", "nat")

    mask = df_reporte.apply(
        lambda row: not all(_es_vacio(row.get(c, "")) for c in campos_presentes),
        axis=1,
    )
    df_ub = df_reporte[mask]
    if df_ub.empty:
        return

    # Expandir mallas múltiples en filas individuales (solo para display, sin duplicar KPIs)
    filas = [["Fecha", "Equipo", "Turno", "Banco", "Fase", "Malla"]]
    for _, row in df_ub.iterrows():
        fecha = texto_pdf(row.get("Fecha turno", ""))
        equipo = texto_pdf(row.get("Número equipo", ""))
        turno = _turno_visible_pdf(row.get("Turno", ""))
        bancos = _split_csv(row.get("Banco", ""))
        fases = _split_csv(row.get("Fase", ""))
        mallas = _split_csv(row.get("Malla", ""))
        combinaciones = {(b, f, m) for b in bancos for f in fases for m in mallas}
        for banco, fase, malla in sorted(combinaciones):
            filas.append([fecha, equipo, turno, banco, fase, malla])

    story.append(Paragraph("Ubicación Operacional", styles["SeccionNaranja"]))
    story.append(tabla_datos_pdf(
        filas,
        [4.0 * cm, 2.5 * cm, 2.0 * cm, 3.0 * cm, 2.5 * cm, 3.0 * cm],
        7.0,
    ))
    story.append(Spacer(1, 0.18 * cm))


def _seccion_observaciones_pdf(df_reporte, story, styles):
    campos_obs = [
        ("Condición del terreno", "Condición del terreno"),
        ("Observaciones", "Observaciones"),
        ("Observación estado equipo", "Observación estado equipo"),
    ]

    filas = [["Fecha", "Equipo", "Turno", "Campo", "Observación"]]
    for _, row in df_reporte.iterrows():
        fecha = texto_pdf(row.get("Fecha turno", ""))
        equipo = texto_pdf(row.get("Número equipo", ""))
        turno = _turno_visible_pdf(row.get("Turno", ""))
        for col, label in campos_obs:
            if col not in df_reporte.columns:
                continue
            val = str(row.get(col, "") or "").strip()
            if val and val.lower() not in ("nan", "none", "nat"):
                filas.append([
                    fecha,
                    equipo,
                    turno,
                    label,
                    Paragraph(escape(val), _OBS_WRAP),
                ])

    if len(filas) <= 1:
        return

    story.append(Paragraph("Observaciones de Terreno", styles["SeccionNaranja"]))
    story.append(tabla_datos_pdf(
        filas,
        [3.5 * cm, 2.0 * cm, 2.0 * cm, 4.5 * cm, 11.5 * cm],
        7.0,
    ))
    story.append(Spacer(1, 0.18 * cm))


def generar_pdf(df_reporte, fecha_turno, turno, df_historico=None, fuente_datos=None, turno_archivo=None):
    REPORTES_PDF_DIR.mkdir(exist_ok=True)
    df_reporte = agregar_columnas_operador_visual(df_reporte)
    fecha_inicio_pdf, fecha_fin_pdf = _resolver_periodo_pdf(fecha_turno)
    fecha_pdf = fecha_inicio_pdf
    fecha_archivo_inicio = fecha_inicio_pdf.strftime("%Y-%m-%d")
    fecha_archivo_fin = fecha_fin_pdf.strftime("%Y-%m-%d")
    turno_archivo = nombre_archivo_seguro(turno_archivo or turno)
    ruta_pdf = REPORTES_PDF_DIR / f"Reporte_Perforacion_{fecha_archivo_inicio}_a_{fecha_archivo_fin}_{turno_archivo}.pdf"

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
    fuente_pdf = _fuente_datos_pdf(df_reporte, fuente_datos)
    proyecto = "Proyecto DES"
    if "Área operacional" in df_reporte.columns:
        valores_proyecto = [valor for valor in df_reporte["Área operacional"].dropna().astype(str).unique() if valor.strip()]
        if valores_proyecto:
            proyecto = valores_proyecto[0]

    total_metros, total_horas, rendimiento = totales_productivos(df_reporte)
    filas_equipos, metricas_equipos = filas_equipos_pdf(df_reporte)
    resumen_equipos_pdf = resumen_operacional_equipos(df_reporte)
    equipos = len(equipos_esperados_pdf())
    kpis_consolidados = calcular_kpis_consolidados_dataframe(df_reporte)
    disponibilidad = kpis_consolidados["disponibilidad"]
    utilizacion = kpis_consolidados["utilizacion"]
    total_metros = kpis_consolidados["metros"]
    total_horas = kpis_consolidados["horas_efectivas"]
    rendimiento = kpis_consolidados["rendimiento"]
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
        "standby_sin_tajo_patio": metricas_equipos["standby_sin_tajo_patio"],
    }

    def pie_pagina(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(1.2 * cm, 0.55 * cm, f"Sistema de Gestión Operacional de Perforación | {proyecto}")
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
        ["Fuente de datos", fuente_pdf, "Turnos incluidos", str(turno)],
        ["Fecha inicio", fecha_inicio_pdf.strftime("%d-%m-%Y"), "Fecha fin", fecha_fin_pdf.strftime("%d-%m-%Y")],
        ["Proyecto", proyecto, "Registros", f"{len(df_reporte):,}"],
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
        ("REGISTROS", f"{len(df_reporte):,}", "Filas consolidadas", colors.HexColor("#334155")),
        ("POZOS/CICLOS", formato_numero(pozos, 0), "Según fuente", colors.HexColor("#7C3AED")),
        ("RENDIMIENTO", f"{formato_numero(rendimiento, 2)} m/h", "Consolidado", colors.HexColor("#0F766E")),
        ("DISPONIBILIDAD", formato_numero(metricas["disponibilidad"], 2, "%"), "Promedio", color_estado(metricas["disponibilidad"])),
        ("UTILIZACIÓN", formato_numero(metricas["utilizacion"], 2, "%"), "Promedio", color_estado(metricas["utilizacion"])),
        ("H. EFECTIVAS", formato_numero(total_horas, 2), "Trabajo productivo", colors.HexColor("#15803D")),
        ("H. NO EFECTIVAS", formato_numero(horas_no_efectivas, 2), "Consolidado", colors.HexColor("#B45309")),
        ("H. AVERÍA", formato_numero(horas_averia, 2), "Mecánica", colors.HexColor("#B91C1C")),
        ("H. MP", formato_numero(serie_numerica(df_reporte, "Horas MP", "Mantención Programada").sum(), 2), "Mantención", colors.HexColor("#1E40AF")),
    ]
    story.append(tarjetas_kpi_pdf(kpis))
    story.append(Spacer(1, 0.18 * cm))

    detenciones = datos_detenciones(df_reporte)
    principal_detencion = detenciones[0] if detenciones else None
    story.append(Paragraph("Análisis breve del periodo", styles["Seccion"]))
    story.append(Paragraph(
        f"Periodo {fecha_inicio_pdf.strftime('%d-%m-%Y')} a {fecha_fin_pdf.strftime('%d-%m-%Y')}, "
        f"turnos {turno}: producción total {formato_numero(metricas['metros'], 2)} m, "
        f"rendimiento consolidado {formato_numero(metricas['rendimiento'], 2)} m/h. "
        f"Se consolidan {len(df_reporte):,} registros de la fuente {fuente_pdf}.",
        styles["Texto"],
    ))
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
        ["Horas MP", formato_numero(serie_numerica(df_reporte, "Horas MP", "Mantención Programada").sum(), 2)],
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

    story.append(Paragraph("Resumen por turno", styles["Seccion"]))
    story.append(tabla_datos_pdf(
        _resumen_turno_pdf(df_reporte),
        [3.0 * cm, 3.0 * cm, 2.0 * cm, 3.0 * cm, 3.0 * cm, 3.0 * cm, 2.7 * cm],
        7.3,
    ))
    story.append(Spacer(1, 0.16 * cm))

    story.append(Paragraph("Resumen por día", styles["Seccion"]))
    story.append(tabla_datos_pdf(
        _resumen_dia_pdf(df_reporte),
        [2.8 * cm, 2.5 * cm, 3.0 * cm, 2.0 * cm, 2.0 * cm, 2.2 * cm],
        7.0,
    ))
    story.append(Spacer(1, 0.16 * cm))

    story.append(Paragraph("Ranking por equipo", styles["Seccion"]))
    story.append(tabla_datos_pdf(
        _ranking_equipos_pdf(df_reporte),
        [5.0 * cm, 3.0 * cm, 2.0 * cm, 2.5 * cm, 2.7 * cm, 2.7 * cm],
        6.8,
    ))
    story.append(Spacer(1, 0.16 * cm))

    story.append(Paragraph("Ranking por operador", styles["Seccion"]))
    story.append(tabla_datos_pdf(
        _ranking_operadores_pdf(df_reporte),
        [9.0 * cm, 3.2 * cm, 2.2 * cm, 2.8 * cm],
        6.8,
    ))
    story.append(Spacer(1, 0.18 * cm))

    story.append(Paragraph("Detalle compacto por equipo", styles["Seccion"]))
    tabla_equipos = tabla_datos_pdf(
        filas_equipos,
        [2.0 * cm, 0.8 * cm, 2.1 * cm, 1.8 * cm, 2.2 * cm, 1.2 * cm, 0.9 * cm, 1.2 * cm, 1.2 * cm, 1.3 * cm, 1.1 * cm, 1.1 * cm, 1.1 * cm, 3.6 * cm],
        font_size=5.5,
    )
    _COLOR_ESTADO_PDF = {
        # Valores oficiales
        "Equipo Operativo con marcación":              colors.HexColor("#2ECC71"),
        "Equipo Operativo, sin marcación":             colors.HexColor("#BDC3C7"),
        "Equipo Operativo, sin patio de perforación":  colors.HexColor("#F39C12"),
        "Equipo en Mantención Programada":             colors.HexColor("#3498DB"),
        "Equipo en Avería":                            colors.HexColor("#E74C3C"),
        # Legacy
        "Sin marcación":                               colors.HexColor("#BDC3C7"),
        "Con marcación":                               colors.HexColor("#2ECC71"),
        "Con marcación (parcial)":                     colors.HexColor("#F39C12"),
        "Fuera de servicio por avería":                colors.HexColor("#E74C3C"),
        "En mantención programada":                    colors.HexColor("#3498DB"),
        "Standby por falta de tajo/Patio":             colors.HexColor("#F39C12"),
    }
    for fila_idx, estado in enumerate(metricas_equipos.get("estados_raw", []), start=1):
        color = _COLOR_ESTADO_PDF.get(estado, colors.white)
        tabla_equipos.setStyle(TableStyle([("BACKGROUND", (13, fila_idx), (13, fila_idx), color)]))
    story.append(tabla_equipos)
    story.append(PageBreak())

    _seccion_ubicacion_pdf(df_reporte, story, styles)
    _seccion_observaciones_pdf(df_reporte, story, styles)

    story.append(Paragraph("Gráficos operacionales resumidos", styles["Seccion"]))
    story.append(grafico_barras_pdf(detenciones, "Pareto de detenciones por horas", height=4.7 * cm, color="#B45309"))
    story.append(Spacer(1, 0.16 * cm))

    operador_col = "Operador"
    if "operador_nombre" in df_reporte.columns:
        nombres_operador = df_reporte["operador_nombre"].fillna("").astype(str).str.strip()
        if nombres_operador.ne("").any():
            operador_col = "operador_nombre"
    base_ranking_pdf = _base_productiva_pdf(df_reporte)
    ranking_operadores = kpi_service.calcular_rendimiento_consolidado(base_ranking_pdf, [operador_col]).sort_values("Rendimiento m/h", ascending=False)
    if operador_col != "Operador":
        ranking_operadores = ranking_operadores.rename(columns={operador_col: "Operador"})
    datos_operadores = list(zip(ranking_operadores.get("Operador", []), ranking_operadores.get("Rendimiento m/h", [])))
    story.append(grafico_barras_pdf(datos_operadores, "Ranking operadores por rendimiento m/h", height=4.7 * cm, color="#2563EB"))
    story.append(Spacer(1, 0.16 * cm))

    seccion_kpi_equipos_pdf(df_reporte, story, styles)

    doc.build(story, onFirstPage=pie_pagina, onLaterPages=pie_pagina)
    audit_log.registrar_generacion_pdf(
        turno=turno,
        resultado="ok",
        detalle={"archivo": ruta_pdf.name, "ruta": str(ruta_pdf)},
    )
    return ruta_pdf
