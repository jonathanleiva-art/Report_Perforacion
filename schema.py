"""
Esquema formal del sistema de reportes de perforacion.

Este modulo es pasivo: declara columnas, aliases y tipos esperados sin cambiar
la lectura/escritura actual basada en Excel.
"""

from unicodedata import normalize

from text_utils import reparar_mojibake

SQLITE_TABLE_REPORTES = "registros_perforacion"

DATE_COLUMNS = [
    "Fecha turno",
]

TIME_COLUMNS = [
    "Hora registro",
]

TEXT_COLUMNS = [
    "Modelo equipo",
    "Número equipo",
    "Operador",
    "Turno",
    "Código operador",
    "Área operacional",
    "Banco",
    "Malla",
    "Fase",
    "Sectores trabajados",
    "Tipo de perforación",
    "tipo_sector",
    "numero_precorte",
    "identificador_sector",
    "Número serie Tricono/Bit",
    "Condición del terreno",
    "Tipo detención",
    "Causa detención",
    "Observaciones",
    "Estatus del Equipo",
    "Descripción avería equipo",
    "Observación estado equipo",
    "Equipo",
    "Fecha",
]

TEXT_TAG_COLUMNS = [
    "Banco",
    "Malla",
    "Fase",
    "Condición del terreno",
    "Sectores trabajados",
    "Tipo detención",
    "Tipo de perforación",
]

INTEGER_COLUMNS = [
    "Petróleo litros",
    "Aceite litros",
    "Horómetro inicial",
    "Horómetro final",
    "Diferencia horómetro",
    "Horas de motor",
    "Número precorte",
    "Horas turno",
    "Tronadura",
    "Falta operador",
    "Total horas ingresadas",
    "Total distribución turno",
    "Diferencia distribución",
    "Cantidad pozos perforados",
    "Pozos perforados turno",
    "Falla Operacional",
    "Geología",
    "Seguridad",
]

REAL_COLUMNS = [
    "Horas detención mecánica",
    "Horas detención No efectivas",
    "Horas efectivas perforando",
    "Trabajando",
    "Combustible",
    "Relleno de agua",
    "Colación",
    "Traslado",
    "Traslado de sector",
    "Traslado pozo a pozo",
    "Traslado largo",
    "Standby por falta de tajo/Patio",
    "Cambio de aceros",
    "Sin marcación",
    "Mantención Programada",
    "Avería",
    "Cambio turno",
    "Otros",
    "Metros perforados",
    "Metros totales operador",
    "Metros totales por equipo",
    "Rendimiento m/h",
    "Disponibilidad %",
    "Utilización",
]

NUMERIC_COLUMNS = [
    *INTEGER_COLUMNS,
    *REAL_COLUMNS,
]

KPI_COLUMNS = [
    "Horas turno",
    "Horas efectivas perforando",
    "Trabajando",
    "Metros perforados",
    "Rendimiento m/h",
    "Disponibilidad %",
    "Utilización",
    "Pozos perforados turno",
    "Metros totales operador",
    "Metros totales por equipo",
]

OPTIONAL_COLUMNS = [
    "Banco",
    "Malla",
    "Tipo de perforación",
    "Sectores trabajados",
    "tipo_sector",
    "numero_precorte",
    "identificador_sector",
    "Número serie Tricono/Bit",
    "Condición del terreno",
    "Causa detención",
    "Observaciones",
    "Estatus del Equipo",
    "Descripción avería equipo",
    "Observación estado equipo",
    "Fecha",
    "Hora registro",
    "Metros totales operador",
    "Metros totales por equipo",
]

HISTORICAL_COMPATIBILITY_COLUMNS = [
    "Utilización",
    "Cantidad pozos perforados",
    "Sin marcación",
]

OFFICIAL_COLUMNS = [
    "Fecha turno",
    "Modelo equipo",
    "Número equipo",
    "Operador",
    "Turno",
    "Código operador",
    "Área operacional",
    "Petróleo litros",
    "Aceite litros",
    "Horómetro inicial",
    "Horómetro final",
    "Diferencia horómetro",
    "Banco",
    "Malla",
    "Fase",
    "Horas turno",
    "Sectores trabajados",
    "Tipo de perforación",
    "tipo_sector",
    "numero_precorte",
    "identificador_sector",
    "Número serie Tricono/Bit",
    "Condición del terreno",
    "Tipo detención",
    "Causa detención",
    "Horas detención mecánica",
    "Horas detención No efectivas",
    "Horas efectivas perforando",
    "Combustible",
    "Relleno de agua",
    "Colación",
    "Traslado",
    "Tronadura",
    "Mantención Programada",
    "Avería",
    "Total horas ingresadas",
    "Metros perforados",
    "Rendimiento m/h",
    "Disponibilidad %",
    "Utilización",
    "Cambio turno",
    "Falta operador",
    "Otros",
    "Standby por falta de tajo/Patio",
    "Total distribución turno",
    "Diferencia distribución",
    "Observaciones",
    "Estatus del Equipo",
    "Trabajando",
    "Pozos perforados turno",
    "Descripción avería equipo",
    "Observación estado equipo",
    "Traslado de sector",
    "Traslado pozo a pozo",
    "Traslado largo",
    "Metros totales operador",
    "Metros totales por equipo",
    "Equipo",
    "Fecha",
    "Hora registro",
    "Horas de motor",
    "Número precorte",
    "Falla Operacional",
    "Cambio de aceros",
    "Geología",
    "Seguridad",
]

NORMALIZED_DATAFRAME_COLUMNS = [
    *OFFICIAL_COLUMNS[:52],
    "Utilización",
    *OFFICIAL_COLUMNS[52:],
]

COLUMN_ALIASES = {
    "Número equipo": "Número equipo",
    "Número equipo": "Número equipo",
    "Número equipo": "Número equipo",
    "Código operador": "Código operador",
    "Código operador": "Código operador",
    "Área operacional": "Área operacional",
    "Área operacional": "Área operacional",
    "Petróleo litros": "Petróleo litros",
    "Petróleo litros": "Petróleo litros",
    "Horómetro inicial": "Horómetro inicial",
    "Horómetro inicial": "Horómetro inicial",
    "Horómetro final": "Horómetro final",
    "Horómetro final": "Horómetro final",
    "Diferencia horómetro": "Diferencia horómetro",
    "Diferencia horómetro": "Diferencia horómetro",
    "Tipo de perforación": "Tipo de perforación",
    "Tipo de perforación": "Tipo de perforación",
    "Sectores trabajados": "Sectores trabajados",
    "Condición del terreno": "Condición del terreno",
    "Condición del terreno": "Condición del terreno",
    "Tipo detención": "Tipo detención",
    "Tipo detención": "Tipo detención",
    "Causa detención": "Causa detención",
    "Causa detención": "Causa detención",
    "Horas detención mecánica": "Horas detención mecánica",
    "Horas detención mecánica": "Horas detención mecánica",
    "Horas detención No efectivas": "Horas detención No efectivas",
    "Horas detención No efectivas": "Horas detención No efectivas",
    "Colación": "Colación",
    "Colación": "Colación",
    "Mantención": "Mantención Programada",
    "Mantención": "Mantención Programada",
    "Mantención": "Mantención Programada",
    "Avería": "Avería",
    "Avería": "Avería",
    "Utilización": "Utilización",
    "Utilización": "Utilización",
    "Utilización": "Utilización",
    "Otros distribución": "Otros",
    "Otros distribución": "Otros",
    "Otros distribución": "Otros",
    "Sin marcación": "Standby por falta de tajo/Patio",
}

EXPECTED_TYPES = {
    **{column: "DATE/TEXT ISO" for column in DATE_COLUMNS},
    **{column: "TEXT" for column in TIME_COLUMNS},
    **{column: "TEXT" for column in TEXT_COLUMNS},
    **{column: "INTEGER" for column in INTEGER_COLUMNS},
    **{column: "REAL" for column in REAL_COLUMNS},
    "Utilización": "REAL",
}

SQLITE_TYPES = {
    column: (
        "TEXT"
        if expected_type == "DATE/TEXT ISO"
        else expected_type
    )
    for column, expected_type in EXPECTED_TYPES.items()
}

SQLITE_TECHNICAL_COLUMNS = {
    "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
    "created_at": "TEXT",
    "updated_at": "TEXT",
    "source": "TEXT",
    "source_row": "INTEGER",
}

MODERN_COLUMN_ALIASES = {
    "Número equipo": "Número equipo",
    "Código operador": "Código operador",
    "Área operacional": "Área operacional",
    "Área operacional": "Área operacional",
    "Petróleo litros": "Petróleo litros",
    "Horómetro inicial": "Horómetro inicial",
    "Horómetro final": "Horómetro final",
    "Diferencia horómetro": "Diferencia horómetro",
    "Tipo de perforación": "Tipo de perforación",
    "Condición del terreno": "Condición del terreno",
    "Tipo detención": "Tipo detención",
    "Causa detención": "Causa detención",
    "Horas detención mecánica": "Horas detención mecánica",
    "Horas detención No efectivas": "Horas detención No efectivas",
    "Colación": "Colación",
    "Mantención": "Mantención Programada",
    "Mantención": "Mantención Programada",
    "Mantención Programada": "Mantención Programada",
    "Avería": "Avería",
    "Utilización": "Utilización",
    "Código operador": "Código operador",
    "Número precorte": "Número precorte",
    "Tipo sector": "tipo_sector",
    "Tipo de sector": "tipo_sector",
    "tipo_sector": "tipo_sector",
    "Numero precorte operacional": "numero_precorte",
    "Número precorte operacional": "numero_precorte",
    "numero_precorte": "numero_precorte",
    "Identificador sector": "identificador_sector",
    "identificador_sector": "identificador_sector",
    "Número serie Tricono/Bit": "Número serie Tricono/Bit",
    "Otros distribución": "Otros",
    "Otros distribución": "Otros",
    "Sin marcación": "Standby por falta de tajo/Patio",
}

LEGACY_COLUMN_ALIASES = {
    "Utilización %": "Utilización",
}

ORTHOGRAPHY_COLUMN_ALIASES = {
    "Nro equipo": "Número equipo",
    "N° equipo": "Número equipo",
    "No equipo": "Número equipo",
    "Num equipo": "Número equipo",
    "N equipo": "Número equipo",
    "Utilisacion": "Utilización",
    "Utilizasion": "Utilización",
    "Utlizacion": "Utilización",
    "Utlización": "Utilización",
    "Horometro inicial": "Horómetro inicial",
    "Horometro final": "Horómetro final",
    "Diferencia horometro": "Diferencia horómetro",
    "Codigo operador": "Código operador",
    "Area operacional": "Área operacional",
    "Petroleo litros": "Petróleo litros",
    "Tipo de perforacion": "Tipo de perforación",
    "Condicion del terreno": "Condición del terreno",
    "Tipo detencion": "Tipo detención",
    "Causa detencion": "Causa detención",
    "Mantencion": "Mantención Programada",
    "Mantencion Programada": "Mantención Programada",
    "Averia": "Avería",
    "Descripcion averia equipo": "Descripción avería equipo",
    "Observacion estado equipo": "Observación estado equipo",
}

def _sin_acentos(texto):
    return normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")


def _variantes_nombre_columna(nombre):
    reparado = reparar_mojibake(nombre)
    return [
        str(nombre).strip(),
        reparado.strip(),
        _sin_acentos(reparado).strip(),
    ]


def _expandir_aliases_columnas(aliases):
    expandidos = {}
    for origen, destino in aliases.items():
        destino_reparado = reparar_mojibake(destino).strip()
        for variante in _variantes_nombre_columna(origen):
            if variante:
                expandidos[variante] = destino_reparado
    return expandidos


def _expandir_equivalentes_columnas(equivalentes):
    expandidos = {}
    for clave, columnas in equivalentes.items():
        variantes = []
        for columna in columnas:
            variantes.extend(_variantes_nombre_columna(columna))
        expandidos[clave] = list(dict.fromkeys(variante for variante in variantes if variante))
    return expandidos


COLUMN_ALIASES.update(MODERN_COLUMN_ALIASES)
COLUMN_ALIASES.update(LEGACY_COLUMN_ALIASES)
COLUMN_ALIASES.update(ORTHOGRAPHY_COLUMN_ALIASES)
COLUMN_ALIASES = _expandir_aliases_columnas(COLUMN_ALIASES)

COLUMN_EQUIVALENTS = {
    "numero_equipo": ["Número equipo", "Número equipo"],
    "modelo_equipo": ["Modelo equipo"],
    "operador": ["Operador"],
    "turno": ["Turno"],
    "fecha_turno": ["Fecha turno"],
    "metros_perforados": ["Metros perforados"],
    "pozos_perforados": ["Pozos perforados turno", "Cantidad pozos perforados"],
    "horas_efectivas": ["Horas efectivas perforando"],
    "horas_no_efectivas": ["Horas detención No efectivas", "Horas detención No efectivas"],
    "horas_averia": ["Horas detención mecánica", "Horas detención mecánica", "Avería", "Avería"],
    "horas_mantencion": ["Mantención Programada", "Mantención Programada", "Mantencion Programada", "Mantención", "Mantención"],
    "horas_standby": ["Standby por falta de tajo/Patio"],
    "sin_marcacion": ["Sin marcación", "Sin marcación"],
    "utilizacion": ["Utilización", "Utilización %", "Utilización %"],
    "disponibilidad": ["Disponibilidad %"],
    "rendimiento": ["Rendimiento m/h"],
    "tipo_sector": ["tipo_sector", "Tipo sector", "Tipo de sector"],
    "sectores_trabajados": ["Sectores trabajados", "Tipo de perforación", "tipo_sector", "Tipo sector", "Tipo de sector"],
    "numero_precorte_operacional": ["numero_precorte", "Numero precorte operacional", "Número precorte operacional"],
    "identificador_sector": ["identificador_sector", "Identificador sector"],
}
COLUMN_EQUIVALENTS = _expandir_equivalentes_columnas(COLUMN_EQUIVALENTS)

CANONICAL_COLUMNS = list(dict.fromkeys([
    *OFFICIAL_COLUMNS,
    *OPTIONAL_COLUMNS,
    *HISTORICAL_COMPATIBILITY_COLUMNS,
]))

CANONICAL_COLUMN_SET = set(CANONICAL_COLUMNS)

COLUMN_VARIANTS = {}
for _origen, _destino in COLUMN_ALIASES.items():
    COLUMN_VARIANTS.setdefault(_destino, set()).add(_origen)
for _columna in CANONICAL_COLUMNS:
    COLUMN_VARIANTS.setdefault(_columna, set()).add(_columna)
    COLUMN_VARIANTS[_columna].update(_variantes_nombre_columna(_columna))
COLUMN_VARIANTS = {
    columna: tuple(sorted(variantes))
    for columna, variantes in COLUMN_VARIANTS.items()
}


def columnas_equivalentes(clave):
    return COLUMN_EQUIVALENTS.get(clave, [clave])


def columna_canonica(nombre):
    texto = reparar_mojibake(nombre).strip()
    return COLUMN_ALIASES.get(texto, texto)


def alias_columna(nombre):
    return columna_canonica(nombre)


def aliases_columnas():
    return COLUMN_ALIASES.copy()


def es_columna_canonica(nombre):
    texto = reparar_mojibake(nombre).strip()
    return texto in CANONICAL_COLUMN_SET and columna_canonica(texto) == texto


def variantes_columna(nombre):
    canonica = columna_canonica(nombre)
    return COLUMN_VARIANTS.get(canonica, (canonica,))


def contrato_columnas():
    return {
        columna: {
            "tipo": EXPECTED_TYPES.get(columna, "TEXT"),
            "sqlite": SQLITE_TYPES.get(columna, "TEXT"),
            "variantes": variantes_columna(columna),
        }
        for columna in CANONICAL_COLUMNS
    }


MODERN_NUMERIC_COLUMNS = [
    "Petróleo litros",
    "Horómetro inicial",
    "Horómetro final",
    "Diferencia horómetro",
    "Número precorte",
    "Horas detención mecánica",
    "Horas detención No efectivas",
    "Colación",
    "Sin marcación",
    "Mantención Programada",
    "Avería",
    "Total distribución turno",
    "Diferencia distribución",
    "Utilización",
]

for _column in MODERN_NUMERIC_COLUMNS:
    if _column not in NUMERIC_COLUMNS:
        NUMERIC_COLUMNS.append(_column)

MODERN_TEXT_TAG_COLUMNS = [
    "Condición del terreno",
    "Tipo detención",
    "Tipo de perforación",
]

for _column in MODERN_TEXT_TAG_COLUMNS:
    if _column not in TEXT_TAG_COLUMNS:
        TEXT_TAG_COLUMNS.append(_column)
