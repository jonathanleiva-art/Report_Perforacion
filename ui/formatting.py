import pandas as pd

from text_utils import reparar_mojibake


def texto_visible(valor):
    return reparar_mojibake(valor)


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
