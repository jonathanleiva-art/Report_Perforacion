from unicodedata import normalize

import pandas as pd

import db


FEATURE_COLUMNS = [
    "Equipo",
    "Operador",
    "Turno",
    "Tipo de perforación",
    "Condición del terreno",
    "Horas efectivas perforando",
    "Horas detención No efectivas",
    "Horas detención mecánica",
    "Metros perforados",
    "Disponibilidad %",
    "Utilización %",
    "Rendimiento m/h",
]

NUMERIC_FEATURES = [
    "Horas efectivas perforando",
    "Horas detención No efectivas",
    "Horas detención mecánica",
    "Metros perforados",
    "Disponibilidad %",
    "Utilización %",
    "Rendimiento m/h",
]

CATEGORICAL_FEATURES = [
    "Equipo",
    "Operador",
    "Turno",
    "Tipo de perforación",
    "Condición del terreno",
]


def cargar_registros_sqlite():
    return db.leer_registros()


def preparar_features(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=FEATURE_COLUMNS)

    base = df.copy()
    if "Equipo" not in base.columns and {"Modelo equipo", "Número equipo"}.issubset(base.columns):
        base["Equipo"] = (base["Modelo equipo"].astype(str) + " " + base["Número equipo"].astype(str)).str.strip()

    for columna in FEATURE_COLUMNS:
        if columna not in base.columns:
            base[columna] = 0 if columna in NUMERIC_FEATURES else ""

    features = base[FEATURE_COLUMNS].copy()
    for columna in NUMERIC_FEATURES:
        features[columna] = pd.to_numeric(features[columna], errors="coerce").fillna(0)

    for columna in CATEGORICAL_FEATURES:
        features[columna] = features[columna].fillna("").astype(str).map(normalizar_texto)

    return features


def agregar_targets_operacionales(features):
    data = features.copy()
    data["target_baja_utilizacion"] = data["Utilización %"].lt(40).astype(int)
    umbral_rendimiento = calcular_umbral_rendimiento(data)
    data["target_bajo_rendimiento"] = (
        data["Rendimiento m/h"].gt(0) & data["Rendimiento m/h"].lt(umbral_rendimiento)
    ).astype(int)
    data["target_turno_improductivo"] = (
        data["Metros perforados"].le(0) & data["Horas efectivas perforando"].le(0)
    ).astype(int)
    return data


def calcular_umbral_rendimiento(features):
    rendimiento = pd.to_numeric(features.get("Rendimiento m/h", pd.Series(dtype=float)), errors="coerce").fillna(0)
    positivos = rendimiento[rendimiento > 0]
    if positivos.empty:
        return 10.0
    return max(float(positivos.quantile(0.25)), 10.0)


def resumen_por_equipo(features):
    if features.empty:
        return pd.DataFrame()

    agrupado = features.groupby("Equipo", as_index=False).agg({
        "Operador": lambda serie: ", ".join(dict.fromkeys(valor for valor in serie if valor)),
        "Turno": lambda serie: ", ".join(dict.fromkeys(valor for valor in serie if valor)),
        "Metros perforados": "sum",
        "Horas efectivas perforando": "sum",
        "Horas detención No efectivas": "sum",
        "Horas detención mecánica": "sum",
        "Disponibilidad %": "mean",
        "Utilización %": "mean",
        "Rendimiento m/h": "mean",
    })
    return agrupado.fillna(0)


def normalizar_texto(valor):
    texto = str(valor).strip()
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
    return texto.replace("", "").strip()


def normalizar_ascii(valor):
    return normalize("NFKD", str(valor)).encode("ascii", "ignore").decode("ascii").lower().strip()
