from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, Spacer, Table, TableStyle

from audit import audit_log
from alerts import evaluar_alertas_operacionales
from data import anexar_registro, crear_registro, leer_reportes, limpiar_cache_reportes, preparar_dataframe, reparar_texto
from pdf_report import generar_pdf as generar_pdf_report
from dashboard import dashboard as dashboard_view
from services import kpi_service
from schema import columnas_equivalentes
from utils import (
    CODIGOS_OPERADOR,
    EQUIPOS,
    EXCEL_PATH,
    HORAS_TURNO,
    OPERADORES,
    TIPOS_DETENCION,
    limpiar_entero,
    opciones_desde_historial,
    ruta_imagen_equipo,
    unir_valores,
)
from validation import report_validation

REPORTES_PDF_DIR = Path(EXCEL_PATH).parent / "reportes_pdf"
VERSION_PATH = Path(EXCEL_PATH).parent / "VERSION.txt"

DETENCION_HORAS_COLUMNAS = {
    "Falla Operacional": "Falla Operacional",
    "Avería mecánica": "Horas detención mecánica",
    "Cambio de aceros": "Cambio de aceros",
    "Geología": "Geología",
    "Seguridad": "Seguridad",
    "Colación": "Colación",
    "Relleno de agua": "Relleno de agua",
    "Combustible": "Combustible",
    "Traslado": "Traslado",
    "Cambio Turno": "Cambio turno",
    "Standby por falta de tajo/Patio": "Standby por falta de tajo/Patio",
    "Mantención Programada": "Mantención Programada",
    "Tronadura": "Tronadura",
    "Falta operador": "Falta operador",
    "Otros": "Otros",
}

COLUMNAS_HORAS_DETENCION = list(dict.fromkeys(DETENCION_HORAS_COLUMNAS.values()))

REEMPLAZOS_TEXTO_VISIBLE = {
    "Perforación": "Perforación",
    "Aplicación": "Aplicación",
    "Versión": "Versión",
    "Número": "Número",
    "número": "número",
    "Código": "Código",
    "C?digo": "Código",
    "Día": "Día",
    "DĂ­a": "Día",
    "Área": "Área",
    "Ubicación": "Ubicación",
    "Producción": "Producción",
    "Petróleo": "Petróleo",
    "Horómetro": "Horómetro",
    "detención": "detención",
    "Detención": "Detención",
    "Condición": "Condición",
    "condición": "condición",
    "perforación": "perforación",
    "avería": "avería",
    "Avería": "Avería",
    "Colación": "Colación",
    "Mantención": "Mantención",
    "mantención": "mantención",
    "Utilización": "Utilización",
    "utilización": "utilización",
    "operación": "operación",
    "Operación": "Operación",
    "Aquí": "Aquí",
    "modificación": "modificación",
    "Tamaño": "Tamaño",
    "válidas": "válidas",
    "están": "están",
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


def clave_detencion(valor):
    texto = texto_visible(valor).strip().lower()
    reemplazos = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ñ": "n",
    }
    for origen, destino in reemplazos.items():
        texto = texto.replace(origen, destino)
    return " ".join(texto.split())


def detenciones_seleccionadas_por_hora(tipo_detencion):
    asociaciones = {
        "horas_averia": ("averia", "averia mecanica"),
        "horas_combustible": ("combustible",),
        "horas_agua": ("agua", "relleno de agua", "abastecimiento agua"),
        "horas_colacion": ("colacion",),
        "horas_traslado": ("traslado",),
        "horas_standby": ("standby por falta de tajo/patio",),
        "horas_tronadura": ("tronadura",),
        "horas_mantencion": ("mantencion", "mantencion programada"),
        "horas_cambio_turno": ("cambio turno", "cambio de turno"),
        "horas_falta_operador": ("falta operador",),
        "horas_otros": ("otros",),
    }
    seleccionadas = {clave_detencion(detencion) for detencion in tipo_detencion}
    return {
        clave
        for clave, opciones in asociaciones.items()
        if any(opcion in seleccionadas for opcion in opciones)
    }


def alerta_horas_detencion_cero(etiqueta):
    st.warning(f"Seleccionaste esta detención, pero sus horas están en 0. ({etiqueta})")


def version_sistema():
    if VERSION_PATH.exists():
        return VERSION_PATH.read_text(encoding="utf-8").splitlines()[0].strip()
    return "v1.0.5 - Dashboard KPI Profesional"


def contar_pdfs_generados():
    if not REPORTES_PDF_DIR.exists():
        return 0
    return sum(1 for _ in REPORTES_PDF_DIR.glob("*.pdf"))


def ultima_fecha_registrada(df):
    columna_fecha = next((col for col in columnas_equivalentes("fecha_turno") if col in df.columns), None)
    if not columna_fecha:
        return None

    fechas = pd.to_datetime(df[columna_fecha], errors="coerce")
    fechas_validas = fechas.dropna()
    if fechas_validas.empty:
        return None
    return fechas_validas.max()


def contar_alertas_actuales(df):
    try:
        resultado = evaluar_alertas_operacionales(df)
        detalle = resultado.get("detalle", pd.DataFrame())
        if isinstance(detalle, pd.DataFrame):
            return len(detalle)
    except Exception:
        pass
    return None


def render_inicio(df_reportes):
    total_registros = len(df_reportes)
    ultima_fecha = ultima_fecha_registrada(df_reportes)
    total_pdfs = contar_pdfs_generados()
    total_alertas = contar_alertas_actuales(df_reportes)

    st.subheader("Inicio")
    st.write(
        "Sistema operacional para registrar, analizar y auditar reportes de perforación con "
        "historial centralizado, alertas operacionales y generación de PDF."
    )
    st.caption(f"Excel activo: {EXCEL_PATH.resolve()}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Registros", f"{total_registros:,}")
    col2.metric(
        "Última fecha",
        ultima_fecha.strftime("%d-%m-%Y") if ultima_fecha is not None else "Sin datos",
    )
    col3.metric("PDFs generados", f"{total_pdfs:,}")
    col4.metric(
        "Alertas actuales",
        f"{total_alertas:,}" if total_alertas is not None else "No disponible",
    )

    st.markdown(
        """
        <style>
        .home-card {
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            padding: 0.9rem 0.95rem;
            background: #ffffff;
            min-height: 130px;
        }
        .home-card h4 {
            margin: 0 0 0.35rem 0;
            font-size: 1.0rem;
        }
        .home-card p {
            margin: 0 0 0.65rem 0;
            color: #4b5563;
            font-size: 0.92rem;
            line-height: 1.35;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Accesos rápidos")
    cards = st.columns(5)
    accesos = [
        ("Dashboard Operacional", "KPIs, alertas y seguimiento operativo.", "pages/01_Dashboard_Operacional.py"),
        ("Formulario Registro", "Ingreso de reportes diarios y control de turno.", "pages/02_Formulario_Registro.py"),
        ("Reportes PDF", "Generación y consulta de reportes documentales.", "pages/03_Reportes_PDF.py"),
        ("Historial Auditoría", "Consulta de historial operacional y trazabilidad.", "pages/04_Historial_Auditoria.py"),
        ("Alertas Operacionales", "Vista consolidada de alertas y recomendaciones.", "pages/05_Alertas_Operacionales.py"),
    ]

    for columna, (titulo, descripcion, pagina) in zip(cards, accesos):
        with columna:
            st.markdown(
                f"""
                <div class="home-card">
                    <h4>{titulo}</h4>
                    <p>{descripcion}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if hasattr(st, "page_link"):
                st.page_link(pagina, label=f"Ir a {titulo}", width="stretch")
            elif st.button(f"Ir a {titulo}", key=f"nav_{Path(pagina).stem}", width="stretch"):
                st.switch_page(pagina)

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
        filtro_turnos = st.multiselect("Turno", turnos, default=turnos, format_func=texto_visible)
        filtro_tipos_detencion = st.multiselect(
            "Tipo detención",
            tipos_detencion,
            default=tipos_detencion,
            format_func=texto_visible,
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
    return report_validation.existe_reporte_duplicado(
        df,
        fecha_turno,
        turno,
        modelo_equipo,
        numero_equipo,
        operador,
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
        st.success("Reportes completos: los 6 equipos están registrados para esta fecha y turno.")


def normalizar_nombre_columna(nombre):
    return kpi_service.normalizar_nombre_columna(nombre)


def buscar_columna(df, *candidatos):
    return kpi_service.buscar_columna(df, *candidatos)


def serie_numerica(df, *columnas):
    return kpi_service.serie_numerica(df, *columnas)


def totales_productivos(df):
    return kpi_service.totales_productivos(df)


def columnas_horas_turno():
    return ["Horas efectivas perforando", *COLUMNAS_HORAS_DETENCION]


def etiqueta_hora(columna):
    etiquetas = {
        "Horas detención mecánica": "Avería mecánica",
        "Relleno de agua": "Relleno de agua",
        "Cambio turno": "Cambio Turno",
    }
    return texto_visible(etiquetas.get(columna, columna))


def numero_pdf(valor):
    return pd.to_numeric(pd.Series([valor]), errors="coerce").fillna(0).iloc[0]


def formato_numero(valor, decimales=2, sufijo=""):
    numero = numero_pdf(valor)
    return f"{numero:,.{decimales}f}{sufijo}"


def mostrar_alertas_operacionales(df):
    st.subheader("Alertas operacionales")
    if df.empty:
        st.info("No hay registros para evaluar alertas operacionales.")
        return

    resultado = evaluar_alertas_operacionales(df, horas_turno=HORAS_TURNO)
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

    detalle = resultado["detalle"]
    if not detalle.empty:
        st.markdown("**Detalle de alertas**")
        detalle_filtrado = filtrar_detalle_alertas(detalle)
        mostrar_resumen_alertas(detalle_filtrado)
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


def color_estado(valor, bueno=80, medio=60):
    valor = numero_pdf(valor)
    if valor >= bueno:
        return colors.HexColor("#15803D")
    if valor >= medio:
        return colors.HexColor("#B45309")
    return colors.HexColor("#B91C1C")


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


def estado_operacional_equipo(metros, pozos, horas_efectivas, horas_no_efectivas, horas_averia, horas_mantencion):
    return kpi_service.estado_operacional_equipo(
        metros,
        pozos,
        horas_efectivas,
        horas_no_efectivas,
        horas_averia,
        horas_mantencion,
    )


def color_estado_operacional(estado):
    return {
        "Operativo": "#DCFCE7",
        "Operativo parcial": "#FEF3C7",
        "Avería": "#FEE2E2",
        "Mantención Programada": "#DBEAFE",
        "Sin marcación": "#F3F4F6",
    }.get(estado, "#FFFFFF")


def color_texto_estado_operacional(estado):
    return {
        "Operativo": "#166534",
        "Operativo parcial": "#92400E",
        "Avería": "#991B1B",
        "Mantención Programada": "#1E40AF",
        "Sin marcación": "#4B5563",
    }.get(estado, "#0F172A")


def borde_estado_operacional(estado):
    return {
        "Operativo": "#16A34A",
        "Operativo parcial": "#F59E0B",
        "Avería": "#DC2626",
        "Mantención Programada": "#2563EB",
        "Sin marcación": "#94A3B8",
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
    base_dir = Path(EXCEL_PATH).parent
    carpetas = [base_dir, base_dir / "assets", base_dir / "assets" / "equipos"]
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


def filas_equipos_pdf(df_reporte):
    columnas = [
        "Modelo",
        "N°",
        "Operador",
        "Estado",
        "Metros",
        "Pozos",
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
        "fuera_servicio": 0,
    }

    resumen = resumen_operacional_equipos(df_reporte)
    for _, equipo in resumen.iterrows():
        if equipo["Marcación"] == "Con marcación":
            metricas["con_marcacion"] += 1
        elif str(equipo["Marcación"]).startswith("Fuera de servicio"):
            metricas["fuera_servicio"] += 1
        else:
            metricas["sin_marcacion"] += 1

        filas.append([
            equipo["Modelo equipo"],
            equipo["Número equipo"],
            equipo["Operador"],
            equipo["Estado operacional"],
            formato_numero(equipo["Metros perforados"], 2),
            formato_numero(equipo["Pozos perforados"], 0),
            formato_numero(equipo["Rendimiento consolidado m/h"], 2),
            formato_numero(equipo["Horas efectivas perforando"], 2),
            formato_numero(equipo["Horas no efectivas"], 2),
            formato_numero(equipo["Horas avería equipo"], 2),
            formato_numero(equipo["Disponibilidad %"], 2),
            formato_numero(equipo["Utilización %"], 2),
            equipo["Marcación"],
        ])

    metricas["registrados"] = int((resumen["Marcación"] != "Sin marcación").sum()) if not resumen.empty else 0
    return filas, metricas


def imagen_o_placeholder_pdf(ruta, width=5.2 * cm, height=3.4 * cm):
    if ruta and Path(ruta).exists():
        return Image(str(ruta), width=width, height=height)

    dibujo = Drawing(width, height)
    dibujo.add(Rect(0, 0, width, height, strokeColor=colors.HexColor("#CBD5E1"), fillColor=colors.HexColor("#F8FAFC")))
    dibujo.add(String(width / 2 - 1.8 * cm, height / 2, "Imagen no disponible", fontSize=8, fillColor=colors.HexColor("#64748B")))
    return dibujo


def tarjeta_equipo_pdf(equipo, styles):
    estado = str(equipo["Estado operacional"])
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
    operador = str(equipo["Operador"]).strip() or "Sin operador"
    datos = [
        ["Operador", operador],
        ["Marcación", str(equipo["Marcación"])],
        ["Metros perforados", formato_numero(equipo["Metros perforados"], 2)],
        ["Pozos perforados", formato_numero(equipo["Pozos perforados"], 0)],
        ["Rendimiento m/h", formato_numero(equipo["Rendimiento consolidado m/h"], 2)],
        ["Disponibilidad", formato_numero(equipo["Disponibilidad %"], 2, "%")],
        ["Utilización", formato_numero(equipo["Utilización %"], 2, "%")],
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


def seccion_reporte_pdf(df):
    st.subheader("Reporte PDF por fecha y turno")

    limpiar_cache_reportes()
    df_actualizado = leer_reportes()
    df_fuente = df_actualizado if not df_actualizado.empty else df

    if "Fecha turno" not in df_fuente.columns or "Turno" not in df_fuente.columns:
        st.info("No hay columnas suficientes para generar PDF por fecha y turno.")
        return

    fechas = pd.to_datetime(df_fuente["Fecha turno"], errors="coerce").dt.date.dropna()
    if fechas.empty:
        st.info("No hay fechas válidas para generar PDF.")
        return

    fechas_disponibles = sorted(fechas.unique(), reverse=True)
    col_fecha, col_turno, col_boton = st.columns([1, 1, 1])
    with col_fecha:
        fecha_pdf = st.selectbox("Fecha turno PDF", fechas_disponibles, format_func=lambda fecha: fecha.strftime("%d-%m-%Y"))
    turnos_pdf = sorted(
        dict.fromkeys(
            reparar_texto(turno)
            for turno in df_fuente["Turno"].dropna().astype(str)
            if reparar_texto(turno)
        )
    )
    with col_turno:
        turno_pdf = st.selectbox("Turno PDF", turnos_pdf, format_func=texto_visible)

    fechas_df = pd.to_datetime(df_fuente["Fecha turno"], errors="coerce").dt.date
    turnos_df = df_fuente["Turno"].astype(str).map(reparar_texto).str.strip()
    df_pdf = df_fuente[(fechas_df == fecha_pdf) & (turnos_df == turno_pdf)].copy()

    ultimo_registro = df_fuente.tail(1).copy()
    st.caption(f"Excel oficial para PDF: {EXCEL_PATH}")
    c_info_1, c_info_2, c_info_3 = st.columns(3)
    c_info_1.metric("Registros PDF", len(df_pdf))
    c_info_2.metric("Fecha seleccionada", fecha_pdf.strftime("%d-%m-%Y"))
    c_info_3.metric("Turno seleccionado", texto_visible(turno_pdf))

    if not ultimo_registro.empty:
        columnas_ultimo = [
            columna
            for columna in ["Fecha turno", "Modelo equipo", "Número equipo", "Operador", "Turno", "Metros perforados", "Hora registro"]
            if columna in ultimo_registro.columns
        ]
        st.caption("Último registro cargado desde Excel oficial")
        st.dataframe(dataframe_visible(ultimo_registro[columnas_ultimo]), width="stretch", hide_index=True)

    columnas_preview = [
        columna
        for columna in [
            "Fecha turno",
            "Modelo equipo",
            "Número equipo",
            "Operador",
            "Turno",
            "Metros perforados",
            "Horas efectivas perforando",
            "Disponibilidad %",
            "Utilización %",
            "Rendimiento m/h",
        ]
        if columna in df_pdf.columns
    ]
    if not df_pdf.empty and columnas_preview:
        st.caption("Datos que se usarán para generar el PDF")
        st.dataframe(dataframe_visible(df_pdf[columnas_preview]), width="stretch", hide_index=True)

    with col_boton:
        st.write("")
        st.write("")
        generar = st.button("Generar reporte PDF", type="primary")

    if generar:
        limpiar_cache_reportes()
        df_actualizado = leer_reportes()
        fechas_actualizadas = pd.to_datetime(df_actualizado["Fecha turno"], errors="coerce").dt.date
        turnos_actualizados = df_actualizado["Turno"].astype(str).map(reparar_texto).str.strip()
        df_pdf = df_actualizado[(fechas_actualizadas == fecha_pdf) & (turnos_actualizados == turno_pdf)].copy()

        if df_pdf.empty:
            audit_log.registrar_generacion_pdf(
                turno=turno_pdf,
                resultado="rechazado",
                detalle="No hay registros para la fecha y turno seleccionados.",
            )
            st.warning("No hay registros para la fecha y turno seleccionados.")
            return

        try:
            ruta_pdf = generar_pdf_report(df_pdf, fecha_pdf, turno_pdf, df_actualizado)
        except Exception as exc:
            audit_log.registrar_generacion_pdf(
                turno=turno_pdf,
                resultado="error",
                detalle=str(exc),
            )
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
            st.image(str(imagen), caption=f"{modelo_equipo} {numero_equipo}", width="stretch")

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
        turno = st.selectbox("Turno", ["Día", "Noche"], format_func=texto_visible, key=k("turno"))

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
            format_func=texto_visible,
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
                    "Estable",
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
        TIPOS_DETENCION,
        format_func=texto_visible,
        key=k("tipo_detencion"),
    )
    causa_detencion = st.text_input("Causa detención", key=k("causa_detencion"))
    observaciones = st.text_area("Observaciones", key=k("observaciones"))

    st.subheader("Horas del turno")
    horas_efectivas = st.number_input(
        "Horas efectivas perforando",
        min_value=0.0,
        max_value=12.0,
        step=0.5,
        key=k("horas_efectivas"),
    )

    campos_detencion = [
        ("horas_averia", "Horas avería equipo"),
        ("horas_combustible", "Abastecimiento combustible"),
        ("horas_agua", "Abastecimiento agua"),
        ("horas_colacion", "Colación"),
        ("horas_traslado", "Traslado"),
        ("horas_standby", "Standby por falta de tajo/Patio"),
        ("horas_tronadura", "Tronadura"),
        ("horas_mantencion", "Mantención Programada"),
        ("horas_cambio_turno", "Cambio turno"),
        ("horas_falta_operador", "Falta operador"),
        ("horas_otros", "Otros"),
    ]
    campos_destacados = detenciones_seleccionadas_por_hora(tipo_detencion)
    valores_horas = {}

    def capturar_hora(campo, etiqueta):
        valor = st.number_input(etiqueta, min_value=0.0, max_value=12.0, step=0.5, key=k(campo))
        if campo in campos_destacados and valor == 0:
            alerta_horas_detencion_cero(etiqueta)
        return valor

    if campos_destacados:
        st.markdown("**Horas asociadas a detenciones seleccionadas**")
        columnas_destacadas = st.columns(min(3, max(1, len(campos_destacados))))
        for indice, (campo, etiqueta) in enumerate([item for item in campos_detencion if item[0] in campos_destacados]):
            with columnas_destacadas[indice % len(columnas_destacadas)]:
                valores_horas[campo] = capturar_hora(campo, etiqueta)

        campos_secundarios = [item for item in campos_detencion if item[0] not in campos_destacados]
        with st.expander("Otros campos no seleccionados", expanded=False):
            columnas_secundarias = st.columns(3)
            for indice, (campo, etiqueta) in enumerate(campos_secundarios):
                with columnas_secundarias[indice % len(columnas_secundarias)]:
                    valores_horas[campo] = capturar_hora(campo, etiqueta)
    else:
        col_horas_1, col_horas_2, col_horas_3 = st.columns(3)
        columnas_horas = [col_horas_1, col_horas_1, col_horas_1, col_horas_2, col_horas_2, col_horas_2, col_horas_2, col_horas_3, col_horas_3, col_horas_3, col_horas_3]
        for columna, (campo, etiqueta) in zip(columnas_horas, campos_detencion):
            with columna:
                valores_horas[campo] = capturar_hora(campo, etiqueta)

    horas_averia = valores_horas["horas_averia"]
    horas_combustible = valores_horas["horas_combustible"]
    horas_agua = valores_horas["horas_agua"]
    horas_colacion = valores_horas["horas_colacion"]
    horas_traslado = valores_horas["horas_traslado"]
    horas_standby = valores_horas["horas_standby"]
    horas_tronadura = valores_horas["horas_tronadura"]
    horas_mantencion = valores_horas["horas_mantencion"]
    horas_cambio_turno = valores_horas["horas_cambio_turno"]
    horas_falta_operador = valores_horas["horas_falta_operador"]
    horas_otros = valores_horas["horas_otros"]

    horas_no_efectivas = round(
        horas_combustible
        + horas_agua
        + horas_colacion
        + horas_traslado
        + horas_standby
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

    rendimiento_turno = kpi_service.calcular_rendimiento_consolidado(pd.DataFrame([{
        "Metros perforados": metros,
        "Horas efectivas perforando": horas_efectivas,
    }]))
    utilizacion = kpi_service.calcular_utilizacion(horas_efectivas)
    disponibilidad = kpi_service.calcular_disponibilidad(
        horas_averia,
        horas_mantencion=horas_mantencion,
    )

    st.subheader("KPI del turno")
    k1, k2, k3 = st.columns(3)
    k1.metric("Rendimiento m/h", f"{rendimiento_turno:.2f}")
    k2.metric("Utilización", f"{utilizacion:.2f}%")
    k3.metric("Disponibilidad", f"{disponibilidad:.2f}%")

    if st.button("Guardar reporte", type="primary", key=k("guardar_reporte")):
        if not report_validation.horas_turno_validas(total_horas, HORAS_TURNO):
            mensaje = report_validation.mensaje_horas_turno_invalidas(total_horas, HORAS_TURNO)
            audit_log.registrar_guardado_rechazado(
                usuario=operador,
                equipo=modelo_equipo,
                numero_equipo=numero_equipo,
                turno=turno,
                detalle=mensaje,
            )
            audit_log.registrar_error_validacion(
                usuario=operador,
                equipo=modelo_equipo,
                numero_equipo=numero_equipo,
                turno=turno,
                detalle=mensaje,
            )
            st.error(texto_visible(mensaje))
            return

        if not report_validation.operador_valido(operador):
            mensaje = report_validation.mensaje_operador_vacio()
            audit_log.registrar_guardado_rechazado(
                usuario=operador,
                equipo=modelo_equipo,
                numero_equipo=numero_equipo,
                turno=turno,
                detalle=mensaje,
            )
            audit_log.registrar_error_validacion(
                usuario=operador,
                equipo=modelo_equipo,
                numero_equipo=numero_equipo,
                turno=turno,
                detalle=mensaje,
            )
            st.error(texto_visible(mensaje))
            return

        if existe_reporte_duplicado(df_historial, fecha_turno, turno, modelo_equipo, numero_equipo, operador):
            mensaje = report_validation.mensaje_reporte_duplicado()
            audit_log.registrar_guardado_rechazado(
                usuario=operador,
                equipo=modelo_equipo,
                numero_equipo=numero_equipo,
                turno=turno,
                detalle=mensaje,
            )
            audit_log.registrar_error_validacion(
                usuario=operador,
                equipo=modelo_equipo,
                numero_equipo=numero_equipo,
                turno=turno,
                detalle=mensaje,
            )
            st.error(texto_visible(mensaje))
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
            "Standby por falta de tajo/Patio": horas_standby,
            "Tronadura": horas_tronadura,
            "Mantención Programada": horas_mantencion,
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
            _, ruta_guardado, ruta_respaldo = anexar_registro(registro)
        except PermissionError:
            audit_log.registrar_evento(
                "creacion_reporte",
                usuario=operador,
                equipo=modelo_equipo,
                numero_equipo=numero_equipo,
                turno=turno,
                resultado="error",
                detalle="No se pudo guardar. Cierra el archivo Excel y vuelve a intentar.",
            )
            st.error("No se pudo guardar. Cierra el archivo Excel y vuelve a intentar.")
            return

        audit_log.registrar_creacion_reporte(registro)
        st.session_state["reporte_guardado"] = True
        st.session_state["ultimo_guardado"] = {
            "ruta": str(ruta_guardado),
            "respaldo": str(ruta_respaldo) if ruta_respaldo else "",
            "equipo": f"{modelo_equipo} {limpiar_entero(numero_equipo)}",
            "fecha_turno": fecha_turno.strftime("%d-%m-%Y") if hasattr(fecha_turno, "strftime") else str(fecha_turno),
            "turno": turno,
            "hora_registro": registro.get("Hora registro", pd.Series([""])).iloc[0] if "Hora registro" in registro.columns else "",
        }
        limpiar_formulario()
        st.rerun()


def mostrar_estado_respaldo_sqlite(df_excel):
    with st.expander("Estado respaldo SQLite", expanded=False):
        try:
            import db

            existe_db = db.DB_PATH.exists()
            registros_excel = len(df_excel)
            registros_sqlite = len(db.leer_reportes_sqlite()) if existe_db else 0
            coincide = registros_excel == registros_sqlite

            col_a, col_b, col_c, col_d = st.columns(4)
            col_a.metric("Base SQLite", "Existe" if existe_db else "No existe")
            col_b.metric("Registros Excel", f"{registros_excel:,}")
            col_c.metric("Registros SQLite", f"{registros_sqlite:,}")
            col_d.metric("Estado", "Coincide" if coincide else "No coincide")

            if not coincide:
                st.warning("El respaldo SQLite no coincide con Excel.")

            if st.button("Sincronizar Excel con SQLite"):
                df_actual = preparar_dataframe(pd.read_excel(EXCEL_PATH, engine="openpyxl"))
                registros = db.reemplazar_dataframe_reportes(df_actual)
                audit_log.registrar_respaldo_sqlite(
                    resultado="ok",
                    detalle={"origen": "sincronizacion_manual", "registros": registros},
                )
                st.success(f"Respaldo SQLite sincronizado correctamente: {registros:,} registros.")

            if st.button("Exportar SQLite a Excel respaldo"):
                df_sqlite = db.leer_reportes_sqlite()
                if df_sqlite.empty:
                    st.warning("SQLite no tiene registros para exportar.")
                else:
                    backup_dir = EXCEL_PATH.parent / "backups_sqlite"
                    backup_dir.mkdir(exist_ok=True)
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    export_path = backup_dir / f"respaldo_sqlite_exportado_{timestamp}.xlsx"
                    df_sqlite.to_excel(export_path, index=False)
                    st.success(f"SQLite exportado a {export_path.name}: {len(df_sqlite):,} registros.")

            backup_dir = EXCEL_PATH.parent / "backups_sqlite"
            st.caption("Aquí se guardan los respaldos exportados desde SQLite")
            st.code(str(backup_dir.resolve()), language=None)
            respaldos = sorted(
                backup_dir.glob("*.xlsx") if backup_dir.exists() else [],
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )[:5]
            if respaldos:
                st.dataframe(
                    dataframe_visible(pd.DataFrame(
                        [
                            {
                                "Archivo": path.name,
                                "Fecha modificación": datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                                "Tamaño KB": round(path.stat().st_size / 1024, 2),
                            }
                            for path in respaldos
                        ]
                    )),
                    width="stretch",
                    hide_index=True,
                )
            else:
                st.info("No hay respaldos SQLite exportados.")
        except Exception as exc:
            st.warning(f"No se pudo verificar el respaldo SQLite: {exc}")


def main():
    st.title("Sistema de Reporte de Perforación")
    st.caption(f"Aplicación oficial: {EXCEL_PATH.parent} | Versión actual: {version_sistema()}")

    with st.sidebar:
        st.caption(f"Datos oficiales: {EXCEL_PATH}")
        if st.button("Recargar datos desde Excel"):
            limpiar_cache_reportes()
            st.rerun()

    df_reportes = leer_reportes()
    render_inicio(df_reportes)

    if st.session_state.pop("reporte_guardado", False):
        ultimo = st.session_state.get("ultimo_guardado", {})
        detalle = (
            f"Reporte guardado correctamente en Excel: {ultimo.get('ruta', EXCEL_PATH)}"
            f" | Equipo: {ultimo.get('equipo', '')}"
            f" | Fecha turno: {ultimo.get('fecha_turno', '')}"
            f" | Turno: {texto_visible(ultimo.get('turno', ''))}"
            f" | Hora registro: {ultimo.get('hora_registro', '')}"
        )
        st.success(detalle)
        if ultimo.get("respaldo"):
            st.caption(f"Respaldo previo creado: {ultimo['respaldo']}")

    mostrar_estado_respaldo_sqlite(df_reportes)

    with st.expander("Nuevo reporte operacional", expanded=True):
        formulario_registro(df_reportes)

    dashboard_view(
        df_reportes,
        aplicar_filtros_fn=aplicar_filtros,
        mostrar_alerta_reportes_faltantes_fn=mostrar_alerta_reportes_faltantes,
        mostrar_alertas_operacionales_fn=mostrar_alertas_operacionales,
        seccion_reporte_pdf_fn=seccion_reporte_pdf,
        resumen_operacional_equipos_fn=resumen_operacional_equipos,
        equipos_esperados_fn=equipos_esperados,
        ruta_imagen_equipo_fn=ruta_imagen_equipo,
        limpiar_entero_fn=limpiar_entero,
        color_estado_operacional_fn=color_estado_operacional,
        color_texto_estado_operacional_fn=color_texto_estado_operacional,
        columnas_horas_turno_fn=columnas_horas_turno,
        etiqueta_hora_fn=etiqueta_hora,
    )


if __name__ == "__main__":
    main()
