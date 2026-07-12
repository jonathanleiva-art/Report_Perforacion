"""
Normalización y filtrado de campos de ubicación operacional (Fase, Banco, Malla).

Los registros pueden contener valores separados por coma en estos campos
(ej: "108, 109, 114"). Este módulo los trata como tokens individuales
para filtros, opciones en cascada y reportes.
"""

import pandas as pd


def split_valor(valor) -> list:
    """
    Separa un valor potencialmente compuesto (ej: "108, 109") en tokens individuales.
    Devuelve lista vacía si el valor es nulo o vacío.
    """
    texto = str(valor or "").strip()
    if not texto or texto.lower() in ("nan", "none", "nat"):
        return []
    return [v.strip() for v in texto.split(",") if v.strip()]


def valores_unicos(df: pd.DataFrame, columna: str) -> list:
    """
    Valores únicos individuales de una columna que puede tener entradas separadas por coma.
    Ej: si la columna tiene ["108, 109", "109, 114"], devuelve ["108", "109", "114"].
    """
    if columna not in df.columns:
        return []
    resultado: set = set()
    for val in df[columna].dropna():
        resultado.update(split_valor(val))
    return sorted(resultado)


def valores_unicos_desde_db(columna: str) -> list:
    """
    Obtiene valores únicos de la BD y los separa si contienen comas.
    Equivalente a db.obtener_valores_distintos_columna pero garantiza splitting.
    """
    import db
    brutos = db.obtener_valores_distintos_columna(columna)
    resultado: set = set()
    for val in brutos:
        resultado.update(split_valor(val))
    return sorted(resultado)


def arbol_ubicacion(df: pd.DataFrame) -> dict:
    """
    Construye árbol jerárquico Fase → {Banco → set(Mallas)} desde el DataFrame.
    Maneja valores separados por coma en cada campo.
    """
    arbol: dict = {}
    for _, row in df.iterrows():
        fases = split_valor(row.get("Fase", "")) or [""]
        bancos = split_valor(row.get("Banco", "")) or [""]
        mallas = split_valor(row.get("Malla", "")) or [""]
        for fase in fases:
            nodo_fase = arbol.setdefault(fase, {})
            for banco in bancos:
                nodo_banco = nodo_fase.setdefault(banco, set())
                for malla in mallas:
                    nodo_banco.add(malla)
    return arbol


def opciones_banco_cascada(df: pd.DataFrame, fases_sel: list) -> list:
    """
    Bancos disponibles dado un subconjunto de fases seleccionadas.
    Si fases_sel está vacío, devuelve todos los bancos.
    """
    if not fases_sel:
        return valores_unicos(df, "Banco")
    arbol = arbol_ubicacion(df)
    bancos: set = set()
    for fase in fases_sel:
        for banco in arbol.get(fase, {}):
            if banco:
                bancos.add(banco)
    return sorted(bancos)


def opciones_malla_cascada(df: pd.DataFrame, fases_sel: list, bancos_sel: list) -> list:
    """
    Mallas disponibles dado un subconjunto de fases y bancos seleccionados.
    Si ambas listas están vacías, devuelve todas las mallas.
    """
    if not fases_sel and not bancos_sel:
        return valores_unicos(df, "Malla")
    arbol = arbol_ubicacion(df)
    mallas: set = set()
    for fase, bancos_dict in arbol.items():
        if fases_sel and fase not in fases_sel:
            continue
        for banco, mallas_set in bancos_dict.items():
            if bancos_sel and banco not in bancos_sel:
                continue
            mallas.update(m for m in mallas_set if m)
    return sorted(mallas)


def _contiene_alguno(valor, seleccion: list) -> bool:
    """True si el valor (potencialmente CSV) contiene alguno de los tokens seleccionados."""
    if not seleccion:
        return True
    return any(parte in seleccion for parte in split_valor(valor))


def filtrar_df(
    df: pd.DataFrame,
    fases=None,
    bancos=None,
    mallas=None,
) -> pd.DataFrame:
    """
    Filtra el DataFrame por Fase, Banco y Malla usando lógica de tokens.
    Una fila coincide si su campo contiene ALGUNO de los valores seleccionados.
    Si una lista está vacía/None, no filtra esa dimensión.
    Los registros nunca se duplican.
    """
    fases = list(fases or [])
    bancos = list(bancos or [])
    mallas = list(mallas or [])
    if not any([fases, bancos, mallas]):
        return df
    mask = pd.Series(True, index=df.index)
    if fases and "Fase" in df.columns:
        mask &= df["Fase"].apply(lambda v: _contiene_alguno(v, fases))
    if bancos and "Banco" in df.columns:
        mask &= df["Banco"].apply(lambda v: _contiene_alguno(v, bancos))
    if mallas and "Malla" in df.columns:
        mask &= df["Malla"].apply(lambda v: _contiene_alguno(v, mallas))
    return df[mask].copy()
