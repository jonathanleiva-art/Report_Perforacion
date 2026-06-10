import re
from datetime import datetime
from pathlib import Path
from unicodedata import normalize

import pandas as pd

try:
    import fitz
except ImportError:  # pragma: no cover
    fitz = None


TIPOS_SECTOR_ENAEX = ("Producción", "Buffer 1", "Buffer 2", "Borde", "Precorte")


def _texto(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def _sin_acentos(valor):
    return normalize("NFKD", _texto(valor)).encode("ascii", "ignore").decode("ascii")


def _numero(valor):
    texto = _texto(valor).replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", texto)
    if not match:
        return 0.0
    try:
        return max(float(match.group(0)), 0.0)
    except ValueError:
        return 0.0


def _entero(valor):
    return int(round(_numero(valor)))


def extraer_texto_pdf(ruta_pdf):
    ruta = Path(ruta_pdf)
    if not ruta.exists() or ruta.suffix.lower() != ".pdf" or fitz is None:
        return ""
    textos = []
    with fitz.open(str(ruta)) as documento:
        for pagina in documento:
            textos.append(pagina.get_text("text") or "")
    return "\n".join(textos).strip()


def _buscar_patron(texto, patrones):
    for patron in patrones:
        match = re.search(patron, texto, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return _texto(match.group(1))
    return ""


def _normalizar_fecha(valor):
    valor = _texto(valor)
    if not valor:
        return ""
    for formato in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(valor, formato).date().isoformat()
        except ValueError:
            continue
    return valor


def _extraer_metadata_nombre_archivo(nombre_archivo):
    nombre = Path(nombre_archivo or "").stem
    texto = _sin_acentos(nombre).upper()
    fase = _buscar_patron(texto, [r"(?:^|[^A-Z0-9])F(?:ASE)?\s*0*([0-9]{1,3})(?=$|[^A-Z0-9])", r"(?:^|[^A-Z0-9])F0*([0-9]{1,3})(?=$|[^A-Z0-9])"])
    banco = _buscar_patron(texto, [r"(?:^|[^A-Z0-9])B(?:ANCO)?\s*0*([0-9]{3,5})(?=$|[^A-Z0-9])", r"(?:^|[^A-Z0-9])B0*([0-9]{3,5})(?=$|[^A-Z0-9])"])
    malla = _buscar_patron(texto, [r"(?:^|[^A-Z0-9])M(?:ALLA)?\s*0*([0-9A-Z._/-]{1,10})(?=$|[^A-Z0-9])", r"(?:^|[^A-Z0-9])M0*([0-9]{1,5})(?=$|[^A-Z0-9])"])
    return {
        "fase": fase,
        "banco": banco,
        "malla": malla,
        "nombre_plan": nombre,
    }


def _extraer_nombre_plano(texto, nombre_archivo=""):
    nombre = _buscar_patron(
        texto,
        [
            r"(?:nombre\s+plano|plano|nombre\s+del\s+plano)\s*:?\s*([^\n\r]+)",
            r"(?:designaci[oó]n|titulo|t[ií]tulo)\s*:?\s*([^\n\r]+)",
        ],
    )
    if nombre:
        return nombre[:120]
    return Path(nombre_archivo).stem if nombre_archivo else "Plan Enaex"


def _lineas_sector(texto):
    lineas = []
    for linea in texto.splitlines():
        limpia = re.sub(r"\s+", " ", linea).strip()
        if limpia:
            lineas.append(limpia)
    return lineas


def _tipo_sector_desde_linea(linea):
    clave = _sin_acentos(linea).lower()
    if "producci" in clave or re.search(r"\bprod\.?\b", clave):
        return "Producción"
    if re.search(r"\bbuffer\s*1\b|\bbuf\s*1\b", clave):
        return "Buffer 1"
    if re.search(r"\bbuffer\s*2\b|\bbuf\s*2\b", clave):
        return "Buffer 2"
    if re.search(r"\bborde\b", clave):
        return "Borde"
    if re.search(r"\bprecorte\b|\bpre\s*corte\b", clave):
        return "Precorte"
    return ""


def _tipos_sector_desde_linea(linea):
    clave = _sin_acentos(linea).lower()
    tipos = []
    if "producci" in clave or re.search(r"\bprod\.?\b", clave):
        tipos.append("Producción")
    if re.search(r"\bbuffer\s*1\b|\bbuf\s*1\b", clave):
        tipos.append("Buffer 1")
    if re.search(r"\bbuffer\s*2\b|\bbuf\s*2\b", clave):
        tipos.append("Buffer 2")
    if re.search(r"\bborde\b", clave):
        tipos.append("Borde")
    if re.search(r"\bprecorte\b|\bpre\s*corte\b", clave):
        tipos.append("Precorte")
    return tipos


def _valor_en_linea(linea, etiquetas):
    etiqueta_regex = "|".join(re.escape(etiqueta) for etiqueta in etiquetas)
    patron = rf"(?:{etiqueta_regex})\s*:?\s*([0-9]+(?:[.,][0-9]+)?|[0-9]+\s*[0-9/]*)"
    match = re.search(patron, linea, flags=re.IGNORECASE)
    return _texto(match.group(1)) if match else ""


def _extraer_sector_desde_linea(linea, banco="", malla="", tipo_forzado=""):
    tipo = tipo_forzado or _tipo_sector_desde_linea(linea)
    if not tipo:
        return None

    pozos = _valor_en_linea(linea, ["pozos", "cantidad de pozos", "cant pozos", "n pozos", "n° pozos"])
    metros = _valor_en_linea(linea, ["metros", "metros planificados", "m planificados", "mts", "m"])
    pasadura = _valor_en_linea(linea, ["pasadura", "pas"])
    diametro = _valor_en_linea(linea, ["diámetro", "diametro", "diam", "ø"])
    numero_precorte = ""
    if tipo == "Precorte":
        numero_precorte = _buscar_patron(linea, [r"precorte\s*([0-9]{1,3})", r"pre\s*corte\s*([0-9]{1,3})"])

    return {
        "tipo_sector": tipo,
        "identificador_sector": f"{tipo} {malla}".strip() if tipo == "Producción" else f"{tipo} {numero_precorte}".strip(),
        "malla": malla if tipo == "Producción" else "",
        "numero_precorte": numero_precorte,
        "pozos_planificados": _entero(pozos),
        "metros_planificados": _numero(metros),
        "pasadura": _texto(pasadura),
        "diametro": _texto(diametro),
        "banco": banco,
    }


def _linea_tiene_metricas(linea):
    return bool(
        _valor_en_linea(linea, ["pozos", "cantidad de pozos", "cant pozos", "n pozos", "n° pozos"])
        or _valor_en_linea(linea, ["metros", "metros planificados", "m planificados", "mts"])
    )


def _es_linea_metadato(linea):
    clave = _sin_acentos(linea).lower().strip()
    return clave.startswith(("plano", "nombre plano", "nombre del plano", "titulo", "designacion"))


def _completar_sectores_por_presencia(texto, banco="", malla=""):
    sectores = []
    texto_simple = _sin_acentos(texto).lower()
    for tipo in TIPOS_SECTOR_ENAEX:
        clave = _sin_acentos(tipo).lower()
        if re.search(rf"\b{re.escape(clave)}\b", texto_simple):
            sectores.append(
                {
                    "tipo_sector": tipo,
                    "identificador_sector": f"{tipo} {malla}".strip() if tipo == "Producción" else tipo,
                    "malla": malla if tipo == "Producción" else "",
                    "numero_precorte": "",
                    "pozos_planificados": 0,
                    "metros_planificados": 0.0,
                    "pasadura": "",
                    "diametro": "",
                    "banco": banco,
                }
            )
    return sectores


def extraer_datos_enaex_desde_texto(texto, nombre_archivo=""):
    texto = _texto(texto)
    metadata_archivo = _extraer_metadata_nombre_archivo(nombre_archivo)
    fase = _buscar_patron(texto, [r"\bfase\s*:?\s*([A-Za-z0-9._/-]+)", r"\bF(?:ASE)?\s*0*([0-9]{1,3})\b"]) or metadata_archivo["fase"]
    banco = _buscar_patron(texto, [r"\bbanco\s*:?\s*([A-Za-z0-9._/-]+)", r"\bB(?:ANCO)?\s*0*([0-9]{3,5})\b"]) or metadata_archivo["banco"]
    malla = _buscar_patron(texto, [r"\bmalla\s*:?\s*([A-Za-z0-9._/-]+)", r"\bM(?:ALLA)?\s*0*([0-9A-Za-z._/-]+)\b"]) or metadata_archivo["malla"]
    fecha = _normalizar_fecha(
        _buscar_patron(
            texto,
            [
                r"\bfecha\s*:?\s*([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4})",
                r"\bfecha\s*:?\s*([0-9]{4}-[0-9]{1,2}-[0-9]{1,2})",
            ],
        )
    )
    nombre_plano = _extraer_nombre_plano(texto, nombre_archivo=nombre_archivo) or metadata_archivo["nombre_plan"]

    sectores = []
    for linea in _lineas_sector(texto):
        if _es_linea_metadato(linea) and not _linea_tiene_metricas(linea):
            continue
        tipos_linea = _tipos_sector_desde_linea(linea)
        if len(tipos_linea) > 1 and not _linea_tiene_metricas(linea):
            for tipo in tipos_linea:
                sector = _extraer_sector_desde_linea(linea, banco=banco, malla=malla, tipo_forzado=tipo)
                if sector:
                    sectores.append(sector)
            continue
        sector = _extraer_sector_desde_linea(linea, banco=banco, malla=malla)
        if sector:
            sectores.append(sector)

    if not sectores:
        sectores = _completar_sectores_por_presencia(texto, banco=banco, malla=malla)

    deduplicados = []
    vistos = set()
    for sector in sectores:
        clave = (sector["tipo_sector"], sector.get("numero_precorte", ""), sector.get("identificador_sector", ""))
        if clave not in vistos:
            vistos.add(clave)
            deduplicados.append(sector)

    errores = []
    if not texto:
        errores.append("PDF sin texto extraible. Puede ser escaneado o imagen.")
    if not fase:
        errores.append("No se detecto fase.")
    if not banco:
        errores.append("No se detecto banco.")
    if not malla:
        errores.append("No se detecto malla.")
    if not deduplicados:
        errores.append("No se detectaron sectores.")

    return {
        "fase": fase,
        "banco": banco,
        "malla": malla,
        "mallas": [malla] if malla else [],
        "fecha_plan": fecha,
        "nombre_plan": nombre_plano,
        "sectores": deduplicados,
        "texto_extraido": texto,
        "texto_len": len(texto),
        "errores": errores,
        "ok": bool(texto),
        "mensaje": "Texto PDF extraído correctamente." if texto else "No se pudo extraer texto del PDF.",
    }


def extraer_datos_enaex_desde_pdf(ruta_pdf, nombre_archivo=""):
    texto = extraer_texto_pdf(ruta_pdf)
    return extraer_datos_enaex_desde_texto(texto, nombre_archivo=nombre_archivo or Path(ruta_pdf).name)


def sectores_a_dataframe(sectores):
    return pd.DataFrame(
        sectores or [],
        columns=[
            "tipo_sector",
            "identificador_sector",
            "malla",
            "numero_precorte",
            "pozos_planificados",
            "metros_planificados",
            "pasadura",
            "diametro",
            "banco",
        ],
    )
