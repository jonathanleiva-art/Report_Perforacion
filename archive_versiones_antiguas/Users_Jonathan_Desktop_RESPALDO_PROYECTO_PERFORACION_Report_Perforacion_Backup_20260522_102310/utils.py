from pathlib import Path
from unicodedata import normalize

import pandas as pd

from catalogs import CODIGOS_OPERADOR, EQUIPOS, IMAGENES_EQUIPO, OPERADORES, TIPOS_DETENCION

HORAS_TURNO = 12
BASE_DIR = Path(__file__).resolve().parent
EXCEL_PATH = BASE_DIR / "reportes_perforacion.xlsx"

def limpiar_entero(valor):
    if valor is None:
        return ""

    texto = str(valor).strip()
    if texto.lower() in ("", "nan", "none", "nat"):
        return ""

    try:
        numero = float(texto)
    except ValueError:
        return texto

    if numero.is_integer():
        return str(int(numero))

    return texto


def unir_valores(valores):
    return ", ".join(str(valor).strip() for valor in valores if str(valor).strip())


def opciones_desde_historial(df, columna, base=None):
    opciones = list(base or [])
    if columna not in df.columns:
        return opciones

    for valor in df[columna].dropna().astype(str):
        for item in valor.split(","):
            item = limpiar_entero(item) if columna in ("Banco", "Fase", "Número equipo") else item.strip()
            if item and item not in opciones:
                opciones.append(item)

    return opciones


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


def ruta_imagen_equipo(modelo, numero):
    imagen = IMAGENES_EQUIPO.get(modelo)
    if isinstance(imagen, dict):
        imagen = imagen.get(numero)

    if not imagen:
        return None

    ruta = BASE_DIR / imagen
    return ruta if ruta.exists() else None
